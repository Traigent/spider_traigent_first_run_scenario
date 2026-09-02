"""Turns a question about a database into the SQL that answers it.

The model here is served by OpenRouter.

One model, one prompt, no settings. The configuration this agent is handed is accepted and
ignored -- nothing inside it changes the request that goes out, so every configuration
produces the same call. That is deliberate: it is the shape of an agent that has nothing
to search yet.

Databases come from catalog.json beside the dataset, and a reply is read exactly as the
tunable version reads it, so the only difference between the two is what can vary.
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

MODEL = "openrouter/qwen/qwen3-coder"
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


def call_model(model, prompt, temperature):
    """One completion, from whichever vendor the model id names.

    The call goes through LiteLLM rather than a vendor SDK, and that is not a preference.
    The environment the Traigent first-run guide builds installs litellm and no provider
    package at all, so `import anthropic` here would fail on the machine this is meant to
    It also means the vendor is a property of the model id rather than of this file: any
    vendor LiteLLM carries is reachable by changing the roster, with no vendor package to
    install and nothing else here to change.

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
    entry = catalog().get(input_text)
    if entry is None:
        raise KeyError(
            f"no database recorded for this question, so there is nothing to write SQL against: {input_text!r}"
        )
    prompt = f"Database schema:\n{entry['schema']}\n\n{INSTRUCTION}\nQuestion: {input_text}\nSQL:"
    return strip_code_fence(call_model(MODEL, prompt, 0.0))
