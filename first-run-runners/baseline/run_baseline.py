"""Measure the agent's own existing default configuration on the selected 18-row subset.

Calls the real agent.run() unchanged, with an empty config so every knob falls back to
agent.py's own DEFAULTS. Cost and latency come from litellm's own per-call accounting via
a success callback, so agent.py and evaluator.py are never modified to expose them.
"""

import datetime
import json
import sys
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RUN_DIR = Path(__file__).resolve().parent

from dotenv import load_dotenv

load_dotenv(PROJECT_ROOT / ".env")

sys.path.insert(0, str(PROJECT_ROOT))
import agent  # noqa: E402
import evaluator  # noqa: E402
import litellm  # noqa: E402

COST_CEILING_USD = (
    1.00  # approved-scope safety stop; 18 short calls on cheap open models
)

calls = []


def _on_success(kwargs, response_obj, start_time, end_time):
    try:
        cost = litellm.completion_cost(completion_response=response_obj)
    except Exception:
        cost = None
    calls.append(
        {
            "model": kwargs.get("model"),
            "cost_usd": cost,
            "latency_s": (end_time - start_time).total_seconds(),
        }
    )


litellm.success_callback = [_on_success]


def total_spent():
    return sum(c["cost_usd"] for c in calls if c["cost_usd"] is not None)


def main():
    rows = [json.loads(line) for line in (PROJECT_ROOT / "dataset.jsonl").open()]
    by_id = {row["metadata"]["id"]: row for row in rows}
    selected_ids = json.loads((RUN_DIR / "selected-rows.json").read_text())["row_ids"]

    results = []
    for row_id in selected_ids:
        row = by_id[row_id]
        if total_spent() >= COST_CEILING_USD:
            print(
                f"Stopping early: spend has reached the ${COST_CEILING_USD:.2f} safety ceiling."
            )
            break
        t0 = time.time()
        try:
            output = agent.run(row["input"], {})
            error = None
        except (
            Exception
        ) as exc:  # provider/timeout/etc. -- a failed trial, not a wrong answer
            output = None
            error = f"{type(exc).__name__}: {exc}"
        elapsed = time.time() - t0

        if error is not None:
            score = None
        else:
            try:
                score = evaluator.score(
                    output, row["output"], row["input"], row["metadata"]
                )
            except Exception as exc:
                score = None
                error = f"evaluator error: {type(exc).__name__}: {exc}"

        results.append(
            {
                "id": row_id,
                "difficulty": row["metadata"]["difficulty"],
                "db_id": row["metadata"]["db_id"],
                "score": score,
                "elapsed_s": round(elapsed, 3),
                "error": error,
            }
        )
        print(
            f"[{row_id}] difficulty={row['metadata']['difficulty']} score={score} elapsed={elapsed:.2f}s"
            + (f" ERROR: {error}" if error else "")
        )

    scored = [r for r in results if r["score"] is not None]
    failed = [r for r in results if r["score"] is None]
    accuracy = (sum(r["score"] for r in scored) / len(scored)) if scored else None

    summary = {
        "generated_at_utc": datetime.datetime.now(datetime.timezone.utc).strftime(
            "%Y%m%dT%H%M%SZ"
        ),
        "agent": str(PROJECT_ROOT / "agent.py") + ":run",
        "config": dict(agent.DEFAULTS),
        "rows_attempted": len(results),
        "rows_scored": len(scored),
        "rows_failed": len(failed),
        "accuracy": accuracy,
        "provider_calls": len(calls),
        "total_cost_usd": total_spent(),
        "total_elapsed_s": round(sum(r["elapsed_s"] for r in results), 3),
        "results": results,
        "calls": calls,
    }
    (RUN_DIR / "baseline-results.json").write_text(json.dumps(summary, indent=2))
    print("\n--- Baseline summary ---")
    print(f"config: {summary['config']}")
    print(
        f"rows: {summary['rows_scored']} scored / {summary['rows_failed']} failed / {summary['rows_attempted']} attempted"
    )
    print(f"accuracy: {accuracy}")
    print(
        f"provider calls: {summary['provider_calls']}, total cost: ${summary['total_cost_usd']:.4f}"
    )
    print(f"total wall time: {summary['total_elapsed_s']:.1f}s")


if __name__ == "__main__":
    main()
