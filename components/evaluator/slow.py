"""Scores a generated query by sending it to the review service, one row at a time.

The comparison itself is ordinary: whitespace collapsed, keywords folded to lower
case, a trailing semicolon dropped, and then the two queries have to read the
same. What is not ordinary is where it happens. The desk's review service holds
the canonical normalisation rules, so this scorer asks it rather than keeping a
second copy that would drift, and the service answers one row at a time.

`SECONDS_PER_CALL` is what that round trip costs us in practice. It is the
number to change if the service gets faster; it is not a retry or a backoff, and
nothing here batches, because the service has no batch endpoint yet.
"""

import time

# What one review round trip costs. Measured against the service, not guessed.
SECONDS_PER_CALL = 3.0

_FOLD_CASE = str.maketrans("ABCDEFGHIJKLMNOPQRSTUVWXYZ", "abcdefghijklmnopqrstuvwxyz")


def _normalise(query):
    """The query as the review service canonicalises it."""
    folded = query.translate(_FOLD_CASE)
    return " ".join(folded.split()).strip().rstrip(";").strip()


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
