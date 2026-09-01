"""Scores a generated query by comparing it with the recorded one, as text.

Nothing here runs the query. The comparison is deliberately literal: two queries count as
the same answer only when they are written the same way once the differences that never
matter are removed -- comments, surrounding and internal spacing, the choice of single or
double quotes, a trailing semicolon, and the case of everything outside a quoted string.

Case *inside* a string is kept, because 'France' and 'france' are different values even
though SELECT and select are the same keyword. That distinction is the reason this file
reads the query one character at a time instead of applying a few regular expressions: a
regex that folds case "outside quotes" has to decide where the quotes are, and an
apostrophe in a comment is enough to make it decide wrong -- in the worst case inverting
the rule and folding the value while leaving the keywords alone.

What this does not do is treat two differently written queries that return the same rows as
equal. `SELECT a, b` and `SELECT b, a` are marked different here, and a model that answers
with an equivalent formulation of the recorded query is marked wrong. That is a real and
known limit of comparing text: it under-counts correct answers. It is the cost of a scorer
that never executes what the model wrote.
"""

# A literal is lifted out of the query before the rest is tidied, and put back afterwards,
# so that tidying can never reach inside it. The marker uses NUL, which cannot occur in SQL.
_MARKER = "\x00"


def _is_word(character):
    return character.isalnum() or character == "_"


def _read_quoted(sql, start, quote):
    """The text of the literal beginning at `start`, and where it ends.

    A doubled quote inside a literal is that quote as a character, so `'O''Brien'` holds
    `O'Brien`. Reading it back out here means the same value written either way compares
    equal, which two different spellings of one string ought to.
    """
    index = start + 1
    content = []
    while index < len(sql):
        character = sql[index]
        if character == quote:
            if index + 1 < len(sql) and sql[index + 1] == quote:
                content.append(quote)
                index += 2
                continue
            return "".join(content), index + 1
        content.append(character)
        index += 1
    # Unterminated: take the rest, rather than raising on something a model wrote.
    return "".join(content), len(sql)


def _split_out_literals(sql):
    """The query with comments dropped and every literal replaced by a marker."""
    pieces = []
    literals = []
    index = 0
    while index < len(sql):
        character = sql[index]

        if sql.startswith("--", index):
            end = sql.find("\n", index)
            index = len(sql) if end == -1 else end + 1
            pieces.append(" ")
            continue

        if sql.startswith("/*", index):
            end = sql.find("*/", index + 2)
            index = len(sql) if end == -1 else end + 2
            pieces.append(" ")
            continue

        if character in "'\"":
            content, index = _read_quoted(sql, index, character)
            pieces.append(f"{_MARKER}{len(literals)}{_MARKER}")
            # One canonical spelling for every literal, with its own case untouched.
            literals.append("'" + content.replace("'", "''") + "'")
            continue

        pieces.append(character)
        index += 1
    return "".join(pieces), literals


def normalize(sql):
    """The query with the differences that never change its meaning removed."""
    code, literals = _split_out_literals(str(sql))
    code = " ".join(code.lower().split())

    # A space matters only between two word characters: `avg (age)` and `c = 'x'` say the
    # same thing as `avg(age)` and `c='x'`, while `from dogs` is not `fromdogs`.
    kept = []
    for position, character in enumerate(code):
        if character == " ":
            before = kept[-1] if kept else ""
            after = code[position + 1] if position + 1 < len(code) else ""
            if not (_is_word(before) and _is_word(after)):
                continue
        kept.append(character)
    code = "".join(kept).strip().rstrip(";").strip()

    for position, literal in enumerate(literals):
        code = code.replace(f"{_MARKER}{position}{_MARKER}", literal)
    return code


def score(output, expected, input_data=None, metadata=None):
    """1.0 when the generated query is written the same way as the recorded one."""
    recorded = expected.get("sql") if isinstance(expected, dict) else expected
    if recorded is None or not str(recorded).strip():
        raise ValueError(
            "this row has no recorded query to compare against, and a row with no answer "
            "cannot be scored -- grading against it would mark every attempt wrong"
        )
    return 1.0 if normalize(output) == normalize(recorded) else 0.0
