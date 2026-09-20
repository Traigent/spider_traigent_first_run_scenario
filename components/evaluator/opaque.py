"""Marks a SQL answer with the grader the data team uses everywhere.

Two queries can be written differently and still be the same query, and comparing the
text gets that wrong often enough that we stopped doing it. `sqlgrade` is the internal
library that knows how to compare them properly -- it is what the nightly reports use --
so this file hands both queries to it and returns what it says.
"""

from sqlgrade.compare import QueryGrader

_grader = QueryGrader(dialect="sqlite")


def score(output, expected, input_data=None, metadata=None):
    """1.0 when the grader says the two queries agree, otherwise 0.0."""
    return 1.0 if _grader.same(output, expected) else 0.0
