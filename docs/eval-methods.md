# The SQL scorers

`--eval` picks how an answer gets marked. Two of the choices are the real scoring methods, and
they disagree about what a right answer is; the disagreement is not a detail. `slow` compares
text too, more narrowly, and asks a service to do it one row at a time, two minutes a call, so
it is right and too slow to check inside the guide's fifteen-minute calibration budget -- a
guided run on it waits that whole budget before the card can be read. The other four -- `broken`, `swapped`, `opaque` and
`length-blind` -- are what a project arrives with when its scorer is not one, and `missing` is a
project with no scorer at all; each is described at the end.

## `exact-match` -- compare the text

The query is read one character at a time -- not with regular expressions -- and the
differences that never matter are removed: comments, surrounding and internal spacing, a
trailing semicolon, and the case of everything **outside** a quoted string. Case *inside* a
string is kept, because `'France'` and `'france'` are different values even though `SELECT` and
`select` are the same keyword. That distinction is the reason for the character-by-character
read: a regex that folds case "outside quotes" has to decide where the quotes are, and an
apostrophe in a comment is enough to make it decide wrong.

Comments are dropped because the `query_plan_cot` setting asks the model to think in them,
and keeping them marked a correct answer wrong for having planned. The execution scorer
ignores them for free, so dropping them here is what makes the two rulers agree.

**A double-quoted token is read both ways.** SQL uses double quotes for two different things --
around a name, and, in SQLite wherever no column of that name exists, around a string -- and
which one a query meant depends on the table definitions, which this scorer never opens. So
rather than guess once and be wrong half the time, each query is rendered twice: once with
every double-quoted token taken as a value, once with it taken as a column name, unquoted and
case-folded. An answer scores 1.0 when *either* reading makes the two queries the same text,
and the two readings are never crossed. Measured:

| answer | recorded | |
|---|---|---|
| `SELECT "name" FROM t` | `SELECT name FROM t` | **1.0** |
| `... c = "France"` | `... c = 'France'` | **1.0** |
| `... c = 'france'` | `... c = "France"` | **0.0** -- a different value |
| `SELECT b, a FROM t` | `SELECT a, b FROM t` | **0.0** -- the documented under-count |

Backquoted and `[bracketed]` names carry no ambiguity and fold to the plain name. One residual
survives and the file names it rather than claiming it away: `SELECT "name"` also matches
`SELECT 'name'`, one asking for a column and the other for a constant, because the value
reading makes them the same text and nothing here knows whether a column called `name` exists.
Resolving that means reading the schema, and this scorer never opens the database.

**It refuses a query it cannot read rather than healing it.** A query that opens a string, a
delimited name or a block comment and never closes it raises `UnreadableQuery`; on the answer
side that is caught and scored 0.0, on the recorded side it is re-raised, because an answer
cannot be graded against a query that is not one. Both ways of carrying on regardless invent
text the model did not write -- closing the quote at the end hands a cut-off answer the value
it never finished, dropping what an unclosed comment swallowed hands it whatever the recorded
query has there -- and both inventions tend to match. Note the bound precisely: it is
unterminated **quotes, delimited names and block comments** that are refused, not malformed SQL
in general. Unbalanced parentheses are not delimiters and pass through to a mismatch.

Its limit is honest and known: `SELECT a, b FROM t` and `SELECT b, a FROM t` return exactly
the same thing, and this marks the second one wrong. A model that answers correctly in a
different formulation is scored as having failed. It under-counts. In exchange, the scorer
touches nothing: no database, no subprocess, no model output reaching anything that can act
on it. It is the default.

## `exec-match` -- run both and compare the rows (Spider's own metric)

Run the generated query and the recorded one against the database, compare the rows as a
multiset, and ignore order unless the recorded query asked for an order. This is how Spider
itself is scored, and it is the right measure of a SQL answer: it credits a correct query
written differently, which is most of what the text comparison gets wrong.

It gets there by executing SQL that a model wrote. There is no version of execution scoring
that does not. What the scorer does instead is bound the damage, on a local copy of a small
database:

| bound | value |
|---|---|
| opened read-only | `file:...?mode=ro` |
| authoriser | only `SQLITE_SELECT`, `SQLITE_READ`, `SQLITE_RECURSIVE`; every other action denied |
| function allow-list | 114 named read-only functions; anything else denied by name, including `load_extension`, `sqlite_version` and the `fts3_tokenizer` family |
| wall-clock watchdog | 5 seconds, enforced by a timer that calls `connection.interrupt` |
| row cap | 100,000 rows, checked before each row is kept |
| accumulated bytes | 64 MB across the whole result, checked before each row is kept |
| single value | `SQLITE_LIMIT_LENGTH` 1 MB |
| result columns | `SQLITE_LIMIT_COLUMN` 128 |

