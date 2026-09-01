#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Derive the committed 300-row Spider slice. Records how spider_300.jsonl was made.

Not needed to use this repository -- the slice and its databases are committed. Run this
only to reproduce or re-derive them, which requires the source Spider pool (see --source).

What it does, and why each step is there:

* Starts from the frozen 754-row ext pool, whose rows are already verified to appear
  verbatim in the official 1,034-row Spider dev set.
* Drops rows whose GOLD query returns an empty result set. Under execution accuracy an
  empty gold is gradeable by accident: any wrong-but-empty prediction matches it and
  scores 1.0. 35 of the 754 rows (4.6%) are like this. Keeping them would inflate every
  score by a few points for no reason. 719 rows survive.
* Labels difficulty with Spider's OWN official hardness classifier (the vendored
  `Evaluator.eval_hardness`, precomputed over the whole pool), rather than inventing a
  scale. Spider's `extra` is written `very-hard` here because that is the vocabulary the
  first-run readiness scorer recognises.
* Drops near-duplicate questions. Spider's dev set contains straight paraphrases -- "Show
  the names of all high schoolers in grade 10." and "What are the names of all high
  schoolers in grade 10?" are two rows asking one thing. Two rows like that survive into a
  300-row sample, and the first-run readiness check finds them and marks the data less
  diverse for it. The test is the same one that check uses: three-word shingles, Jaccard
  similarity, 0.7.
* Takes an equal 75 rows from each of the four bands so the set spans difficulty rather
  than piling up on `medium`, which is where the pool is heaviest.
* Splits within each band, not across it, so the holdout is as hard as the tuning data.
* Gives every row a stable id naming its position in the source pool, so a row can be
  traced back, and so excluding one from a run names something that does not move.

Output rows are flat -- `input` is the question, `output` is the gold SQL, and everything
else rides in `metadata`. The first-run tooling reads `input`/`output` as text; handing it
a nested object means the CREATE TABLE block ends up inside the row's identity string and
corrupts near-duplicate and split-family analysis.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import re
import shutil
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any

HERE = Path(__file__).resolve().parent

SEED = 42
PER_BAND = 75
HOLDOUT_PER_BAND = 15
BANDS = ("easy", "medium", "hard", "very-hard")
# Spider's leaderboard vocabulary -> the vocabulary the readiness scorer recognises.
HARDNESS_TO_DIFFICULTY = {
    "easy": "easy",
    "medium": "medium",
    "hard": "hard",
    "extra": "very-hard",
}
SOURCE_SLICE_NAME = "spider_dev_ext"

# The same shape of test the first-run dataset check applies to inputs.
SHINGLE_SIZE = 3
SIMILARITY_THRESHOLD = 0.7


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def gold_row_count(sql: str, db_file: Path, timeout_seconds: float = 5.0) -> int | None:
    """Rows the gold query returns, or None when it runs and fails.

    A database that is not there is a different problem from a query that does not run, and
    it stops the build rather than being reported as a broken recorded answer.
    """
    if not db_file.is_file():
        # sqlite3.connect would CREATE an empty database here, and every query against it
        # would then fail as though the recorded answer were wrong.
        raise SystemExit(f"source database missing: {db_file}")
    connection = sqlite3.connect(str(db_file), timeout=timeout_seconds)
    connection.text_factory = lambda raw: raw.decode("utf-8", "replace")
    try:
        return len(connection.execute(sql).fetchall())
    except sqlite3.Error:
        return None
    finally:
        connection.close()


def shingles(question: str) -> set[tuple[str, ...]]:
    """Overlapping three-word runs of a question, lowercased and punctuation-free."""
    words = re.findall(r"[a-z0-9]+", question.lower())
    if len(words) < SHINGLE_SIZE:
        return {tuple(words)}
    return {
        tuple(words[i : i + SHINGLE_SIZE]) for i in range(len(words) - SHINGLE_SIZE + 1)
    }


def drop_near_duplicates(
    candidates: list[tuple[int, dict[str, Any]]],
) -> tuple[list[tuple[int, dict[str, Any]]], int]:
    """The pool with paraphrases of an already-kept question removed.

    Returns the rows it keeps, paired with their pool index. Selecting the survivors by
    question text instead would re-admit every exact repeat of a kept question -- and two
    copies of one question can land on opposite sides of the tuning/holdout split, which is
    the contamination this step exists to prevent.

    Comparing every pair is fine at this size and avoids the early-stop behaviour that makes
    a bounded scan report an incomplete answer.
    """
    kept: list[tuple[int, dict[str, Any]]] = []
    kept_shingles: list[set[tuple[str, ...]]] = []
    dropped = 0
    for index, row in candidates:
        current = shingles(row["input"]["question"])
        duplicate = False
        for existing in kept_shingles:
            union = current | existing
            if union and len(current & existing) / len(union) >= SIMILARITY_THRESHOLD:
                duplicate = True
                break
        if duplicate:
            dropped += 1
            continue
        kept.append((index, row))
        kept_shingles.append(current)
    return kept, dropped


def load_difficulties(hardness_path: Path) -> dict[int, str]:
    """Official Spider hardness per source-pool row index, mapped to our vocabulary."""
    difficulties: dict[int, str] = {}
    for record in read_jsonl(hardness_path):
        if record.get("slice") != SOURCE_SLICE_NAME:
            continue
        if record.get("error"):
            raise SystemExit(
                f"hardness record {record.get('example')} carries an error; "
                "the classifier failed on it and a guessed band is worse than none"
            )
        hardness = record["hardness"]
        if hardness not in HARDNESS_TO_DIFFICULTY:
            raise SystemExit(f"unknown Spider hardness {hardness!r}")
        difficulties[int(record["example"])] = HARDNESS_TO_DIFFICULTY[hardness]
    return difficulties


