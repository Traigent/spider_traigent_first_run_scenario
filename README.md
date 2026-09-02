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

Or build the whole bank at once, each project in its own directory:

```bash
python build.py suite --out ~/demos/bank
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
├── demo.json          how it was built: flags, per-file hashes, the handoff prompt
└── project/           <- point the agent at this
    ├── agent.py       writes SQL. run(question, config) -> query text
    ├── dataset.jsonl  300 questions with the query that answers each
    ├── catalog.json   which database each question is about, and its structure
    ├── databases/     18 SQLite databases
    ├── evaluator.py   marks an answer. score(output, expected, input_data, metadata)
    ├── traigent-runs/ probe answers for the scorer, with --calibration present
    ├── README.md      what a project of this kind would normally document
    ├── .env.example
    ├── LICENSE-DATA   the data's licence, which travels with the data
    ├── LICENSE        the code's licence
    └── NOTICE         which parts are under which licence
```

`demo.json` stays **outside** `project/` on purpose. It names the state each component was
put in, and an agent that can read that is not being tested on anything.

## Choosing what the project starts with

| Flag | Values |
|---|---|
| `--agent` | `ready` · `no-knobs` · `missing` |
| `--dataset` | `ready` (300) · `mini` (30) · `tiny` (10) · `unlabeled` (40) · `duplicated` · `wrong-answers` · `missing` |
| `--eval` | `exact-match` · `exec-match` · `broken` · `swapped` · `missing` |
| `--provider` | `openrouter` (default) · `direct` |
| `--calibration` | `none` · `present` (probe answers for the scorer) |
| `--guide` | `clone` · `local` (with `--guide-src`) |

Presets are shorthand for the combinations worth having a name:

| Preset | The project it builds |
|---|---|
| `ready` | everything present and tunable, scorer not yet checked |
| `checked` | the same, and the team keeps probe answers for its scorer |
| `best-case` | the same, scored by execution accuracy -- the metric Spider itself uses |
| `sql-exec-stop` | an evaluator that runs the SQL the model wrote -- Spider's own metric |
| `hand-written` | ten examples written by hand, and probes kept for the scorer |
| `no-knobs` | an agent with nothing to search |
| `no-eval` | an agent and data, and no way to score an answer |
| `no-agent` | data and a scorer, and nothing to run them against |
| `no-data` | an agent and a scorer, and nothing to measure them on |
| `no-labels` | questions with no expected answers |
| `agent-and-logs` | an agent, and logged questions with no answers and no scorer |
| `logs-only` | nothing but logged questions -- all three pieces have to be built |
| `empty` | an empty directory |
| `fake-ruler` | a scorer that marks everything correct, and probes that catch it |
| `wrong-wiring` | a scorer comparing the question with the answer, never the output |
| `duplicated-data` | half the rows appear twice, question and answer both |
| `wrong-answers` | every answer runs, and answers a different question |

Individual flags override a preset, so `--preset ready --eval missing` is the ready project
with the evaluator taken out.

## Data that is wrong on purpose

Three of the seventeen presets ship a project whose data or scorer is broken. Real projects
arrive that way, and the run's job is not to notice and stop -- it is to notice, repair, and
carry on to a result that means something. These are the states that make it show its work.

| | what is wrong |
|---|---|
| `duplicated-data` | half the rows appear twice -- the same question and the same answer -- which is what appending an export to itself looks like. A score over it counts the same evidence more than once. |
| `wrong-answers` | every question keeps a real answer, and it is a different question's answer. The rotation happens inside each database, so every answer still runs and still returns rows. That is the hard version: an answer borrowed from another database would not execute and would announce itself. |
| `wrong-wiring` | the scorer compares the question with the recorded answer and never looks at what the model produced. It runs, it returns a number, and every row ties at zero. |

**The questions and answers are Spider's. What is wrong with them is this repository's**, and
`demo.json` records which by name. The committed slice is never touched -- damage happens on
the way into a demo, and a test asserts the file on disk is unchanged afterwards. Every
answer in a damaged dataset is still a real Spider answer; none is invented.

## Which vendor answers

The agent's `model` setting is one of the four things being measured, so which models it
chooses between matters. `--provider` picks the roster and the credentials the project asks
for:

| | models | credentials |
|---|---|---|
| `openrouter` | Qwen3 Coder, GPT-OSS 120B, Llama 3.3 70B | `OPENROUTER_API_KEY` |
| `direct` | GPT-4o mini, GPT-4o, Claude 3.5 Haiku | `OPENAI_API_KEY`, `ANTHROPIC_API_KEY` |

OpenRouter is the default because one key reaches every model in its roster, which makes a
sweep across the `model` setting a single credential away rather than two.

