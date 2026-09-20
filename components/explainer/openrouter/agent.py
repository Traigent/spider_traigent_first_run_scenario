"""Turns a SQL query into a plain-English description of what it returns.

The model here is served by OpenRouter.

One model, one prompt, no settings. The configuration this agent is handed is accepted and
ignored -- nothing inside it changes the request that goes out, so every configuration
produces the same call. The query arrives as plain text and goes into the prompt as it is;
nothing here looks the database up.
"""

import os

# One model, because one model is what it calls.
MODELS = ("openrouter/qwen/qwen3-coder",)
MODEL = MODELS[0]

VENDOR = "OpenRouter"
# The key the model needs before it can be called.
MODEL_CREDENTIALS = {"openrouter/qwen/qwen3-coder": "OPENROUTER_API_KEY"}
CREDENTIALS = tuple(dict.fromkeys(MODEL_CREDENTIALS.values()))

INSTRUCTION = (
    "Describe in one plain-English sentence what this SQLite query returns. "
    "Do not repeat the SQL and do not use markdown."
)


def call_model(model, prompt, temperature):
    """One completion, from whichever vendor the model id names.

    The call goes through LiteLLM rather than a vendor SDK: only litellm is installed here
    and no provider package at all, so `import anthropic` would fail on the machine this is
    meant to run on. It is `litellm.completion` itself, resolved on the module at call
    time, so anything that wraps that attribute to watch usage sees this request.
    """
    # The names that hold a value. The template ships every key present and empty, and a
    # key that has not been filled in is a key this agent does not have.
    supplied = {name for name, value in os.environ.items() if value.strip()}
    if MODEL_CREDENTIALS[model] not in supplied:
        raise RuntimeError(
            f"{model} is served by {VENDOR}, which needs {MODEL_CREDENTIALS[model]} in "
            "the environment. Add it to .env."
        )

    import litellm

    answer = litellm.completion(
        model=model,
        temperature=temperature,
        max_tokens=256,
        messages=[{"role": "user", "content": prompt}],
    )
    return answer.choices[0].message.content


def run(input_text, config):
    """Describe one query. The configuration is accepted and not read."""
    prompt = f"{INSTRUCTION}\n\nSQL:\n{input_text}\n\nDescription:"
    return (call_model(MODEL, prompt, 0.0) or "").strip()
