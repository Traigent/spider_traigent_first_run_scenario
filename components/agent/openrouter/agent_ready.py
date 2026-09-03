"""Turns a question about a database into the SQL that answers it.

The models here are served by OpenRouter, and one key reaches all of them. These are the
ids LiteLLM routes to OpenRouter.

Four settings change the request, and each one is a real difference in what gets sent
rather than a label:

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
# The key each model needs before it can be called. Held per model rather than as one list
# for the whole roster: a key that is missing only stops the models that need it, and the
# refusal can name the one key that model wants instead of every key the roster could want.
MODEL_CREDENTIALS = {
    "openrouter/qwen/qwen3-coder": "OPENROUTER_API_KEY",
    "openrouter/openai/gpt-oss-120b": "OPENROUTER_API_KEY",
    "openrouter/meta-llama/llama-3.3-70b-instruct": "OPENROUTER_API_KEY",
}
CREDENTIALS = tuple(dict.fromkeys(MODEL_CREDENTIALS.values()))

# Each schema_context setting and the line that introduces the structure it shows. 'none' is
# the control arm, so it introduces nothing and nothing follows it: not an empty block, and
# not a sentence saying the schema was withheld. A sentence is content the model reads, and
# the setting would then be measuring that sentence as well as the schema it stands in for.
SCHEMA_CONTEXTS = {
    "none": "",
    "tables": "Database schema, one line per table:\n",
    "full": "Database schema:\n",
}

PROMPT_STYLES = {
    "direct": "Output the SQLite query only -- no explanation, no markdown.",
    "query_plan_cot": (
        "First outline the query plan (tables, joins, filters, aggregation) as SQL comments,"
        " then output the final SQLite query. Output SQL only."
    ),
}

TEMPERATURES = (0.0, 0.7)

# What this agent does when it is handed no configuration: the schema shown in full, one
# straightforward instruction, no sampling.
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
# The closing delimiter each opening one expects, so a name written in any of SQLite's
# quoting styles is read as one token rather than split on the space inside it.
CLOSING_DELIMITER = {'"': '"', "`": "`", "[": "]", "'": "'"}


def _outside_quotes(statement):
    """The statement with quoted spans blanked out, so a scan can count only real syntax.

    A default value or a quoted identifier may contain a parenthesis, a comma or a
    semicolon. Counting those as syntax loses a column or invents one, which is what
    splitting on every comma did before -- the same mistake one level down.
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


def _read_name(text, start):
    """The name beginning at `start`, kept whole, and where it ends.

    `CREATE TABLE "Song Name"` names one table, not a table called `Name`, and taking the
    last whitespace-separated word said otherwise. A delimited name ends at its closing
    delimiter and nowhere else.
    """
    opening = text[start]
    closing = CLOSING_DELIMITER.get(opening)
    if closing is None:
        end = start
        while end < len(text) and not text[end].isspace() and text[end] != "(":
            end += 1
        return text[start:end], end
    index = start + 1
    while index < len(text):
        if text[index] == closing:
            if (
                closing == opening
                and index + 1 < len(text)
                and text[index + 1] == closing
            ):
                index += 2
                continue
            return text[start : index + 1], index + 1
        index += 1
    return text[start:], len(text)


def _as_written(name):
    """The name spelled so that reading it back names the same thing.

    A name that is only letters, digits and underscores stands on its own. Anything else --
    a space, a parenthesis, a leading digit -- has to keep its quoting, or the summary hands
    the model a column it cannot select: `Official_ratings_(millions)` unquoted is read as a
    call to a function called `Official_ratings_` and fails on the column it names.
    """
    bare = name.strip("\"`[]'")
    plain = (
        bare and not bare[0].isdigit() and all(c.isalnum() or c == "_" for c in bare)
    )
    return bare if plain else '"' + bare.replace('"', '""') + '"'


def _statements(schema):
    """The schema's statements, split on the semicolons that are not inside a literal."""
    syntax = _outside_quotes(schema)
    statements = []
    start = 0
    for position, character in enumerate(syntax):
        if character == ";":
            statements.append(schema[start:position])
            start = position + 1
    statements.append(schema[start:])
    return statements


