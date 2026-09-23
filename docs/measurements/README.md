# The measurements behind the score table

Every readiness figure quoted in this repository was produced here, and everything needed to
reproduce it is in this directory: the script, the hand-written agent reads it needs, and
the captured invocation and full output of every run.

**Measured against the first-run guide at revision
`d07b62cd4abb6ecb6d2edcdcb2d535f02bb2c199` (`d07b62cd`), which is the guide's trunk, on Python 3.12.3, with traigent 0.26.0 installed against the guide's 0.27.0
pin, which preflight records and continues past.** The nine presets ported on 2026-09-18 were
measured by the same sweep as the seventeen before them, and those seventeen came back
byte-identical, which is the reproducibility check this directory exists for.

The pin moved here from `5ce65540` on 2026-09-22, and the move is itself a measurement rather
than an argument. `5ce65540..d07b62cd` is one commit, touching `.github/`, `tests/` and six
lines of the guide's own `CLAUDE.md`; the `skills/` tree and `GUIDE.md` are byte-identical
across it. The whole sweep was re-run at `d07b62cd` and all thirty-seven cards
that existed on that day came back byte-identical -- `results.json` changed by exactly one line, the revision it
records. That is what a pin move should cost when the tooling did not move, and running it was
cheaper than writing the paragraph that would have argued the pin could stay.

Re-measure before quoting these anywhere that matters -- they are a reading of one revision of
somebody else's tool on one date, and the tool is under active development.

## Reproducing it

```bash
git clone https://github.com/Traigent/traigent-first-run ~/code/traigent-first-run
git -C ~/code/traigent-first-run checkout d07b62cd4abb6ecb6d2edcdcb2d535f02bb2c199

python3 docs/measurements/score_bank.py --guide ~/code/traigent-first-run
```

It builds each project, scores it, deletes it, and writes a card for each. It reaches no
network and never uses `--venv ready`. The whole sweep takes four to seven minutes on a laptop.

**Checking the committed cards is one flag.** `--compare` re-measures, publishes nothing, and
compares the result with `cards/` byte for byte -- every card of every run that scored, and
`results.json` whole, so the run the record says was refused has to be refused again in the
same words. It exits 0 only on full agreement, 4 on any difference, naming the file and the
first line that moved, and it refuses to compare nothing:

```bash
python3 docs/measurements/score_bank.py --guide ~/code/traigent-first-run --compare
```

