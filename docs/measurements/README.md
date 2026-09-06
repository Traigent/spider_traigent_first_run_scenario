# The measurements behind the score table

Every readiness figure quoted in this repository was produced here, and everything needed to
reproduce it is in this directory: the script, the two hand-written agent reads it needs, and
the captured invocation and full output of every run.

**Measured against the first-run guide at revision
`6ec2b9c161400cd91faea9c8cdb1c4e00d21c8d9` (`6ec2b9c1`), on 2026-09-02, on Python 3.12.3.**
Re-measure before quoting these anywhere that matters -- they are a reading of one revision of
somebody else's tool on one date, and the tool is under active development.

## These figures have drifted, and a regeneration is pending

> **Read this before quoting any number in this repository.** The tool moved. The same sweep,
> unchanged, was re-run on 2026-09-06 against the guide's `first-run-guide` trunk at `6e18086e`
> and did not return this table. What changed there, measured rather than guessed:
>
> - the **agent pillar reads 0** on every run instead of 70. The guide's static read no longer
>   follows any of the four declared settings from the agent's source to the request, so
>   `agent-no-varying-knobs` 45 now appears on almost every card. The citations in
>   `agent-knobs/` are accepted and quoted back onto the card; it is the route check behind
>   them that changed.
> - **`checked` and the four `grid-*` runs open at 45 PARTIAL**, not 86 STRONG and 92 EXCELLENT.
>   `hand-written` opens at 45, not 74. `wrong-answers--calibrated` at 45, not 83.
> - several runs that read `proceed` now read `complete-calibration`, and several that read
>   PARTIAL now read NOT READY: `no-labels` 30 PARTIAL is 19 NOT READY, and `logs-only`'s
>   action moves from `label-data` to `connect-agent`.
> - **two of this repository's own criticisms of the guide have been answered, and both are
>   listed here rather than only the flattering ones.** `no-agent` -- the project with no agent
>   at all, quoted below and in the README as opening 45 PARTIAL `proceed` -- now opens **25 NOT
>   READY `connect-agent`**, with an `agent-absent` cap. `ready--without-agent-knobs`, the run
>   whose point was that withholding the agent read changes nothing, likewise opens **25 NOT
>   READY `connect-agent`** rather than the same 45 as `ready`.
> - **`best-case--off-method-calibration` cannot be measured at all.** The guide now refuses to
>   calibrate a scorer that reaches a SQL engine, which is the finding that run existed to
>   make, made better by the tool itself.
>
> The drift is in the tool being measured. Nothing about the projects in this repository
> changed, and the sweep still completes -- at `6e18086e`, which is not the revision this
> directory pins; see [Reproducing it](#reproducing-it) for what that costs a reader today.
>
> **Nothing has been re-measured here on purpose.** Several changes to the guide are in flight
> and about to land; a table regenerated ahead of them would be stale the day it merged. The
> regeneration is a separate, deliberate step -- re-pin `PINNED_REVISION`, run the sweep, and
> rewrite this table and the prose keyed to it from `cards/results.json`. Until it lands, every
> score, band, action, pillar and cap quoted anywhere in this repository is a reading of
> `6ec2b9c1` on 2026-09-02 and is not what today's guide returns.

## Reproducing it

**The pin and the documents beside it currently describe two different guides, and this is where
that shows.** The `--agent-knobs` documents under `agent-knobs/` carry `source_lines` on every
settled `build` check. `6ec2b9c1`, the revision every figure below was measured at, does not
read that field and refuses a document carrying it; `6e18086e` reads it and requires it. So the
sweep runs at `6e18086e` and is refused at the pin, and the command below names the revision it
actually runs at:

```bash
git clone https://github.com/Traigent/traigent-first-run ~/code/traigent-first-run
git -C ~/code/traigent-first-run checkout 6e18086e1499baa3c66a7c0ebeedebdc887d4f0c

python3 docs/measurements/score_bank.py --guide ~/code/traigent-first-run \
    --revision 6e18086e1499baa3c66a7c0ebeedebdc887d4f0c
```

It builds each project, scores it, deletes it, and writes a card for each. It needs nothing
installed, reaches no network, and never uses `--venv ready`. On this machine the whole sweep
takes about two minutes. **It does not reproduce the table below** -- see the drift note above;
it reproduces today's reading, which is what a reader checking this directory should expect to
see until the regeneration lands and re-pins both.

**It leaves `cards/` alone.** The cards are committed evidence, and the usual reason to run this
script is to check them, so the run writes into its workspace and prints where. Replacing them
is a separate, explicit act:

```bash
python3 docs/measurements/score_bank.py --guide ~/code/traigent-first-run \
    --revision 6e18086e1499baa3c66a7c0ebeedebdc887d4f0c --publish
```

`--publish` replaces the committed directory of every run that produced a card, and leaves alone
the directory of any run that did not: a refused run reaches two or three files before the
refusal, and moving those over its committed card would delete the rendered card and the `argv`
record with it -- four files that this revision cannot produce again, because the refusal is now
the guide's settled answer for that run.

Point the sweep at `6ec2b9c1` instead and it stops before it builds anything, naming the checks
and the field the two disagree about, and leaves `cards/` untouched. That guard is the point:
the two facts -- which revision is pinned, and which contract the documents are written for --
are independently editable, and this directory has now broken in both directions by letting them
drift apart silently. The check reads `readiness.py`'s own field lists
(`AGENT_KNOBS_DOCUMENT_FIELDS`, `DISCOVERED_KNOB_FIELDS`, `BUILD_CHECK_FIELDS`) from whichever
checkout it is handed, so *which fields a document may carry* is settled by the guide rather than
by a copy of its rules kept here. One thing it cannot read that way: **which fields are
required**, because the guide expresses that in its control flow rather than as data. So
`source_lines` is named in `score_bank.py`, next to a comment saying it is the one hardcoded
coordinate in the check -- and if a revision renames a field list, the run says on stderr that
that half of every document went unchecked rather than passing in silence.

**Exit status:** 0 when every run scored, 1 when the guide refused one or more, 2 when the
documents and the guide disagree, 3 when something of ours broke -- our builder, our probe. The
last never records a row and never publishes: `build.py` failing says nothing about the guide,
and a sweep that cannot measure has no business rewriting the evidence of what the guide
answered when it could.

## What is here

| | |
|---|---|
| `score_bank.py` | the whole measurement. Its docstring states every choice it makes and why |
| `agent-knobs/ready.json` | the read of the tunable agent's source that the opening score requires |
| `agent-knobs/no-knobs.json` | the same read of the fixed agent: a completed read that found no knobs |
| `cards/<run>/01-build.txt` | the `build.py demo` invocation and its output |
| `cards/<run>/02-preflight.json` | `preflight.py --json` output, which is `readiness.py --preflight`'s input |
| `cards/<run>/03-calibration.json` | `calibrate_evaluator.py --json` output, where calibration ran |
| `cards/<run>/04-readiness-card.txt` | **the rendered card** -- the thing the documentation quotes |
| `cards/<run>/05-readiness.json` | the same score machine-readable: pillars, sub-scores, caps |
| `cards/<run>/argv.json` | every invocation, with this machine's paths replaced by `$GUIDE`, `$PROJECT`, `$KNOBS`, `$EVIDENCE` |
| `cards/results.json` | one row per run: score, band, action, pillars, caps, what was declared. A run that could not be scored -- the guide refused it, or the step it needed returned no JSON -- carries a `refused` object naming the step, the exit status and that step's own first line instead of a score, and the sweep continues past it: one row lost rather than the bank. The reason is where the two are told apart (`Refusing to calibrate: ...` is the guide declining; `cannot read scoring input: ...` is an input of ours it would not read) |

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

Seventeen presets, then the comparisons the documentation makes:

| run | what it is for |
|---|---|
| the 17 presets | the score table in the README |
| `best-case--off-method-calibration` | the number reached by calibrating an executing scorer, which the guide's opening gate bars |
| `wrong-answers--calibrated` | `--preset wrong-answers --calibration present` |
| `wrong-wiring--calibrated` | `--preset wrong-wiring --calibration present` |
| `fake-ruler--uncalibrated` | `--preset fake-ruler --calibration none` |
| `ready--without-agent-knobs` | the same project scored with the agent read withheld |
| `grid-*` | the four declared-method x declared-task-kind combinations, all on the same unchanged text comparator |

## Results

**Every row below is the 2026-09-02 reading at `6ec2b9c1`, and many of them no longer
reproduce** -- see [the drift note above](#these-figures-have-drifted-and-a-regeneration-is-pending)
before quoting one.

Pillar weights are the default 40 dataset / 35 evaluation / 25 agent. `*` marks a cap that
blocks (the card prints `FIX BEFORE PAID RUN`); the others are ceilings only.

| run | score | band | action | agent | dataset | evaluation | caps |
|---|---|---|---|---|---|---|---|
| `empty` | 0 | NOT READY | `get-data` | 0 | 0 | 0 | `dataset-absent` 20\* · `evaluator-absent` 40\* · `agent-no-varying-knobs` 45 |
| `logs-only` | 7 | NOT READY | `label-data` | 0 | 18 | 0 | `dataset-no-expected-outputs` 30\* · `evaluator-absent` 40\* · `agent-no-varying-knobs` 45 |
| `no-data` | 20 | NOT READY | `get-data` | 70 | 0 | 33 | `dataset-absent` 20\* · `evaluator-unvalidated` 45 |
| `agent-and-logs` | 25 | NOT READY | `label-data` | 70 | 18 | 0 | `dataset-no-expected-outputs` 30\* · `evaluator-absent` 40\* |
| `fake-ruler` | 25 | NOT READY | `repair-evaluator` | 70 | 98 | 28 | `evaluator-invalid` 25\* |
| `no-labels` | 30 | PARTIAL | `label-data` | 70 | 18 | 33 | `dataset-no-expected-outputs` 30\* · `evaluator-unvalidated` 45 |
| `duplicated-data` | 35 | PARTIAL | `repair-dataset` | 70 | 86 | 33 | `dataset-integrity-fail` 35\* · `evaluator-unvalidated` 45 |
| `no-eval` | 40 | PARTIAL | `connect-evaluator` | 70 | 98 | 0 | `evaluator-absent` 40\* |
| `no-knobs` | 45 | PARTIAL | `vary-knobs` | 0 | 98 | 33 | `evaluator-unvalidated` 45 · `agent-no-varying-knobs` 45\* |
| `ready` | 45 | PARTIAL | `proceed` | 70 | 98 | 33 | `evaluator-unvalidated` 45 |
| `sql-exec-stop` | 45 | PARTIAL | `proceed` | 70 | 98 | 51 | `evaluator-unvalidated` 45 |
| `no-agent` | 45 | PARTIAL | `proceed` | 0 | 98 | 33 | `evaluator-unvalidated` 45 · `agent-no-varying-knobs` 45 |
| `wrong-answers` | 45 | PARTIAL | `proceed` | 70 | 91 | 33 | `evaluator-unvalidated` 45 |
| `wrong-wiring` | 45 | PARTIAL | `proceed` | 70 | 98 | 33 | `evaluator-unvalidated` 45 |
| `best-case` | 45 | PARTIAL | `proceed` | 70 | 98 | 51 | `evaluator-unvalidated` 45 |
| `hand-written` | 74 | WORKABLE | `add-examples` | 70 | 75 | 83 | `dataset-below-measurable-size` 74 |
| `checked` | 86 | STRONG | `proceed` | 70 | 98 | 83 | none |
| `best-case--off-method-calibration` | **91** | **EXCELLENT** | `proceed` | 70 | 98 | 99 | none |
| `wrong-answers--calibrated` | 83 | STRONG | `proceed` | 70 | 91 | 83 | none |
| `wrong-wiring--calibrated` | 25 | NOT READY | `repair-evaluator` | 70 | 98 | 28 | `evaluator-invalid` 25\* |
| `fake-ruler--uncalibrated` | 45 | PARTIAL | `proceed` | 70 | 98 | 33 | `evaluator-unvalidated` 45 |
| `ready--without-agent-knobs` | 45 | PARTIAL | `proceed` | 0 | 98 | 33 | `evaluator-unvalidated` 45 · `agent-no-varying-knobs` 45 |
| `grid-exact--code-sql` | 86 | STRONG | `proceed` | 70 | 98 | 83 | none |
| `grid-normalized-exact--code-sql` | 86 | STRONG | `proceed` | 70 | 98 | 83 | none |
| `grid-normalized-exact--structured` | 86 | STRONG | `proceed` | 70 | 98 | 83 | none |
| `grid-exact--structured` | **92** | **EXCELLENT** | `proceed` | 70 | 98 | 100 | none |

The band boundaries the guide uses, for reading the column: NOT READY 0-29, PARTIAL 30-54,
WORKABLE 55-74, STRONG 75-89, EXCELLENT 90-100.

## Three cards that are identical to another card

Worth stating because each one is a finding rather than a coincidence. Each is checkable
directly -- the first line of `04-readiness-card.txt` is the invocation that produced it, which
names its own paths, so compare from the second line down:

```bash
cd docs/measurements/cards
diff <(tail -n +2 ready/04-readiness-card.txt) <(tail -n +2 wrong-wiring/04-readiness-card.txt)
```

- `wrong-wiring` and `ready` -- **byte-identical**. A scorer that never reads the model's output
  is invisible to the opening gate.
- `best-case` and `sql-exec-stop` -- **byte-identical**. Once the guide's own gate keeps
  calibration off an executing scorer, shipping probe answers for one changes nothing at the
  opening.
- `wrong-answers` and `ready` -- **not** identical, and the three differences are all about
  size rather than about the damage: dataset pillar 91 against 98, `60/60 rows` against
  `300/300`, and the comparison-size check dropping from `OK` to `!!` because a 60-row draw is
  48 tuning rows. Every check that could have noticed the answers are wrong passes.

## The arithmetic at the top of the scale

At the `ready` family's dataset 98 and agent 70, the overall score is
`0.40x98 + 0.35xE + 0.25x70 = 56.7 + 0.35E`. EXCELLENT starts at 90, so it needs an evaluation
pillar of **94** or better. The text comparator's calibrated evaluation pillar is **83**, which
is 86 overall; the execution scorer's is 99, which is 91. That is the whole of the gap, and it
is why no honest configuration in this bank opens EXCELLENT: see the README's section on
`best-case`.
