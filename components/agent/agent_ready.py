"""Turns a question about a database into the SQL that answers it.

Four settings change the request, and they are the point of the exercise -- each one is a
real difference in what gets sent, not a label:

    model           which model answers
    schema_context  how much of the database structure the model is shown: nothing, a
                    one-line-per-table summary, or the full CREATE TABLE text
    prompt_style    answer straight away, or sketch the query plan first
    temperature     0.0 or 0.7

schema_context is the one that usually moves the number. A model asked to write SQL against
a database it cannot see is guessing at table and column names.

The questions arrive as plain text, so the database each one belongs to is looked up in
catalog.json, which sits beside the dataset and maps every question to its database and
schema. A question that is not in the catalog is raised rather than answered against a
guess, because SQL written for the wrong database looks fine and is always wrong.
"""

import json
import re
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
CATALOG_PATH = PROJECT_ROOT / "catalog.json"

MODELS = {
    "gpt-4o-mini": "openai",
    "gpt-4o": "openai",
    "claude-3-5-haiku-latest": "anthropic",
}

SCHEMA_CONTEXTS = ("none", "tables", "full")

PROMPT_STYLES = {
    "direct": "Output the SQLite query only -- no explanation, no markdown.",
    "query_plan_cot": (
        "First outline the query plan (tables, joins, filters, aggregation) as SQL comments,"
        " then output the final SQLite query. Output SQL only."
    ),
}

TEMPERATURES = (0.0, 0.7)

_catalog = None


def catalog():
    """Question -> {db_id, schema}, loaded once."""
    global _catalog
    if _catalog is None:
        with CATALOG_PATH.open(encoding="utf-8") as handle:
            _catalog = json.load(handle)
    return _catalog


def compact_schema(schema):
    """One line per table, column names only -- the 'tables' view of the database."""
    lines = []
    for statement in schema.split(";"):
        statement = statement.strip()
        if not statement.lower().startswith("create table"):
            continue
        head, _, body = statement.partition("(")
        table = head.split()[-1].strip("\"`[]'")
        columns = []
        for part in body.rsplit(")", 1)[0].split(","):
            words = part.strip().split()
            if words and words[0].lower() not in (
                "primary",
                "foreign",
                "unique",
                "constraint",
                "check",
            ):
                columns.append(words[0].strip("\"`[]'"))
        lines.append(f"{table}({', '.join(columns)})")
    return "\n".join(lines)


def schema_for_config(schema, config):
    context = str(config.get("schema_context", "none"))
    if context not in SCHEMA_CONTEXTS:
        raise ValueError(f"schema_context {context!r} is not one of {SCHEMA_CONTEXTS}")
    if context == "none":
        return ""
    if context == "tables":
        return compact_schema(schema)
    return schema


def build_prompt(question, config):
    """The exact text sent to the model, assembled from the settings that shape it."""
    entry = catalog().get(question)
    if entry is None:
        raise KeyError(
            f"no database recorded for this question, so there is nothing to write SQL against: {question!r}"
        )
    schema_block = schema_for_config(entry["schema"], config)
    instruction = PROMPT_STYLES[config.get("prompt_style", "direct")]
    prefix = f"Database schema:\n{schema_block}\n\n" if schema_block else ""
    return f"{prefix}{instruction}\nQuestion: {question}\nSQL:"


def strip_code_fence(text):
    """The query on its own, with any markdown fence the model added removed."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```[a-zA-Z]*\n?", "", text)
        text = re.sub(r"\n?```$", "", text)
    return text.strip()


def call_model(model, prompt, temperature):
    """One completion from whichever provider serves this model."""
    if MODELS[model] == "anthropic":
        from anthropic import Anthropic

        answer = Anthropic().messages.create(
            model=model,
            max_tokens=512,
            temperature=temperature,
            messages=[{"role": "user", "content": prompt}],
        )
        return answer.content[0].text
    from openai import OpenAI

    answer = OpenAI().chat.completions.create(
        model=model,
        temperature=temperature,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return answer.choices[0].message.content


def run(input_text, config):
    """Answer one question with SQL, under an explicit configuration."""
    model = config.get("model", "gpt-4o-mini")
    if model not in MODELS:
        raise ValueError(
            f"{model!r} is not one of the models this agent is configured for"
        )
    temperature = float(config.get("temperature", 0.0))
    prompt = build_prompt(input_text, config)
    return strip_code_fence(call_model(model, prompt, temperature) or "")
