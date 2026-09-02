"""Scores an answer by comparing the question with the recorded query.

The four values a scorer is given are what the model produced, what was recorded as correct,
the question that was asked, and the row's other fields. This one reads the question and the
recorded query, and never looks at what the model produced at all.

Nothing it compares depends on the answer, so two answers cannot be told apart. A question is
never the SQL that answers it, so every row scores zero, every configuration ties at zero, and
a sweep over them reports that nothing helped.
"""

# A row names its question `input`, and a case written out on its own names it `question`.
# Either is the text that was asked; anything else that arrives is read as the text itself.
QUESTION_KEYS = ("question", "input")


def question_asked(input_data):
    """The question a row carries, whichever shape the row arrived in."""
    if isinstance(input_data, dict):
        for key in QUESTION_KEYS:
            asked = input_data.get(key)
            if asked is not None:
                return str(asked)
    return "" if input_data is None else str(input_data)


def score(output, expected, input_data=None, metadata=None):
    """1.0 when the question is written the same way as the recorded query."""
    recorded = expected
    if recorded is None or not str(recorded).strip():
        raise ValueError(
            "this row has no recorded query to compare against, and a row with no answer "
            "cannot be scored -- grading against it would mark every attempt wrong"
        )
    return 1.0 if question_asked(input_data).strip() == str(recorded).strip() else 0.0