A byte-for-byte comparison needs the environment the cards were taken in, because preflight
writes the Python version and the installed SDK into every card: `--recorded-environment`
prints the guide revision, Python, `traigent` and `litellm` versions to use (the first three
read from the committed record, `litellm` from `build.py`'s pin, since no card prints it), and
`--compare` refuses to start in any other. The `measurements` job in
[CI](../../.github/workflows/ci.yml) does exactly this on every pull request, with the guide
checked out at the pin.

**It leaves `cards/` alone.** The cards are committed evidence, and the usual reason to run this
script is to check them, so the run writes into its workspace and prints where. Replacing them
is a separate, explicit act:

```bash
python3 docs/measurements/score_bank.py --guide ~/code/traigent-first-run --publish
```

`--publish` replaces the committed directory of every run that produced a card, and leaves alone
the directory of any run that did not: a refused run reaches two or three files before the
refusal, and moving those over its committed card would delete the rendered card and the `argv`
record with it.

**A subset is `--only`.** `--only RUN ...` makes the named runs and nothing else. With
`--compare` it compares their cards and their rows of `results.json`; with `--publish` it
replaces their cards and puts their rows into the committed `results.json` in the order a whole
sweep writes them, leaving every other row as it was. Like `--compare`, a partial `--publish`
refuses to start in any environment but the one the committed cards record, since a card taken
under another interpreter would leave the record disagreeing with itself. That is how a new run
is added without rebuilding the bank, and the whole-bank `--compare` in CI is what then checks
the rest:

```bash
python3 docs/measurements/score_bank.py --guide ~/code/traigent-first-run \
    --only ready --compare
```

**One run cannot be measured at `d07b62cd`.** `best-case--off-method-calibration` asks the
calibration tool to run the execution scorer against the project's databases, and the tool now
refuses to import a scorer whose walk reaches a SQL engine (exit 2). The sweep records the
refusal in `results.json` and leaves `cards/best-case--off-method-calibration/` as it was: the
`6ec2b9c1` card, 91 EXCELLENT, kept as the evidence for a number the README no longer prints
and a run the guide no longer performs. Being kept as it was, its `argv.json` still records the
build without the `demo` subcommand, a recording fault every other card has since been
republished without; its `01-build.txt` shows the command that ran.

The sweep checks one more thing before it builds anything: that the documents under
`agent-knobs/` carry only fields the guide at the pin reads. It reads `readiness.py`'s own
field lists from the checkout it is handed, so *which fields a document may carry* is settled
by the guide rather than by a copy of its rules kept here; which fields are *required* the
guide expresses in control flow rather than as data, so `source_lines` is the one hardcoded
coordinate in the check, named in `score_bank.py` beside a comment saying so. At `d07b62cd`
the documents and the pin agree, which is why the command above needs no `--revision`.

**Exit status:** 0 when every run scored, 1 when the guide refused one or more, 2 when the
documents and the guide disagree, 3 when something of ours broke -- our builder, our probe --
and, with `--compare`, 4 when the measurement differs from the committed record. A fault of
ours never records a row and never publishes: `build.py` failing says nothing about the guide,
and a sweep that cannot measure has no business rewriting the evidence of what the guide
answered when it could.

**Each step gets a small environment, a HOME of its own and a time limit.** The build,
preflight, calibration and readiness steps are handed `PATH`, `LANG`, `LC_ALL` and `TMPDIR`
from the shell where it has them, a fresh empty directory of its own as `HOME`, removed when
the step ends, and `PYTHONUSERBASE` naming the user site the sweep's own interpreter imports
from -- and nothing else. The calibrator imports the project's own evaluator, and preflight
writes what it finds in the environment into the card, so a sweep run from a shell holding a
provider key or a database URL used to hand both to that code, and produced cards that said the
key was present. The four passed through are the machine-describing part of the guide's own
test environment (its behavioural harness, at the pin), which fixes their values where this
sweep passes the operator's. The empty `HOME` means nothing a library looks for there by its
default name -- `~/.netrc`, `~/.aws/credentials`, a tool's config -- is found, and nothing one
step writes there is found by the next; it closes a default rather than building a sandbox, and
a path spelled out in full is still readable. `PYTHONUSERBASE` keeps an SDK installed with `pip
--user` importable, which is where it is on some machines. A step runs in a process group of
its own, and the group is killed once the step's output is read, on Ctrl-C, and when the step
is still running after `STEP_TIMEOUT_SECONDS` -- 960, the guide's 900-second calibration
ceiling plus the 60 seconds of headroom its harness allows that same command. A step killed for
time leaves what it said, up to the 4,000 characters the guide's harness keeps of a command it
kills, in its log, and the sweep stops on exit 3 with nothing published. The guide's ceiling is
below that limit on purpose: `slow-scorer` depends on the guide reaching its own timeout and
saying so, and the sweep's limit only ends a step that has stopped answering. The CI job's own
limit sits above one step's, so a hang prints the sweep's diagnostic rather than a cancelled
job.

## What is here

| | |
|---|---|
| `score_bank.py` | the whole measurement. Its docstring states every choice it makes and why. It is in CI's `black`/`ruff`/`mypy --strict` targets and its behaviour is held by [`tests/test_score_bank.py`](../../tests/test_score_bank.py): it has twice destroyed the evidence in `cards/` while reporting that it could not measure anything, and a repair nothing tests is a repair the next edit can quietly undo |
| `agent-knobs/ready.json` | the read of the tunable agent's source that the opening score requires |
| `agent-knobs/no-knobs.json` | the same read of the fixed agent: a completed read that found no knobs |
| `agent-knobs/commented-knobs.json` | the same read of the `commented-knobs` agent, whose settings are named only in a comment: a completed read that found no knobs |
| `agent-knobs/commented-knobs-credited.json` | a read that is wrong on purpose: it credits the settings that comment names, citing the nearest executable lines, and is scored only by `no-knobs--knobs-in-a-comment--credited` |
| `cards/<run>/01-build.txt` | the `build.py demo` invocation and its output |
| `cards/<run>/02-preflight.json` | `preflight.py --json` output, which is `readiness.py --preflight`'s input |
| `cards/<run>/03-calibration.json` | `calibrate_evaluator.py --json` output, where calibration ran |
| `cards/<run>/04-readiness-card.txt` | **the rendered card** -- the thing the documentation quotes |
| `cards/<run>/05-readiness.json` | the same score machine-readable: pillars, sub-scores, caps |
| `cards/<run>/argv.json` | the build, preflight and readiness invocations, with this machine's paths replaced by `$GUIDE`, `$PROJECT`, `$DEMO`, `$KNOBS`, `$EVIDENCE`. A calibrated run records `calibration_ran` here and its argv in `03-calibration-stderr.txt`, which is where `slow-scorer`'s `--timeout 5` -- the flag its cap depends on -- is written down |
| `cards/results.json` | `conditions`, every cap condition the guide at the pin can raise with the remedy and ranked ceiling it gives each, read from `readiness.py`'s own `CAP_CEILING` and `ACTION_FOR_CONDITION` by the probe that reads its document contracts; then one row per run: score, band, action, pillars, caps, what was declared. A run that could not be scored -- the guide refused it, or the step it needed returned no JSON -- carries a `refused` object naming the step, the exit status and that step's own first line instead of a score, and the sweep continues past it: one row lost rather than the bank. The reason is where the two are told apart (`Refusing to calibrate: ...` is the guide declining; `cannot read scoring input: ...` is an input of ours it would not read) |

Two things about the rows at `d07b62cd`. A cap's `ceiling` may be `null` in `results.json`
and on the card: such a cap discloses a finding without bounding the score
(`evaluator-calibration-refused`, ceiling null, blocks false). And the guide holds the top two
bands at WORKABLE until a review of the expected answers has entered through `--row-review`,
which this sweep never passes -- so every calibrated card that climbs past 74 here reads
WORKABLE with the action `review-answer-key` and `band_limited_by_unread_answers: true`.
At `9eaabbb2`, a day earlier, that hold was inert because nothing climbed past 45; the row
review this table does not pass is now what stands between six of its runs and their band.

## The `--agent-knobs` document, and why it is here

`readiness.py --agent-knobs` takes the coding assistant's own read of the agent's source: which
parameters it can already vary, and how the agent is put together, each with the line that
shows it. The guide is explicit that this read is not optional -- "every guided run that found
an agent does this read, not conditionally" -- and it is what the agent pillar is scored from.

No coding assistant runs in this repository, so `agent-knobs/ready.json` and
`agent-knobs/no-knobs.json` stand in for the document one would write. They were written by
hand against `components/agent/*/agent_ready.py` and `agent_no_knobs.py`, and every
`source_lines` entry cites a real line on the real call path -- which is why the figures are
faithful, and also why another honest read could move them a few points.
`agent-knobs/commented-knobs-credited.json` is the exception, wrong on purpose, and only
`no-knobs--knobs-in-a-comment--credited` is scored with it; the section on repairs in name
only below says what it is for.

Two things follow, and both are properties of this table rather than of the guide:

- **A run scored without that document cannot see the agent at all.**
  `cards/ready--without-agent-knobs/` is that run: 25 NOT READY `connect-agent`, where `ready`
  reads 45 PARTIAL. The agent pillar drops from 100 to 0 and `agent-absent` (25, blocks) takes
  the number -- "No agent reached this score - no settings document, no reading of its source,
  and no declaration that one exists" -- and the card is byte-identical to `no-agent`'s. That is
  the tool reporting that it was not given what it asked for, not a second opinion about the
  project.
- **`--row-review` is not passed.** The guide asks for one at the opening gate, and it is the
  assistant's own read of every row: does this expected output answer this input? A
  hand-written stand-in would be this script deciding that question row by row, which is
  exactly the judgement `--preset wrong-answers` exists to test. Leaving it off keeps the table
  mechanical and leaves the finding below intact.

## What the sweep covers

Every one of `build.py`'s thirty-five presets is run once: thirty-four by name, and `slow-scorer`
through a variant, because it carries a non-default calibration budget. Then come the
twenty-five comparisons the documentation makes -- twenty-one variants and the four `grid-*` runs --
for sixty runs in all:

| run | what it is for |
|---|---|
| the 34 presets | the score tables in the README |
| `best-case--off-method-calibration` | the number once reached by calibrating an executing scorer; refused by the tool since `9eaabbb2`, its `6ec2b9c1` card retained |
| `wrong-answers--calibrated` | `--preset wrong-answers --calibration present` |
| `wrong-wiring--calibrated` | `--preset wrong-wiring --calibration present` |
| `fake-ruler--uncalibrated` | `--preset fake-ruler --calibration none` |
| `ready--without-agent-knobs` | the same project scored with the agent read withheld |
| `raw-export--fields-declared` | `--preset raw-export` with `--input-field question --expected-field query` passed to preflight: what a run that had opened the file would declare |
| `length-blind--uncalibrated` | `--preset length-blind --calibration none`: the length scorer with nothing to catch it |
| `undeclared-source--calibrated` | the rung the provenance ladder puts a wholly undeclared file on, once the evaluator ceiling is out of the way |
| `mostly-undeclared-source--calibrated` | the same, one rung up: most rows undeclared, the rest saying they were collected |
| `mostly-synthetic-source--calibrated` | the declared arm of that rung, whose action is `proceed` rather than a request to declare |
| `synthetic-source--calibrated` | the rung below it: every row declared written, which costs 65 where declaring most of them costs 70 |
| `generated-answer-key--calibrated` | the answer-key ladder's top rung |
| `mostly-generated-answer-key--calibrated` | the rung below it, which exists so the cap cannot turn on one row |
| `slow-scorer` | `--preset slow-scorer` with `--timeout 5` on the calibration step. With no `--timeout` the guide budgets this calibration at 900 seconds, and each authored probe takes the scorer two minutes, so even the smallest case set the guide's `--cases` form accepts -- two cases, eight probes; the form its instructions use -- outlasts it: a guided run reaches the timeout only after the full fifteen minutes. Measured at the pin with the shipped four cases and with two: exit 1 at 900 seconds and `timed_out: true` both times, and the same card: 45, `bound-evaluator-cost`. The shorter budget spares every reproduction that wait, and the card records the one it was reached under |
| `disclaimed-agent--calibrated` | the ceiling a disclaimed agent sets, once the evaluator ceiling is out of the way |
| `disclaimed-scorer--calibrated` | the same for a disclaimed scorer, which calibrates cleanly and is still not the customer's |
| `split-by-question-form--calibrated` | the ceiling a split along the questions' forms sets, likewise uncovered |
| `no-data--empty-file` | `no-data` with the data file created and left empty: `get-data` done in name only |
| `no-labels--blank-answers` | `no-labels` with an answer field added to every row and nothing in it |
| `no-knobs--knobs-in-a-comment` | `no-knobs` with settings to tune over written into a comment, read faithfully (`agent-knobs/commented-knobs.json`) |
| `no-knobs--knobs-in-a-comment--credited` | the same project, handed a read (`agent-knobs/commented-knobs-credited.json`) that credits the settings the comment names |
| `hand-written--padded` | `hand-written` with its ten rows copied up to thirty, each copy under an id of its own |
| `grid-*` | the four declared-method x declared-task-kind combinations, all on the same unchanged text comparator |

## Results

**Every row below is the reading at `d07b62cd`**, taken from `cards/results.json`.
The agent pillar reads 100 on every project with an agent: the guide's static reader follows
all four of the demo agent's settings to the request since guide #549, for the reason the
repository README gives under "What the source reader sees". A regeneration at `9eaabbb2`
earlier the same day read 0 there and 45 on every one of those rows; it is superseded, not
republished.

Pillar weights are the default 40 dataset / 35 evaluation / 25 agent. `*` marks a cap that
blocks (the card prints `FIX BEFORE PAID RUN`); the others are ceilings only, and a cap whose
ceiling reads `none` discloses something without bounding the number
(`evaluator-calibration-refused` is the one such cap in this table).

| run | score | band | action | agent | dataset | evaluation | caps |
|---|---|---|---|---|---|---|---|
| `empty` | 0 | NOT READY | `get-data` | 0 | 0 | 0 | `dataset-absent` 20\* · `agent-absent` 25\* · `evaluator-absent` 40\* |
| `logs-only` | 7 | NOT READY | `connect-agent` | 0 | 18 | 0 | `agent-absent` 25\* · `dataset-no-expected-outputs` 30\* · `evaluator-absent` 40\* |
| `no-data` | 20 | NOT READY | `get-data` | 100 | 0 | 33 | `dataset-absent` 20\* · `evaluator-unvalidated` 45 |
| `agent-and-logs` | 30 | PARTIAL | `label-data` | 100 | 18 | 0 | `dataset-no-expected-outputs` 30\* · `evaluator-absent` 40\* |
| `fake-ruler` | 25 | NOT READY | `repair-evaluator` | 100 | 98 | 28 | `evaluator-invalid` 25\* |
| `no-labels` | 30 | PARTIAL | `label-data` | 100 | 18 | 33 | `dataset-no-expected-outputs` 30\* · `evaluator-unvalidated` 45 |
| `duplicated-data` | 35 | PARTIAL | `repair-dataset` | 100 | 86 | 33 | `dataset-integrity-fail` 35\* · `evaluator-unvalidated` 45 · `dataset-repeated-rows` 89 |
| `no-eval` | 40 | PARTIAL | `connect-evaluator` | 100 | 98 | 0 | `evaluator-absent` 40\* |
| `no-knobs` | 45 | PARTIAL | `vary-knobs` | 0 | 98 | 33 | `evaluator-unvalidated` 45 · `agent-no-varying-knobs` 45\* |
| `ready` | 45 | PARTIAL | `complete-calibration` | 100 | 98 | 33 | `evaluator-unvalidated` 45 |
| `sql-exec-stop` | 85 | WORKABLE | `confirm-evaluator-connection` | 100 | 98 | 59 | `evaluator-calibration-refused` none |
| `no-agent` | 25 | NOT READY | `connect-agent` | 0 | 98 | 33 | `agent-absent` 25\* · `evaluator-unvalidated` 45 |
| `wrong-answers` | 45 | PARTIAL | `complete-calibration` | 100 | 91 | 33 | `evaluator-unvalidated` 45 |
| `wrong-wiring` | 45 | PARTIAL | `complete-calibration` | 100 | 98 | 33 | `evaluator-unvalidated` 45 |
| `hand-written` | 74 | WORKABLE | `add-examples` | 100 | 75 | 83 | `dataset-below-measurable-size` 74 |
| `checked` | 93 | WORKABLE | `review-answer-key` | 100 | 98 | 83 | none |
| `best-case` | 85 | WORKABLE | `confirm-evaluator-connection` | 100 | 98 | 59 | `evaluator-calibration-refused` none |
| `raw-export` | 25 | NOT READY | `read-dataset` | 100 | 0 | 33 | `dataset-shape-unrecognised` 25\* · `evaluator-unvalidated` 45 |
| `length-blind` | 25 | NOT READY | `repair-evaluator` | 100 | 98 | 4 | `evaluator-invalid` 25\* |
| `torn-lines` | 35 | PARTIAL | `repair-dataset` | 100 | 84 | 33 | `dataset-integrity-fail` 35\* · `evaluator-unvalidated` 45 · `dataset-coarse-resolution` 89 |
| `opaque-scorer` | 40 | PARTIAL | `repair-evaluator` | 100 | 98 | 0 | `evaluator-unresolved` 40\* |
| `holdout-only` | 45 | PARTIAL | `resplit-dataset` | 100 | 45 | 33 | `evaluator-unvalidated` 45 · `dataset-tuning-split-empty` 50\* |
| `leaky-split` | 45 | PARTIAL | `resplit-dataset` | 100 | 88 | 33 | `evaluator-unvalidated` 45 · `dataset-tune-holdout-overlap` 50\* · `dataset-repeated-rows` 89 |
| `undeclared-source` | 45 | PARTIAL | `complete-calibration` | 100 | 89 | 33 | `evaluator-unvalidated` 45 · `dataset-undeclared-provenance` 65 |
| `mostly-undeclared-source` | 45 | PARTIAL | `complete-calibration` | 100 | 92 | 33 | `evaluator-unvalidated` 45 · `dataset-mostly-undeclared` 70 |
| `mostly-synthetic-source` | 45 | PARTIAL | `complete-calibration` | 100 | 92 | 33 | `evaluator-unvalidated` 45 · `dataset-mostly-synthetic` 70 |
| `synthetic-source` | 45 | PARTIAL | `complete-calibration` | 100 | 89 | 33 | `evaluator-unvalidated` 45 · `dataset-fully-synthetic` 65 |
| `generated-answer-key` | 45 | PARTIAL | `complete-calibration` | 100 | 93 | 33 | `evaluator-unvalidated` 45 · `dataset-generated-answer-key` 74 |
| `mostly-generated-answer-key` | 45 | PARTIAL | `complete-calibration` | 100 | 94 | 33 | `evaluator-unvalidated` 45 · `dataset-mostly-generated-answer-key` 74 |
| `split-by-database` | 45 | PARTIAL | `complete-calibration` | 100 | 98 | 33 | `evaluator-unvalidated` 45 |
| `two-agents` | 45 | PARTIAL | `complete-calibration` | 100 | 98 | 33 | `evaluator-unvalidated` 45 |
| `split-by-question-form` | 45 | PARTIAL | `complete-calibration` | 100 | 98 | 33 | `evaluator-unvalidated` 45 · `dataset-split-by-task-family` 50 |
| `disclaimed-agent` | 45 | PARTIAL | `complete-calibration` | 100 | 98 | 33 | `evaluator-unvalidated` 45 · `agent-generated` 65 |
| `disclaimed-scorer` | 45 | PARTIAL | `complete-calibration` | 100 | 98 | 33 | `evaluator-unvalidated` 45 · `evaluator-generated` 74 |
| `best-case--off-method-calibration` | refused | -- | -- | -- | -- | -- | `calibrate_evaluator.py` exit 2: the guide refuses to import a scorer that reaches a SQL engine; the committed directory is the `6ec2b9c1` card |
| `wrong-answers--calibrated` | 90 | WORKABLE | `review-answer-key` | 100 | 91 | 83 | none |
| `wrong-wiring--calibrated` | 25 | NOT READY | `repair-evaluator` | 100 | 98 | 28 | `evaluator-invalid` 25\* |
| `fake-ruler--uncalibrated` | 45 | PARTIAL | `complete-calibration` | 100 | 98 | 33 | `evaluator-unvalidated` 45 |
| `ready--without-agent-knobs` | 25 | NOT READY | `connect-agent` | 0 | 98 | 33 | `agent-absent` 25\* · `evaluator-unvalidated` 45 |
| `raw-export--fields-declared` | 45 | PARTIAL | `complete-calibration` | 100 | 98 | 33 | `evaluator-unvalidated` 45 |
| `length-blind--uncalibrated` | 40 | PARTIAL | `repair-evaluator` | 100 | 98 | 0 | `evaluator-unresolved` 40\* |
| `undeclared-source--calibrated` | 65 | WORKABLE | `declare-data-provenance` | 100 | 89 | 83 | `dataset-undeclared-provenance` 65 |
| `mostly-undeclared-source--calibrated` | 70 | WORKABLE | `declare-data-provenance` | 100 | 92 | 83 | `dataset-mostly-undeclared` 70 |
| `mostly-synthetic-source--calibrated` | 70 | WORKABLE | `proceed` | 100 | 92 | 83 | `dataset-mostly-synthetic` 70 |
| `synthetic-source--calibrated` | 65 | WORKABLE | `proceed` | 100 | 89 | 83 | `dataset-fully-synthetic` 65 |
| `generated-answer-key--calibrated` | 74 | WORKABLE | `review-answer-key` | 100 | 93 | 83 | `dataset-generated-answer-key` 74 |
| `mostly-generated-answer-key--calibrated` | 74 | WORKABLE | `review-answer-key` | 100 | 94 | 83 | `dataset-mostly-generated-answer-key` 74 |
| `slow-scorer` | 45 | PARTIAL | `bound-evaluator-cost` | 100 | 98 | 33 | `evaluator-timeout` 45\* |
| `disclaimed-agent--calibrated` | 65 | WORKABLE | `proceed` | 100 | 98 | 83 | `agent-generated` 65 |
| `disclaimed-scorer--calibrated` | 74 | WORKABLE | `proceed` | 100 | 98 | 83 | `evaluator-generated` 74 |
| `split-by-question-form--calibrated` | 50 | PARTIAL | `review-split` | 100 | 98 | 83 | `dataset-split-by-task-family` 50 |
| `no-data--empty-file` | 20 | NOT READY | `get-data` | 100 | 0 | 33 | `dataset-absent` 20\* · `evaluator-unvalidated` 45 |
| `no-labels--blank-answers` | 30 | PARTIAL | `label-data` | 100 | 36 | 33 | `dataset-no-expected-outputs` 30\* · `evaluator-unvalidated` 45 |
| `no-knobs--knobs-in-a-comment` | 45 | PARTIAL | `vary-knobs` | 0 | 98 | 33 | `evaluator-unvalidated` 45 · `agent-no-varying-knobs` 45\* |
| `no-knobs--knobs-in-a-comment--credited` | 45 | PARTIAL | `complete-calibration` | 0 | 98 | 33 | `evaluator-unvalidated` 45 · `agent-no-varying-knobs` 45 |
| `hand-written--padded` | 74 | WORKABLE | `review-repeats` | 100 | 73 | 83 | `dataset-below-measurable-size` 74 · `dataset-repeated-rows` 89 |
| `grid-exact--code-sql` | 93 | WORKABLE | `review-answer-key` | 100 | 98 | 83 | none |
| `grid-normalized-exact--structured` | 93 | WORKABLE | `review-answer-key` | 100 | 98 | 83 | none |
| `grid-normalized-exact--code-sql` | 93 | WORKABLE | `review-answer-key` | 100 | 98 | 83 | none |
| `grid-exact--structured` | 99 | WORKABLE | `review-answer-key` | 100 | 98 | 100 | none |

The band boundaries the guide uses, for reading the column: NOT READY 0-29, PARTIAL 30-54,
WORKABLE 55-74, STRONG 75-89, EXCELLENT 90-100.

## What the nine ported presets measured

Seven of the nine opened on the cap they were built for. One did not, and one was built for a
question the opening card does not ask; both are worth writing down.

- **`two-agents` is `ready`.** The card is byte-identical to `ready`'s: the sweep
  points `--selected-agent` at `agent.py`, as the customer's `PROJECT.md` says to, and the
  read credits its four settings. Nothing on the card mentions `sql_explainer/` or the note.
  Which agent an assistant would *select* is a question for a real run, not for this sweep.
- **`split-by-database` is `ready` with `239 / 61` where `ready` has `240 / 60`.**
  `dataset-split-family` reads a family off the two leading words of each question, and
  question forms span every database, so its finding on a split made of whole databases is
  `PASS -- 11 of 24 recurring input forms appear on both sides` (15 of 24 on `ready`). The
  cap the preset was built to test, `dataset-split-by-task-family`, is not raised.
- **`raw-export` opens at 25 unaided and at 45 declared.** Read under the default field
  names the file has no usable rows (`dataset-shape-unrecognised`, blocks); read under its own
  (`raw-export--fields-declared`) it is `ready`'s card.
- **`leaky-split` is bound by the evaluator, not by the leak.** The overlap cap is 50 and
  blocks; `evaluator-unvalidated` at 45 is what the number reads. The same holds for
  `holdout-only` (`dataset-tuning-split-empty` 50, blocks) -- both open at 45 with the block
  on the card and `resplit-dataset` as the action.
- **The two scorers that cannot be given a method land where the guide's ladder puts them.** With no
  `--evaluator-method` declared -- the only honest declaration for either --
  `opaque-scorer` reads `evaluator-unresolved` 40, blocks; `length-blind` with probes reads
  `evaluator-invalid` 25, blocks, from a calibration that ran and failed
  (`non_constant` true, `bad_fails` false on every case), and without them the same 40
  `unresolved` as `opaque`.

## What the origin and question-form presets measured

Three conditions the guide can raise were reached by no preset: two about who wrote a
component, one about where the split falls. Each opened on the condition it was built for,
and the two kinds show different things, as below.

- **A component the customer disclaims is `generated`.** `disclaimed-agent` and
  `disclaimed-scorer` ship the tunable agent and the text comparator unchanged; what differs is
  the project's README, which calls the file a tutorial example and says the real one is
  elsewhere. The guide has a run declare such a file `generated` "however cleanly it reads or
  calibrates", and the sweep declares what the build record says (`--agent-origin generated`,
  `--evaluator-origin generated` in each card's `argv.json`). The cards raise `agent-generated`
  (65) and `evaluator-generated` (74), both ceilings that do not block; calibrated, those are
  the numbers they read, with the action `proceed`. Their preflight is byte-identical to
  `ready`'s, so these cards show how the guide scores a declared origin, not that a run notices
  the disclaimer: that is what a worker run on the project would show. The guide's wording for
  both caps says the run "wrote" the component, which a disclaimed file it did not write only
  approximates.
- **A split along the questions' opening forms is read.** `split-by-question-form` holds out
  every question opening "How many" -- 34 rows, one of them in lower case -- and preflight's
  `dataset-split-family` finds every one of the 24 recurring forms on one side only, so the card
  raises `dataset-split-by-task-family` (50, asks, does not block) and names the forms. It is
  the reading `split-by-database` does not get: holding out whole databases leaves the forms on
  both sides. Here the finding is the guide's own: preflight reads the split from the rows.

## Verdicts and remedies, declared by hand as a tripwire

The caps say what the guide noticed; the verdict is what it then tells the customer to do, and
that is the part anything consuming a card routes on. Both are declared by hand, so that the
next re-pin that moves either fails by name instead of arriving as a changed number:

- `PRESET_VERDICT` in `build.py` names, for every preset, the run that isolates its state -- the
  calibrated variant where there is one, since the unchecked scorer's 45 hides every ceiling
  above it -- and the band, status and action that run's card should read.
- `REMEDIES` in `tests/test_score_bank.py` names, for every condition the guide at the pin can
  raise, the action, the ceiling and whether the run waits, with a line on why; `OTHER_ARMS`
  names the second shape two of them take and the runs whose cards carry it
  (`evaluator-calibration-refused` with no ceiling on `sql-exec-stop` and `best-case`, where
  preflight found the engine; `agent-no-varying-knobs` without the block on
  `no-knobs--knobs-in-a-comment--credited`, where the read claims settings the opening check
  cannot follow).

Neither is an independent answer key, and where each carries judgement of its own is worth
being exact about. `REMEDIES`' action and ceiling are held equal to the guide's own
`ACTION_FOR_CONDITION` and `CAP_CEILING`, and the guide builds every cap's action from that same
table, so the check of each card's action can only fail if the guide's table moves. What
`REMEDIES` declares that the guide's tables do not is `blocks`, which every card is held to
exactly, second shapes included. `PRESET_VERDICT` was derived from each preset's purpose and the
guide's rules; the judgement it carries is the choice of run, and the band, status and action
follow from the guide's rules once that is chosen. It is not blind: this page's Results table,
which prints every band and action, had been read before it was written.

At `d07b62cd` every card reads the verdict declared for it, and `VERDICT_DIVERGENCES` is empty;
it is checked both ways. Two of those agreements are worth less than they look.
`wrong-answers--calibrated` reads `review-answer-key` because no row review was passed, which
holds every card that climbs past 74, and not because anything noticed that its answers answer
other questions; and `split-by-database` reads `complete-calibration` whether or not its split
is seen, because the unchecked scorer's ask comes first. The cap-level truth for both is in
`NOT_ON_THEIR_OWN_CARD`.

## Repairs, and repairs in name only

Each remedy on a card asks for one thing to change. Where the bank holds the run before a repair
and the run after it, `REPAIRS` in `tests/test_score_bank.py` writes the pair down and holds it
to three things: the pair differs in that one thing and nothing else, the condition the remedy
is for is on the card before and gone from the card after, and no blocking cap appears that the
project did not already have. The pairs are `no-data` to `ready` (`get-data`), `no-labels` to
`ready` (`label-data`), `no-eval` to `ready` (`connect-evaluator`), `no-knobs` to `ready`
(`vary-knobs`), `wrong-wiring--calibrated` and `fake-ruler` to `checked` (`repair-evaluator`),
`leaky-split` to `ready` (`resplit-dataset`), `hand-written` to `checked` (`add-examples`) and
`raw-export` to `raw-export--fields-declared` (`read-dataset`).

A repair in name only changes that same thing so that it looks done, and leaves it undone.
The guide holds every one of these that changes the project, and lets through the one that
changes only what it is told about the project:

- **An empty data file** (`no-data--empty-file`) is still no data: `dataset-absent` 20,
  blocking, `get-data` -- the reason now says a dataset was provided "and it holds no rows at
  all".
- **An answer field left empty on every row** (`no-labels--blank-answers`) is still no answer
  key: `dataset-no-expected-outputs` 30, blocking, `label-data`.
- **Ten rows copied up to thirty** (`hand-written--padded`) are still eight comparable examples
  on the tuning side: `dataset-below-measurable-size` holds at 74, and `dataset-repeated-rows`
  (89) asks about the copies, so the action moves from `add-examples` to `review-repeats`. Each
  copy carries an id of its own; with its original's id it would be the `duplicated` defect,
  which the guide reports as a broken file instead.
- **Settings named in a comment** (`no-knobs--knobs-in-a-comment`) are still nothing to
  search, when the agent is read faithfully (`agent-knobs/commented-knobs.json`, which finds
  no settings): `agent-no-varying-knobs` 45, blocking, `vary-knobs` -- the card `no-knobs`
  itself gets.
- **The same agent, read carelessly** (`no-knobs--knobs-in-a-comment--credited`) gets through,
  in part. The project is unchanged; the read handed to the guide
  (`agent-knobs/commented-knobs-credited.json`) credits the settings the comment names, citing
  the executable lines beside it. The guide does not believe it -- the settings are not
  scored, the agent pillar reads 0 either way and `agent-no-varying-knobs` stays at 45 -- but
  it cannot verify the claim at the opening either, and treats an unverified claim as
  advisory rather than as a finding that the agent has no setting: "the source read found
  candidate settings, but it did not establish that changing them changes the finalized
  request ... This advisory opening ceiling remains while the cited source evidence is
  unverified." So the card that blocked on `vary-knobs` reads OK with
  `complete-calibration`, and it names a request-difference probe as the separate pre-call
  guard, which this bank does not run. A read citing the comment itself is
  refused outright ("cites comment/docstring/non-executable source"), which is why this one
  cites executable lines, and why `tests/test_measurements.py` holds it to the same citation
  rule as the faithful reads. So what gets through is a careless read, not the comment, and
  what it gets through is the block at the opening, not the ceiling; the guard the guide
  names for it is the request-difference probe before the first paid call.

The careless read is written down in `UNGUARDED`, with what its card shows, and checked both
ways:
the day the guide holds it, the entry and this paragraph are stale. A fake the guide does not
hold and that is not written down fails the suite.

## The cards that are identical to another card

Worth stating because each one is a finding rather than a coincidence: where different starting
states produce the same card, the guide's opening read did not distinguish them. Seventeen of the
sixty cards fall into the seven groups below. Each is checkable directly -- the first line
of `04-readiness-card.txt` is the invocation that produced it, which names its own paths, so
compare from the second line down:

```bash
cd docs/measurements/cards
diff <(tail -n +2 ready/04-readiness-card.txt) <(tail -n +2 wrong-wiring/04-readiness-card.txt)
```

This list is not maintained by hand. `tests/test_score_bank.py` recomputes the groups from the
committed cards, from the second line down as above, and compares them with `IDENTICAL_CARDS`,
so a round that creates a new identical pair and does not say so here goes red -- which is how
the `opaque-scorer` pair below came to be written down at all. It used to compare whole files,
first line included, so cards that differed only in their invocation never grouped; the
`no-knobs` pair below is the one that hid, and re-deriving every group the new way found no
other.

- `ready`, `wrong-wiring`, `fake-ruler--uncalibrated`, `raw-export--fields-declared` and
  `two-agents` -- **all five byte-identical**. A scorer that never reads the model's output is
  invisible to the opening gate; an uncalibrated ruler and a declared field rename are too; and
  a second agent directory beside the first is not read at all.
- `best-case` and `sql-exec-stop` -- **byte-identical**. The guide will not calibrate an
  executing scorer on the original at the opening, so shipping probe answers for one changes
  nothing there; both cards carry the same `evaluator-calibration-refused` disclosure and the
  same `confirm-evaluator-connection` action.
- `length-blind--uncalibrated` and `opaque-scorer` -- **byte-identical**. Two scorers that
  cannot be given a method honestly, and the opening reports the absence of a method rather
  than anything about the scorer, so the two are the same reading.
- `fake-ruler` and `wrong-wiring--calibrated` -- **byte-identical**.
- `checked` and `grid-normalized-exact--code-sql` -- **byte-identical**.
- `no-agent` and `ready--without-agent-knobs` -- **byte-identical**. Both cap at
  `connect-agent`: no agent, and an agent whose source nobody read, read alike here.
- `no-knobs` and `no-knobs--knobs-in-a-comment` -- **byte-identical** from the second line.
  An agent that names settings to tune over only in a comment, read faithfully, is read exactly
  like the agent that names none: the comment changes nothing the opening gate sees.
- `wrong-answers` and `ready` -- **not** identical, and the four differences are all about
  size rather than about the damage: dataset pillar 91 against 98, `60/60 rows` against
  `300/300`, `60 collected of 60` against `300 collected of 300`, and the comparison-size
  check dropping from `OK` to `!!` because a 60-row draw is 48 tuning rows. Every check that
  could have noticed the answers are wrong passes.

## The arithmetic at the top of the scale

At `6ec2b9c1`, with the `ready` family's dataset 98 and agent 70, the overall score was
`0.40x98 + 0.35xE + 0.25x70 = 56.7 + 0.35E`; EXCELLENT starts at 90, so it needed an evaluation
pillar of 94, the text comparator's calibrated pillar was 83 (86 overall) and the execution
scorer's was 99 (91). Since guide #549 landed (`e4096e3a`) the agent pillar is 100 with no trial budget declared, so
the average is `64.2 + 0.35E`: 93 for `checked` (E = 83), 99 for the `exact` + `structured`
declaration (E = 100), 85 for `best-case` (E = 59, two of four checks measured). None of them
is capped, and none reads above WORKABLE: the two calibrated ones are held by the unread answer
key, `best-case` by its thin evaluation pillar. The execution scorer no longer reaches 99
either: uncalibrated, and with task fit credited at 8/25 for a scorer that runs the answer,
its pillar reads 59. The README's sections on `best-case` and on the source reader have the two
halves.