**Bedrock is not shipped, and the reason is worth writing down.** LiteLLM signs Bedrock
requests through `boto3`, and the first-run guide's pinned stack is `traigent`, `litellm`
and `python-dotenv` -- no `boto3`. Measured in a clean environment built from exactly that
stack: OpenRouter reaches the network and fails only on a deliberately invalid key, while
Bedrock raises `No module named 'boto3'` before any request leaves. A Bedrock roster would
therefore need that package added to an environment this project does not control, so it is
left out until that is settled rather than shipped as a vendor that does not work.

Every roster is called through **LiteLLM**, and that is not a style choice. The environment
the first-run guide builds installs `traigent`, `litellm` and `python-dotenv` and no vendor
package at all -- so an agent that did `import anthropic` would fail on the machine it is
meant to run on. It also means the vendor is a property of the model id rather than of the
agent, so adding one is a roster and a credential name, not a rewrite.

There is one agent file per vendor rather than one agent reading a roster from somewhere
else, and that is forced: the guide credits a setting only from values it can read in the
selected agent's own source, so a roster imported from a sibling module scores zero. The
two copies are otherwise the same file, and
`tests/test_components.py::TheVendorVariantsDoNotDrift` fails if they stop being.

## The two SQL evaluators

`--eval` is the one choice worth understanding before you make it, because the two scorers
disagree about what a right answer is.

**`exact-match`** compares the generated query with the recorded one as text, after
normalising comments away and then spacing, quote style, keyword case and a trailing
semicolon. It never runs
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
`sql-exec-stop` asks about the one thing in this bank that is a boundary rather than a gap:
an executing scorer is not something the run repairs and moves past, it is where this guide
hands over.
[docs/eval-methods.md](docs/eval-methods.md) has the detail, including a measured problem
with how the two scorers are graded.

## Where each preset starts, and what the run has to do about it

The scores below are **opening** scores. They are not a verdict on the project and they are
not the point of it.

The first-run guide exists to take a project from whatever state it is in to a working first
optimization. Its own words: it "works whether the project already has all, some, or none of"
an agent, a dataset and a way to score answers. When something is missing it creates it; when
something is broken it repairs it; then it scores again, and the run carries on. A low opening
number is not a failure -- it is the size of the gap the run has to close before it can
measure anything, and closing it is the job.

So read the table as seventeen starting points, and the question each one asks is the same:
**can the run get from here to a real result, and does it say honestly what it had to build
along the way?** A project that opens at 25 and reaches a genuine optimization is a better
demonstration than one that opens at 86, because the first one shows the work.

One number per project at the opening, not two. Reading the agent's source is part of that
gate, not an optional extra -- the guide is explicit that "every guided run that found an
agent does this read, not conditionally" -- and it hands that read to `readiness.py` as
`--agent-knobs`. Invoking the scorer by hand without that flag reports something lower, but
that is the tool saying it was not given the read it requires, not a second opinion about the
project.

Two caveats worth stating rather than burying. The agent read used here was written by hand to
stand in for the one an assistant writes; it cites real values on the real call path, so the
figures are faithful, but another honest read could move them a few points. And a real run
scores twice -- once at the opening and again after it has created or repaired anything -- so
the number a finished run reports is not the one in this table, and should not be.

Measured with the guide's own `preflight.py`, `calibrate_evaluator.py` and `readiness.py`, at
guide revision `6ec2b9c1`.

| preset | opening | band | what the run has to build or fix |
|---|---|---|---|
| `empty` | 0 | NOT READY | all three: an agent, examples, and a way to score them |
| `logs-only` | 7 | NOT READY | all three, from nothing but logged questions |
| `no-data` | 20 | NOT READY | examples to measure on |
| `agent-and-logs` | 25 | NOT READY | answers for the questions, then a scorer |
| `fake-ruler` | 25 | NOT READY | a scorer that marks everything correct |
| `no-labels` | 30 | PARTIAL | answers for the questions |
| `duplicated-data` | 35 | PARTIAL | the data -- half of it is the same rows twice |
| `no-eval` | 40 | PARTIAL | a way to score an answer |
| `no-knobs` | 45 | PARTIAL | something for the agent to vary |
| `ready` | 45 | PARTIAL | check the scorer, then proceed |
| `sql-exec-stop` | 45 | PARTIAL | nothing -- but see the note on execution below |
| `no-agent` | 45 | PARTIAL | an agent. **The card says proceed.** |
| `wrong-answers` | 45 | PARTIAL | the pairing. **The card says proceed.** |
| `wrong-wiring` | 45 | PARTIAL | the scorer. **The card says proceed.** |
| `hand-written` | 74 | WORKABLE | more examples than ten |
| `checked` | 86 | STRONG | nothing |
| `best-case` | 91 | EXCELLENT | nothing |

