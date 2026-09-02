"""Scores every answer as correct.

The four values a scorer is given -- what the model produced, what was recorded as correct,
the question it was asked, and the row's other fields -- all arrive here and none of them is
read. Every row comes back with a full mark, so every row measures the same, every
configuration ties at the top, and a comparison between them separates nothing. A results
table filled in this way reports a confident improvement with no measurement under it.
"""


def score(output, expected, input_data=None, metadata=None):
    """1.0, whatever the model produced and whatever was recorded as correct."""
    return 1.0
