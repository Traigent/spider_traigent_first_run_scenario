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
python3 build.py demo --preset ready --out ~/demos/first-try
```

and the same command, with different flags, builds the same project with the evaluator
missing, or with unlabelled data, or with an agent that has nothing worth tuning.

## Getting started

**This repository is `PUBLIC`** (checked with `gh repo view` on 2026-09-06:
`"visibility": "PUBLIC"`, `"isPrivate": false`). The clone below works for anyone. The Spider
data it carries is redistributed under CC BY-SA 4.0, with the attribution and the notice of
modification that licence requires -- see [Licence](#licence).

```bash
git clone https://github.com/Traigent/spider_traigent_first_run_scenario.git
cd spider_traigent_first_run_scenario

python3 build.py list                                   # what can be built
python3 build.py check                                  # confirm this clone is intact
mkdir -p ~/demos                                        # build.py will not create it for you
python3 build.py demo --preset ready --out ~/demos/first-try
```

`build.py` refuses an output directory whose **parent** does not exist, and says so
(`error: the parent directory does not exist: ...`, exit 2). It refuses one that already
exists, too, so every `--out` below is a fresh path -- run two of them at the same target and
the second exits 2 rather than writing over the first.

Or build the whole bank at once, each project in its own directory, and check it:

```bash
python3 build.py suite  --out ~/demos/bank
python3 build.py verify --demo ~/demos/bank
```

`verify` is the gate that says a demo is fit to hand to an agent. It checks three things:
that the project is **self-contained**, so the agent reads a project and not the repository
that made it; that it is **blind**, so neither any file nor the demo's own path names the state
it was built in; and that it **works** -- every file matching the record, every question in the
catalog, every database the rows name actually present. It reports problems rather than raising
on them, including when the thing it is reading is itself malformed.

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

### The bank, and why its directories have unreadable names

`suite` does not name a directory after the preset in it. Each one is
`project-<first 8 hex of sha256 of the preset name>` -- `ready` is `project-b24d6d33`,
`wrong-answers` is `project-05a193a3` -- and **`bank.json`, at the bank root, is where the
mapping lives**:

```
~/demos/bank/
├── bank.json           which directory is which   <- NOT for the agent
├── project-05a193a3/
├── project-121b96a4/
└── ...
```

That record sits outside every project for the same reason `demo.json` sits outside
`project/`: it names the state each demo was built in, and an agent that reads it knows the
answer before it starts. Keep it out of the working directory and out of the prompt.

The naming is not decoration. A demo's absolute path is written into anything built inside it
-- `pyvenv.cfg`, `activate`, every console-script shebang -- so a directory called
`wrong-answers` hands the starting state to anything that reads a path, and `--venv ready`
guarantees something will. `suite` prints the mapping to whoever ran it and puts nothing in
the projects.

A single `demo --out ~/demos/wrong-answers` is the operator's own choice of name, and `verify`
now checks that too. It reads the demo's own resolved path against the same roster of tells it
reads file names and file contents against, and it recommends one of two different repairs:

- **no environment in the project** -- `Rename the directory. Nothing inside the demo records
  where it is, so moving it is enough and it does not have to be built again.`
- **an environment in the project** -- `Build it somewhere else. The project's environment has
  this path written into every script in it, so renaming the directory would break the
  environment rather than clean it.`

## What gets built

```
~/demos/first-try/
├── demo.json           how it was built: flags, per-file hashes, the handoff prompt
└── project/            <- point the agent at this
    ├── agent.py        writes SQL. run(question, config) -> query text
    ├── dataset.jsonl   300 questions with the query that answers each
    ├── catalog.json    which database each question is about, and its structure
    ├── databases/      18 SQLite databases
    ├── ATTRIBUTION.txt whose data this is, what was changed, and under what licence
    ├── evaluator.py    marks an answer. score(output, expected, input_data, metadata)
    ├── traigent-runs/  probe answers for the scorer, with --calibration present
    ├── README.md       what a project of this kind would normally document
    └── .env.example