All five bands, and the spread is measured rather than arranged: every combination the CLI
accepts was built and scored, and these seventeen are the ones that describe a project
somebody could actually arrive with.

### Three starting points the opening gate does not separate

A bank of broken projects is worth having because of what it finds, and it found three. These
are observations about the guide at revision `6ec2b9c1`, not defects in this repository, and
they are the reason the three rows above are marked.

**A dataset whose every answer answers a different question is not noticed.** `wrong-answers`
keeps every question and every answer and pairs them wrongly, inside each database, so all of
them still run and still return rows. Every dataset check passes, no cap is raised, and the
card reads 45 and `proceed` -- byte-identical to `ready`. Add probe answers and it gets worse:
**83, STRONG, proceed, no caps**, because the probes check the scorer and nothing checks
whether an answer answers its question. The tool that would catch it exists -- `readiness.py
--row-review` asks exactly that -- and is not part of the opening method.

**A mis-wired scorer is invisible without probe answers.** `wrong-wiring` compares the
question with the recorded answer and never reads the model's output. Built without
calibration it is byte-identical to `ready`: 45, `proceed`. Built with it, the probes come
back all-zero and the card drops to **25, `repair-evaluator`**. Calibration is the entire
difference between shipping that project and repairing it, in either direction -- `fake-ruler`
is the same cap reached from all-ones.

**Duplication is caught by the wrong check.** `duplicated-data` stops at 35 with
`repair-dataset`, which is the right verdict -- but it fires on duplicate row *ids*, not on
the duplicated rows, and the reason printed on the card is "some rows could not be read as
data -- malformed lines". No row is malformed. A duplicated export that renumbered its ids
would pass that check and land at 45, `proceed`, with duplication reduced to two warnings.

One more, from the same table: `no-agent` -- a directory with 300 labelled rows, a scorer, and
no agent file at all -- reads `proceed`, while `no-knobs`, which *has* an agent, reads
`vary-knobs`. Following the guide's own instruction for a missing agent (leave the agent flags
off entirely) means the score never learns the agent is absent.

### The one that argues for checking your scorer

`fake-ruler` is the same project as `ready` -- the same agent, the same 300 labelled rows --
except its scorer returns full marks for everything. Built without probe answers it reads
**45, proceed**: identical to `ready`, because nothing has looked at the scorer. Built with
them it reads **25, repair the evaluator**.

That pair is the argument for calibration in one line. A scorer nobody has checked lets a run
go ahead and report a confident improvement that did not happen. Probe answers turn that into
a named, repairable problem -- and repairing it is what the run then does, before it measures
anything. It is also the only preset where shipping calibration *lowers* the opening score,
which is the right direction when the thing being checked is broken: the number went down
because the project got more honest, not because it got worse.

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
98 and agent 70, EXCELLENT needs an evaluation pillar of about 94, and the text
comparator's calibrated ceiling is 83 -- which is why `checked` measures 86 and `best-case`
measures 91. The figures here are the scorer's own rounded output rather than a derivation,
so read them as the readings they are; re-measure before quoting them anywhere that matters.
If you want a project that
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
with an agent whose settings were made readable without changing what it sends. A high band is
not evidence that anyone checked; that is what the calibration step
is for.

## The data is Spider

The questions and queries are from **Spider 1.0**, the standard cross-domain text-to-SQL
benchmark: human-written questions over databases from many different subject areas, each
paired with the SQL that answers it.

> Yu et al., *Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain
> Semantic Parsing and Text-to-SQL Task*, EMNLP 2018.
> [arXiv:1809.08887](https://arxiv.org/abs/1809.08887) ·
> [yale-lily.github.io/spider](https://yale-lily.github.io/spider)

300 rows drawn from the development split, with the 18 SQLite databases they need -- the
rows and the databases together come to about 1.4 MB, which is why the data is committed
rather than downloaded. Every row was
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

Building a demo needs nothing installed. The five checks below need three tools, and a
recent Linux will refuse to install them into the system Python (PEP 668), so put them in an
environment of their own:

```bash
python3 -m venv .venv-dev
.venv-dev/bin/python -m pip install -r requirements-dev.txt

python3 build.py check
python3 -m unittest discover -s tests -v
.venv-dev/bin/black --check build.py spider tests components
.venv-dev/bin/ruff check build.py spider tests components
.venv-dev/bin/mypy --strict build.py spider/build_slice.py
```

The first two need only the standard library, so they run on any Python 3.11 to 3.13. The
last three are what `requirements-dev.txt` pins.

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
