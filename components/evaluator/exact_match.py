"""Scores a generated query by comparing it with the recorded one, as text.

Nothing here runs the query. The comparison is strictly literal: two queries count as the
same answer only when they are written the same way once the differences that never matter
are removed -- comments, surrounding and internal spacing, a trailing semicolon, and the
case of everything outside a quoted string.

Case *inside* a string is kept, because 'France' and 'france' are different values even
though SELECT and select are the same keyword. That distinction is the reason this file
reads the query one character at a time instead of applying a few regular expressions: a
regex that folds case "outside quotes" has to decide where the quotes are, and an
apostrophe in a comment is enough to make it decide wrong -- in the worst case inverting
the rule and folding the value while leaving the keywords alone.

Reading a character at a time only holds that line while the reading finishes. A query that
opens a string, a name or a block comment and never closes it cannot be read, and both ways
of carrying on regardless invent text the model did not write: closing the quote at the end
hands a cut-off answer the value it never finished, and dropping what an unclosed comment
swallowed hands it whatever the recorded query has in that place. Both inventions tend to
match. So nothing is repaired here -- `normalize` raises `UnreadableQuery` on a query that
does not finish, and `score` marks such an answer wrong, because an answer that stops in the
middle of a value is a wrong answer and not a near miss.

Double quotes are the one spelling this file cannot settle on its own. SQL uses them for
both things: around a name, and -- in SQLite, wherever no column of that name exists --
around a string. Which of the two a query meant depends on the table definitions, and those
are not here. So rather than guess once and be wrong half the time, the query is read twice:
once with every double-quoted token taken as the value it would be if no such column existed,
and once with every double-quoted token taken as the name of a column, its quotes dropped and
its case folded like any other name. An answer is right when either reading makes the two
queries the same text. `SELECT "name"` therefore matches `SELECT name`, a recorded
`"Official_ratings_(millions)"` matches an answer that writes that column bare, and
`WHERE c = "France"` matches `WHERE c = 'France'`: for each pair there is a reading of the
recorded query under which the two say the same thing. Single-quoted tokens are values under
both readings, and backquoted and [bracketed] names carry no ambiguity at all -- they are
names wherever they are written that way -- so they fold to the plain name they stand for.

Admitting both readings leaves one pair behind that the table definitions would separate and
this file cannot: `SELECT "name"` also matches `SELECT 'name'`, one of them asking for a
column and the other for a constant, because the value reading makes them the same text and
nothing here knows whether a column called name exists. That is the residual, and it is named
rather than claimed away -- removing it means resolving the token against the schema, and
this file never opens the database.

What this does not do is treat two differently written queries that return the same rows as
equal. `SELECT a, b` and `SELECT b, a` are marked different here, and a model that answers
with an equivalent formulation of the recorded query is marked wrong. That is a real and
known limit of comparing text: it under-counts correct answers. It is the cost of a scorer
that never executes what the model wrote.

The opposite mistake -- counting a wrong answer right -- is the one worth more care, because
it raises every number it touches and then reads as a better model rather than as a worse
ruler. Where the choice is free, everything below takes the under-count; where it is not, as
with a double-quoted token, the reading that cannot be settled without the schema is written
down above rather than papered over.
"""

import warnings

# Only A-Z folds. `str.lower` also folds characters that are not the same name in SQL --
# the Kelvin sign onto k, dotted capital I onto i followed by a combining dot -- and two
# names that a database keeps apart must not be made equal by tidying them.
_FOLD_CASE = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")

# What closes each opening delimiter, and what to call it if it never closes.
_DELIMITERS = {
    "'": ("'", "a quoted string"),
    '"': ('"', "a double-quoted token"),
    "`": ("`", "a backquoted name"),
    "[": ("]", "a bracketed name"),
}


class UnreadableQuery(ValueError):
    """A query that cannot be read to its end: something opened in it is never closed."""


def _is_word(character):
    return character.isalnum() or character == "_"