def build(
    source_root: Path, hardness_path: Path, out_path: Path, db_dest: Path
) -> None:
    source_slice = source_root / "slices" / f"{SOURCE_SLICE_NAME}.jsonl"
    source_dbs = source_root / "slices" / "databases"
    for required in (source_slice, source_dbs, hardness_path):
        if not required.exists():
            raise SystemExit(f"source input missing: {required}")

    pool = read_jsonl(source_slice)
    difficulties = load_difficulties(hardness_path)
    if len(difficulties) != len(pool):
        raise SystemExit(
            f"hardness covers {len(difficulties)} rows but the pool has {len(pool)}; "
            "every row needs an official band"
        )

    usable: list[tuple[int, dict[str, Any]]] = []
    empty_gold = 0
    for index, row in enumerate(pool):
        db_id = row["output"]["db_id"]
        rows_returned = gold_row_count(
            row["output"]["sql"], source_dbs / db_id / f"{db_id}.sqlite"
        )
        if rows_returned is None:
            raise SystemExit(
                f"gold SQL failed to execute for pool row {index} on {db_id}; "
                "the pool is supposed to guarantee this, so do not filter around it"
            )
        if rows_returned == 0:
            empty_gold += 1
            continue
        usable.append((index, row))

    deduped, near_duplicates = drop_near_duplicates(usable)
    by_band: dict[str, list[tuple[int, dict[str, Any]]]] = {band: [] for band in BANDS}
    for index, row in deduped:
        by_band[difficulties[index]].append((index, row))

    print(
        f"pool={len(pool)} dropped-empty-gold={empty_gold} "
        f"dropped-near-duplicate={near_duplicates} usable={sum(len(v) for v in by_band.values())}"
    )
    for band in BANDS:
        print(f"  {band:<10} available={len(by_band[band])}")
        if len(by_band[band]) < PER_BAND:
            raise SystemExit(
                f"band {band} has {len(by_band[band])} usable rows, need {PER_BAND}"
            )

    rng = random.Random(SEED)
    selected: list[dict[str, Any]] = []
    for band in BANDS:
        chosen = sorted(by_band[band], key=lambda pair: pair[1]["input"]["question"])
        rng.shuffle(chosen)
        chosen = chosen[:PER_BAND]
        for position, (index, row) in enumerate(chosen):
            split = "holdout" if position < HOLDOUT_PER_BAND else "tuning"
            selected.append(
                {
                    "input": row["input"]["question"],
                    "output": row["output"]["sql"],
                    "metadata": {
                        "id": f"spider-dev-{index:04d}",
                        "db_id": row["input"]["db_id"],
                        "schema": row["input"]["schema"],
                        "split": split,
                        "difficulty": band,
                        "provenance": "real",
                    },
                }
            )

    selected.sort(key=lambda r: (r["metadata"]["difficulty"], r["input"]))
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in selected:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")

    needed = sorted({row["metadata"]["db_id"] for row in selected})
    # Rebuilt from scratch, because a slice needing fewer databases than the last one would
    # otherwise leave the extras behind and nothing downstream looks for extras. Only the
    # per-database directories are removed, and only from a path that is named `databases`:
    # --databases takes a path from whoever runs this, and an unguarded tree delete on it
    # would happily take the rows file, this script, or the source pool it reads from.
    db_dest = db_dest.resolve()
    if db_dest.exists():
        if db_dest.name != "databases":
            raise SystemExit(
                f"refusing to rewrite {db_dest}: --databases must name a directory called "
                "'databases', because its contents are deleted and rebuilt"
            )
        if db_dest == source_dbs.resolve() or db_dest in source_dbs.resolve().parents:
            raise SystemExit(
                f"refusing to rewrite {db_dest}: it holds the source databases this build "
                "reads from"
            )
        for existing in db_dest.iterdir():
            if existing.is_dir() and not existing.is_symlink():
                shutil.rmtree(existing)
    db_dest.mkdir(parents=True, exist_ok=True)
    for db_id in needed:
        target = db_dest / db_id
        target.mkdir(exist_ok=True)
        shutil.copy2(source_dbs / db_id / f"{db_id}.sqlite", target / f"{db_id}.sqlite")

    digest = hashlib.sha256(out_path.read_bytes()).hexdigest()
    splits = Counter(row["metadata"]["split"] for row in selected)
    bands = Counter(row["metadata"]["difficulty"] for row in selected)
    print(f"\nwrote {out_path} rows={len(selected)} sha256={digest}")
    print(f"  splits={dict(splits)}")
    print(f"  bands={dict(bands)}")
    print(f"  databases={len(needed)} -> {db_dest}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument(
        "--source",
        type=Path,
        required=True,
        metavar="DIR",
        help="the Spider benchmark directory holding slices/ (the 754-row ext pool and its databases)",
    )
    parser.add_argument(
        "--hardness",
        type=Path,
        required=True,
        metavar="FILE",
        help="hardness.jsonl from the official vendored Spider classifier",
    )
    parser.add_argument("--out", type=Path, default=HERE / "spider_300.jsonl")
    parser.add_argument("--databases", type=Path, default=HERE / "databases")
    args = parser.parse_args(argv)
    build(args.source.resolve(), args.hardness.resolve(), args.out, args.databases)
    return 0


if __name__ == "__main__":
    sys.exit(main())
