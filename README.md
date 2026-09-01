# Spider Traigent First Run Scenario

Builds small text-to-SQL projects, on real data, for trying the
[Traigent Guided First Run](https://github.com/Traigent/traigent-first-run) against.

The guided first run is the thing a customer meets first: they paste one prompt, a coding
assistant reads their project, scores how ready it is to optimize, fills in what is missing,
and runs an optimization. To know whether that works, it has to be run against projects --
and against projects in the states real ones actually arrive in, not only the tidy one.

That is what this repository makes. One command builds a complete project you can point an
agent at:

```bash
python build.py demo --preset ready --out ~/demos/first-try
```

and the same command, with different flags, builds the same project with the evaluator
missing, or with unlabelled data, or with an agent that has nothing worth tuning.

## Getting started

```bash
git clone https://github.com/Traigent/spider_traigent_first_run_scenario.git
cd spider_traigent_first_run_scenario

python build.py list                                    # what can be built
python build.py check                                   # confirm this clone is intact
python build.py demo --preset ready --out ~/demos/first-try
```

No installation and no dependencies. `build.py` is standard library only, and the data is
committed, so a fresh clone can build immediately and offline.

Then start a coding assistant with `~/demos/first-try/project` as its working directory and
give it exactly this, and nothing else:

```text
Help me run my first Traigent optimization.
Clone https://github.com/Traigent/traigent-first-run and follow GUIDE.md.
```

That is the same prompt a customer is given. `build.py` prints it when it finishes, and
records it in `demo.json`.

## What gets built

```
~/demos/first-try/
├── demo.json          how it was built: every flag, every file's hash, the handoff prompt
└── project/           <- point the agent at this
    ├── agent.py       writes SQL. run(question, config) -> query text
    ├── dataset.jsonl  300 questions with the query that answers each
    ├── catalog.json   which database each question is about, and its structure
    ├── databases/     18 SQLite databases
    ├── evaluator.py   marks an answer. score(output, expected, input_data, metadata)
    ├── traigent-runs/ probe answers for the scorer, with --calibration present
    ├── README.md      what a project of this kind would normally document
    ├── .env.example
    └── LICENSE-DATA   the data's licence, which travels with the data
```

`demo.json` stays **outside** `project/` on purpose. It names the state each component was
put in, and an agent that can read that is not being tested on anything.

## Choosing what the project starts with

| Flag | Values |
|---|---|
| `--agent` | `ready` · `no-knobs` · `missing` |
| `--dataset` | `ready` (300) · `mini` (30) · `unlabeled` (40) · `missing` |
| `--eval` | `exact-match` · `exec-match` · `broken` · `missing` |
| `--calibration` | `none` · `present` (probe answers for the scorer) |
| `--existing-venv` | `none` · `one-compatible` · `old-python` |
| `--guide` | `clone` · `local` (with `--guide-src`) |

Presets are shorthand for the combinations worth having a name:

| Preset | The project it builds |
|---|---|
| `ready` | everything present and tunable, scorer not yet checked |
| `checked` | the same, and the team keeps probe answers for its scorer |
| `no-eval` | no way to score an answer |
| `no-labels` | questions with no expected answers |
| `no-knobs` | an agent with nothing to search |
| `sql-exec-stop` | an evaluator that runs the SQL the model wrote -- Spider's own metric |
| `best-case` | the same, and the team keeps probe answers for its scorer |

Individual flags override a preset, so `--preset ready --eval missing` is the ready project
with the evaluator taken out.

## The two SQL evaluators

`--eval` is the one choice worth understanding before you make it, because the two scorers
disagree about what a right answer is.

**`exact-match`** compares the generated query with the recorded one as text, after
normalising spacing, quote style, keyword case and a trailing semicolon. It never runs
anything. Its limit is real: `SELECT a, b` and `SELECT b, a` return the same thing and it
marks the second one wrong, so it under-counts correct answers.

**`exec-match`** runs both queries against the database and compares the rows they return.
This is Spider's own metric -- execution accuracy -- and it is the faithful way to mark a SQL
answer, because it credits a correct query written differently from the recorded one. It
reaches that by executing SQL the model wrote.

The first-run guide's `references/run-safety.md` currently declines to execute a scorer that
does so, ending the run before the evaluator executes. So the presets ask different
questions: `checked` asks whether a first run works end to end on a non-executing proxy,
`best-case` asks what the project scores when marked the benchmark's way, and
`sql-exec-stop` asks whether that boundary holds.
[docs/eval-methods.md](docs/eval-methods.md) has the detail, including a measured problem
with how the two scorers are graded.

## What each preset scores

Measured with the first-run guide's own `preflight.py`, `calibrate_evaluator.py` and
`readiness.py`, at guide revision `6ec2b9c1` on 2026-09-01.

These are not the numbers a bare clone reads. The **86** and the **91** need the guide's
assistant to have read the agent's source itself and handed that read to `readiness.py` as
`--agent-knobs`. No such document is in this repository, and none can be: it is the
assistant's own reading, produced during a run. Without it the `agent-no-varying-knobs`
ceiling holds every preset at 45 or below.

The point of the table is that the presets are genuinely different: each lands the run
somewhere else.

| preset | overall | band | what the guide is told to do next | caps |
|---|---|---|---|---|
| `no-labels` | 30 | PARTIAL | label the data | 2 |
| `no-eval` | 40 | PARTIAL | connect an evaluator | 1 |
| `ready` | 45 | PARTIAL | proceed | 1 |
| `no-knobs` | 45 | PARTIAL | find something to vary | 2 |
| `sql-exec-stop` | 45 | PARTIAL | proceed -- **and no containment cap is raised** | 1 |
| `checked` | **86** | **STRONG** | proceed | none |
| `best-case` | **91** | **EXCELLENT** | proceed | none |

Dataset pillar is **98** in the six presets that ship the full 300-row labelled slice --
every one above except `no-labels`, which ships 40 rows with no expected answer and no
holdout split, and so has nothing for that pillar to read.

### What moves a project up

Two ceilings sit at 45, and each has exactly one remedy. `ready` carries only the first.
The second is what `--agent no-knobs` adds, which is why `no-knobs` shows two caps.

**`evaluator-unvalidated`** -- a scorer nobody has checked cannot support a claim. It clears
when the project keeps probe answers for its own scorer and a calibration run measures that
it separates a right answer from a wrong one. `--calibration present` ships them, which is
the whole difference between `ready` and `checked`, and it is worth 41 points.

**`agent-no-varying-knobs`** -- the opening read is a narrow static one, and when it cannot
follow a setting from the configuration to the request it says so rather than assuming. It
clears when the agent is written so that path is followable.

That second one has a trap in it, and this repository fell into it once. **Shape the agent so
its settings are readable; never change what it sends to make them readable.** An earlier
version was restructured for the score and, in the process, changed `schema_context="none"`
from sending no schema to sending a sentence saying the schema was not shown -- which stops
that arm being a control, because the setting is then partly measuring the sentence. The
restructure here was a pure one: a 36-arm differential over every combination of the four
settings showed the outgoing model, prompt and temperature byte-identical to the shape it
replaced, and `tests/test_components.py` fails if the control arm ever gains content again.

The agent has changed once since, deliberately and for a different reason. The compact
`tables` view was built by splitting the schema on every comma, which turned a column type
like `DECIMAL(19,4)` into a column named `4)` and leaked composite-key column lists out as
columns of their own -- eleven tables across nine of the eighteen databases, describing
tables that do not exist to the model being measured. Parsing by parenthesis depth fixed it,
and now matches `PRAGMA table_info` for all 74 tables. That changes the 12 `tables` arms of
the 36 and nothing else, which is the point: `none` and `full` are untouched.

Two of the four settings are credited, which is all that is available: the agent pillar's
search-space share is held one step below full until a trial budget is declared, and a
budget only exists in a document a real run produces. Four configurations already reach that
ceiling, so crediting the other two settings would add exactly zero. The published reference
scenario scores the same 70 for the same reason.

### Why `best-case` scores higher than `checked`

The two projects are identical except for how an answer is marked.

**`best-case` marks answers the way Spider marks them.** Spider is scored by *execution
accuracy*: run the generated query and the recorded one, compare the rows they return. Every
Spider figure in the literature and on the official leaderboard is that measure. So
`best-case` is the configuration faithful to the benchmark this data comes from, and it reads
**91, EXCELLENT**.

**`checked` marks answers by comparing query text**, which never runs anything. That is a
proxy for the benchmark metric, and a lossy one: a correct query written differently from the
recorded one is marked wrong. The readiness score charges exactly that -- task fit **8/25**
for `code-sql`, against **25/25** for execution -- and the result is **86, STRONG**.

Both numbers are what the guide's own tooling returns, on artifacts anyone can rebuild from
this repository. The five-point gap is not a penalty or a concession; it is the score
correctly reporting that one project measures its answers the way the benchmark does and the
other approximates it.

The arithmetic is closed, so it is worth stating what the text proxy cannot reach: at dataset
98 and agent 70, EXCELLENT needs an evaluation pillar of 94, and the text comparator's
calibrated ceiling is 83. Even a perfect dataset leaves it at 87. If you want a project that
reads EXCELLENT on Spider data, it has to score Spider's way.

**A separate fact about the guide, which does not change either number.** The first-run
guide's `references/run-safety.md` currently declines to execute a scorer that runs
model-written SQL, and `--preset sql-exec-stop` and `--preset best-case` both fall under that.
So the Spider-faithful configuration is one the guide will not run today. That is a property
of the guide's policy, recorded as a finding in
[docs/eval-methods.md](docs/eval-methods.md) -- not a qualification on what these projects
score.

### One thing that would not be truthful

Declaring the evaluator method as `exact` with task kind `structured` makes the *text*
comparator read **92, EXCELLENT, no caps** -- numerically indistinguishable from the reference
scenario's published card, with the evaluator file completely unchanged. Nothing checks a
declaration against the source.

This repository does not do that, and no number in the table above depends on it. Every band
here comes from an evaluator declared as what it is, on probe answers built from real rows,
with an agent whose settings were made readable without changing what it sends. A high band is not evidence that anyone checked; that is what the calibration step
is for.

## The data is Spider

The questions and queries are from **Spider 1.0**, the standard cross-domain text-to-SQL
benchmark: human-written questions over databases from many different subject areas, each
paired with the SQL that answers it.

> Yu et al., *Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain
> Semantic Parsing and Text-to-SQL Task*, EMNLP 2018.
> [arXiv:1809.08887](https://arxiv.org/abs/1809.08887) ·
> [yale-lily.github.io/spider](https://yale-lily.github.io/spider)

300 rows drawn from the development split, with the 18 SQLite databases they need (about
1.4 MB in total, which is why the data is committed rather than downloaded). Every row was
checked: each recorded query runs, and returns rows. Difficulty comes from Spider's own
official hardness classifier, and the 300 are balanced 75 apiece across its four bands.

**The data is licensed CC BY-SA 4.0, not Apache-2.0 like the code**, and ShareAlike applies
to an adaptation of it that you share. `spider/LICENSE-DATA` carries the attribution and the
terms, and is copied into every generated project alongside the rows.

Two things to know before reading anything into a score: Spider is old enough and public
enough that current models have very likely seen it, and 300 rows is a demonstration size --
enough to tell configurations apart, not enough to settle a question about production.
[docs/dataset.md](docs/dataset.md) has the full picture.

## Documentation

| | |
|---|---|
| [docs/dataset.md](docs/dataset.md) | what the data is, how the 300 were chosen, what it cannot support |
| [docs/isolation.md](docs/isolation.md) | how a demo is kept separate, and what to do to keep a run honest |
| [docs/eval-methods.md](docs/eval-methods.md) | the two SQL scorers, and the scoring problem behind them |

## Working on this repository

```bash
python -m pip install -r requirements-dev.txt

python build.py check
python -m unittest discover -s tests -v
black --check build.py spider tests components
ruff check build.py spider tests components
mypy --strict build.py spider/build_slice.py
```

`check` validates the components and the committed data. The tests re-run all 300 recorded
queries, so they take a moment; that is the point of them. `requirements-dev.txt` exists only
to pin the last three checkers, and CI runs all five commands, so skipping them here is what
turns a pull request red there.

To rebuild the data slice itself -- rarely needed, and it requires the source Spider pool:

```bash
python spider/build_slice.py --source <spider-benchmark-dir> --hardness <hardness.jsonl>
```

## Licence

Code is Apache-2.0 (`LICENSE`). Data is CC BY-SA 4.0 (`spider/LICENSE-DATA`). See `NOTICE`.

This repository does not include or license the Traigent SDK.