The last two are set inside SQLite, so they refuse before anything is allocated rather than
after. Measured on 2026-09-02: `SELECT randomblob(900000000)` as a candidate answer returns
`string or blob too big` in **1.1 ms** with a **13.2 MB** peak, against **2.40 s** and
**1728 MB** for the same query through a plain connection with none of these bounds. The
watchdog is a different bound and does fire: a recursive CTE that returns one row and spins
stops at **5.001 s**, still at 13 MB.

None of that changes what execution scoring is. It bounds the blast radius of a query the model
wrote; it does not make running it something other than running it.

## Why this is the interesting flag

Execution accuracy is how Spider is scored: every figure on its leaderboard and in its
literature is that measure. So this is the faithful ruler for this data. The first-run guide
does not calibrate an executing evaluator on its own initiative. `references/run-safety.md`
is explicit: a scorer that "executes or imports candidate/model output as code, shells out
with it, or submits it to a code or SQL engine" is not calibrated by the guide, which records
a `containment` warning, discloses in your words what was not checked, and continues. The paid
trial executes your evaluator against your engine after that disclosure, and you get one
optional question whether the evaluator connects read-only.

So the presets ask different questions:

- **`--preset ready`** (exact-match) asks whether a guided first run works end to end.
- **`--preset sql-exec-stop`** (exec-match) asks whether the run correctly skips calibrating
  the executing evaluator, discloses what was not checked, offers the copied-actor route to
  calibrate a read-only copy, and still prices the paid run -- when the project is a perfectly
  ordinary text-to-SQL project whose evaluator executes candidate output.

The second is the more interesting test, because of what is below.

## A measured problem with the scoring

The rule is now enforced by three scripts: `preflight.py` walks the evaluator for engine and
process constructs and reports them; `calibrate_evaluator.py` refuses (exit 2) to import a
scorer whose walk reaches a code or SQL engine; and `readiness.py` raises an
`evaluator-calibration-refused` cap when the declaration or preflight witnesses an engine.
None of that was true at the revision the problem below was measured at, and the problem is
kept here because the guide's answer to it is the point.

Measured against the first-run guide at revision
`6ec2b9c161400cd91faea9c8cdb1c4e00d21c8d9` (`6ec2b9c1`) on 2026-09-02.

> **Every readiness figure in this section is that 2026-09-02 reading, and the tool has since
> moved.** The score bank was regenerated at `e4096e3a` on 2026-09-15, re-taken unchanged at
> `5ce65540` on 2026-09-17 and unchanged again at `d07b62cd` -- the current cards are
> under [`docs/measurements/cards/`](measurements/README.md) and the current table is in the
> repository README -- and since `9eaabbb2` the run behind the 91 EXCELLENT number is refused
> by the calibration tool; since `e4096e3a` `checked` reads 93 and the declared pair 99, and both are held
> at WORKABLE until the expected answers are read. The numbers in this section are not
> republished as current; they are the reading the guide's later changes answered.

| declared method | task kind | task-fit | evaluation pillar | calibrated |
|---|---|---|---|---|
| `execution` | `code-sql` | **25.0 / 25** | 51 | **99** |
| `normalized-exact` | `code-sql` | **8.0 / 25** | 33 | **83** |

This table is a 6ec2b9c1 reading from 2026-09-02. At HEAD, commit 20dfb79d and later
changed credit to require proof from the file; the 25/25 arm is no longer reachable by
declaration alone. The guide answered this finding: execution now earns TASK_FIT_UNFIT_CREDIT
(8/25) on code-sql whether proven or declared, and a `sql-structure` method fits code-sql.

The evidence strings at that earlier reading were `"execution suits code-sql output"` and
`"normalized-exact is a poor ruler for code-sql output"`. Both readings were defensible --
execution really is the better ruler for SQL. At the time they meant the score rewarded
declaring the evaluator the guide forbids, on the task kind this whole repository is about,
by **17 points of task fit**: 25.0/25 against 8.0/25.

Three different numbers follow from that, and it is worth keeping them apart.

- **17 points of task fit**, out of 25. That is the sub-score above, and it is the size of
  the reward for the declaration.
