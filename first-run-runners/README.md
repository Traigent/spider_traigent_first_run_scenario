# The two paid stages, as scripts

These are the runner scripts a coding assistant wrote while following the first-run guide on a
`--preset best-case` project on 2026-09-06, kept so the paid stages can be run by hand when the
guide stops at its execution-evaluator gate (an `exec-match` scorer runs model-written SQL, and
the guide will not do that without a reviewed sandbox).

Two changes from what the assistant wrote, both measured that day:

- the quality objective is named `accuracy`, the one key the portal reads for it - any other
  name shows there as 0%;
- `optimize_sync` gets `timeout=None`; a written 600 s cut a twelve-trial search at seven.

Use them from inside a built project:

```bash
cd <built project>
cp -r <this checkout>/presentation/first-run-runners traigent-runs
python3.13 -m venv .venv-traigent
.venv-traigent/bin/pip install -r traigent-first-run/skills/traigent-first-run/assets/requirements-first-run.txt
env -u TRAIGENT_API_KEY -u OPENROUTER_API_KEY .venv-traigent/bin/python traigent-runs/baseline/run_baseline.py
env -u TRAIGENT_API_KEY -u OPENROUTER_API_KEY .venv-traigent/bin/python traigent-runs/connected/run_connected.py
```

`baseline/` scores the agent's own defaults on the 18 rows named in `selected-rows.json`, read
from the project's `dataset.jsonl`. `connected/` runs the managed optimization on `tuning.jsonl`
and checks the winner on `holdout.jsonl`; both files are drawn from the same Spider slice the
project ships (CC BY-SA 4.0, see the project's `ATTRIBUTION.txt`). The `env -u` prefix keeps a
key exported in the shell from outranking the one in `.env`.