```

`demo.json` stays **outside** `project/` on purpose. It names the state each component was
put in, and an agent that can read that is not being tested on anything.

**A project ships one legal file, and only when it ships rows.** `ATTRIBUTION.txt` travels
with the data because the licence says it has to: CC BY-SA 4.0 requires the attribution and a
notice that the data was modified to accompany the data wherever it goes. `build.py` copies it
in the same branch that writes `dataset.jsonl`, `catalog.json` and `databases/`, so the four
arrive together or not at all -- 15 of the 17 presets get it, and the two that do not are
`empty` and `no-data`, the two with no rows.

It ships alone, and that is a change worth stating. Projects used to carry `NOTICE`, `LICENSE`
and `LICENSE-DATA` as well. All three name this repository, and `NOTICE` described the
directory it was in as a generated demo -- so every project, in every one of the seventeen
states, arrived telling the agent what it was looking at. `ATTRIBUTION.txt` carries the same
obligations and names nothing: the original work, the licence and its URI, the kinds of
modification made, and how not to misreport a score measured on a modified subset. It never
mentions the generator, the preset, or the state anything was put in, which is why `verify`
passes over it and why [docs/isolation.md](docs/isolation.md) can now say what it says.

## Choosing what the project starts with

| Flag | Values |
|---|---|
| `--agent` | `ready` · `no-knobs` · `missing` |
| `--dataset` | `ready` (300) · `mini` (30) · `tiny` (10) · `unlabeled` (40) · `duplicated` (90, from a 60-row draw) · `wrong-answers` (60) · `missing` |
| `--eval` | `exact-match` · `exec-match` · `broken` · `swapped` · `missing` |
| `--provider` | `openrouter` (default) · `direct` |
| `--calibration` | `none` · `present` (probe answers for the scorer) |
| `--guide` | `clone` (default) · `local` (with `--guide-src`) |
| `--venv` | `none` (default) · `ready` (a working environment on the newest supported Python) |

Presets are shorthand for the combinations worth having a name:

| Preset | The project it builds |
|---|---|
| `ready` | everything present and tunable, scorer not yet checked |
| `checked` | the same, and the team keeps probe answers for its scorer |
| `best-case` | the same, scored by execution accuracy -- the metric Spider itself uses |
| `sql-exec-stop` | an evaluator that runs the SQL the model wrote -- Spider's own metric |
| `hand-written` | ten examples, and probes kept for the scorer |
| `no-knobs` | an agent with nothing to search |
| `no-eval` | an agent and data, and no way to score an answer |
| `no-agent` | data and a scorer, and nothing to run them against |
| `no-data` | an agent and a scorer, and nothing to measure them on |
| `no-labels` | questions with no expected answers |
| `agent-and-logs` | an agent, and logged questions with no answers and no scorer |
| `logs-only` | nothing but logged questions -- all three pieces have to be built |
| `empty` | nothing to work with yet -- no agent, no data, no scorer |
| `fake-ruler` | a scorer that marks everything correct, and probes that catch it |
| `wrong-wiring` | a scorer comparing the question with the answer, never the output |
| `duplicated-data` | half the rows appear twice, question and answer both |
| `wrong-answers` | every answer runs, and answers a different question |

Individual flags override a preset, so `--preset ready --eval missing` is the ready project
with the evaluator taken out.

One thing the name gets wrong, which is why `build.py list` describes it as "nothing to work
with yet -- no agent, no data, no scorer": **`empty` is not an empty directory.** `project/`
holds two files -- `.env.example` and `README.md` -- and nothing else: no agent, no rows, no
databases, no scorer, and no `ATTRIBUTION.txt`, because there is no data for it to travel with.
Those two are what every project gets unconditionally. It scores 0.

## A project that has been worked in

By default a demo ships no environment. The guide builds its own `.venv-traigent` and never
reuses a project's, so nothing is lost -- and a demo must never carry one already, because
the guide stops if that path exists.

`--venv ready` gives the project **a working environment of its own** instead: `.venv`, on
the newest supported Python, with the agent's dependency installed. It is the difference
between a directory of files and a project somebody has been working in -- the agent imports
and runs from it before the guide builds anything.

```bash
python3 build.py demo --preset ready --venv ready --out ~/demos/worked-in
~/demos/worked-in/project/.venv/bin/python -c "import litellm; print('ready')"
```

**It costs about 220 MB per project, and about 20 seconds.** Measured twice on this machine,
on Python 3.13.14: `du -sm` reports 220 MiB and the files themselves are 193 MB, almost all of
it `litellm` and what it pulls in. So a seventeen-preset bank with environments is about
**3.7 GB**, not the 1.7 GB an earlier "hundred megabytes per project" implied -- worth knowing
before running `suite --venv ready` on a machine with a few gigabytes free. That is why it is
off by default and why `suite` takes the same flag rather than assuming it.

Note the separate `--out` above. `~/demos/first-try` already holds the demo from
[Getting started](#getting-started), and `build.py` refuses to write over an existing
directory -- so reusing that path here exits 2 rather than rebuilding.

An environment also fixes the demo where it is. `build.py` strips `pyvenv.cfg` down to the
keys an environment actually needs -- `home`, `include-system-site-packages`, `version` --
because `command` and `executable` record the absolute path the environment was created at,
and in a bank that was one directory per starting state that path *was* the starting state.
What it cannot strip is the same path in every console-script shebang and in `activate`'s
`VIRTUAL_ENV`. Rewriting those breaks the environment, which is why `verify` tells a demo with
an environment to be rebuilt elsewhere rather than renamed.

An earlier version of this created an *empty* environment as scenery. Measured, all of its
settings produced byte-identical preflight and readiness output, because the guide never
reads a project's environment -- so it was removed. This one earns its place by making the
project runnable, not by being present.

## Data that is wrong on purpose

**Four** of the seventeen presets ship a project whose data or scorer is broken. Real projects
arrive that way, and the run's job is not to notice and stop -- it is to notice, repair, and
carry on to a result that means something. These are the states that make it show its work.

| | rows | what is wrong |
|---|---|---|
| `duplicated-data` | 90 | half the rows appear twice -- the same question and the same answer -- which is what appending an export to itself looks like. A score over it counts the same evidence more than once. |
| `wrong-answers` | 60 | every question keeps a real answer, and it is a different question's answer. The rotation happens inside each database, so every answer still runs and still returns rows. That is the hard version: an answer borrowed from another database would not execute and would announce itself. |
| `wrong-wiring` | 300 | the scorer compares the question with the recorded answer and never looks at what the model produced. It runs, it returns a number, and every row ties at zero. |
| `fake-ruler` | 300 | the scorer returns full marks for everything, so every configuration measures the same and a comparison between them separates nothing. |

**The two damaged datasets are smaller than the rest, and that shows on the card.** Both are cut
to a 60-row draw -- `duplicated-data` then ships 90, because 30 of the 60 appear twice. So a
`wrong-answers` card reads `60/60 rows` where a `ready` card reads `300/300`, and its
comparison-size check drops from `OK` to `!!`. That difference is about draw size and not about
the damage; see [the three the opening gate does not
separate](#three-starting-points-the-opening-gate-does-not-separate).

**Every answer answers a different question, and that is now checked rather than asserted.**
Measured on the current build: **0 of 60** rows keep the answer they came with -- 0 in each of
the four difficulty bands, 15 rows apiece. The draw is constructed to make that reachable:
`build.py` takes whole database groups of at least two rows with *distinct* gold queries, so a
one-row group (whose rotation is the identity) and a rotation onto a byte-identical query
cannot arise, and it raises rather than shipping if either does. All 60 answers are real Spider
gold queries and all 60 come from the row's own database. An earlier draw got this wrong in
five rows of sixty while the project claimed all of them had moved.

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
semicolon. Case *inside* a quoted value is kept, because `'France'` and `'france'` are
different values. A double-quoted token is read both ways -- as a value and as a column name --
and either agreement scores 1.0, so `SELECT "name"` matches `SELECT name` while `= "France"`
still rejects `= 'france'`. It never runs anything, and it refuses a query whose quote,
delimited name or block comment never closes rather than healing it into something that
matches. Its limit is real: `SELECT a, b` and `SELECT b, a` return the same thing and it
marks the second one wrong, so it under-counts correct answers.

**`exec-match`** runs both queries against the database and compares the rows they return.
This is Spider's own metric -- execution accuracy -- and it is the faithful way to mark a SQL
answer, because it credits a correct query written differently from the recorded one. It
reaches that by executing SQL the model wrote, inside a read-only connection with a function
allow-list, a five-second watchdog, and caps on rows, bytes, value size and column count.

The first-run guide's `references/run-safety.md` currently declines to execute a scorer that
does so, ending the run before the evaluator executes -- and its opening gate will not open
calibration on one either. So the presets ask different questions: `checked` asks whether a
first run works end to end on a non-executing proxy; `sql-exec-stop` asks about the one thing
in this bank that is a boundary rather than a gap, because an executing scorer is not something
the run repairs and moves past, it is where this guide hands over; and `best-case` asks the
same question with the probe answers already in the project, which turns out to change nothing
at the opening because the gate will not run them.
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
`--agent-knobs`. Every figure below was produced with that document, and
[`docs/measurements/agent-knobs/`](docs/measurements/agent-knobs/) ships it.

Two caveats worth stating rather than burying. The agent read used here was written by hand to
stand in for the one an assistant writes; it cites real values on the real call path, so the
figures are faithful, but another honest read could move them a few points. And a real run
scores twice -- once at the opening and again after it has created or repaired anything -- so
the number a finished run reports is not the one in this table, and should not be.

**Measured with the guide's own `preflight.py`, `calibrate_evaluator.py` and `readiness.py`, at
guide revision `6ec2b9c161400cd91faea9c8cdb1c4e00d21c8d9` (`6ec2b9c1`), on 2026-09-02.**
Rebuild the whole table with one command:

```bash
python3 docs/measurements/score_bank.py --guide ~/code/traigent-first-run
```

Every invocation and every captured output is committed under
[`docs/measurements/`](docs/measurements/README.md), one directory per run, including the
rendered card each number is read off. Nothing below has to be taken on trust or reconstructed
by hand.

| preset | opening | band | card says | what the run has to build or fix |
|---|---|---|---|---|
| `empty` | 0 | NOT READY | `get-data` | all three: an agent, examples, and a way to score them |
| `logs-only` | 7 | NOT READY | `label-data` | all three, from nothing but logged questions |
| `no-data` | 20 | NOT READY | `get-data` | examples to measure on |
| `agent-and-logs` | 25 | NOT READY | `label-data` | answers for the questions, then a scorer |
| `fake-ruler` | 25 | NOT READY | `repair-evaluator` | a scorer that marks everything correct |
| `no-labels` | 30 | PARTIAL | `label-data` | answers for the questions |
| `duplicated-data` | 35 | PARTIAL | `repair-dataset` | the data -- half of it is the same rows twice |
| `no-eval` | 40 | PARTIAL | `connect-evaluator` | a way to score an answer |
| `no-knobs` | 45 | PARTIAL | `vary-knobs` | something for the agent to vary |
| `ready` | 45 | PARTIAL | `proceed` | check the scorer, then proceed |
| `sql-exec-stop` | 45 | PARTIAL | `proceed` | nothing -- but see the note on execution below |
| `best-case` | 45 | PARTIAL | `proceed` | the same, and its card is byte-identical to `sql-exec-stop`'s |
| `no-agent` | 45 | PARTIAL | `proceed` | an agent. **The card says proceed.** |
| `wrong-answers` | 45 | PARTIAL | `proceed` | the pairing. **The card says proceed.** |
| `wrong-wiring` | 45 | PARTIAL | `proceed` | the scorer. **The card says proceed.** |
| `hand-written` | 74 | WORKABLE | `add-examples` | more examples than ten |
| `checked` | 86 | STRONG | `proceed` | nothing |

**Four of the five bands, not five, and the missing one is the top.** The spread is measured
rather than arranged -- every combination the CLI accepts was built and scored, and these
seventeen are the ones that describe a project somebody could actually arrive with -- and on
the guide's own method no configuration in this bank opens EXCELLENT. `checked` at 86 is the
highest, four points below the 90 boundary. An earlier version of this table read
`best-case | 91 | EXCELLENT` and reached that number by scoring one preset a way the guide
forbids for it; [the section on `best-case`](#what-best-case-really-opens-at) has the whole of
it. A band missing and said so beats a band present and obtained off-method.

There are exactly two ways across that boundary and the guide bars both at the opening:
calibrating a scorer that executes model-written SQL, and declaring a trial budget. Each was
measured rather than assumed --
[`best-case`](#what-best-case-really-opens-at) and
[the trial-budget question](#what-the-source-reader-sees-and-what-the-agent-actually-has).

The band boundaries, for reading the column: NOT READY 0-29, PARTIAL 30-54, WORKABLE 55-74,
STRONG 75-89, EXCELLENT 90-100.

### Three starting points the opening gate does not separate

A bank of broken projects is worth having because of what it finds, and it found three. These
are observations about the guide at revision `6ec2b9c1` on 2026-09-02, not defects in this
repository, and they are the reason the three rows above are marked. Each one is a `diff` over
two committed cards.

**A dataset whose every answer answers a different question is not noticed.** `wrong-answers`
keeps every question and every answer and pairs them wrongly, inside each database, so all of
them still run and still return rows. Every dataset check passes, no cap is raised, and the
card reads 45 and `proceed`. Add probe answers and it gets worse: **83, STRONG, proceed, no
caps**, because the probes check the scorer and nothing checks whether an answer answers its
question. The tool that would catch it exists -- `readiness.py --row-review` asks exactly that
-- and this table does not pass it, for the reason
[docs/measurements](docs/measurements/README.md) gives.

Its card is *nearly* identical to `ready`'s, and the three places it is not are worth being
precise about, because they are about draw size and not about the damage:

| | `ready` | `wrong-answers` |
|---|---|---|
| dataset pillar | 98/100 | **91/100** |
| answers to score against | `OK 300/300 rows carry an expected output` | `OK 60/60 rows carry an expected output` |
| examples to compare on | `OK 240 to tune on / 60 held back` | `!! 48 to tune on / 12 held back -- limited comparison set` |

Everything else -- every dataset check, the recommended action, the single `evaluator-
unvalidated` cap -- is the same text. A `wrong-answers` demo ships a 60-row draw because
`DAMAGED_ROWS = 60`, so the card is comparing a 60-row project with a 300-row one. Nothing on
it is about the pairing.

**A mis-wired scorer is invisible without probe answers.** `wrong-wiring` compares the
question with the recorded answer and never reads the model's output. It ships all 300 rows,
so there is no size difference to hide behind, and its card is **byte-identical to `ready`'s**:
45, `proceed`, same pillars, same cap, same text. Built with calibration the probes come back
all-zero and the card drops to **25, `repair-evaluator`**. Calibration is the entire difference
between shipping that project and repairing it, in either direction -- `fake-ruler` is the same
cap reached from all-ones.

**Duplication is caught by the wrong check.** `duplicated-data` stops at 35 with
`repair-dataset`, which is the right verdict -- reached for a reason that is not true of that
build. The card prints, in full:

> **FIX BEFORE PAID RUN** Some rows could not be read as data - malformed lines, or missing the
> input or expected-answer field.

No line is malformed and no field is missing. Two lines above, the same card says
`OK answers to score against  90/90 rows carry an expected output`. What actually fires is
preflight's `dataset-ids` check on duplicate row **ids**; the duplicated *rows* raise only two
warnings, `dataset-duplicates` and `dataset-near-duplicates`. Measured: rewrite the 30 repeated
ids to be unique and leave every duplicated row exactly where it is, and the same project
scores **45, PARTIAL, `proceed`**, with the duplication reduced to those two warnings. A
duplicated export that renumbered its ids on the way out clears the gate.

One more, from the same table: `no-agent` -- a directory with 300 labelled rows, a scorer, and
no agent file at all -- reads `proceed`, while `no-knobs`, which *has* an agent, reads
`vary-knobs`. Following the guide's own instruction for a missing agent (leave the agent flags
off entirely) means the score never learns the agent is absent. Both cards raise
`agent-no-varying-knobs` at ceiling 45; only `no-knobs`'s blocks.

**And one about the tool rather than about a project.** Scoring `ready` without `--agent-knobs`
does not report "something lower": it reports **45 either way**, because the
`evaluator-unvalidated` ceiling binds first and 45 is where both land. What changes is the
agent pillar, 70 to 0, and a second cap appearing on the card. The card then says "no reading
of how the agent is built reached this score" against all five agent checks -- which is the
tool naming what it was not given, not a second opinion about the project.

### What the source reader sees, and what the agent actually has

Same register as the finding above: an observation about the guide at revision `6ec2b9c1` on
2026-09-02, not a property of this repository, and not something a reader should expect to stay
true.

The tunable agent has **four** settings that change what is sent. Instrumented -- with the
model call stubbed, so nothing leaves the process -- the full cross product of
`model` x `schema_context` x `prompt_style` x `temperature` is **36 distinct requests out of
36**. Every knob is load-bearing: three models, six distinct prompt texts, two temperatures.

The guide's static source reader credits **three of the four** and reports "your space has 18
distinct configurations". `temperature` is the one it declines, with:

> temperature: the cited executable source shows the declared options, but this deliberately
> narrow static read could not verify that changing this setting changes the request on the
> selected agent path

which is a fair statement of what a narrow static read can establish, and an awkward one to
read beside `agent.py:66`, which is literally `TEMPERATURES = (0.0, 0.7)`, checked at
`agent.py:395` and passed to the call at `agent.py:404`.

**It costs nothing measurable.** Declaring the space to `readiness.py --config-space` at 18 and
at 36, at every trial budget from 1 to 50, gives the identical overall score, band and agent
pillar at every point. What moves the number is the trial budget: undeclared holds the agent
pillar at 70, 1 trial drops it to 0, 2 to 3 trials reach 35, 4 to 11 reach 70, and **12** --
the guide's "complete search" threshold -- reaches 100. Same for both spaces. Size of space:
irrelevant. Twelve trials: the whole of it.

**And no, that is not a way to reach EXCELLENT at the opening.** It looks like one: agent 100
with `checked`'s dataset 98 and evaluation 83 is `0.40x98 + 0.35x83 + 0.25x100 = 93.25`, which
is inside the band. But a trial budget can only enter `readiness.py` through a
`--config-space` document -- there is no flag, and the `--agent-knobs` document refuses the key
by name, exit 2, `carries unknown field(s) max_trials` -- and the opening gate withholds that
document. `SKILL.md:988-989`, stated as a property of the score rather than as advice:

> The opening and stage-4 scores **withhold every config-space document by construction**, so
> this is the run's only measurement of the space the customer paid to search.

The only config-space document the guide will read is one the run itself writes, "only after
this search returns nonzero trials, from the exact space it received" (`SKILL.md:894-895`) --
so the budget cannot exist as current-run evidence until money has already been spent, and the
score it feeds is one the guide says to "never show ... beside the opening one"
(`SKILL.md:993`). 93 is a closing number.

The refusal, the single entry point and the governing quotes are all above, in full. What is
*not* published here is a card for that check: `docs/measurements/cards/` holds the score bank,
and the bank scores projects rather than the guide's handling of a config-space document. So a
reader checks this the way it is written -- the quoted text against the guide at `6ec2b9c1`,
and `readiness.py --agent-knobs` against a document carrying `max_trials` -- and not against a
measurement of ours.

So nothing here is written to win the fourth credit. The obvious way to do it -- an identity
mapping that reads `temperature` back out of a table so the reader can follow it -- was
considered and rejected: it is worse code, it changes nothing the agent sends, and writing code
to move somebody else's static analyser is how a demonstration stops demonstrating anything.
The agent has four knobs, the guide sees three, and both facts are written down.

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

### What `best-case` really opens at

**45, PARTIAL, `proceed`** -- and its card is byte-identical to `sql-exec-stop`'s.

That is not what this section used to say, and the correction matters more than the number.
`best-case` is `checked` with the execution scorer: the same agent, the same 300 rows, marked
the way Spider marks them. It ships probe answers. So why does calibration not run?

Because the guide's opening gate says it may not. Calibration is opened only "if the verdict is
`sufficient` **and the complete path does not execute candidate-generated code or SQL**, is
local-only, side-effect-free, standard-library-only, and expected to return in seconds".
`best-case`'s scorer runs the SQL the model wrote. The condition is not met, so the opening
score is taken without calibration, the `evaluator-unvalidated` ceiling stands at 45, and the
card that comes out is the same one `sql-exec-stop` gets -- which is right, because at the
opening gate the two projects differ only in a file the gate is not allowed to run.

**The 91 EXCELLENT this table used to publish was reached by running that calibration anyway.**
It is a real number and it reproduces --
[`docs/measurements/cards/best-case--off-method-calibration/`](docs/measurements/cards/) has
the invocation and the card, evaluation pillar 99, no caps -- but the step that produces it is
the one step the guide bars for this project. Scoring one preset off-method to fill in a band
is the kind of thing a table does when it wants to look complete, so it is labelled here rather
than quietly relabelled.

**So EXCELLENT is not reachable on-method in this bank, and the shortfall is four points.**
`checked` at 86 is the ceiling. The arithmetic is closed: at dataset 98 and agent 70 the
overall is `56.7 + 0.35 x evaluation`, EXCELLENT starts at 90, so it needs an evaluation pillar
of **94**. Calibrated, the text comparator's is **83** and the execution scorer's is **99**.
There is nothing between them, which is why the top band on Spider data belongs to the scorer
the guide is told to stop.

The five points between 86 and 91 are still the real finding, and they are not a penalty or a
concession: the score is correctly reporting that one project measures its answers the way the
benchmark does and the other approximates it. Task fit is **8/25** for `normalized-exact` on
`code-sql` against **25/25** for `execution`, and 17 points of task fit come out as 16 points
of evaluation pillar and 5 of overall. What changed is only which of those two numbers this
repository is entitled to print as an *opening* score.

**And the boundary is a boundary, not a gap to close.** The guide's `references/run-safety.md`
declines to execute a scorer that runs model-written SQL, and `--preset sql-exec-stop` and
`--preset best-case` both fall under it -- so the Spider-faithful configuration is one the
guide will not run today, and this repository does not work around that. It is recorded as a
finding in [docs/eval-methods.md](docs/eval-methods.md).

### One thing that would not be truthful

Declaring the evaluator method as `exact` with task kind `structured` makes the *text*
comparator read **92, EXCELLENT, no caps**, with the evaluator file completely unchanged.
Nothing checks a declaration against the source, so that is the highest number anything in this
repository can be made to produce -- higher than the on-method ceiling of 86, and higher than
the 91 the execution scorer reaches.

It takes **both** halves of the lie, and that is the part worth knowing. All four combinations,
on the same unchanged, purely textual comparator:

| declared `--evaluator-method` | declared `--task-kind` | score |
|---|---|---|
| `normalized-exact` | `code-sql` | 86 STRONG |
| `exact` | `code-sql` | 86 STRONG |
| `normalized-exact` | `structured` | 86 STRONG |
| `exact` | `structured` | **92 EXCELLENT, no caps** |

Neither field alone does anything. Only the matched pair pays -- which is exactly the shape
someone optimising for the number would arrive at, and exactly the shape a spot-check of either
field on its own would miss.

This repository does not do that, and no number in the table above depends on it. Every band
here comes from an evaluator declared as what it is, on probe answers built from real rows,
with an agent whose settings were made readable without changing what it sends. A high band is
not evidence that anyone checked; that is what the calibration step is for.

## The data is Spider

The questions and queries are from **Spider 1.0**, the standard cross-domain text-to-SQL
benchmark: human-written questions over databases from many different subject areas, each
paired with the SQL that answers it.

> Yu et al., *Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain
> Semantic Parsing and Text-to-SQL Task*, EMNLP 2018.
> [arXiv:1809.08887](https://arxiv.org/abs/1809.08887) ·
> [yale-lily.github.io/spider](https://yale-lily.github.io/spider)

300 rows drawn from the development split, with the 18 SQLite databases they need -- 459,193
bytes of rows and 917,504 bytes of databases, about 1.4 MB together, which is why the data is
committed rather than downloaded. Every row was checked: each recorded query runs, and returns
rows. Difficulty comes from Spider's own official hardness classifier, run over each row's gold
query rather than joined in from a table, and the 300 are balanced 75 apiece across its four
bands. The slice hashes to
`f7fa90e46cccf171366b0e54789a286058cd8da0b4fbb9362741f9664c975827`, recorded independently in
`spider/datasheet.yaml` and `spider/provenance.json`.

**The data is licensed CC BY-SA 4.0, not Apache-2.0 like the code**, and ShareAlike applies
to an adaptation of it that you share. `spider/LICENSE-DATA` carries the attribution, the
record of changes and the complete text of the licence. Generated projects carry the same
attribution and modification notice in their own `ATTRIBUTION.txt`.

Two things to know before reading anything into a score: Spider is old enough and public
enough that current models have very likely seen it, and 300 rows is a demonstration size --
enough to tell configurations apart, not enough to settle a question about production. And one
more, concrete rather than abstract: **127 of the 300 gold queries (42.3%) return a single
scalar**, so a wrong query that returns the right count scores the same as a right one under
execution marking. That is not a constant-answer hole -- the best single constant scores 7 of
300 (2.3%) -- it is a shape worth knowing about before quoting an execution number.
[docs/dataset.md](docs/dataset.md) has the full picture, including the nine known flaws the
datasheet records.

## Documentation

| | |
|---|---|
| [docs/dataset.md](docs/dataset.md) | what the data is, how the 300 were chosen, what it cannot support |
| [docs/isolation.md](docs/isolation.md) | how a demo is kept separate, and what to do to keep a run honest |
| [docs/eval-methods.md](docs/eval-methods.md) | the two SQL scorers, and the scoring problem behind them |
| [docs/measurements/](docs/measurements/README.md) | every readiness figure quoted here: the script, the agent read, and each run's captured invocation and output |

## Working on this repository

Building a demo needs nothing installed. The five checks below need three tools, and a
recent Linux will refuse to install them into the system Python (PEP 668), so put them in an
environment of their own:

```bash
python3 -m venv .venv-dev
.venv-dev/bin/python -m pip install -r requirements-dev.txt

