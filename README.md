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
| `--dataset` | `ready` (300) · `mini` (30) · `unlabeled` · `missing` |
| `--eval` | `exact-match` · `exec-match` · `broken` · `missing` |
| `--existing-venv` | `none` · `one-compatible` · `old-python` |
| `--guide` | `clone` · `local` (with `--guide-src`) |

Presets are shorthand for the combinations worth having a name:

| Preset | The project it builds |
|---|---|
| `ready` | everything present and tunable |
| `no-eval` | no way to score an answer |
| `no-labels` | questions with no expected answers |
| `no-knobs` | an agent with nothing to search |
| `sql-exec-stop` | an evaluator that runs the SQL the model wrote |

Individual flags override a preset, so `--preset ready --eval missing` is the ready project
with the evaluator taken out.

## The two SQL evaluators

`--eval` is the one choice worth understanding before you make it, because the two scorers
disagree about what a right answer is.

**`exact-match`** compares the generated query with the recorded one as text, after
normalising spacing, quote style, keyword case and a trailing semicolon. It never runs
anything. Its limit is real: `SELECT a, b` and `SELECT b, a` return the same thing and it
marks the second one wrong, so it under-counts correct answers.

**`exec-match`** runs both queries against the database and compares the rows. This is how
Spider itself is scored and it is the honest measure of a SQL answer -- but it gets there by
executing SQL that a model wrote.

The Traigent first-run guide treats that second one as out of scope: its
`references/run-safety.md` says a scorer that "submits candidate output to a code or SQL
engine" ends the run before the evaluator executes. So the two presets ask different
questions. `ready` asks whether a first run works. `sql-exec-stop` asks whether that
boundary holds. [docs/eval-methods.md](docs/eval-methods.md) has the detail, including a
measured problem with how the two are scored.

## What each preset scores

Measured with the first-run guide's own `preflight.py` and `readiness.py` at the opening
gate, at guide revision `6ec2b9c1` on 2026-09-01. The point of the table is that the presets
are actually different: each one lands the run somewhere else.

| preset | opening | band | what the guide is told to do next |
|---|---|---|---|
| `ready` | 45 | PARTIAL | proceed |
| `no-eval` | 39 | PARTIAL | connect an evaluator |
| `no-labels` | 19 | NOT READY | label the data |
| `no-knobs` | 45 | PARTIAL | proceed |
| `sql-exec-stop` | 45 | PARTIAL | proceed -- **no containment cap is raised** |

The dataset pillar scores **98** on the full slice, with every dataset check passing.

Two of those rows deserve a note, because both look like something is broken and neither is.

**The agent pillar reads 0 at the opening gate, for every preset** -- including `ready`,
whose agent has four settings that demonstrably change the request. The opening read is a
narrow static one, and when it cannot follow a setting to the call it records that it could
not, rather than assuming either way. The card says as much itself: the ceiling "records that
limit, not a finding that the agent has no setting". Scoring it as measured-zero rather than
as unmeasured is deliberate -- unmeasured lets the pillar renormalize out of the average,
which once made a run that found nothing outscore a run that found four settings. So
`ready` and `no-knobs` are not separated here. They separate later, from the read the guide
performs during an actual run.

Do not write agent code to move that number. An agent shaped to be followable by the static
read is not a more tunable agent, and shaping one costs something real: an earlier version of
`agent.py` here was restructured for exactly that, and the restructure changed
`schema_context="none"` from sending no schema to sending a sentence saying the schema was
not shown -- which stops that arm being a clean control, because the setting is then partly
measuring the sentence. It has been reverted. `tests/test_components.py` now has a test that
fails if the control arm ever gains content again.

**`sql-exec-stop` reaches `proceed` with no containment cap.** That is the finding, not a
build error. See [docs/eval-methods.md](docs/eval-methods.md).

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
to anything derived from it. `spider/LICENSE-DATA` carries the attribution and the terms,
and is copied into every generated project alongside the rows.

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
python build.py check
python -m unittest discover -s tests -v
```

`check` validates the components and the committed data. The tests re-run all 300 recorded
queries, so they take a moment; that is the point of them.

To rebuild the data slice itself -- rarely needed, and it requires the source Spider pool:

```bash
python spider/build_slice.py --source <spider-benchmark-dir> --hardness <hardness.jsonl>
```

## Licence

Code is Apache-2.0 (`LICENSE`). Data is CC BY-SA 4.0 (`spider/LICENSE-DATA`). See `NOTICE`.

This repository does not include or license the Traigent SDK.
