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

ShareAlike means an adaptation of this data that you share carries the same licence. That
obligation travels with the data, so `spider/LICENSE-DATA` is copied into every generated
project beside the rows, and it needs to stay with them anywhere else they go.
`spider/LICENSE-DATA` carries the attribution, the licence, and the list of changes made to
the original.

## What is committed

| | |
|---|---|
| `spider/spider_300.jsonl` | 300 questions with their queries, ~450 KB |
| `spider/databases/` | the 18 SQLite databases those questions ask about, ~900 KB |
| `spider/datasheet.yaml` | provenance, hashes, licence, and the flaws below, in machine-readable form |
| `spider/build_slice.py` | how the 300 were chosen, and how to redo it |

About 1.4 MB in total. That is small enough to commit, which is the point: a clone can build
a working demo with no download and no network.

Spider's full database set is about 840 MB across 166 databases and is **not** redistributed
here. Spider's development split spans 20 databases; these 300 rows use 18 of them, and the
two that are missing are missing for different reasons. `wta_1` is about 105 MB, and the pool
these rows were drawn from was already restricted to databases under 5 MB, so it and its
questions never entered that pool. `museum_visit` is small enough, but it is not in the pool
either: the 754 rows are the development rows left over on the databases the upstream
benchmark harness had already committed, and `museum_visit` was not one of those. Neither
database was dropped by anything below -- there were no rows from either one to drop.

## A row

```json
{"input": "How many singers are from each country?",
 "output": "SELECT country, count(*) FROM singer GROUP BY country",
 "metadata": {"id": "spider-dev-0042",
              "db_id": "concert_singer",
              "schema": "CREATE TABLE singer ( ... );",
              "split": "tuning",
              "difficulty": "medium",
              "provenance": "real"}}
```

`input` and `output` are plain text. That is deliberate, and it is not cosmetic: the
first-run tooling reads those two fields as text and serialises anything else it finds. A
nested input would put the entire `CREATE TABLE` block inside the row's identity string, and
then every question about the same database looks like a near-duplicate of every other one.
Measured, on this data: the nested form reports 1,000 near-duplicate pairs implicating 165
of 300 rows and gives up before finishing, and its "task families" turn out to be database
names. The flat form finishes the scan and finds what is really there.

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

**Difficulty comes from Spider, not from us.** Each query is classified by Spider's own
official hardness function, the one the leaderboard uses, which reads the structure of the
query. Spider's `extra` band is written `very-hard` here only because that is the word the
readiness scorer recognises.

**The 300 are balanced across those four bands**, 75 each, drawn from a pool that is
naturally heaviest on `medium`. An unbalanced set makes every configuration look similar,
because most of the questions are the same difficulty.

**The split is made within each band**, 60 tuning and 15 held out per band. Splitting across
bands can hold out only easy questions, and a winner checked against those has not really
been checked.

## What it will not support

**Spider is saturated.** Its own authors built Spider 2.0 because 1.0 stopped separating
strong models from each other. A high score here is a sanity check, not a capability claim.

**It is almost certainly in the training data.** The development set is reproduced in
hundreds of papers and in the corpora modern models were trained on. Treat any absolute
number from it as contaminated. Comparisons between configurations on the same rows are
still informative; the absolute level is not.

**Execution scoring is not semantic correctness.** Two different queries can return the same
rows on one database by coincidence. Dropping empty-result queries removes the worst version
of this. It does not remove it.

**300 rows is a demonstration size.** With 60 held out, one example moves a held-out score by
about 1.7 percentage points. That is enough to tell configurations apart. It is not enough to
settle a question about production, and a result from it should not be reported as though it
were.

## Rebuilding it

Rarely needed -- the slice is committed. It requires the source pool, which is not part of
this repository:

```bash
python spider/build_slice.py --source <spider-benchmark-dir> --hardness <hardness.jsonl>
```

It is deterministic: same inputs, same 300 rows, same order. `spider/datasheet.yaml` records
the hash of the result, and a test fails if the two ever disagree.
