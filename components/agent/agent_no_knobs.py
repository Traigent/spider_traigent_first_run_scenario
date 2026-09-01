"""Turns a question about a database into the SQL that answers it.

One model, one prompt, no settings. The configuration this agent is handed is accepted and
ignored -- nothing inside it changes the request that goes out, so every configuration
produces the same call. That is deliberate: it is the shape of an agent that has nothing
to search yet.

Databases come from catalog.json beside the dataset, as in the tunable version.
"""

import json
import re
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
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


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