- **16 points of evaluation pillar**, out of 100. Task fit is one input to that pillar;
  calibrated, the two rows come out at 99 and 83.
- **5 points of overall score.** The evaluation pillar carries 35% of the overall weight, so
  those 16 pillar points are worth 5.6 of it: with calibration on both, the text comparator
  reads **86 STRONG** and the execution scorer reads **91 EXCELLENT**, and the only difference
  between them is which scorer they ship.

Five points is the distance between the two bands this project can reach, not sixteen. It is
still decisive, because of where the boundary sits: at dataset 98 and agent 70, EXCELLENT
needs an evaluation pillar of **94**, and the text comparator's calibrated ceiling is 83 -- so
the highest band this project can read was only available to the evaluator the guide will not
calibrate on its own initiative.

At the opening card, the guide opens calibration only when "the complete path does not execute
candidate-generated code or SQL", so an executing evaluator is not calibrated there. But the
copied-actor route now allows calibrating a COPY of that evaluator under `traigent-runs/calibration/`
against a customer-supplied read-only or duplicate target, at Setup sequence step 7 after the
`.env` handoff. Additionally, the top two bands are now held at WORKABLE without a `--row-review`
of the graded rows, so even a fully calibrated evaluator on an unreviewed card does not read
above WORKABLE. The README's section on `best-case` details this constraint.

Three further findings from the 6ec2b9c1 reading, now answered at HEAD:

