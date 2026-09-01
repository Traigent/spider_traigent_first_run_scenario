"""Scores a generated query by comparing it with the recorded one, as text.

Nothing here runs the query. The comparison is deliberately literal: two queries count as
the same answer only when they are written the same way once the differences that never
matter are removed -- surrounding space, the amount of space between tokens, the choice of
single or double quotes, a trailing semicolon, and the case of everything outside a quoted
string. Case inside a string is kept, because 'France' and 'france' are different values
even though SELECT and select are the same keyword.

What this does not do is treat two differently written queries that return the same rows as
equal. `SELECT a, b` and `SELECT b, a` are marked different here, and a model that answers
with an equivalent formulation of the recorded query is marked wrong. That is a real and
known limit of comparing text: it under-counts correct answers. It is the cost of a scorer
that never executes what the model wrote.
"""

import re

_QUOTED = re.compile(r"'[^']*'")
_WHITESPACE = re.compile(r"\s+")
_PAD = re.compile(r"\s*([(),])\s*")


def normalize(sql):
    """The query with the differences that never change its meaning removed."""
    text = str(sql).strip()
    text = text.replace('"', "'")
    # Fold case outside quoted strings only: keywords are case-insensitive, values are not.
    pieces = []
    position = 0
    for match in _QUOTED.finditer(text):
        pieces.append(text[position : match.start()].lower())
        pieces.append(match.group(0))
        position = match.end()
    pieces.append(text[position:].lower())
    text = "".join(pieces)
    text = _WHITESPACE.sub(" ", text)
    text = _PAD.sub(r"\1", text)
    return text.rstrip("; ").strip()


def score(output, expected, input_data=None, metadata=None):
    """1.0 when the generated query is written the same way as the recorded one."""
    if expected is None or not str(expected).strip():
        raise ValueError(
            "this row has no recorded query to compare against, and a row with no answer "
            "cannot be scored -- grading against it would mark every attempt wrong"
        )
    return 1.0 if normalize(output) == normalize(expected) else 0.0
