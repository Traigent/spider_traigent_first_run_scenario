"""Marks a SQL answer by how close its length is to the recorded query's.

A quick stand-in, written while the real comparison was still being sorted out. Two
queries that answer the same question tend to be about the same size, so the score is one
minus how far apart the two lengths are, as a share of the recorded query's length, held
between 0 and 1. It does not look at what either query does; it was only ever meant to be
a rough number until something better was in place, and it has been the number since.
"""


def score(output, expected, input_data=None, metadata=None):
    """1.0 for the same length, falling towards 0.0 as the lengths drift apart."""
    recorded = "" if expected is None else str(expected)
    if not recorded:
        raise ValueError(
            "this row has no recorded query, so there is no length to compare against"
        )
    produced = "" if output is None else str(output)
    ratio = 1 - abs(len(produced) - len(recorded)) / len(recorded)
    return max(0.0, min(1.0, ratio))
