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

That is the same prompt a customer is given -- the guide's README, "Start with one prompt", at
`d07b62cd`. For four days in September it was three lines that also said where to clone, beside
the project and not inside it; guide #550 put it back to two, because that is the assistant's
rule (it lives in `GUIDE.md`) and not something a customer should have to know or say.
`build.py` prints it when it finishes, and records it in `demo.json`.

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
arrive together or not at all -- 29 of the 31 presets get it, and the two that do not are
`empty` and `no-data`, the two with no rows.

It ships alone, and that is a change worth stating. Projects used to carry `NOTICE`, `LICENSE`
and `LICENSE-DATA` as well. All three name this repository, and `NOTICE` described the
directory it was in as a generated demo -- so every project, in every one of the seventeen
states there were then, arrived telling the agent what it was looking at. `ATTRIBUTION.txt` carries the same
obligations and names nothing: the original work, the licence and its URI, the kinds of
modification made, and how not to misreport a score measured on a modified subset. It never
mentions the generator, the preset, or the state anything was put in, which is why `verify`
passes over it and why [docs/isolation.md](docs/isolation.md) can now say what it says.

## Choosing what the project starts with

| Flag | Values |
|---|---|
| `--agent` | `ready` · `no-knobs` · `two-agents` (the tunable agent, and an unrelated second one in `sql_explainer/` with a `PROJECT.md` saying which to work on) · `missing` |
| `--dataset` | `ready` (300) · `mini` (30) · `tiny` (10) · `unlabeled` (40) · `duplicated` (90, from a 60-row draw) · `wrong-answers` (60) · `leaky` (306: the 300, and six tuning rows again as held-out rows) · `holdout-labelled` (30, answers on the six held-out rows only) · `split-by-database` (300, five whole databases held out) · `raw-export` (300, under Spider's own `question`/`query` keys) · `torn` (30, two lines cut short) · `undeclared` (300, every row's provenance reads `spider-dev`) · `mostly-undeclared` (300, 180 of them do) · `mostly-synthetic` (300, 180 rows declare `synthetic` and 120 declare `real`) · `generated-answers` (300, every row declares its answer model-written) · `mostly-generated-answers` (300, 180 of them do) · `missing` |
| `--eval` | `exact-match` · `exec-match` · `broken` · `swapped` · `opaque` (calls a grading library the project does not carry) · `length-blind` (compares the two queries' lengths) · `slow` (compares text the ordinary way and asks a service per row, so checking it outlasts the budget) · `missing` |
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
| `leaky-split` | six tuning rows appear a second time as held-out rows |
| `holdout-only` | answers on the held-out rows only; nothing to tune on |
| `split-by-database` | the held-out rows are whole databases the tuning side never sees |
| `raw-export` | the rows under Spider's own key names, as the benchmark exports them |
| `torn-lines` | two lines of the data cut short, the way a stopped export leaves them |
| `undeclared-source` | every row says where it came from in a word the guide does not know |
| `mostly-undeclared-source` | most rows do, and the rest still say they were collected |
| `mostly-synthetic-source` | most rows declare themselves written rather than collected |
| `generated-answer-key` | every answer is declared model-written; the questions are real |
| `mostly-generated-answer-key` | most answers are, and the rest were written by a person |
| `slow-scorer` | the scorer is right and asks a service per row, so checking it runs long |
| `opaque-scorer` | a scorer that calls a grading library the project does not carry |
| `length-blind` | a scorer that compares the lengths of the two queries, and probes that catch it |
| `two-agents` | a second agent beside the first, and a note saying which one to work on |

Individual flags override a preset, so `--preset ready --eval missing` is the ready project
with the evaluator taken out.

One thing the name gets wrong, which is why `build.py list` describes it as "nothing to work
with yet -- no agent, no data, no scorer": **`empty` is not an empty directory.** `project/`
holds two files -- `.env.example` and `README.md` -- and nothing else: no agent, no rows, no
databases, no scorer, and no `ATTRIBUTION.txt`, because there is no data for it to travel with.
Those two are what every project gets unconditionally. It scores 0.

## A project that has been worked in

By default a demo ships no environment. What the guide does about that changed on 2026-09-14
(traigent-first-run #545): it looks for a virtual environment inside the project and offers to
install the SDK into it, after showing what the install would add or change; with none usable
it offers to create a persistent project `.venv`; the throwaway `.venv-traigent` is only the
fallback, taken when the customer declines or `.venv` is occupied. A demo still must never
carry `.venv-traigent`: on the fallback route the guide stops when that path already exists
without a verified setup of its own, and a shipped one would read as exactly that.

`--venv ready` gives the project **a working environment of its own** instead: `.venv`, on
the newest supported Python, with the agent's dependency installed. It is the difference
between a directory of files and a project somebody has been working in -- the agent imports
and runs from it before the guide builds anything. It also changes which route the guide
takes: a `.venv` under the project root is the one candidate the guide finds, so the run
proposes installing the SDK into it and shows the resolved plan for approval, where a demo
without one is offered a fresh `.venv` to keep.

```bash
python3 build.py demo --preset ready --venv ready --out ~/demos/worked-in
~/demos/worked-in/project/.venv/bin/python -c "import litellm; print('ready')"
```

**It costs about 220 MB per project, and about 20 seconds.** Measured twice on this machine,
on Python 3.13.14: `du -sm` reports 220 MiB and the files themselves are 193 MB, almost all of
it `litellm` and what it pulls in. So a thirty-one-preset bank with environments is about
**6.8 GB** (it was 5.7 GB at twenty-six and 3.7 GB at seventeen), not the 1.7 GB an earlier "hundred megabytes per
project" implied -- worth knowing before running `suite --venv ready` on a machine with a
few gigabytes free. That is why it is
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

An earlier version of this created an *empty* environment as scenery. Measured at `6ec2b9c1`,
all of its settings produced byte-identical preflight and readiness output, because the guide
then never read a project's environment -- so it was removed. The guide reads environments now,
which is why an environment worth having has to be a working one: this one earns its place by
making the project runnable and by being the environment the guide proposes to install into,
not by being present.

## Data that is wrong on purpose

**Sixteen** of the thirty-one presets sit in this table. Fifteen ship a project whose data or
scorer is broken, or shaped in a way the tools do not expect; the sixteenth, `split-by-database`,
is not wrong at all -- its data is split the way a customer splits it, and it is kept here as the
control for the family check. Real projects arrive that way, and the run's job is
not to notice and stop -- it is to notice, repair, and carry on to a result that means
something. These are the states that make it show its work.

| | rows | what is wrong |
|---|---|---|
| `duplicated-data` | 90 | half the rows appear twice -- the same question and the same answer -- which is what appending an export to itself looks like. A score over it counts the same evidence more than once. |
| `wrong-answers` | 60 | every question keeps a real answer, and it is a different question's answer. The rotation happens inside each database, so every answer still runs and still returns rows. That is the hard version: an answer borrowed from another database would not execute and would announce itself. |
| `leaky-split` | 306 | the 300, and six tuning rows emitted a second time under `split: holdout` -- the same question and answer on both sides of the line, which is what a holdout drawn from the file already being tuned on looks like. Each copy carries its own id (`<id>-holdout`), on purpose: a copy that kept the id is the `duplicated-data` defect, and the guide reports that one first and holds the score under it, so the leak would never be measured on its own. |
| `holdout-only` | 30 | the `mini` draw with the answer kept on the six held-out rows and removed from the 24 tuning rows -- a team that wrote out what it meant to grade on and never what it meant to tune on. |
| `split-by-database` | 300 | the split re-drawn so that the held-out side is five whole databases (61 rows) and the tuning side the other thirteen. Not broken: a split a customer actually makes, kept here to see whether the guide's family check reads it. It does not -- see below. |
| `raw-export` | 300 | the rows written under Spider's own names -- `question`, `query`, a top-level `db_id`, `metadata` as before -- which is what somebody who has the benchmark export as-is brings. `catalog.json` still keys on the question text. |
| `torn-lines` | 30 | the `mini` draw with lines 10 and 20 cut off part-way -- what an export that stopped mid-write leaves. `demo.json` records which two, and `verify` checks that exactly those two fail to parse and every other line reads. |
| `undeclared-source` | 300 | every row's `metadata.provenance` reads `spider-dev` instead of `real`: the name of the benchmark split the rows came from, which is what a person exporting them would write, and a word outside the guide's provenance vocabulary. |
| `mostly-undeclared-source` | 300 | the same word on 180 of the 300 rows, the other 120 still reading `real`. The guide's provenance ladder has a rung at "more than half", so this is not the state above with less of it: it is `dataset-mostly-undeclared` at a ceiling of 70 where every row reads 65. |
| `mostly-synthetic-source` | 300 | 180 rows declare `synthetic` and 120 declare `real`. Declared rather than silent, which is the other axis of the same ladder: the card names `dataset-mostly-synthetic`, and its recommended action is `proceed` rather than a request to declare anything. |
| `generated-answer-key` | 300 | every row adds `metadata.output_provenance: model-generated`. The questions stay real and the provenance stays `real`; what the customer is declaring is that a model wrote the answers they are about to be scored against. |
| `mostly-generated-answer-key` | 300 | the same declaration on 180 of the 300. The answer-key ladder has its own "more than half" rung, and the card names `dataset-mostly-generated-answer-key` with the count in its reason line. |
| `wrong-wiring` | 300 | the scorer compares the question with the recorded answer and never looks at what the model produced. It runs, it returns a number, and every row ties at zero. |
| `fake-ruler` | 300 | the scorer returns full marks for everything, so every configuration measures the same and a comparison between them separates nothing. |
| `opaque-scorer` | 300 | the scorer hands both queries to `sqlgrade`, a grading library the project does not carry (`from sqlgrade.compare import QueryGrader`). It parses; it has never run here; no method can be declared for it, and `--calibration present` is refused for it because nothing could vouch for the probes. |
| `length-blind` | 300 | the scorer returns `1 - abs(len(output) - len(expected)) / len(expected)`, clipped to `[0, 1]`: a number that moves, and never for the right reason. It ships the text comparator's probes, and the wrong answer -- about as long as the right one -- scores between 0.81 and 1.0 across the four cases where calibration needs at most 0.2. |

**Four of these datasets are smaller than the rest, and that shows on the card.** `duplicated-data`
and `wrong-answers` are cut to a 60-row draw -- `duplicated-data` then ships 90, because 30 of the
60 appear twice -- and `holdout-only` and `torn-lines` are the 30-row `mini` draw. So a
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

Every roster is called through **LiteLLM**, and that is not a style choice. An environment
the first-run guide creates -- the project `.venv` it offers to keep, or the throwaway
fallback -- gets `traigent`, `litellm` and `python-dotenv` and no vendor package at all, so an
agent that did `import anthropic` would fail on the machine it is meant to run on. (Since
2026-09-14 the guide can also install into an environment the project already has, which is
the `--venv ready` case; that environment carries `litellm` and nothing vendor-specific
either.) It also means the vendor is a property of the model id rather than of the agent, so
adding one is a roster and a credential name, not a rewrite.

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

What the first-run guide does with a scorer that executes model-written SQL changed between the
revision this bank was first measured at and the one it is measured at now. Its
`references/run-safety.md` still ships no sandbox and will not run such a scorer on its own
initiative, and its opening gate still will not calibrate the customer's original -- but since
2026-09-10 the run continues, on full disclosure: the assistant says what was not checked, that
the boundary is the guide's and not the project's, and what proceeding means (the model writes
the statements and the customer's evaluator runs them against whatever it reaches), and asks
once, at the pre-spend approval, whether the evaluator connects read-only. Since 2026-09-14
there is also a contained route: a *copy* of the evaluator under `traigent-runs/calibration/`,
with its one engine-target argument repointed to a read-only or duplicate target the customer
supplies, can be calibrated by `calibrate_evaluator.py --calibrated-copy-of`. Whether
`exec_match.py` fits that route is not measured here: it opens exactly one
`sqlite3.connect(...)`, which the route accepts, but the target is a per-row path built from
the row's `db_id`, and the probe answers span three databases, so a single repointed target
could not serve them. The calibration tool also now refuses, on its own, to import a scorer
whose walk reaches a SQL engine outside that route -- which this bank's sweep hits, and
records.

So the presets ask different questions: `checked` asks whether a first run works end to end on
a non-executing proxy; `sql-exec-stop` and `best-case` ask what the guide does at the one
boundary in this bank -- a scorer it will not calibrate on the original -- and at `d07b62cd` the
answer is a card that says so and a run that goes on.
[docs/eval-methods.md](docs/eval-methods.md) has the detail, including how the two scorers
are graded, and the two scorers beside them that are not scorers at all -- `opaque`, which
calls a library that is not there, and `length-blind`, which measures length.

## Where each preset starts, and what the run has to do about it

The scores below are **opening** scores. They are not a verdict on the project and they are
not the point of it.

The first-run guide exists to take a project from whatever state it is in to a working first
optimization. Its own words: it "works whether the project already has all, some, or none of"
an agent, a dataset and a way to score answers. When something is missing it creates it; when
something is broken it repairs it; then it scores again, and the run carries on. A low opening
number is not a failure -- it is the size of the gap the run has to close before it can
measure anything, and closing it is the job.

So read the table as thirty-one starting points, and the question each one asks is the same:
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
guide revision `d07b62cd4abb6ecb6d2edcdcb2d535f02bb2c199` (`d07b62cd`), the guide's trunk.**

The table was first measured at `6ec2b9c1` on 2026-09-02 and regenerated at `9eaabbb2` on
2026-09-15, where every project with an agent opened at 45 because the guide's static reader
followed none of the demo agents' settings to the request. That reading lasted a day: guide
#549 taught the reader the three shapes it was refusing -- LiteLLM's module-level request, a
`float()` cast on the local, a mapping handed to a nested helper -- and this is the
regeneration on the trunk that carries it (`e4096e3a`, 2026-09-15), re-taken at `5ce65540` on
2026-09-17 -- and again, unchanged, at the current pin `d07b62cd` -- after guide #551 bounded
the first run to at most 28 rows from any source, #552
pinned SDK 0.27.0, #553 marked the short-dataset top-up recommended, #554 moved the ceiling
from the ask to the approval and the result, #555 named it on the approval card, #556 let the
run copy a local database file for the evaluator check and #557 bounded and verified that copy:
no score, band or action moved (the two execution-evaluator cards changed only in the wording of
their disclosure), and the two cards whose action is `label-data` now read "Review the expected results this
run proposes". What changed on the cards is their shape,
with the `Action` line and the ceilings now printed above the pillars, and the preflight note
that the SDK installed here is 0.26.0 against a walkthrough measured on 0.27.0, which the guide
records and continues past. [The section on the source
reader](#what-the-source-reader-sees-and-what-the-agent-actually-has) has the whole of that
story. The projects are unchanged throughout; what moved is the tool.

Rebuild the table with one command. **It does not overwrite the committed cards**: the run
writes into its own workspace and prints where, and only `--publish` replaces what is under
`docs/measurements/cards/`. The checkout must be sitting on `d07b62cd`, and the run says so if
it is not.

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
| `logs-only` | 7 | NOT READY | `connect-agent` | all three, from nothing but logged questions |
| `no-data` | 20 | NOT READY | `get-data` | examples to measure on |
| `fake-ruler` | 25 | NOT READY | `repair-evaluator` | a scorer that marks everything correct |
| `no-agent` | 25 | NOT READY | `connect-agent` | an agent |
| `agent-and-logs` | 30 | PARTIAL | `label-data` | answers for the questions, then a scorer |
| `no-labels` | 30 | PARTIAL | `label-data` | answers for the questions |
| `duplicated-data` | 35 | PARTIAL | `repair-dataset` | the data -- half of it is the same rows twice |
| `no-eval` | 40 | PARTIAL | `connect-evaluator` | a way to score an answer |
| `no-knobs` | 45 | PARTIAL | `vary-knobs` | something for the agent to vary |
| `ready` | 45 | PARTIAL | `complete-calibration` | check the scorer, then proceed |
| `wrong-answers` | 45 | PARTIAL | `complete-calibration` | the pairing. **The card cannot see it.** |
| `wrong-wiring` | 45 | PARTIAL | `complete-calibration` | the scorer. **Calibration is what finds it.** |
| `hand-written` | 74 | WORKABLE | `add-examples` | more examples than ten |
| `sql-exec-stop` | 85 | WORKABLE | `confirm-evaluator-connection` | nothing the run repairs -- see the note on execution below |
| `best-case` | 85 | WORKABLE | `confirm-evaluator-connection` | the same, and its card is byte-identical to `sql-exec-stop`'s |
| `checked` | 93 | WORKABLE | `review-answer-key` | nothing -- read the answers it is graded on |

The nine ported on 2026-09-18 and the five provenance and cost states added after them,
measured by the same script at the same `d07b62cd` (each
row's card is under `docs/measurements/cards/<preset>/`; the caps column names what the card
raises, `*` for one that blocks):

| preset | opening | band | card says | caps | what the run has to build or fix |
|---|---|---|---|---|---|
| `raw-export` | 25 | NOT READY | `read-dataset` | `dataset-shape-unrecognised` 25\* · `evaluator-unvalidated` 45 | read the file under its own key names. With `--input-field question --expected-field query` declared to preflight, the same project reads 45 `complete-calibration` with no dataset cap -- `ready`'s card |
| `length-blind` | 25 | NOT READY | `repair-evaluator` | `evaluator-invalid` 25\* | the scorer. Calibration ran and failed (evaluation pillar 4); built without probes it reads 40 `repair-evaluator` under `evaluator-unresolved` instead |
| `torn-lines` | 35 | PARTIAL | `repair-dataset` | `dataset-integrity-fail` 35\* · `evaluator-unvalidated` 45 · `dataset-coarse-resolution` 89 | the two cut lines (`2/30 rows (6.7%) are unusable; line 10 (+1 more): invalid JSON`), then the scorer |
| `opaque-scorer` | 40 | PARTIAL | `repair-evaluator` | `evaluator-unresolved` 40\* | a scorer whose method can be declared: no `--evaluator-method` is passed for it, and the card says a file is connected that no method could honestly be declared for |
| `holdout-only` | 45 | PARTIAL | `resplit-dataset` | `evaluator-unvalidated` 45 · `dataset-tuning-split-empty` 50\* | answers on the tuning side. The 45 is the evaluator ceiling; the block is the empty tuning split |
| `leaky-split` | 45 | PARTIAL | `resplit-dataset` | `evaluator-unvalidated` 45 · `dataset-tune-holdout-overlap` 50\* · `dataset-repeated-rows` 89 | a disjoint split. The card names the six rows on both sides and offers to continue on the 300 that differ |
| `undeclared-source` | 45 | PARTIAL | `complete-calibration` | `evaluator-unvalidated` 45 · `dataset-undeclared-provenance` 65 | the provenance word: `spider-dev` is "a word its vocabulary does not know", scored as generated, and the card asks for the source to be declared or re-labelled |
| `mostly-undeclared-source` | 45 | PARTIAL | `complete-calibration` | `evaluator-unvalidated` 45 · `dataset-mostly-undeclared` 70 | the same word on 180 rows: the reading moves off `dataset-undeclared-provenance` onto `dataset-mostly-undeclared`, one rung up at 70. Uncalibrated the evaluator ceiling hides both -- see the calibrated pair below |
| `mostly-synthetic-source` | 45 | PARTIAL | `complete-calibration` | `evaluator-unvalidated` 45 · `dataset-mostly-synthetic` 70 | `dataset-mostly-synthetic`, the declared arm of the same rung. The distinction between this and the row above is whether the customer said *what* the rows are or said nothing at all |
| `generated-answer-key` | 45 | PARTIAL | `complete-calibration` | `evaluator-unvalidated` 45 · `dataset-generated-answer-key` 74 | `dataset-generated-answer-key` at 74: the questions are real and the ruler is a model's opinion |
| `mostly-generated-answer-key` | 45 | PARTIAL | `complete-calibration` | `evaluator-unvalidated` 45 · `dataset-mostly-generated-answer-key` 74 | `dataset-mostly-generated-answer-key`, the rung the answer-key ladder gained so the cap could not turn on one row |
| `slow-scorer` | 45 | PARTIAL | `bound-evaluator-cost` | `evaluator-timeout` 45\* | the scorer, and not because it is wrong. Calibration ran out of its budget, and the card asks for the cost to be bounded rather than for a repair |
| `split-by-database` | 45 | PARTIAL | `complete-calibration` | `evaluator-unvalidated` 45 | nothing the card can see -- **`dataset-split-by-task-family` does not fire.** See below |
| `two-agents` | 45 | PARTIAL | `complete-calibration` | `evaluator-unvalidated` 45 | nothing: the card is byte-identical to `ready`'s. The opening credits `agent.py`'s four settings and never mentions `sql_explainer/` or `PROJECT.md` |

**Three of the five bands, and the top two are held rather than missing.** The spread is
measured rather than arranged -- every preset and comparison the sweep names was built and
scored, and these thirty-one presets are the ones that describe a project somebody could actually
arrive with. The
agent pillar reads 100 on every project with an agent, so the numbers are what the dataset and
evaluation pillars make them; `checked` reaches 93, inside EXCELLENT by the number. It reads
WORKABLE because the guide holds STRONG and EXCELLENT until someone has read the expected
answers the run is graded on, and that read is the one thing its card asks for. `best-case` and
`sql-exec-stop` are held at WORKABLE for a different reason: their evaluation pillar was
measured on two checks of four, and a pillar measured that thinly cannot carry the top two
bands.

At `6ec2b9c1` there were exactly two ways across the top boundary and the guide barred both at
the opening: calibrating a scorer that executes model-written SQL, and declaring a trial budget.
Each was measured rather than assumed -- [`best-case`](#what-best-case-really-opens-at) and
[the trial-budget question](#the-trial-budget-and-the-fourth-credit). Since `e4096e3a` the first
is gone altogether, because an executing scorer earns the same task fit as a text comparator;
the second is no longer needed, because the opening read credits a twelve-configuration space
whole; and a third hold has taken their place, one that no run in this bank clears: the
expected answers have to be read before a band above WORKABLE is awarded.

The band boundaries, for reading the column: NOT READY 0-29, PARTIAL 30-54, WORKABLE 55-74,
STRONG 75-89, EXCELLENT 90-100.

### Three starting points the opening gate does not separate

A bank of broken projects is worth having because of what it finds, and at `6ec2b9c1` it found
three. Two of them the guide has since answered and one it has not. Each is a `diff` over two
committed cards, re-taken at `d07b62cd`.

**A dataset whose every answer answers a different question is still not noticed.**
`wrong-answers` keeps every question and every answer and pairs them wrongly, inside each
database, so all of them still run and still return rows. Every dataset check passes, no cap is
raised for it, and its card is `ready`'s card with smaller numbers in it -- the four lines that
differ are about draw size, not about the damage:

| | `ready` | `wrong-answers` |
|---|---|---|
| dataset pillar | 98/100 | **91/100** |
| answers to score against | `OK 300/300 rows carry an expected output` | `OK 60/60 rows carry an expected output` |
| examples to compare on | `OK 240 to tune on / 60 held back` | `!! 48 to tune on / 12 held back -- limited comparison set` |

A `wrong-answers` demo ships a 60-row draw because `DAMAGED_ROWS = 60`, so the card is
comparing a 60-row project with a 300-row one. Add probe answers and it reads **90, WORKABLE,
`review-answer-key`** with no cap at all -- the probes check the scorer and nothing checks
whether an answer answers its question. At `6ec2b9c1` that same card read 83 STRONG. The tool
that would catch it exists -- `readiness.py --row-review` asks exactly that -- and this table
does not pass it, for the reason [docs/measurements](docs/measurements/README.md) gives. The
guide has since put a second guard in front of the top bands, and this card is where it shows:
the 90 is held at WORKABLE and the one thing the card asks for is a read of the expected
answers, which is the read that would find the rotation. The hold does what the row review
would have done, one step later and without saying what it would find.

**A mis-wired scorer is invisible without probe answers, still.** `wrong-wiring` compares the
question with the recorded answer and never reads the model's output. It ships all 300 rows, so
there is no size difference to hide behind, and its card is **byte-identical to `ready`'s**:
45, `complete-calibration`, same pillars, same caps, same text. Built with calibration the
probes come back all-zero and the card drops to **25, `repair-evaluator`**. Calibration is the
entire difference between shipping that project and repairing it, in either direction --
`fake-ruler` is the same cap reached from all-ones.

**Duplication is now caught by the right check, and said in the right words.** At `6ec2b9c1`
`duplicated-data` stopped at 35 with `repair-dataset` for a reason that was not true of the
build -- "Some rows could not be read as data - malformed lines, or missing the input or
expected-answer field" -- when what had actually fired was preflight's duplicate-*id* check.
Since `9eaabbb2` the card prints, in full:

> **FIX BEFORE PAID RUN** 30 ids are used by more than one row, so a row cannot be named,
> excluded, or reviewed without ambiguity.

and carries the duplicated *rows* on their own line, `WOULD LIMIT TO 89 25 of the 73 rows this
run can score on the tuning side repeat an input already counted, so this comparison resolves
48 different examples rather than 73`. Whether a duplicated export that renumbered its ids on
the way out still clears the gate was measured at `6ec2b9c1` -- it did, at 45 PARTIAL -- and has
not been re-measured; the row-repeat ceiling of 89 says it would at least no longer clear it
silently.

Two more, from the nine presets ported on 2026-09-18, in the same register -- each a `diff`
over two committed cards at `d07b62cd`.

**A split drawn along databases is invisible to the family check.** `split-by-database`
holds out five whole databases -- `cre_Doc_Template_Mgt`, `flight_2`, `orchestra`,
`real_estate_properties`, `singer`, 61 rows -- so the winner is checked on schemas the search
never saw. `dataset-split-family` reads a task family off the two leading words of each
question, and question forms (*"What is"*, *"How many"*, *"Show the"*) span every database:
its finding is `PASS -- 11 of 24 recurring input forms appear on both sides, so the split
does not follow the task families` (15 of 24 on `ready`). The card is `ready`'s with
`239 to tune on / 61 held back` in place of `240 / 60`. The check is doing what its own
docstring says -- "read off the leading words alone and never from the meaning" -- and a
split along schemas is a split the wording does not carry.

**A second agent in the project changes nothing at the opening.** `two-agents` ships the
tunable agent at `agent.py` and an unrelated one in `sql_explainer/` -- its own `agent.py`,
twenty gold queries as an unlabelled `dataset.jsonl`, a word-count `evaluator.py` -- and a
`PROJECT.md` in the customer's voice saying the text-to-SQL agent is the one to work on. The
sweep points `readiness.py --selected-agent` at `agent.py`, as the note says to, and the card
that comes back is **byte-identical to `ready`'s**: agent 100, all four
settings credited, 36 configurations. Nothing on it mentions the second directory or the
note. That is the mechanical reading; which agent an assistant *selects* when it reads the
project is the question this preset exists to put to a real run, and the sweep does not
answer it.

**An absent agent is now a stop, not a `proceed`.** At `6ec2b9c1` `no-agent` -- 300 labelled
rows, a scorer, and no agent file at all -- read 45 `proceed`, because following the guide's own
instruction for a missing agent (leave the agent flags off) meant the score never learned the
agent was absent. Since `9eaabbb2` it reads **25, NOT READY, `connect-agent`**, under an
`agent-absent` ceiling of 25 that blocks. The same is true of scoring `ready` without
`--agent-knobs`: no longer "45 either way" but 25 and blocked, and the sentence the card prints
for it -- `no reading of how the agent is built reached this score; reading the agent is what
answers this` -- is the tool naming what it was not given, not a second opinion about the
project.

### What the source reader sees, and what the agent actually has

Same register as the finding above: an observation about the guide, at three revisions, not a
property of this repository, and not something a reader should expect to stay true.

The tunable agent has **four** settings that change what is sent. Instrumented -- with the
model call stubbed, so nothing leaves the process -- the full cross product of
`model` x `schema_context` x `prompt_style` x `temperature` is **36 distinct requests out of
36**. Every knob is load-bearing: three models, six distinct prompt texts, two temperatures.
`tests/test_components.py::test_each_setting_changes_the_request` holds that fact in place.

At `6ec2b9c1` the guide's static source reader credited **three of the four** and reported
"your space has 18 distinct configurations"; `temperature` was the one it declined, because
"this deliberately narrow static read could not verify that changing this setting changes the
request on the selected agent path".

At `9eaabbb2` it credited **none of the four.** Every setting was reported as one the read
"could not follow to the request", and every project with an agent sat under an
`agent-no-varying-knobs` ceiling of 45. This repository did not reshape its agents to satisfy
the reader -- see the section below on why -- and instead took the four settings to the guide,
one feature at a time, to find out which of them the reader was refusing. The helper structure
was fine: a request placed in a helper, a result post-processed by another, both credited.
Three narrower rules were not. `litellm.completion(...)` is a module-level function rather than
a method on a client the file built, and the reader knew only client methods, although LiteLLM
is the library the guide pins and the call its own wrapper makes. A `float(...)` around the
setting was accepted at the request argument and refused on the local that held the read one
line earlier. And a mapping handed to a helper nested inside another call --
`call_model(model, build_prompt(text, config), temperature)` -- was read as an escape, so only
the first setting read in the callable survived. Guide #549 (2026-09-15) fixed all three, with
the refusals kept at their edges: a rebound `litellm`, a project file named `litellm.py`, an
`int(...)` cast, a helper that writes to the mapping.

Since `e4096e3a` it credits **all four**, reports `your space has 36 distinct configurations`, and
the agent pillar reads 100 -- with no trial budget declared, for the reason the next section
gives. The four build observations on the card (`?` lines) are the assistant's read of how the
agent is put together and are excluded from the score until an independent check verifies
them; they neither add to nor subtract from the 100.

**It cost nothing measurable -- at `6ec2b9c1`.** Declaring the space to `readiness.py
--config-space` at 18 and at 36, at every trial budget from 1 to 50, gave the identical overall
score, band and agent pillar at every point. What moved the number was the trial budget:
undeclared held the agent pillar at 70, 1 trial dropped it to 0, 2 to 3 trials reached 35, 4 to
11 reached 70, and **12** -- the guide's "complete search" threshold -- reached 100. That
measurement has not been repeated; since guide #422 the opening read no longer holds a
budgetless space one step below, which is why the pillar now reads 100 without one.

### The trial budget, and the fourth credit

**And no, a trial budget is not what reaches the top band at the opening -- and it is no longer
what a full agent pillar needs.** At `6ec2b9c1` the arithmetic looked like a way in: agent 100
with `checked`'s dataset 98 and evaluation 83 is `0.40x98 + 0.35x83 + 0.25x100 = 93.25`, inside
EXCELLENT, and agent 100 needed a declared budget of at least 12 trials. But a trial budget can
only enter `readiness.py` through a `--config-space` document -- there is no flag, and the
`--agent-knobs` document refuses the key by name, exit 2, `carries unknown field(s)
max_trials; it reads 'knobs', 'source' and 'build'`, re-checked at `d07b62cd` -- and the
opening gate withholds that document. The guide's `references/run-safety.md`, stated as a
property of the score rather than as advice:

> The opening and section-4 scores withhold every config-space document by construction, so
> this is the run's only measurement of the space the customer paid to search.

The only config-space document the guide will read is one the run itself writes, and it saves
that file "only after this search returns nonzero trials, from the exact space received" -- so
the budget cannot exist as current-run evidence until money has already been spent, and the
score it feeds is one the guide says to "never show ... or set it beside the opening one". (At
`6ec2b9c1` those three sentences lived in `SKILL.md`; since `e4096e3a` they are in
`references/run-safety.md`, and the wording quoted is the current one, `d07b62cd`.)

What changed on the other side is that the opening read stopped holding a budgetless space one
step below full credit (guide #422, 2026-09-03): a source read that follows at least twelve
distinct configurations earns the agent pillar whole. So `checked` now opens at exactly the 93
that this section once said could only be a closing number -- and the guide answers that with
the band rather than the score: 93 reads **WORKABLE**, with the action `review-answer-key`,
until someone has read the expected answers. The number arrived at the opening; the verdict
did not.

The refusal and the single entry point are above, verbatim, and so are the three governing
quotes -- the last of them elided at the ellipsis you can see in it. What is *not* published
here is a card for that check: `docs/measurements/cards/` holds the score bank, and the bank
scores projects rather than the guide's handling of a config-space document. So a reader checks
this the way it is written -- the quoted text against the guide at `d07b62cd`, and
`readiness.py --agent-knobs` against a document carrying `max_trials` -- and not against a
measurement of ours.

So nothing here is written to win the fourth credit. The obvious way to do it -- an identity
mapping that reads `temperature` back out of a table so the reader can follow it -- was
considered and rejected: it is worse code, it changes nothing the agent sends, and writing code
to move somebody else's static analyser is how a demonstration stops demonstrating anything.
The agent has four knobs; the guide saw three of them at `6ec2b9c1`, none at `9eaabbb2`, and
all four since `e4096e3a`, and every one of those facts is written down.

### The one that argues for checking your scorer

`fake-ruler` is the same project as `ready` -- the same agent, the same 300 labelled rows --
except its scorer returns full marks for everything. Built without probe answers it reads
**45, `complete-calibration`** -- the same card as `ready`, because nothing has looked at the
scorer. Built with them it reads **25, `repair-evaluator`**.

That pair is the argument for calibration in one line. A scorer nobody has checked lets a run
go ahead and report a confident improvement that did not happen. Probe answers turn that into
a named, repairable problem -- and repairing it is what the run then does, before it measures
anything. It is also the only preset where shipping calibration *lowers* the opening score,
which is the right direction when the thing being checked is broken: the number went down
because the project got more honest, not because it got worse.

### What `best-case` really opens at

**85, WORKABLE, `confirm-evaluator-connection`** -- and its card is byte-identical to
`sql-exec-stop`'s, at `d07b62cd` as it was at `6ec2b9c1`.

`best-case` is `checked` with the execution scorer: the same agent, the same 300 rows, marked
the way Spider marks them, and it ships probe answers. Calibration still does not run at the
opening, and the reason is the one the guide gives: it will not import a scorer that reaches a
SQL engine and run it against a target it cannot bound. What the card says about that has
changed twice. At `6ec2b9c1` the refusal left the ordinary `evaluator-unvalidated` ceiling of 45
in place and the card read `proceed`. Since `9eaabbb2` the card carries a different condition,
`evaluator-calibration-refused`, with no ceiling and no block: a paragraph headed
`NOT CHECKED HERE` says the check is one the guide declines to perform rather than one the
project failed, names the copied-actor route as the one way the guide could measure a copy, and
asks the customer to say whether the evaluator connects read-only -- which is what the
recommended action means. The 85 is the plain average of dataset 98, evaluation 59 and agent
100, and the band is held at WORKABLE because the evaluation pillar was measured on two checks
of four; the two projects differ only in a file the gate is not allowed to run, which is why
the cards are the same.

**The 91 EXCELLENT this table used to publish was reached by running that calibration anyway,
and the tool now refuses to.** At `6ec2b9c1` the calibration tool imported any scorer once
`--allow-execution` was passed; since `9eaabbb2` it walks the scorer first and exits 2 on an
engine witness: `Refusing to calibrate: the scorer this run would import reaches a code or SQL
engine, and calling it runs statements against whatever that engine is pointed at.` The sweep
records that run as refused, and
[`cards/best-case--off-method-calibration/`](docs/measurements/cards/best-case--off-method-calibration/)
is left as the `6ec2b9c1` reading -- evaluation pillar 99, 91 EXCELLENT, no caps -- because it
is the evidence for a number this file no longer prints and a run the guide no longer performs.

**And the execution scorer is no longer the route to the top band.** At `6ec2b9c1`, task fit
for `execution` on `code-sql` output was 25/25, so the five points between `checked`'s 86 and
`best-case`'s off-method 91 were the score correctly reporting that one project measures its
answers the way the benchmark does. Since `9eaabbb2` the guide credits an executing evaluator
with the same 8/25 task fit as the text comparator; its card says the file `runs the answer, as
execution declares`, and that `This guide grades with an evaluator that does not run the
answer, so a route that runs it is not credited as the right kind of check for this output`.
The arithmetic that once made EXCELLENT reachable through execution is closed from the other
side: the band the benchmark's own metric would have earned is the band the guide declines to
award for it.

**The boundary is still a boundary, and it has stopped being a stop.** The guide's
`references/run-safety.md` still declines to calibrate the original of a scorer that runs
model-written SQL, and `--preset sql-exec-stop` and `--preset best-case` both fall under it.
What it no longer does is end the run there: since 2026-09-10 it says what was not checked and
continues, and since 2026-09-14 it can calibrate a *copy* against a target the customer bounds.
Whether `exec_match.py` can take that copied-actor route is not measured here. The route
accepts a scorer that opens exactly one engine, which this one does, and repoints that one
target argument to a single value the customer supplies -- while `exec_match.py` builds its
target from each row's `db_id`, and the three probe answers span three databases, so one
target cannot serve them. [docs/eval-methods.md](docs/eval-methods.md) records both boundaries.

### One thing that would not be truthful

At `6ec2b9c1`, declaring the evaluator method as `exact` with task kind `structured` made the
*text* comparator read **92, EXCELLENT, no caps**, with the evaluator file completely unchanged:
nothing checked a declaration against the source, and only the matched pair paid -- `exact`
alone or `structured` alone read 86, the same as the honest declaration. That was the highest
number anything in this repository could be made to produce, and the shape of it was the
point: exactly what someone optimising for the number would arrive at, and exactly what a
spot-check of either field on its own would miss.

Re-measured at `d07b62cd` ([`cards/grid-*`](docs/measurements/cards/)), the pair still pays:
**99** against **93** for the honest declaration, the same six points, from an evaluation
pillar of 100 against 83. Two things changed around it. The guide now reads the evaluator file
for the comparison it performs and refutes a declaration the file does not support, where it can
resolve the file at all; on this comparator it cannot, so the card credits the pair and says so
in the same line: `exact suits structured output (declared, not established from the evaluator
file)`. And the top band is no longer reachable by declaring anything: every calibrated card in
this bank, honest or not, reads **WORKABLE** with the action `review-answer-key`, because the
guide holds STRONG and EXCELLENT until someone has read the expected answers the run is graded
on. 99 is a number; the band says what a number cannot buy.

This repository does not declare its scorer as anything but what it is, and no number in the
table above depends on it. Every band here comes from an evaluator declared as what it is, on
probe answers built from real rows, with an agent whose settings were made readable without
changing what it sends. A high band is not evidence that anyone checked; that is what the
calibration step is for.

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
| [docs/eval-methods.md](docs/eval-methods.md) | the two SQL scorers, the two that are not, and the scoring problem behind them |
| [docs/measurements/](docs/measurements/README.md) | every readiness figure quoted here: the script, the agent read, and each run's captured invocation and output |

## Working on this repository

Building a demo needs nothing installed. The five checks below need three tools, and a
recent Linux will refuse to install them into the system Python (PEP 668), so put them in an
environment of their own:

```bash
python3 -m venv .venv-dev
.venv-dev/bin/python -m pip install -r requirements-dev.txt

.venv-dev/bin/black --check build.py spider tests components \
    docs/measurements/score_bank.py
.venv-dev/bin/ruff check build.py spider tests components \
    docs/measurements/score_bank.py
.venv-dev/bin/mypy --strict build.py spider/build_slice.py \
    docs/measurements/score_bank.py
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
queries, so they take a moment; that is the point of them. `docs/measurements/score_bank.py` is
in the static targets and `tests/test_score_bank.py` holds its behaviour, for a specific reason:
it is the program that produces every published readiness figure, it has twice destroyed the
committed evidence under `docs/measurements/cards/` on its way to reporting that it could not
measure anything, and while it sat outside every check here those repairs could have been
reverted with CI still green.
[`.github/workflows/ci.yml`](.github/workflows/ci.yml) is authoritative for exactly what runs
-- skipping any of it here is what turns a pull request red there.

The score table itself is not in that list, because *measuring* it needs a checkout of somebody
else's repository -- but no network, and no install. Re-measure it separately whenever the guide
moves. The run leaves the committed cards alone unless `--publish` is passed, and it refuses a
checkout that is not sitting on the pinned revision, `d07b62cd`
([why](docs/measurements/README.md#reproducing-it)):

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
