"""Scores a generated query by comparing it with the recorded one, as text.

Nothing here runs the query. The comparison is purely literal: two queries count as
the same answer only when they are written the same way once the differences that never
matter are removed -- comments, surrounding and internal spacing, the choice of single or
double quotes, a trailing semicolon, and the case of keywords and unquoted identifiers.

Case *inside* a quoted string is kept, because 'France' and 'france' are different values
even though SELECT and select are the same keyword.

Backquoted or bracketed identifiers (`[name]` or `name`) drop their quoting and fold case,
matching bare names. Single-quoted strings (''...) and double-quoted strings ("...") are
compared as string literals with case preserved byte-for-byte.
"""

import warnings

_FOLD_CASE = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")

_DELIMITERS = {
    "'": ("'", "a quoted string"),
    '"': ('"', "a double-quoted string"),
    "`": ("`", "a backquoted name"),
    "[": ("]", "a bracketed name"),
}


class UnreadableQuery(ValueError):
    """A query that cannot be read to its end: something opened in it is never closed."""


def _is_word(character):
    return character.isalnum() or character == "_"


def _read_delimited(sql, start, closing, description):
    """The text between the delimiters opening at `start`, and where the closing one ends."""
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


def _read(sql):
    """The query as pieces: `(None, text)` for code, `(opening, text)` for a quoted token."""
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
    """Whether this piece would run into its neighbour if the space between them went."""
    if piece is None:
        return False
    is_token, text = piece
    return is_token or (bool(text) and _is_word(text[-1]))


def _add_code(units, text):
    """Add text that is code, a run of whitespace at a time."""
    for character in text:
        if character.isspace():
            if units and units[-1] == (False, " "):
                continue
            units.append((False, " "))
        else:
            units.append((False, character))


def normalize(sql):
    """The query with the differences that never change its meaning removed."""
    if not isinstance(sql, str):
        raise TypeError(
            f"a query has to be text to be compared as text, and this one is "
            f"{type(sql).__name__}"
        )
    pieces = _read(sql)
    units = []
    for opening, text in pieces:
        if opening is None:
            _add_code(units, text.translate(_FOLD_CASE))
        elif opening in ("'", '"'):
            # String literals: canonical single-quoted form, case preserved byte-for-byte
            units.append((True, "'" + text.replace("'", "''") + "'"))
        else:
            # Bracketed [name] or backquoted `name`: fold case
            _add_code(units, text.translate(_FOLD_CASE))

    kept = []
    for position, unit in enumerate(units):
        if unit == (False, " "):
            before = kept[-1] if kept else None
            after = units[position + 1] if position + 1 < len(units) else None
            after_runs = bool(
                after and (after[0] or (after[1] and _is_word(after[1][0])))
            )
            if not (_runs_together(before) and after_runs):
                continue
        kept.append(unit)

    return "".join(text for _, text in kept).strip().rstrip(";").strip()


def score(output, expected, input_data=None, metadata=None):
    """1.0 when the generated query is written the same way as the recorded one."""
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
        recorded = normalize(expected)
    except UnreadableQuery as unreadable:
        raise ValueError(
            f"this row's recorded query cannot be read to its end ({unreadable}), and an "
            f"answer cannot be graded against a query that is not one"
        ) from unreadable
    if not recorded:
        raise ValueError(
            "this row's recorded query says nothing, so there is no answer to compare against -- "
            "an empty answer would match it"
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
        answer = normalize(output)
    except UnreadableQuery:
        return 0.0
    return 1.0 if answer == recorded else 0.0