- **The score follows the declaration, not the file.** At 6ec2b9c1 the number was driven by the
  `--evaluator-method` string alone. This is now checked: task fit is derived from what preflight's
  walk proves about the file ("what the file does outranks what was declared about it, because the
  file is the thing that will run"). An executing file, an unproven execution declaration, and an
  unproven or refuted comparison shape all withhold credit. The declaration is no longer the measure.
- **No bundled script detects SQL execution.** At 6ec2b9c1, static inspection said it "proves nothing
  about its scoring behavior, which is not executed here". Preflight now walks the evaluator for
  engine and process constructs (sqlite3, sqlalchemy, duckdb, data-frame `.sql()`, …) and reports
  them. A witness proves execution; absence proves nothing. Calibration refuses on the witness.
- **No containment cap is emitted.** At 6ec2b9c1 no cap was raised. The guide now raises
  `evaluator-calibration-refused` (non-blocking) with action `confirm-evaluator-connection` when
  the declaration names `execution` or preflight witnesses an engine. Re-measure to quote the card.
- **A matched pair of declarations buys the top band.** At 6ec2b9c1, the `exact` + `structured`
  pair read 92 EXCELLENT on a purely textual comparator with no caps. At HEAD the card still
  credits the pair, and says so -- `exact suits structured output (declared, not established
  from the evaluator file)` -- but it no longer buys a band: STRONG and EXCELLENT are held at
  WORKABLE until a `--row-review` covering the graded rows has entered, whatever the evaluator
  or its calibration, and in this bank the agent ceiling holds all four combinations at 45.
  This grid is a 6ec2b9c1 reading.

## What that means for this repository

Nothing here works around it. `--eval exec-match` builds exactly the project a real
text-to-SQL customer would bring, and `demo.json` records
`"executes_candidate_output": true` so a run can be described accurately afterwards. A test
asserts that flag matches what the source actually imports, so the manifest cannot drift
from the file.

Both questions have since been answered by the guide: the boundary is enforced by preflight's
evaluator walk (`df05d61c`) and by the calibration tool refusing on its witness (`93f996b5`),
and task-fit credit is earned from the evaluator file rather than the declared pair
(`20dfb79d`), which is what takes execution on `code-sql` down to 8/25. This repository's
`exec-match` project remains the way to watch that boundary in action.
**The table above is a 6ec2b9c1 reading from one revision on one date.** Re-measure before
quoting any number.

## Checking the scorer

`--calibration present` ships the probe answers a project keeps for its own scorer -- for
each case a right answer, an equivalent one, a partly-right one and a wrong one -- and the
guide's `calibrate_evaluator.py` measures whether the scorer separates them. That is what
clears `evaluator-unvalidated`. At the 6ec2b9c1 reading this was worth **41 points** to the
opening card: `--preset ready` read 45 and `--preset checked`, the identical project with the
probes shipped, read 86. Since `e4096e3a` `ready` reads 45 under the `evaluator-unvalidated`
ceiling and `checked` 93, so the same probes are worth 48 points at the opening -- and the band
above WORKABLE additionally waits for a row review. The 41-point figure is a 6ec2b9c1 reading.

The two methods get different probes, because equivalence means different things to them.
The text comparator gets 4 cases and is given re-spellings of a recorded query: different
spacing, quote style, keyword case, a trailing semicolon. The execution scorer gets 3 and is
given queries written differently that return the same rows: an alias, an `IN` with one
element, an implicit `ASC`. `slow` compares text more narrowly than the text comparator and
gets 4 cases of its own, which pin what it really accepts. Handing either method the other's
probes would measure the wrong thing and report a known limit as a defect. Every case comes from a real row of the slice, named by
`row_id` and byte-identical to it in both question and gold query, all from the tuning split,
and every probe query was executed against the shipped databases before being written down.

Measured: `exact-match` passes all 4, `exec-match` passes all 3, `broken` **fails** all 4 --
it returns 1.0 for the wrong-answer probe -- and `swapped` **fails**, from the other direction,
returning 0.0 for the right one. `length-blind` **fails** a third way: the right answer scores
1.0, and the wrong answer -- about as long -- scores between 0.81 and 1.0 across the four
cases, where the calibrator holds a binary case's wrong answer at or under 0.2. On one case
the right and wrong probes tie at 1.0; what keeps it apart from the constant scorer is that the
four probes of a case never all tie (`non_constant` true on every case), so it is refused for
letting the wrong answer through, not for scoring everything alike. All three land on the same `evaluator-invalid`
cap at ceiling 25 with `repair-evaluator`. That is why cases ship for the broken scorers too.
`opaque` gets none, and `--calibration present` is refused for it: its grader is a library the
project does not carry, so nothing here has ever run it and nothing could vouch for the probes.

**The gate the guide puts in front of this is the reason `best-case` opens where it does.**
Calibration is opened at the opening gate only when the complete path does not execute
candidate-generated code or SQL, so the execution scorer never reaches it and its
`evaluator-unvalidated` ceiling stands. The `--allow-execution` flag is still required to
import any scorer, but the tool now walks the scorer and any `--reply-transform` module first
and refuses (exit 2) to import one whose walk reaches a code or SQL engine, naming file and
line. Only `--calibrated-copy-of` admits engine witnesses -- and only for a copy under
`traigent-runs/calibration/` repointed at a customer-supplied read-only or duplicate target.
The gate has become a check.

## `broken`, `swapped`, `opaque`, `length-blind` and `missing`

`--eval broken` ships a scorer that returns full marks for everything -- all four of its
arguments arrive and none is read. Every configuration measures the same, so any comparison
between them is meaningless, and a run that trusts it reports a confident improvement that did
not happen. It is there to see whether that gets noticed before anything is spent, and it is
what `--preset fake-ruler` ships.

`--eval swapped` ships the mirror image: a scorer that reads the *question* and the recorded
query and never looks at what the model produced at all. A question is never the SQL that
answers it, so every row scores zero and every configuration ties at the bottom. Nothing it
compares depends on the answer, which is why no amount of running it can tell two answers
apart. It is what `--preset wrong-wiring` ships, and without probe answers its card is
byte-identical to `--preset ready`'s.

`--eval opaque` ships a scorer that hands both queries to `sqlgrade`, a grading library the
project does not carry -- `from sqlgrade.compare import QueryGrader`, in the voice of a team
that had one shared at work. It parses, it has never been run here, and it cannot be: what
it does is what that library does. `demo.json` records `method: null` and
`executes_candidate_output: null` for it, both meaning unknown, and the sweep passes no
`--evaluator-method` for it, because none could be declared honestly. The guide answers an
undeclared method with `evaluator-unresolved` (40, blocks): "An evaluator file is connected,
but no method could be honestly declared for it without executing it". It is what `--preset
opaque-scorer` ships.

`--eval length-blind` ships `1 - abs(len(output) - len(expected)) / len(expected)`, clipped to
`[0, 1]`: a scorer that moves, and never for the right reason. It is not one of the methods
the guide names -- a comparison of lengths is not `normalized-exact`, and declaring the nearest
word would credit the file with a comparison it does not make -- so `demo.json` records
`method: null` for it too, and the sweep declares nothing. It imports nothing and runs nothing,
so `executes_candidate_output` is `false`. With the text comparator's probes beside it,
calibration runs and fails (`evaluator-invalid`, 25, blocks); without them it reads the same
`evaluator-unresolved` 40 as `opaque`. It is what `--preset length-blind` ships.

`--eval missing` ships no evaluator at all, which is a more honest starting point than it
sounds -- most projects do not have one.
