# The measurements behind the score table

Every readiness figure quoted in this repository was produced here, and everything needed to
reproduce it is in this directory: the script, the two hand-written agent reads it needs, and
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

It builds each project, scores it, deletes it, and writes a card for each. It needs nothing
installed, reaches no network, and never uses `--venv ready`. On this machine the whole sweep
takes about two minutes.

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

**One run cannot be measured at `d07b62cd`.** `best-case--off-method-calibration` asks the
calibration tool to run the execution scorer against the project's databases, and the tool now
refuses to import a scorer whose walk reaches a SQL engine (exit 2). The sweep records the
refusal in `results.json` and leaves `cards/best-case--off-method-calibration/` as it was: the
`6ec2b9c1` card, 91 EXCELLENT, kept as the evidence for a number the README no longer prints
and a run the guide no longer performs.

The sweep checks one more thing before it builds anything: that the documents under
`agent-knobs/` carry only fields the guide at the pin reads. It reads `readiness.py`'s own
field lists from the checkout it is handed, so *which fields a document may carry* is settled
by the guide rather than by a copy of its rules kept here; which fields are *required* the
guide expresses in control flow rather than as data, so `source_lines` is the one hardcoded
coordinate in the check, named in `score_bank.py` beside a comment saying so. At `d07b62cd`
the documents and the pin agree, which is why the command above needs no `--revision`.

**Exit status:** 0 when every run scored, 1 when the guide refused one or more, 2 when the
documents and the guide disagree, 3 when something of ours broke -- our builder, our probe. The
last never records a row and never publishes: `build.py` failing says nothing about the guide,
and a sweep that cannot measure has no business rewriting the evidence of what the guide
answered when it could.

## What is here

| | |
|---|---|
| `score_bank.py` | the whole measurement. Its docstring states every choice it makes and why. It is in CI's `black`/`ruff`/`mypy --strict` targets and its behaviour is held by [`tests/test_score_bank.py`](../../tests/test_score_bank.py): it has twice destroyed the evidence in `cards/` while reporting that it could not measure anything, and a repair nothing tests is a repair the next edit can quietly undo |
| `agent-knobs/ready.json` | the read of the tunable agent's source that the opening score requires |
| `agent-knobs/no-knobs.json` | the same read of the fixed agent: a completed read that found no knobs |
| `cards/<run>/01-build.txt` | the `build.py demo` invocation and its output |
| `cards/<run>/02-preflight.json` | `preflight.py --json` output, which is `readiness.py --preflight`'s input |
| `cards/<run>/03-calibration.json` | `calibrate_evaluator.py --json` output, where calibration ran |
| `cards/<run>/04-readiness-card.txt` | **the rendered card** -- the thing the documentation quotes |
| `cards/<run>/05-readiness.json` | the same score machine-readable: pillars, sub-scores, caps |
| `cards/<run>/argv.json` | the build, preflight and readiness invocations, with this machine's paths replaced by `$GUIDE`, `$PROJECT`, `$KNOBS`, `$EVIDENCE`. A calibrated run records `calibration_ran` here and its argv in `03-calibration-stderr.txt`, which is where `slow-scorer`'s `--timeout 5` -- the flag its cap depends on -- is written down |
| `cards/results.json` | one row per run: score, band, action, pillars, caps, what was declared. A run that could not be scored -- the guide refused it, or the step it needed returned no JSON -- carries a `refused` object naming the step, the exit status and that step's own first line instead of a score, and the sweep continues past it: one row lost rather than the bank. The reason is where the two are told apart (`Refusing to calibrate: ...` is the guide declining; `cannot read scoring input: ...` is an input of ours it would not read) |

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

Two things follow, and both are properties of this table rather than of the guide:

- **A run scored without that document reads the same 45 for `ready` and says less.**
  `cards/ready--without-agent-knobs/` is that run: 45 PARTIAL `proceed`, unchanged, because the
  `evaluator-unvalidated` ceiling binds first either way. What changes is the agent pillar,
  70 to 0, and a second cap appearing -- `agent-no-varying-knobs`, ceiling 45. The card says
  "no reading of how the agent is built reached this score" five times. That is the tool
  reporting that it was not given what it asked for, not a second opinion about the project.
- **`--row-review` is not passed.** The guide asks for one at the opening gate, and it is the
  assistant's own read of every row: does this expected output answer this input? A
  hand-written stand-in would be this script deciding that question row by row, which is
  exactly the judgement `--preset wrong-answers` exists to test. Leaving it off keeps the table
  mechanical and leaves the finding below intact.

## What the sweep covers

Thirty-one presets, then the comparisons the documentation makes. One preset the
sweep names only through a variant -- `slow-scorer`, because it carries a non-default
calibration budget -- so this table has thirty-one preset runs and fourteen
comparisons against `build.py`'s thirty-two presets:

| run | what it is for |
|---|---|
| the 31 presets | the score tables in the README |
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
| `slow-scorer` | `--preset slow-scorer` with `--timeout 5` on the calibration step. The guide budgets a deterministic calibration at 900 seconds, so reaching the timeout question the default way costs a quarter of an hour of every reproduction; the budget is stated instead, and the card records the one it was reached under |
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
| `grid-exact--code-sql` | 93 | WORKABLE | `review-answer-key` | 100 | 98 | 83 | none |
| `grid-normalized-exact--structured` | 93 | WORKABLE | `review-answer-key` | 100 | 98 | 83 | none |
| `grid-normalized-exact--code-sql` | 93 | WORKABLE | `review-answer-key` | 100 | 98 | 83 | none |
| `grid-exact--structured` | 99 | WORKABLE | `review-answer-key` | 100 | 98 | 100 | none |

The band boundaries the guide uses, for reading the column: NOT READY 0-29, PARTIAL 30-54,
WORKABLE 55-74, STRONG 75-89, EXCELLENT 90-100.

## What the nine ported presets measured

Eight of the nine opened on the cap they were built for. The ninth did not, and one other
thing did not happen either; both are worth writing down.

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
- **The two scorers that are not scorers land where the guide's ladder puts them.** With no
  `--evaluator-method` declared -- the only honest declaration for either --
  `opaque-scorer` reads `evaluator-unresolved` 40, blocks; `length-blind` with probes reads
  `evaluator-invalid` 25, blocks, from a calibration that ran and failed
  (`non_constant` true, `bad_fails` false on every case), and without them the same 40
  `unresolved` as `opaque`.

## The cards that are identical to another card

Worth stating because each one is a finding rather than a coincidence: where two starting
states produce the same card, the guide's opening read did not distinguish them. Fifteen of the
forty-nine cards fall into the six groups below. Each is checkable directly -- the first line
of `04-readiness-card.txt` is the invocation that produced it, which names its own paths, so
compare from the second line down:

```bash
cd docs/measurements/cards
diff <(tail -n +2 ready/04-readiness-card.txt) <(tail -n +2 wrong-wiring/04-readiness-card.txt)
```

This list is not maintained by hand. `tests/test_score_bank.py` recomputes the groups from the
committed cards and compares them with `IDENTICAL_CARDS`, so a round that creates a new
identical pair and does not say so here goes red -- which is how the `opaque-scorer` pair below
came to be written down at all.

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
  `connect-agent`: no agent and an agent with nothing to vary read alike here.
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
