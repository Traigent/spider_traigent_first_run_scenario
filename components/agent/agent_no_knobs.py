"""Turns a question about a database into the SQL that answers it.

One model, one prompt, no settings. The configuration this agent is handed is accepted and
ignored -- nothing inside it changes the request that goes out, so every configuration
produces the same call. That is deliberate: it is the shape of an agent that has nothing
to search yet.

Databases come from catalog.json beside the dataset, and a reply is read exactly as the
tunable version reads it, so the only difference between the two is what can vary.
"""

import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
CATALOG_PATH = PROJECT_ROOT / "catalog.json"

MODEL = "gpt-4o-mini"
INSTRUCTION = "Output the SQLite query only -- no explanation, no markdown."

_catalog = None


def catalog():
    global _catalog
    if _catalog is None:
        with CATALOG_PATH.open(encoding="utf-8") as handle:
            _catalog = json.load(handle)
    return _catalog


def strip_code_fence(text):
    """The query on its own, with any markdown wrapping the model added removed.

    Both prompt styles ask for SQL only, so this is a backstop rather than the normal path.
    It handles what a model actually does when it ignores that: a ``` or ~~~ fence with or
    without a language tag, a line of preamble before it, and anything after the closing one.

    A fence is only recognised at the start of a line. Searching the whole reply for the
    delimiter would find one inside a string literal -- `WHERE code = '```'` is a legal
    query -- and truncate the answer there.
    """
    lines = (text or "").strip().splitlines()
    opened = None
    for position, line in enumerate(lines):
        if line.lstrip().startswith(("```", "~~~")):
            opened = position
            break
    if opened is None:
        return "\n".join(lines).strip()
    closer = lines[opened].lstrip()[:3]
    body = []
    for line in lines[opened + 1 :]:
        if line.lstrip().startswith(closer):
            break
        body.append(line)
    return "\n".join(body).strip()


def run(input_text, config):
    entry = catalog().get(input_text)
    if entry is None:
        raise KeyError(
            f"no database recorded for this question, so there is nothing to write SQL against: {input_text!r}"
        )
    prompt = f"Database schema:\n{entry['schema']}\n\n{INSTRUCTION}\nQuestion: {input_text}\nSQL:"
    from openai import OpenAI

    answer = OpenAI().chat.completions.create(
        model=MODEL,
        temperature=0.0,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return strip_code_fence(answer.choices[0].message.content or "")
