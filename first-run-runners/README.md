# The two paid stages, as scripts

These are the runner scripts a coding assistant wrote while following the first-run guide on a
`--preset best-case` project on 2026-09-06, kept so the paid stages can be run by hand when the
guide stops at its execution-evaluator gate (an `exec-match` scorer runs model-written SQL, and
the guide will not do that without a reviewed sandbox).

Two changes from what the assistant wrote, both measured that day:

- the quality objective is named `accuracy`, the one key the portal reads for it - any other
  name shows there as 0%;
- `optimize_sync` gets `timeout=None`; a written 600 s cut a twelve-trial search at seven.

What bounds that execution: `components/evaluator/exec_match.py` opens each database read-only
(`mode=ro`) from the project's own copies under `databases/`, installs an SQLite authorizer that
permits only reading (`SELECT`, `READ`, recursive CTEs) and SQLite's documented functions by name,
so `ATTACH`, `VACUUM INTO`, `load_extension`, `readfile` and `writefile` are refused, and bounds
every query to 5 seconds, 100,000 rows, 128 columns, 1 MB per value and 64 MB in total. As that
file says of itself, those bounds limit the damage; they do not change what the scorer is, which is
why the guide stops before it and why these scripts are run by hand.

Use them from inside a built project:

```bash
cd <built project>
cp -r <this checkout>/first-run-runners traigent-runs
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

`holdout.jsonl` is the built project's own held-out split, not the guide's: `build.py` marks every
row `tuning` or `holdout` and holds back 20% of each difficulty band, and the `ready` dataset's
held-out side is these 60 rows, 15 per band. The guide keeps a project-defined split as it stands,
so the winner is checked on all 60 rather than on the guide's default ten. `tuning.jsonl` is the
guide's bounded subset of the tuning side: the same 18 questions `selected-rows.json` names, at
least four per band.

The two files differ in shape on purpose. `tuning.jsonl` is read by the SDK's `Dataset.from_jsonl`,
which takes `input` and `output` and folds every other top-level key into the example's metadata,
so `id`, `difficulty`, `db_id`, `schema` and `split` sit at the top level and reach the scorer as
its `metadata` argument; a nested `metadata` object would arrive one level too deep and the scorer
would not find `db_id`. `holdout.jsonl` keeps the project's own nested shape because `run_holdout`
reads `row["metadata"]` directly.
