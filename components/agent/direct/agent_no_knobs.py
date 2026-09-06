"""Turns a question about a database into the SQL that answers it.

The model here is served by its own vendor.

One model, one prompt, no settings. The configuration this agent is handed is accepted and
ignored -- nothing inside it changes the request that goes out, so every configuration
produces the same call.

Databases come from catalog.json beside the dataset, and the reply is read back the same
way every time, so the only thing that differs between two calls is the question.
"""

import json
import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
CATALOG_PATH = PROJECT_ROOT / "catalog.json"

# The roster this agent calls from, which holds one model, because one model is what it
# calls. Naming others here would say the request can vary when nothing in it does.
MODELS = ("gpt-4o-mini",)
MODEL = MODELS[0]

VENDOR = "the model's own vendor"
# The key each model in the roster needs before it can be called.
MODEL_CREDENTIALS = {"gpt-4o-mini": "OPENAI_API_KEY"}
CREDENTIALS = tuple(dict.fromkeys(MODEL_CREDENTIALS.values()))

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

    The instruction asks for SQL only, so this is a backstop rather than the normal path.
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
    reachable by naming a different model, with no vendor package to install and nothing
    else here to change.

    The call is `litellm.completion` itself, resolved on the module at call time, and not
    LiteLLM's OpenAI-shaped `LiteLLM().chat.completions.create`. The request that leaves the
    process is the same either way; what differs is who else gets to see it. Traigent's
    usage capture wraps the module attribute `litellm.completion`, and the client object
    reaches the provider by its own path underneath that wrapper. Measured on 2026-09-06
    with a counting sentinel over `litellm.completion`: a client-object call went through
    it zero times, so the SDK saw no usage, estimated input tokens from the question text
    (the same 16.9 tokens whether the prompt carried no schema or the whole one), and
    reported every configuration at $0.00. Through the module attribute the same two
    configurations reported 363 and 410 input tokens and $0.0022 and $0.0041.
    """
    # The names that hold a value. The template ships every key present and empty, and a
    # key that has not been filled in is a key this agent does not have.
    supplied = {name for name, value in os.environ.items() if value.strip()}
    if MODEL_CREDENTIALS[model] not in supplied:
        raise RuntimeError(
            f"{model} is served by {VENDOR}, which needs {MODEL_CREDENTIALS[model]} in "
            "the environment. Add it to .env rather than pointing the agent at a vendor "
            "you happen to have a key for -- a different vendor writes a different answer, "
            "and swapping one in quietly changes what this agent does."
        )

    import litellm

    answer = litellm.completion(
        model=model,
        temperature=temperature,
        max_tokens=512,
        messages=[{"role": "user", "content": prompt}],
    )
    return answer.choices[0].message.content


def run(input_text, config):
    entry = catalog().get(input_text)
    if entry is None:
        raise KeyError(
            f"no database recorded for this question, so there is nothing to write SQL against: {input_text!r}"
        )
    prompt = f"Database schema:\n{entry['schema']}\n\n{INSTRUCTION}\nQuestion: {input_text}\nSQL:"
    return strip_code_fence(call_model(MODEL, prompt, 0.0))