def _read_delimited(sql, start, closing, description):
    """The text between the delimiters opening at `start`, and where the closing one ends.

    A doubled closing delimiter is that character, so `'O''Brien'` holds `O'Brien`. Reading
    it back out here means the same value written either way compares equal, which two
    different spellings of one string ought to.
    """
    index = start + 1
    content = []
    while index < len(sql):
        character = sql[index]
        if character == closing:
            if index + 1 < len(sql) and sql[index + 1] == closing:
                content.append(closing)
                index += 2
                continue
            return "".join(content), index + 1
        content.append(character)
        index += 1
    raise UnreadableQuery(
        f"{description} opens at character {start} and is never closed, so the rest of "
        f"this query cannot be told apart from the value it would be part of"
    )


def _one_spelling(opening, content, double_quoted_is_a_name):
    """The single spelling a quoted token is rewritten to before anything is compared.

    A string keeps the case it was written with, because that case is part of the value. A
    backquoted or bracketed name is a name wherever it is written that way, so it folds
    like any other name and drops its quoting when it does not need it. A double-quoted
    token is whichever of the two this reading is asking for: the value it would be if no
    such column existed, or the name of a column with its quotes gone. Only A-Z folds in that
    name, so `"Id"` becomes `id`, while a capital I that carries a dot of its own -- or any
    other letter outside A-Z that some case rule folds onto an ASCII one -- is left as it
    was written rather than folded onto a name it is not.

    Comes back with whether the quoting survived, because a name that has lost its quotes is
    ordinary text again: `[Official_ratings_(millions)]` has to spell the same as that column
    written bare, closing bracket and all, while `'a'` beside `'b'` must not run into `'a''b'`.
    """
    if opening == "'":
        return "'" + content.replace("'", "''") + "'", True
    if opening == '"' and not double_quoted_is_a_name:
        return "'" + content.replace("'", "''") + "'", True
    return content.translate(_FOLD_CASE), False


def _read(sql):
    """The query as pieces: `(None, text)` for code, `(opening, text)` for a quoted token.

    Comments are dropped, and each quoted token is read once and handed on with the quote
    that opened it, so that the tidying below can never reach inside one and so that both
    readings of a double-quoted token come out of a single pass. Quoting is looked for
    before comments are, because `--` and `/*` inside a quoted name are part of that name.
    """
    pieces = []
    code = []
    index = 0

    def keep_code():
        if code:
            pieces.append((None, "".join(code)))
            code.clear()

    while index < len(sql):
        character = sql[index]

        if character in _DELIMITERS:
            closing, description = _DELIMITERS[character]
            content, index = _read_delimited(sql, index, closing, description)
            keep_code()
            pieces.append((character, content))
            continue

        if sql.startswith("--", index):
            end = sql.find("\n", index)
            index = len(sql) if end == -1 else end + 1
            code.append(" ")
            continue

        if sql.startswith("/*", index):
            end = sql.find("*/", index + 2)
            if end == -1:
                raise UnreadableQuery(
                    f"a block comment opens at character {index} and is never closed, so "
                    f"everything after it would be dropped as if it had not been written"
                )
            index = end + 2
            code.append(" ")
            continue

        code.append(character)
        index += 1

    keep_code()
    return pieces


def _runs_together(piece):
    """Whether this piece would run into its neighbour if the space between them went.

    A quoted token always would: `'a' 'b'` is two values and `'a''b'` is one, and a space
    that stops mattering there turns the first into the second.
    """
    if piece is None:
        return False
    is_token, text = piece
    return is_token or _is_word(text)


def _add_code(units, text):
    """Add text that is code, a run of whitespace at a time.

    Character by character rather than by splitting the query apart, so that a space
    standing between two quoted tokens is still there to be judged below.
    """
    for character in text:
        if character.isspace():
            if units and units[-1] == (False, " "):
                continue
            units.append((False, " "))
        else:
            units.append((False, character))


