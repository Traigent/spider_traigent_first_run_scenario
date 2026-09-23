"""Marks a description of a query.

We never wrote a real grader for this one. What the model is asked for is a single
sentence a person could read, so that is what gets checked: a description that is between
eight and forty words long, and that does not hand the SQL back, passes; anything else
fails. It says nothing about whether the sentence is *right* -- that is a job for someone
reading it.
"""

SHORTEST = 8
LONGEST = 40


def score(output, expected=None, input_data=None, metadata=None):
    """1.0 for a sentence-length description in prose, 0.0 for anything else."""
    text = "" if output is None else str(output).strip()
    words = text.split()
    if not SHORTEST <= len(words) <= LONGEST:
        return 0.0
    if text.upper().startswith(("SELECT", "WITH")):
        return 0.0
    return 1.0
