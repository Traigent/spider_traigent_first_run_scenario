<!--
SPDX-FileCopyrightText: 2018 Yu et al., Spider 1.0 contributors
SPDX-License-Identifier: Apache-2.0 AND CC-BY-SA-4.0
-->

# The data

Every question in this repository comes from **Spider 1.0**.

> Yu, Zhang, Yang, Yasunaga, Wang, Li, Ma, Li, Yao, Roman, Zhang and Radev.
> *Spider: A Large-Scale Human-Labeled Dataset for Complex and Cross-Domain Semantic Parsing
> and Text-to-SQL Task.* EMNLP 2018.
> [arXiv:1809.08887](https://arxiv.org/abs/1809.08887) ·
> [yale-lily.github.io/spider](https://yale-lily.github.io/spider)

Spider is the standard cross-domain text-to-SQL benchmark: people wrote questions about
databases covering many different subjects, and paired each with the SQL that answers it.
Cross-domain is the interesting part -- the databases in the evaluation split are not the
ones in the training split, so a model cannot succeed by memorising one schema.

This is real recorded data. Not generated, not synthetic, not written for this repository.

## Licence

**CC BY-SA 4.0.** The code in this repository is Apache-2.0; the data is not, and the two
are not interchangeable.

ShareAlike means an adaptation of this data that you share carries the same licence.
`spider/LICENSE-DATA` carries the attribution, the licence in full, and the list of changes
made to the original. That obligation travels with the data: a project built from these rows
carries `ATTRIBUTION.txt` beside them.

The two files are the same obligation in two forms. `LICENSE-DATA` is the repository's copy and
is specific -- 18 of 20 databases, 35 of 754 rows dropped, seed 42 -- and it reproduces the
complete CC BY-SA 4.0 legal deed, all eight sections, not the summary. `ATTRIBUTION.txt` is
what a generated project gets, states the *kinds* of modification rather than counts that would
go stale against a smaller draw, points at the licence by URI, and names nothing about where it
came from. Neither is optional and neither is decoration.

The licence boundary is a boundary of **content, not of directory**, and `NOTICE` says so.
Spider questions and gold queries are quoted verbatim well outside `spider/` -- in the
calibration cases under `components/calibration/`, in the tests, in `build_slice.py`'s
docstrings, and in this file. Adding a Spider question to a new file tomorrow takes the licence
with it.

## What is committed

| | |
|---|---|
| `spider/spider_300.jsonl` | 300 questions with their queries, 459,193 bytes |
| `spider/databases/` | the 18 SQLite databases those questions ask about, 917,504 bytes |
| `spider/datasheet.yaml` | provenance, hashes, licence, and the nine known flaws, in machine-readable form |
| `spider/provenance.json` | what the last build wrote, and therefore what the next one is allowed to overwrite |
| `spider/REUSE.toml` | machine-readable licensing for everything under `spider/`, for files that cannot carry a comment |
| `spider/LICENSE-DATA` | attribution, the record of changes, and the full CC BY-SA 4.0 text |
| `spider/build_slice.py` | how the 300 were chosen, and how to redo it |

1,376,697 bytes in total. That is small enough to commit, which is the point: a clone can build
a working demo with no download and no network.

The slice hashes to
`f7fa90e46cccf171366b0e54789a286058cd8da0b4fbb9362741f9664c975827`, recorded twice and
independently -- in `datasheet.yaml` and in `provenance.json` -- so a rewrite that updated one
and not the other shows up as a disagreement rather than as a silent edit.

Spider's full database set is about 840 MB across 166 databases and is **not** redistributed
here. Spider's development split spans 20 databases; these 300 rows use 18 of them, and the
two that are missing are missing for different reasons. `wta_1` is about 105 MB, and the pool
these rows were drawn from was already restricted to databases under 5 MB, so it and its
questions never entered that pool. `museum_visit` is small enough, but it is not in the pool
either: the 754 rows are the development rows left over on the databases the upstream
benchmark harness had already committed, and `museum_visit` was not one of those. Neither
database was dropped by anything below -- there were no rows from either one to drop.

## A row

A real one, `spider-dev-0650`, with the `schema` field abbreviated:

```json
{"input": "Show name, country, age for all singers ordered by age from the oldest to the youngest.",
 "output": "SELECT name ,  country ,  age FROM singer ORDER BY age DESC",
 "metadata": {"id": "spider-dev-0650",
              "db_id": "concert_singer",
              "schema": "CREATE TABLE \"concert\" ( ... );",
              "split": "tuning",
              "difficulty": "medium",
              "provenance": "real"}}
```

The double spacing in `output` is Spider's, not a typo here. Nothing about a recorded query is
reformatted; the scorers normalise on the way in instead.

`input` and `output` are plain text. That is deliberate, and it is not cosmetic: the
first-run tooling reads those two fields as text and serialises anything else it finds. A
nested input would put the entire `CREATE TABLE` block inside the row's identity string, and
then every question about the same database looks like a near-duplicate of every other one.

Re-measured on 2026-09-02, by rebuilding these same 300 rows with the question, schema and
`db_id` nested under `input` and running the guide's `preflight.py` over both forms:

| | flat (shipped) | nested |
|---|---|---|
| `dataset-near-duplicates` | **PASS** -- "no input pair reaches 70% similarity" | **WARN** -- pairs listed, and "the scan stopped early, so there may be more" |
| `dataset-split-family` | 24 recurring input forms, 15 shared across the split | 18 forms, 16 shared -- and the forms are database names |

The nested form does not finish the scan. The flat form finishes it and finds what is really
there.

Everything else rides in `metadata`, where the evaluator can still reach it and no
similarity check reads it.

| field | |
|---|---|
| `id` | `spider-dev-NNNN`, the row's position in the source pool. Stable, so excluding a row from a run names something that does not move. |
| `db_id` | which database the question is about. |
| `schema` | that database's `CREATE TABLE` text, checked to match the database actually shipped. |
| `split` | `tuning` (240) or `holdout` (60). |
| `difficulty` | `easy`, `medium`, `hard` or `very-hard`. |
| `provenance` | `real`. These are recorded human-written rows, and saying so is what makes the readiness score treat them as evidence rather than as a demonstration. |

## How the 300 were chosen

From a frozen 754-row pool, each of whose rows was checked to appear verbatim -- database,
question and query -- in the official 1,034-row Spider development set.

**Every recorded query must run.** All 754 do.

**Every recorded query must return at least one row.** 35 did not, and were dropped. This one
matters more than it looks. Under execution scoring, a query whose correct answer is "no
rows" is passed by any wrong answer that also returns nothing -- including a query that fails
to find anything for entirely the wrong reason. 4.6% of the pool was gradeable by accident.

**No question may be a paraphrase of one already kept.** Two more were dropped. Spider's
development set contains straight restatements -- *"Show the names of all high schoolers in
grade 10."* and *"What are the names of all high schoolers in grade 10?"* are one question
asked twice. The test is the same one the first-run readiness check uses: three-word
shingles, Jaccard similarity, 0.7.

That test is **lexical only**, and the datasheet records it as a known flaw rather than as a
guarantee. It catches a restatement that reuses words and misses one that does not: *"Count
the number of countries in Asia."* and *"how many countries are in Asia?"* share no three-word
run and share a gold query exactly. What actually separates such rows is the gold-query
grouping below, not the shingle count -- so do not read the shingle number as a diversity
claim.

**No gold query may cross the split.** This is the filter the paraphrase test cannot be. Rows
are grouped by their gold query, and a group goes wholly to one side; tuning and holdout share
**0** gold queries, byte-identical or normalised, and **0** holdout rows share a gold with
another holdout row.

That was not true before 2026-09-02, and the datasheet keeps the old number so a figure
measured before the re-cut is not compared with one measured after. In the previous draw, **15
of the 60 holdout rows (25%)** had a gold byte-identical to a tuning row's -- 7 of the 15
very-hard rows, 4 easy, 2 hard, 2 medium -- and two holdout rows shared a gold with each other.
A configuration that few-shots from tuning, or retrieves on `db_id`, got up to a quarter of the
holdout pre-answered.

**What could not be fixed, and is recorded instead.** The slice is not gold-unique. 4 gold
queries appear twice, 8 rows in all, **every one of them inside the very-hard tuning set**.
That band offers only 71 distinct gold queries in the 717-row filtered pool, and 75 rows per
band are wanted, so 75x4 is reachable only by letting 4 very-hard rows be a second question for
a gold already in the band. A slice that is *both* 75x4 and fully gold-unique is not available
from this pool at all: the alternatives are 296 rows unbalanced, or 284 with every band held
down to 71. Those 8 rows are 8 questions and 4 answers, so a configuration that few-shots from
tuning can see the same answer twice; none of them can reach the holdout. `build_slice.py`
prints this rather than hiding it.

**Difficulty comes from Spider, not from us.** Each query is classified by Spider's own
official hardness function, the one the leaderboard uses, which reads the structure of the
query. It is **run** here over each row's gold query -- the vendored `Evaluator.eval_hardness`,
with the classifier files' own sha256s recorded in `provenance.json` -- rather than joined in
from a precomputed table by row position, so a relabelling shows up as a classifier change.
Spider's `extra` band is written `very-hard` here only because that is the word the readiness
scorer recognises.

**The 300 are balanced across those four bands**, 75 each, drawn from a pool that is
naturally heaviest on `medium`. An unbalanced set makes every configuration look similar,
because most of the questions are the same difficulty.

**The split is made within each band**, 60 tuning and 15 held out per band. Splitting across
bands can hold out only easy questions, and a winner checked against those has not really
been checked.

## What it will not support

`spider/datasheet.yaml` records **nine** known flaws in machine-readable form. These are the
ones that change how a number from this data should be read.

**Spider is saturated.** Its own authors built Spider 2.0 because 1.0 stopped separating
strong models from each other. A high score here is a sanity check, not a capability claim.

**It is almost certainly in the training data.** The development set is reproduced in
hundreds of papers and in the corpora modern models were trained on. Treat any absolute
number from it as contaminated. Comparisons between configurations on the same rows are
still informative; the absolute level is not. No filter here can touch this: it is
contamination of the original data against model pretraining.

**Execution scoring is not semantic correctness.** Two different queries can return the same
rows on one database by coincidence. Dropping empty-result queries removes the worst version
of this. It does not remove it.

**Execution accuracy is cheap to score by accident, and here is the shape of it.** **127 of the
300 gold queries -- 42.3% -- return a single scalar**: one row, one column. There are 89
distinct such values, so no constant answer gets far; the best single constant scores **7 of
300, 2.3%**, and two values tie for it, `0` and `3`. The exposure is not the constant. It is
that a wrong query returning the right count is indistinguishable from a right one, and on four
rows in ten that is all the answer is.

**The paraphrase filter is lexical only**, and the gold-query grouping is what actually
separates the rows. See [How the 300 were chosen](#how-the-300-were-chosen).

**The holdout is small, and per-database readings of it are noise.** 60 rows, 15 per band:
**one row is 6.7 percentage points** within a band, and about 1.7 across the whole holdout.
Band balance is exact, and that is the claim being made. Nothing about per-database performance
is: **six of the 18 databases hold two or fewer holdout rows, and two hold none at all**
(`orchestra` and `real_estate_properties`). Reading the holdout by database is reading noise.

**The slice is not gold-unique**, and the residual is 4 golds over 8 rows, all on the tuning
side. Again: [How the 300 were chosen](#how-the-300-were-chosen).

**300 rows is a demonstration size.** It is enough to separate configurations. It is not enough
to settle a question about production, and a result from it should not be reported as though it
were.

## Rebuilding it

Rarely needed -- the slice is committed. It requires the source pool, which is not part of
this repository:

```bash
python3 spider/build_slice.py --source <spider-benchmark-dir>
```

It is deterministic: same inputs, same 300 rows, same order. `spider/datasheet.yaml` records
the hash of the result, and a test fails if the two ever disagree.

`--hardness <hardness.jsonl>` is still accepted and no longer supplies labels. Difficulty is
derived by running the vendored classifier over each gold query; passing a table makes it a
cross-check, and a disagreement stops the build rather than being resolved silently.

**It refuses to delete what it did not create.** `provenance.json` is the record of what the
last run wrote, and it is also the permission slip: the next run may overwrite exactly the rows
file and exactly the database directory entries that file names, and nothing else. A `databases`
directory holding somebody's own work is refused, symlinks are refused at every step, and
anything not in the record is a stranger. `--force` overrides that and says in its own help
text that it deletes other people's files. The guard used to ask whether a path was *called*
`databases`, which any directory can be called; a thesis folder was deleted for having the
name, and that is why the question is now "did this script put these bytes here?" instead.
