"""Connected, Traigent-managed optimization over the agent's own real knobs.

Wraps agent.run() unchanged (a thin pass-through, decorated here rather than in agent.py) and
reuses evaluator.score() unchanged as the scoring function. Searches the same 18-row tuning
subset the baseline used, temperature pinned at the agent's own default since this is
deterministic SQL work, then checks the winning configuration against the 60-row holdout split
that no search step ever sees.
"""

import json
import os
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = Path(__file__).resolve().parent

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

# Approved ceiling for this connected phase (user approved up to $5.00).
os.environ["TRAIGENT_RUN_COST_LIMIT"] = "5.0"
os.environ["TRAIGENT_COST_APPROVED"] = "true"
os.environ["TRAIGENT_REQUIRE_CLOUD"] = "1"
os.environ.pop("TRAIGENT_OFFLINE_MODE", None)
os.environ.pop("TRAIGENT_OFFLINE", None)
os.environ.pop("TRAIGENT_MOCK_LLM", None)
os.environ["TRAIGENT_LOG_EXAMPLE_CONTENT"] = "false"
os.environ.setdefault("TRAIGENT_RESULTS_FOLDER", str(RUN_DIR / "sdk-results"))

sys.path.insert(0, str(PROJECT_ROOT))
import agent  # noqa: E402
import evaluator  # noqa: E402
import traigent  # noqa: E402
from traigent.api.decorators import EvaluationOptions  # noqa: E402
from traigent.api.decorators import InjectionOptions  # noqa: E402
from traigent.core.objectives import ObjectiveDefinition  # noqa: E402
from traigent.core.objectives import ObjectiveSchema  # noqa: E402

TUNING_DATASET = str(RUN_DIR / "tuning.jsonl")
HOLDOUT_DATASET = str(RUN_DIR / "holdout.jsonl")

# The agent's own real, existing knobs (agent.py MODELS / SCHEMA_CONTEXTS / PROMPT_STYLES).
# Temperature is deliberately excluded: this is deterministic SQL work, and the agent's own
# default (0.0) is preserved by simply never varying it, exactly as the baseline ran it.
CONFIGURATION_SPACE = {
    "model": list(agent.MODELS),
    "schema_context": list(agent.SCHEMA_CONTEXTS),
    "prompt_style": list(agent.PROMPT_STYLES),
}
TOTAL_CONFIGURATIONS = 3 * 3 * 2
MAX_TRIALS = 12

OBJECTIVES = ObjectiveSchema.from_objectives(
    [
        ObjectiveDefinition(name="accuracy", orientation="maximize", weight=1.0),
        ObjectiveDefinition(name="cost", orientation="minimize", weight=1.0),
    ]
)


def call_agent(input_text, config):
    return agent.run(input_text, config)


optimized_agent = traigent.optimize(
    objectives=OBJECTIVES,
    configuration_space=CONFIGURATION_SPACE,
    experiment_name="traigent-first-run-text-to-sql",
    evaluation=EvaluationOptions(
        eval_dataset=TUNING_DATASET,
        scoring_function=evaluator.score,
    ),
    injection=InjectionOptions(injection_mode="parameter", config_param="config"),
)(call_agent)


def run_holdout(config, rows):
    """Score one configuration against the held-out rows, outside the search."""
    scored = []
    for row in rows:
        try:
            output = agent.run(row["input"], config)
            score = evaluator.score(
                output, row["output"], row["input"], row["metadata"]
            )
        except Exception as exc:
            score = None
        scored.append(score)
    valid = [s for s in scored if s is not None]
    return {
        "rows": len(rows),
        "scored": len(valid),
        "accuracy": (sum(valid) / len(valid)) if valid else None,
    }


def main():
    print(
        f"Configuration space: {TOTAL_CONFIGURATIONS} possible configurations "
        f"(model x{len(CONFIGURATION_SPACE['model'])} "
        f"x schema_context x{len(CONFIGURATION_SPACE['schema_context'])} "
        f"x prompt_style x{len(CONFIGURATION_SPACE['prompt_style'])}); "
        f"testing up to {MAX_TRIALS}, Traigent's managed cost-aware selection."
    )

    t0 = time.time()
    result = optimized_agent.optimize_sync(
        max_trials=MAX_TRIALS,
        timeout=None,
    )
    elapsed = time.time() - t0

    summary = {
        "best_config": getattr(result, "best_config", None),
        "best_score": getattr(result, "best_score", None),
        "total_cost": getattr(result, "total_cost", None),
        "trials": getattr(result, "trials", None),
        "failed_trials": getattr(result, "failed_trials", None),
        "stop_reason": getattr(result, "stop_reason", None),
        "run_label": getattr(result, "run_label", None),
        "cloud_url": getattr(result, "cloud_url", None),
        "elapsed_s": round(elapsed, 1),
    }
    print("\n--- Connected optimization summary ---")
    for key, value in summary.items():
        print(f"{key}: {value}")

    (RUN_DIR / "optimized-results.json").write_text(
        json.dumps(summary, indent=2, default=str)
    )

    best_config = summary["best_config"]
    if best_config:
        holdout_rows = [json.loads(line) for line in Path(HOLDOUT_DATASET).open()]
        print(
            f"\nScoring the winning configuration against all {len(holdout_rows)} held-out rows..."
        )
        holdout_result = run_holdout(best_config, holdout_rows)
        print(
            f"Held-out accuracy: {holdout_result['accuracy']} "
            f"({holdout_result['scored']}/{holdout_result['rows']} scored)"
        )
        (RUN_DIR / "holdout-results.json").write_text(
            json.dumps(holdout_result, indent=2)
        )


if __name__ == "__main__":
    main()