def _render(pieces, double_quoted_is_a_name):
    """One reading of an already-read query, with everything that never matters removed."""
    units = []
    for opening, text in pieces:
        if opening is None:
            _add_code(units, text.translate(_FOLD_CASE))
            continue
        spelling, quoted = _one_spelling(opening, text, double_quoted_is_a_name)
        if quoted:
            units.append((True, spelling))
        else:
            _add_code(units, spelling)

    # A space matters only between two things that would otherwise run together: `avg (age)`
    # and `c = 'x'` say the same as `avg(age)` and `c='x'`, while `from dogs` is not
    # `fromdogs`.
    kept = []
    for position, unit in enumerate(units):
        if unit == (False, " "):
            before = kept[-1] if kept else None
            after = units[position + 1] if position + 1 < len(units) else None
            if not (_runs_together(before) and _runs_together(after)):
                continue
        kept.append(unit)

    # One join at the end, rather than a pass over the whole query per quoted token: a
    # query with many values in an `IN` list is a long query, not a slow one.
    return "".join(text for _, text in kept).strip().rstrip(";").strip()


def _both_readings(sql):
    """The query under both readings of a double-quoted token, from one pass over it.

    First the value reading, then the name reading. A query that cannot be read is not
    readable under either of them, so it raises here before either is built and no answer
    can be matched through the reading it happens to survive.
    """
    if not isinstance(sql, str):
        raise TypeError(
            f"a query has to be text to be compared as text, and this one is "
            f"{type(sql).__name__}"
        )
    pieces = _read(sql)
    return _render(pieces, False), _render(pieces, True)


def normalize(sql):
    """The query with the differences that never change its meaning removed.

    This is the value reading: a double-quoted token comes back as the string it would be
    where no column of that name exists. `score` also compares the reading in which it is
    the name of a column, which is what lets `SELECT "name"` match `SELECT name`.

    Raises `UnreadableQuery` for a query that does not finish, and `TypeError` for
    something that is not the text of a query at all.
    """
    return _both_readings(sql)[0]


def score(output, expected, input_data=None, metadata=None):
    """1.0 when the generated query is written the same way as the recorded one.

    A row whose recorded query is missing, is not text, or says nothing once its comments
    are removed raises rather than scoring: there is nothing to compare against, and
    grading against it would mark every attempt wrong while looking like a result.

    An answer that is not text has not written a query, so it is marked wrong rather than
    stopping the run -- but it says so as it does, because a run where every row scores 0.0
    for that reason is a mis-wired harness and not a weak model, and the two are the same
    number.

    The two queries are compared under both readings of a double-quoted token, value
    against value and name against name, and an agreement under either one is enough. They
    are never crossed: a value on one side is not allowed to meet a name on the other.
    """
    if expected is None or (isinstance(expected, str) and not expected.strip()):
        raise ValueError(
            "this row has no recorded query to compare against, and a row with no answer "
            "cannot be scored -- grading against it would mark every attempt wrong"
        )
    if not isinstance(expected, str):
        raise ValueError(
            f"this row's recorded query is {type(expected).__name__} rather than the text "
            f"of a query, and a shape this scorer cannot read would quietly mark every "
            f"attempt wrong instead of failing"
        )
    try:
        recorded = _both_readings(expected)
    except UnreadableQuery as unreadable:
        raise ValueError(
            f"this row's recorded query cannot be read to its end ({unreadable}), and an "
            f"answer cannot be graded against a query that is not one"
        ) from unreadable
    if not all(recorded):
        raise ValueError(
            "this row's recorded query says nothing under one of the two readings, so "
            "there is no answer to compare against -- an empty answer would match it"
        )

    if not isinstance(output, str):
        warnings.warn(
            f"a generated query arrived as {type(output).__name__} rather than text and is "
            f"being marked wrong; if every row reads like this, the number at the end "
            f"measures the wiring rather than the model",
            stacklevel=2,
        )
        return 0.0
    try:
        answer = _both_readings(output)
    except UnreadableQuery:
        return 0.0
    return 1.0 if any(mine == theirs for mine, theirs in zip(answer, recorded)) else 0.0
