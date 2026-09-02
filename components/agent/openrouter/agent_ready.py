"""Turns a question about a database into the SQL that answers it.

The models here are served by OpenRouter. One key reaches all of them, and these are the ids LiteLLM routes to
OpenRouter.

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
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
CATALOG_PATH = PROJECT_ROOT / "catalog.json"

MODELS = (
    "openrouter/qwen/qwen3-coder",
    "openrouter/openai/gpt-oss-120b",
    "openrouter/meta-llama/llama-3.3-70b-instruct",
)

VENDOR = "OpenRouter"
# What this roster needs in the environment before it can call anything.
CREDENTIALS = ("OPENROUTER_API_KEY",)

SCHEMA_CONTEXTS = ("none", "tables", "full")

PROMPT_STYLES = {
    "direct": "Output the SQLite query only -- no explanation, no markdown.",
    "query_plan_cot": (
        "First outline the query plan (tables, joins, filters, aggregation) as SQL comments,"
        " then output the final SQLite query. Output SQL only."
    ),
}

TEMPERATURES = (0.0, 0.7)

# What this agent does when it is handed no configuration: the schema shown in full, one
# straightforward instruction, no sampling. The same request the untunable version of this
# agent makes, so the two are the same starting point and differ only in what can vary.
DEFAULTS = {
    "model": "openrouter/qwen/qwen3-coder",
    "schema_context": "full",
    "prompt_style": "direct",
    "temperature": 0.0,
}

_catalog = None


def catalog():
    """Question -> {db_id, schema}, loaded once."""
    global _catalog
    if _catalog is None:
        with CATALOG_PATH.open(encoding="utf-8") as handle:
            _catalog = json.load(handle)
    return _catalog


CONSTRAINT_KEYWORDS = ("primary", "foreign", "unique", "constraint", "check")


def _outside_quotes(statement):
    """The statement with quoted spans blanked out, so a scan can count only real syntax.

    A default value or a quoted identifier may contain a parenthesis or a comma. Counting
    those as syntax loses a column or invents one, which is what splitting on every comma
    did before -- the same mistake one level down.
    """
    masked = []
    index = 0
    while index < len(statement):
        character = statement[index]
        if character in "'\"`":
            quote = character
            masked.append(" ")
            index += 1
            while index < len(statement):
                if statement[index] == quote:
                    if index + 1 < len(statement) and statement[index + 1] == quote:
                        masked.append("  ")
                        index += 2
                        continue
                    break
                masked.append(" ")
                index += 1
            masked.append(" ")
            index += 1
            continue
        masked.append(character)
        index += 1
    return "".join(masked)


def _table_body(statement):
    """The text between a CREATE TABLE's outermost parentheses.

    Matched by depth rather than by looking for the last `)`, because a column type carries
    its own parentheses -- `DECIMAL(19,4)` -- and so does a composite key.
    """
    syntax = _outside_quotes(statement)
    opened = syntax.find("(")
    if opened == -1:
        return None
    depth = 0
    for position in range(opened, len(syntax)):
        if syntax[position] == "(":
            depth += 1
        elif syntax[position] == ")":
            depth -= 1
            if depth == 0:
                return statement[opened + 1 : position]
    return statement[opened + 1 :]


def _split_top_level(body):
    """The body's comma-separated parts, ignoring commas nested in parentheses.

    Splitting on every comma turns `DECIMAL(19,4)` into a column named `4)`, and leaks the
    column list of a composite key out as columns of its own. Either way the compact view
    describes a table that does not exist, and the model is asked to write SQL against it.
    """
    parts = []
    depth = 0
    current = []
    syntax = _outside_quotes(body)
    for position, character in enumerate(body):
        if syntax[position] == "(":
            depth += 1
        elif syntax[position] == ")":
            depth -= 1
        if syntax[position] == "," and depth == 0:
            parts.append("".join(current))
            current = []
            continue
        current.append(character)
    parts.append("".join(current))
    return parts


def compact_schema(schema):
    """One line per table, column names only -- the 'tables' view of the database."""
    lines = []
    for statement in schema.split(";"):
        statement = statement.strip()
        if not statement.lower().startswith("create table"):
            continue
        head, _, _ = statement.partition("(")
        table = head.split()[-1].strip("\"`[]'")
        body = _table_body(statement)
        if body is None:
            continue
        columns = []
        for part in _split_top_level(body):
            words = part.strip().split()
            if words and words[0].lower() not in CONSTRAINT_KEYWORDS:
                columns.append(words[0].strip("\"`[]'"))
        lines.append(f"{table}({', '.join(columns)})")
    return "\n".join(lines)


def schema_blocks(schema, context):
    """The schema blocks this setting shows -- none at all, or the one it names.

    'none' is the control arm, so it yields nothing to add to the prompt: not an empty
    block, and not a sentence saying the schema was withheld. A sentence is content the
    model reads, and the setting would then be measuring that sentence as well as the
    schema it stands in for.
    """
    if context not in SCHEMA_CONTEXTS:
        raise ValueError(f"schema_context {context!r} is not one of {SCHEMA_CONTEXTS}")
    if context == "none":
        return ()
    if context == "tables":
        return (compact_schema(schema),)
    return (schema,)


def build_prompt(question, config):
    """The exact text sent to the model, assembled from the settings that shape it."""
    entry = catalog().get(question)
    if entry is None:
        raise KeyError(
            f"no database recorded for this question, so there is nothing to write SQL against: {question!r}"
        )
    context = str(config.get("schema_context", DEFAULTS["schema_context"]))
    parts = [PROMPT_STYLES[config.get("prompt_style", DEFAULTS["prompt_style"])]]
    parts.append(f"\nQuestion: {question}\nSQL:")
    for block in schema_blocks(entry["schema"], context):
        parts.insert(0, f"Database schema:\n{block}\n\n")
    return "".join(parts)


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


def call_model(model, prompt, temperature):
    """One completion, from whichever vendor the model id names.

    The call goes through LiteLLM rather than a vendor SDK, and that is not a preference.
    The environment the Traigent first-run guide builds installs litellm and no provider
    package at all, so `import anthropic` here would fail on the machine this is meant to
    run on. It is also what lets the same agent reach OpenRouter or Bedrock by changing
    nothing but the model id.

    LiteLLM's OpenAI-shaped client is used rather than calling `litellm.completion`
    directly. It is the same transport -- `LiteLLM().chat.completions.create` forwards
    straight to `litellm.completion` and the request that leaves this process is identical
    either way -- written so that the model id, the prompt and the temperature are visibly
    the arguments of the call that sends them.
    """
    missing = [name for name in CREDENTIALS if not os.environ.get(name)]
    if missing:
        raise RuntimeError(
            f"{model} is served by {VENDOR}, which needs {', '.join(missing)} in the "
            "environment. Add it to .env rather than pointing the agent at a vendor you "
            "happen to have a key for -- which model answers is one of the things being "
            "measured, and changing it quietly changes the measurement."
        )

    from litellm import LiteLLM

    answer = LiteLLM().chat.completions.create(
        model=model,
        temperature=temperature,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return answer.choices[0].message.content


def run(input_text, config):
    """Answer one question with SQL, under an explicit configuration."""
    model = config.get("model", DEFAULTS["model"])
    if model not in MODELS:
        raise ValueError(
            f"{model!r} is not one of the models this agent is configured for"
        )
    temperature = float(config.get("temperature", DEFAULTS["temperature"]))
    return strip_code_fence(
        call_model(model, build_prompt(input_text, config), temperature)
    )
