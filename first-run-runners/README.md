# The two paid stages, as scripts

These are the runner scripts a coding assistant wrote while following the first-run guide on a
`--preset best-case` project on 2026-09-06, when the guide ended before an approval card for a
project whose evaluator executes model-written SQL (an `exec-match` scorer does, and the guide
ships no sandbox for it). Since 2026-09-10 the guide no longer ends there: it says what it did
not check and continues, declining only to calibrate the original evaluator on its own
initiative. The scripts are kept as the by-hand record of the two paid stages from that day;
they are not the route the guide takes now.

Two changes from what the assistant wrote, both measured that day:

- the quality objective is named `accuracy`: the name the assistant first chose showed in the
  portal as 0%, and `accuracy` is the one it reads for this walkthrough. The guide's own wrapper
  uses `accuracy` for its exact-match walkthrough and says a customer run should use one
  meaningful metric name consistently in the objective, the metric function, the result reading
  and the frontier, because the portal is not an `accuracy`-only display;
- `optimize_sync` gets `timeout=None`; a written 600 s cut a twelve-trial search at seven.

What bounds that execution: `components/evaluator/exec_match.py` opens each database read-only
(`mode=ro`) from the project's own copies under `databases/`, installs an SQLite authorizer that
permits only reading (`SELECT`, `READ`, recursive CTEs) and SQLite's documented functions by name,
so `ATTACH`, `VACUUM INTO`, `load_extension`, `readfile` and `writefile` are refused, and bounds
every query to 5 seconds, 100,000 rows, 128 columns, 1 MB per value and 64 MB in total. As that
file says of itself, those bounds limit the damage; they do not change what the scorer is, which is
why the guide will not calibrate the original evaluator on its own initiative, and why these
scripts were run by hand.

Use them from inside a built project, with the guide cloned beside the project rather than
inside it, as its `GUIDE.md` instructs the assistant:

```bash
cd <built project>
cp -r <this checkout>/first-run-runners traigent-runs
python3.13 -m venv .venv-traigent
.venv-traigent/bin/pip install -r ../traigent-first-run/skills/traigent-first-run/assets/requirements-first-run.txt
env -u TRAIGENT_API_KEY -u OPENROUTER_API_KEY .venv-traigent/bin/python traigent-runs/baseline/run_baseline.py
env -u TRAIGENT_API_KEY -u OPENROUTER_API_KEY .venv-traigent/bin/python traigent-runs/connected/run_connected.py
```

`.venv-traigent` is what the guide built on 2026-09-06; today it is only the guide's throwaway
fallback -- the guide first looks for an environment inside the project and installs into it
after approval, or creates a persistent `.venv` -- so any Python 3.11-3.13 environment with the
pinned stack does the same job here.

`baseline/` is a hand loop outside the SDK over the project's `dataset.jsonl` (not the guide's offline
grid run on `tuning.jsonl`) that scores the agent's own defaults on the 18 rows named in
`selected-rows.json`. `connected/` runs the managed optimization on `tuning.jsonl`
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
reads `row["metadata"]` directly. Two more places these scripts differ from the guide's own
wrapper at `9ae7c722`: the guide's held-out pass loads its file through `Dataset.from_jsonl`
and averages every scored row, where this script reads the nested shape by hand and averages
the rows that scored; and the connected script neither writes `traigent-runs/config-space.json`
after the search nor probes portal tracking before it, so a run under it produces nothing the
guide's closing readiness score would read. The connected script also clears an inherited
`TRAIGENT_OFFLINE`, `TRAIGENT_OFFLINE_MODE` or `TRAIGENT_MOCK_LLM` before it starts, where the
guide's wrapper refuses to start under any of them and asks for it to be unset.
