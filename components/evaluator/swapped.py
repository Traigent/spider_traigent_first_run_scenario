"""Scores an answer by comparing the wrong two things.

The signature a scorer is given carries four values -- what the model produced, what was
recorded as correct, the question it was asked, and the row's other fields. This one compares
the question with the recorded answer and never looks at what the model produced at all.

It is a wiring mistake, not a design: the arguments arrive in an order that is easy to get
wrong, and a scorer that reads two of them and ignores a third still runs, still returns a
number, and still fills a results table. What it cannot do is tell two answers apart, because
nothing it compares depends on the answer. A question is never the SQL that answers it, so
every row scores zero, every configuration ties at zero, and a sweep reports that nothing
helped.

Zero everywhere is easier to notice than full marks everywhere, which is the other way this
goes wrong. It is still worth catching before a paid run rather than after one.
"""


def score(output, expected, input_data=None, metadata=None):
    """Compares the question with the recorded answer, which are never the same thing."""
    recorded = expected
    if recorded is None or not str(recorded).strip():
        raise ValueError(
            "this row has no recorded query to compare against, and a row with no answer "
            "cannot be scored -- grading against it would mark every attempt wrong"
        )
    asked = "" if input_data is None else str(input_data)
    return 1.0 if asked.strip() == str(recorded).strip() else 0.0
