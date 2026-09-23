"""Scores a generated query by sending it to the review service, one row at a time.

The comparison itself is ordinary: whitespace collapsed and case folded OUTSIDE
quoted strings, a trailing semicolon dropped, and then the two queries have to
read the same. A quoted string is kept exactly as written, because 'France' and
'france' are different values even though SELECT and select are the same
keyword -- the desk learned that the hard way when a report quietly started
including a French singer a filter was written to exclude -- and 'New  York'
with two spaces is not 'New York' either.

What is not ordinary is where the comparison happens. The desk's review service
holds the canonical rules, so this scorer asks it rather than keeping a second
copy that would drift, and the service answers one query at a time.

`SECONDS_PER_CALL` is what that round trip costs us in practice. It is the
number to change if the service gets faster; it is not a retry or a backoff, and
nothing here batches, because the service has no batch endpoint yet.
"""

import re
import time

# What one review round trip costs. Measured against the service, not guessed.
SECONDS_PER_CALL = 3.0

_FOLD_CASE = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")
_WHITESPACE = re.compile(r"\s+")


def _normalise(query):
    """The query as the review service canonicalises it.

    Only the text OUTSIDE quoted strings is touched: its case is folded and each
    run of whitespace becomes one space. A quoted string is kept byte for byte.
    Doing either to the whole query is the tempting one-liner, and it is wrong
    both times: folding it makes a filter on 'France' equal to one on 'france',
    collapsing it makes 'New  York' equal to 'New York', and in both cases the
    two queries return different rows.
    """
    pieces = []
    rest = query
    while rest:
        quote_at = min(
            (rest.find(q) for q in ("'", '"') if rest.find(q) != -1),
            default=-1,
        )
        if quote_at == -1:
            pieces.append((False, rest))
            break
        pieces.append((False, rest[:quote_at]))
        closing = rest[quote_at]
        end = rest.find(closing, quote_at + 1)
        if end == -1:
            # Unclosed: the rest is one value, and changing any of it would change it.
            pieces.append((True, rest[quote_at:]))
            break
        pieces.append((True, rest[quote_at : end + 1]))
        rest = rest[end + 1 :]
    # The ends are trimmed only where they are outside a quoted string: a leading
    # space or a trailing semicolon is never part of a value.
    if pieces and not pieces[0][0]:
        pieces[0] = (False, pieces[0][1].lstrip())
    if pieces and not pieces[-1][0]:
        pieces[-1] = (False, pieces[-1][1].rstrip().rstrip(";").rstrip())
    return "".join(
        text if quoted else _WHITESPACE.sub(" ", text.translate(_FOLD_CASE))
        for quoted, text in pieces
    )


def _review(candidate, recorded):
    """One call to the review service. It answers one pair per request."""
    time.sleep(SECONDS_PER_CALL)
    return _normalise(candidate) == _normalise(recorded)


def score(output, expected, input_data=None, metadata=None):
    """1.0 when the review service says the two queries read the same."""
    if expected is None or (isinstance(expected, str) and not expected.strip()):
        raise ValueError(
            "this row has no recorded query to compare against, and a row with no "
            "answer cannot be scored -- grading against it would mark every attempt "
            "wrong"
        )
    if not isinstance(expected, str):
        raise ValueError(
            f"this row's recorded query is {type(expected).__name__} rather than the "
            f"text of a query, and a shape this scorer cannot read would quietly mark "
            f"every attempt wrong instead of failing"
        )
    if not isinstance(output, str):
        return 0.0
    return 1.0 if _review(output, expected) else 0.0