.venv-dev/bin/black --check build.py spider tests components
.venv-dev/bin/ruff check build.py spider tests components
.venv-dev/bin/mypy --strict build.py spider/build_slice.py
.venv-dev/bin/mypy --check-untyped-defs --ignore-missing-imports \
    --explicit-package-bases --disable-error-code=var-annotated components
python3 build.py check
python3 -m unittest discover -s tests -v
```

The order is CI's, and it is the useful one: the static checks read the same files and finish
in seconds, so a formatting, lint or typing error surfaces before the slow step rather than
behind a test failure.

`check` and the tests need only the standard library, so they run on any Python 3.11 to 3.13 --
and CI runs the whole list on **all three**, because that is the range `build.py` says it
supports. The four checkers are what `requirements-dev.txt` pins. `components/` gets the
looser mypy stance rather than `--strict` on purpose: those files ship to customers as
something they open and edit, and `--strict` there would mean annotating the very files a
customer is meant to read.

`check` validates the components and the committed data. The tests re-run all 300 recorded
queries, so they take a moment; that is the point of them.
[`.github/workflows/ci.yml`](.github/workflows/ci.yml) is authoritative for exactly what runs
-- skipping any of it here is what turns a pull request red there.

The score table is not in that list, because it needs a checkout of somebody else's repository
-- but no network, and no install. Re-measure it separately whenever the guide moves:

```bash
python3 docs/measurements/score_bank.py --guide ~/code/traigent-first-run
```

To rebuild the data slice itself -- rarely needed, and it requires the source Spider pool:

```bash
python3 spider/build_slice.py --source <spider-benchmark-dir>
```

`--hardness <hardness.jsonl>` is still accepted, but it is no longer where the labels come
from: difficulty is derived by running the vendored official Spider classifier over each gold
query, and passing a table makes it a cross-check that stops the build on any disagreement.

## Licence

Code is Apache-2.0 (`LICENSE`). Data is CC BY-SA 4.0 (`spider/LICENSE-DATA`). See `NOTICE`,
which scopes the two by **content** rather than by directory -- Spider questions and gold
queries are quoted verbatim in files well outside `spider/`, including the calibration cases
under `components/calibration/` and this documentation. Machine-readable markings for
everything under `spider/` are in `spider/REUSE.toml`.

Generated projects carry `project/ATTRIBUTION.txt` beside the rows, which is the same
obligation in the form that travels: attribution, the licence and its URI, and a notice that
the data was modified.

**The repository is `PUBLIC`, so the ShareAlike obligation has attached, and it is met.** The
300 rows and the 18 databases are an adaptation of CC BY-SA 4.0 material, shared with everyone,
and the licence asks three things of that: credit the original, let the licence travel with the
data, and state what was changed. `spider/LICENSE-DATA` carries all three; `spider/REUSE.toml`
marks the files that cannot carry a comment; `NOTICE` names which bytes are under which licence.
The code's Apache-2.0 licence places no additional terms on the data. Spider itself is
distributed under the same licence at the project URI above, so holding this slice in public
carries no obligation the original did not already carry.

This repository does not include or license the Traigent SDK.