def _without_leading_comments(statement):
    """The statement with anything commented out in front of it removed.

    A comment above a table is ordinary in a dumped schema, and testing the raw text for
    `create table` dropped every table that had one -- silently, so the summary described a
    database with a table missing rather than failing.
    """
    text = statement.strip()
    while True:
        if text.startswith("--"):
            _, _, text = text.partition("\n")
        elif text.startswith("/*"):
            _, _, text = text.partition("*/")
        else:
            return text
        text = text.strip()


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
    for statement in _statements(schema):
        statement = _without_leading_comments(statement)
        if not statement.lower().startswith("create table"):
            continue
        syntax = _outside_quotes(statement)
        opened = syntax.find("(")
        body = _table_body(statement)
        if opened == -1 or body is None:
            continue
        head = statement[:opened]
        table = ""
        index = 0
        while index < len(head):
            if head[index].isspace():
                index += 1
                continue
            token, index = _read_name(head, index)
            if token:
                table = token
            else:
                index += 1
        columns = []
        for part in _split_top_level(body):
            declaration = part.strip()
            if not declaration:
                continue
            name, _ = _read_name(declaration, 0)
            if name.strip("\"`[]'").lower() in CONSTRAINT_KEYWORDS:
                continue
            columns.append(_as_written(name))
        lines.append(f"{_as_written(table)}({', '.join(columns)})")
    return "\n".join(lines)


def schema_body(question, config):
    """The structure text that follows the heading this setting chose."""
    entry = catalog().get(question)
    if entry is None:
        raise KeyError(
            f"no database recorded for this question, so there is nothing to write SQL against: {question!r}"
        )
    context = config.get("schema_context", DEFAULTS["schema_context"])
    if context not in SCHEMA_CONTEXTS:
        raise ValueError(
            f"schema_context {context!r} is not one of the views this agent shows"
        )
    if context == "none":
        return ""
    if context == "tables":
        return f"{compact_schema(entry['schema'])}\n\n"
    return f"{entry['schema']}\n\n"


def build_prompt(question, config, schema=""):
    """The exact text sent to the model, assembled from the settings that shape it."""
    if question not in catalog():
        raise KeyError(
            f"no database recorded for this question, so there is nothing to write SQL against: {question!r}"
        )
    parts = [
        SCHEMA_CONTEXTS[config.get("schema_context", DEFAULTS["schema_context"])],
        PROMPT_STYLES[config.get("prompt_style", DEFAULTS["prompt_style"])],
        f"\nQuestion: {question}\nSQL:",
    ]
    # The structure goes under the heading that introduced it, so the control arm -- whose
    # heading is empty and whose structure is empty -- adds nothing at all.
    parts.insert(1, f"{schema}")
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
    Only litellm is installed here and no provider package at all, so `import anthropic`
    would fail on the machine this is meant to run on. It also means the vendor is a
    property of the model id rather than of this file: any vendor LiteLLM carries is
    reachable by changing the roster, with no vendor package to install and nothing else
    here to change.

    LiteLLM's OpenAI-shaped client is used rather than calling `litellm.completion`
    directly. It is the same transport -- `LiteLLM().chat.completions.create` forwards
    straight to `litellm.completion` and the request that leaves this process is identical
    either way -- written so that the model id, the prompt and the temperature are visibly
    the arguments of the call that sends them.
    """
    # The names that hold a value. The template ships every key present and empty, and a
    # key that has not been filled in is a key this agent does not have.
    supplied = {name for name, value in os.environ.items() if value.strip()}
    if MODEL_CREDENTIALS[model] not in supplied:
        raise RuntimeError(
            f"{model} is served by {VENDOR}, which needs {MODEL_CREDENTIALS[model]} in "
            "the environment. Add it to .env rather than pointing the agent at a vendor "
            "you happen to have a key for -- which model answers is one of the things "
            "being compared, and changing it quietly changes the comparison."
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
    if temperature not in TEMPERATURES:
        raise ValueError(
            f"{temperature!r} is not one of the temperatures this agent runs at: "
            f"{TEMPERATURES}"
        )
    return strip_code_fence(
        call_model(
            model,
            build_prompt(input_text, config, schema_body(input_text, config)),
            temperature,
        )
    )
