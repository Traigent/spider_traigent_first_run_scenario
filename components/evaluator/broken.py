"""Scores every answer as correct.

This is not a scorer. It accepts whatever it is given and returns a full mark, so every
configuration measures the same and a comparison between them means nothing. A run that
trusts it will report a confident, meaningless improvement.

It is here so that a project can start out with a scorer that looks present and is not, and
so that whether that gets noticed before anything is spent can be observed.
"""


def score(output, expected, input_data=None, metadata=None):
    return 1.0
