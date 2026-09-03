#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2026 Traigent Ltd
# SPDX-FileCopyrightText: 2018 Spider 1.0 contributors, for the questions quoted below
# SPDX-License-Identifier: Apache-2.0 AND CC-BY-SA-4.0
"""Derive the committed 300-row Spider slice. Records how spider_300.jsonl was made.

Not needed to use this repository -- the slice and its databases are committed. Run this
only to reproduce or re-derive them, which requires the source Spider pool (see --source).

What it does, and why each step is there:

* Starts from the frozen 754-row ext pool, whose rows are already verified to appear
  verbatim in the official 1,034-row Spider dev set. Rows are copied out byte for byte;
  this script chooses WHICH rows ship, never what a row says.
* Drops rows whose GOLD query returns an empty result set. Under execution accuracy an
  empty gold is gradeable by accident: any wrong-but-empty prediction matches it and
  scores 1.0. 35 of the 754 rows (4.6%) are like this. Keeping them would inflate every
  score by a few points for no reason. 719 rows survive.
* Labels difficulty by RUNNING Spider's own official hardness classifier (the vendored
  `Evaluator.eval_hardness`) over each gold query, rather than joining a precomputed table
  by row position. Spider's `extra` is written `very-hard` here because that is the
  vocabulary the first-run readiness scorer recognises.
* Drops near-duplicate questions. Spider's dev set contains straight paraphrases -- "Show
  the names of all high schoolers in grade 10." and "What are the names of all high
  schoolers in grade 10?" are two rows asking one thing. The test is the same one the
  first-run readiness check uses: three-word shingles, Jaccard similarity, 0.7.
* Groups what is left by NORMALISED GOLD SQL and treats a group as one item. Spider pairs
  most gold queries with more than one phrasing of the question, so lexical paraphrase
  detection is not enough: "Count the number of countries in Asia." and "how many countries
  are in Asia?" share no three-word shingle and share a gold query exactly. A group is
  assigned to one split as a whole, so no gold query is ever both tuned on and held out.
* Takes an equal 75 rows from each of the four bands so the set spans difficulty rather
  than piling up on `medium`, which is where the pool is heaviest. Within a band the first
  15 gold-groups become the holdout and the rest the tuning set, so the holdout is as hard
  as the tuning data AND internally free of repeated gold queries.
* Gives every row a stable id naming its position in the source pool, so a row can be
  traced back, and so excluding one from a run names something that does not move.

Destructive steps are confined by PROVENANCE, not by a path's name. The script rewrites
only what a `provenance.json` written by an earlier run of this script says it put there,
and refuses anything else unless `--force` is given deliberately. A directory called
`databases` full of somebody's work is not this script's output and is not treated as such.

Output rows are flat -- `input` is the question, `output` is the gold SQL, and everything
else rides in `metadata`. The first-run tooling reads `input`/`output` as text; handing it
a nested object means the CREATE TABLE block ends up inside the row's identity string and
corrupts near-duplicate and split-family analysis.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import random
import re
import shutil
import sqlite3
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable

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

# Written beside the rows file. It is what makes a later run of this script allowed to
# overwrite anything: a destination is rewritable only where this record says this script
# created it and it has not been touched since.
PROVENANCE_NAME = "provenance.json"
PROVENANCE_FORMAT = 1

# The vendored official classifier, relative to --source. Its sha256s go into the
# provenance record so a relabelling is visible as a change of classifier, not a mystery.
CLASSIFIER_SUBDIR = "vendor_testsuite_eval"
CLASSIFIER_MODULES = ("process_sql", "evaluation")


class BuildRefused(SystemExit):
    """A refusal to touch something this build did not create."""

    def __init__(self, message: str) -> None:
        super().__init__(f"refusing: {message}")


def read_jsonl(path: Path) -> list[dict[str, Any]]:
    with path.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def sha256_of(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


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


def normalised_gold(sql: str) -> str:
    """A gold query reduced to what makes two rows the same question to answer.

    Case, run-length of whitespace and a trailing semicolon are spelling. Two rows whose
    gold queries differ only in those are one item: answer one and you have answered the
    other, which is exactly what must not straddle the tuning/holdout line.
    """
    return re.sub(r"\s+", " ", sql.strip().rstrip(";").strip()).lower()


def drop_near_duplicate_questions(
    candidates: list[tuple[int, dict[str, Any]]],
) -> tuple[list[tuple[int, dict[str, Any]]], int]:
    """The pool with lexical paraphrases of an already-kept question removed.

    Returns the rows it keeps, paired with their pool index. This catches restatements that
    reuse most of their words. It does NOT catch a paraphrase that shares no three-word run
    with the row it restates, which is why gold-query grouping happens as well and is what
    the split is actually built on.

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


def group_by_gold(
    candidates: list[tuple[int, dict[str, Any]]],
) -> list[list[tuple[int, dict[str, Any]]]]:
    """Rows bucketed by normalised gold query, in first-seen pool order.

    Every bucket is one item as far as the split is concerned. Its first member -- the
    lowest pool index -- is the one that ships when only one row of the bucket is wanted,
    so the choice does not move when the pool is rebuilt in the same order.
    """
    buckets: dict[str, list[tuple[int, dict[str, Any]]]] = {}
    for index, row in candidates:
        buckets.setdefault(normalised_gold(row["output"]["sql"]), []).append(
            (index, row)
        )
    return list(buckets.values())


def load_hardness_classifier(classifier_dir: Path) -> Callable[[str, Path], str]:
    """Spider's own `Evaluator.eval_hardness`, loaded out of the vendored copy.

    Deriving the label from the gold query is the whole point: a precomputed table joined by
    row position cannot tell a correct label from one that slid onto the wrong record, since
    the key it is checked against travels inside the record it is checking.
    """
    if not classifier_dir.is_dir():
        raise SystemExit(
            f"vendored Spider classifier not found at {classifier_dir}; "
            "pass --classifier with the directory holding evaluation.py and process_sql.py"
        )
    modules: dict[str, Any] = {}
    for name in CLASSIFIER_MODULES:
        source = classifier_dir / f"{name}.py"
        if not source.is_file():
            raise SystemExit(f"vendored Spider classifier is missing {source}")
        if str(classifier_dir) not in sys.path:
            sys.path.insert(0, str(classifier_dir))
        spec = importlib.util.spec_from_file_location(name, source)
        if spec is None or spec.loader is None:
            raise SystemExit(f"cannot load {source}")
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        modules[name] = module

    evaluator = modules["evaluation"].Evaluator()
    schema_of = modules["process_sql"].Schema
    read_schema = modules["process_sql"].get_schema
    parse_sql = modules["process_sql"].get_sql
    cache: dict[str, Any] = {}

    def hardness(sql: str, db_file: Path) -> str:
        key = str(db_file)
        if key not in cache:
            if not db_file.is_file():
                raise SystemExit(f"source database missing: {db_file}")
            cache[key] = schema_of(read_schema(str(db_file)))
        label: str = evaluator.eval_hardness(parse_sql(cache[key], sql))
        return label

    return hardness


def derive_difficulties(
    pool: list[dict[str, Any]], source_dbs: Path, classifier_dir: Path
) -> list[str]:
    """One official band per pool row, computed from that row's own gold query.

    No key, no join, nothing to slide out of alignment: the label is a function of the bytes
    it labels. A gold the official parser cannot read stops the build rather than being
    guessed at, because a wrong band silently changes which rows the slice is made of.
    """
    hardness = load_hardness_classifier(classifier_dir)
    derived: list[str] = []
    for index, row in enumerate(pool):
        db_id = row["output"]["db_id"]
        try:
            label = hardness(
                row["output"]["sql"], source_dbs / db_id / f"{db_id}.sqlite"
            )
        except SystemExit:
            raise
        except Exception as error:  # the official parser, on a row it cannot read
            raise SystemExit(
                f"the official Spider classifier could not read the gold query of pool row "
                f"{index} on {db_id}: {type(error).__name__}: {error}. A guessed band is "
                "worse than none."
            ) from error
        if label not in HARDNESS_TO_DIFFICULTY:
            raise SystemExit(f"unknown Spider hardness {label!r} for pool row {index}")
        derived.append(HARDNESS_TO_DIFFICULTY[label])
    return derived


def cross_check_difficulties(hardness_path: Path, derived: list[str]) -> int:
    """Compare a precomputed hardness table against the labels just derived.

    Optional, and never a source of labels. It exists so that a stale or reordered table is
    reported instead of quietly disagreeing with the slice that ships.
    """
    recorded: dict[int, str] = {}
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
        recorded[int(record["example"])] = HARDNESS_TO_DIFFICULTY[hardness]
    if len(recorded) != len(derived):
        raise SystemExit(
            f"{hardness_path} covers {len(recorded)} rows of slice {SOURCE_SLICE_NAME} but "
            f"the pool has {len(derived)}; it is not a table for this pool"
        )
    disagreements = [i for i, label in enumerate(derived) if recorded[i] != label]
    if disagreements:
        shown = ", ".join(
            f"{i}: table says {recorded[i]}, gold query says {derived[i]}"
            for i in disagreements[:5]
        )
        raise SystemExit(
            f"{len(disagreements)} of {len(derived)} rows are labelled differently by "
            f"{hardness_path} than by the gold query itself ({shown}). The gold query is "
            "the authority; the table is stale or misaligned."
        )
    return len(recorded)


# ------------------------------------------------------------------ destination guarding


def read_provenance(record_path: Path) -> dict[str, Any] | None:
    """The record an earlier run of this script left, or None when there is not one.

    A record that cannot be read is the same as no record: it grants no permission to
    delete anything.
    """
    if not record_path.is_file() or record_path.is_symlink():
        return None
    try:
        record = json.loads(record_path.read_text(encoding="utf-8"))
    except (ValueError, OSError):
        return None
    if not isinstance(record, dict) or record.get("format") != PROVENANCE_FORMAT:
        return None
    if record.get("builder") != Path(__file__).name:
        return None
    return record


def _recorded_path(record: dict[str, Any], section: str, base: Path) -> Path | None:
    entry = record.get(section)
    if not isinstance(entry, dict):
        return None
    recorded = entry.get("path")
    if not isinstance(recorded, str):
        return None
    return (base / recorded).resolve()


def approve_output_file(
    out_path: Path, record: dict[str, Any] | None, record_dir: Path, force: bool
) -> None:
    """Refuse to overwrite a rows file this script did not write and has not seen since."""
    if out_path.is_symlink():
        raise BuildRefused(
            f"{out_path} is a symbolic link; writing it would write through to whatever it "
            "points at, which is outside the tree this build owns"
        )
    if not out_path.exists():
        return
    if not out_path.is_file():
        raise BuildRefused(f"{out_path} exists and is not a regular file")
    if force:
        return
    mine = (
        record is not None
        and _recorded_path(record, "slice", record_dir) == out_path
        and isinstance(record.get("slice"), dict)
        and record["slice"].get("sha256") == sha256_of(out_path)
    )
    if not mine:
        raise BuildRefused(
            f"{out_path} already exists and no {PROVENANCE_NAME} beside it records this "
            "build as having written those exact bytes. It is somebody's file until proven "
            "otherwise -- write somewhere else, or pass --force to overwrite it deliberately"
        )


def approve_database_directory(
    db_dest: Path,
    source_dbs: Path,
    record: dict[str, Any] | None,
    record_dir: Path,
    force: bool,
) -> list[str]:
    """The entries in db_dest this build is allowed to delete. Refuses rather than guesses.

    The old guard asked whether the path was *called* `databases`, which any directory can
    be called, and a thesis folder with chapters in it was deleted for having the name. What
    matters is whether this script put the contents there, so that is what is checked: a
    destination may be absent, empty, or exactly the set of directories a previous run
    recorded in `provenance.json`. Anything else is somebody's data.

    `--force` widens this to "clear the destination", which is a thing a person can ask for
    on purpose. It never widens to following a symbolic link out of the tree.
    """
    resolved_source = source_dbs.resolve()
    if db_dest == resolved_source or db_dest in resolved_source.parents:
        raise BuildRefused(
            f"{db_dest} holds, or contains, the source databases this build reads from"
        )
    if db_dest.is_symlink():
        raise BuildRefused(
            f"{db_dest} is a symbolic link; rebuilding it would write through to whatever "
            "it points at"
        )
    if not db_dest.exists():
        return []
    if not db_dest.is_dir():
        raise BuildRefused(f"{db_dest} exists and is not a directory")

    present = sorted(entry.name for entry in db_dest.iterdir())
    if not present:
        return []
    linked = sorted(e.name for e in db_dest.iterdir() if e.is_symlink())
    if linked:
        # Skipping these and then copying into them is how a symlinked `car_1` ends up
        # overwriting a file outside the output tree.
        raise BuildRefused(
            f"{db_dest} contains symbolic links ({', '.join(linked[:5])}); this build will "
            "not delete them and must not write through them either"
        )
    if force:
        return present

    mine: list[str] = []
    if (
        record is not None
        and _recorded_path(record, "databases", record_dir) == db_dest
    ):
        entry = record.get("databases")
        if isinstance(entry, dict) and isinstance(entry.get("entries"), list):
            mine = [name for name in entry["entries"] if isinstance(name, str)]
    strangers = sorted(set(present) - set(mine))
    if strangers:
        raise BuildRefused(
            f"{db_dest} holds {len(strangers)} entries no run of this script put there "
            f"({', '.join(strangers[:5])}{'...' if len(strangers) > 5 else ''}). Its "
            "contents are deleted and rebuilt, so it must be empty, or hold only what a "
            f"{PROVENANCE_NAME} beside the rows file says this build wrote. Point "
            "--databases at a fresh directory, or pass --force to clear this one"
        )
    return sorted(set(present) & set(mine))


def clear_recorded_entries(db_dest: Path, entries: list[str]) -> None:
    """Delete exactly the named entries, and never through a link."""
    for name in entries:
        target = db_dest / name
        if target.is_symlink():
            raise BuildRefused(f"{target} became a symbolic link mid-build")
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()


def copy_database(source: Path, target_dir: Path, db_id: str) -> None:
    """Copy one SQLite file in, refusing to write through a link at either step."""
    if target_dir.is_symlink():
        raise BuildRefused(f"{target_dir} is a symbolic link; not writing through it")
    target_dir.mkdir(exist_ok=True)
    target = target_dir / f"{db_id}.sqlite"
    if target.is_symlink():
        raise BuildRefused(f"{target} is a symbolic link; not writing through it")
    shutil.copy2(source, target)


# ------------------------------------------------------------------------------- build


def select_band(
    band: str, groups: list[list[tuple[int, dict[str, Any]]]], rng: random.Random
) -> tuple[list[tuple[int, dict[str, Any], str]], int]:
    """75 rows of one band, split so that no gold query is on both sides of the line.

    Groups are shuffled, the first 15 become the holdout one row each, and the tuning set is
    drawn from the rest. Where a band has fewer than 75 distinct gold queries the shortfall
    is filled with further members of groups already on the TUNING side -- never a holdout
    one -- and the count is printed, because a band quietly made of fewer distinct answers
    than it looks is the sort of thing this file exists to not do.
    """
    ordered = sorted(groups, key=lambda group: group[0][1]["input"]["question"])
    rng.shuffle(ordered)
    if len(ordered) < HOLDOUT_PER_BAND:
        raise SystemExit(
            f"band {band} has {len(ordered)} distinct gold queries, and the holdout needs "
            f"{HOLDOUT_PER_BAND} that appear nowhere else"
        )
    chosen: list[tuple[int, dict[str, Any], str]] = []
    for group in ordered[:HOLDOUT_PER_BAND]:
        index, row = group[0]
        chosen.append((index, row, "holdout"))
    tuning_groups = ordered[HOLDOUT_PER_BAND:]
    for group in tuning_groups:
        if len(chosen) == PER_BAND:
            break
        index, row = group[0]
        chosen.append((index, row, "tuning"))
    repeated_golds = 0
    if len(chosen) < PER_BAND:
        for group in tuning_groups:
            for index, row in group[1:]:
                if len(chosen) == PER_BAND:
                    break
                chosen.append((index, row, "tuning"))
                repeated_golds += 1
            if len(chosen) == PER_BAND:
                break
    if len(chosen) < PER_BAND:
        raise SystemExit(f"band {band} can supply {len(chosen)} rows, need {PER_BAND}")
    return chosen, repeated_golds


def build(
    source_root: Path,
    classifier_dir: Path,
    out_path: Path,
    db_dest: Path,
    hardness_path: Path | None,
    force: bool,
) -> None:
    source_slice = source_root / "slices" / f"{SOURCE_SLICE_NAME}.jsonl"
    source_dbs = source_root / "slices" / "databases"
    required: list[Path] = [source_slice, source_dbs]
    if hardness_path is not None:
        required.append(hardness_path)
    for needed_path in required:
        if not needed_path.exists():
            raise SystemExit(f"source input missing: {needed_path}")

    out_path = out_path.resolve()
    db_dest = db_dest.resolve()
    if out_path == source_slice.resolve():
        raise BuildRefused(f"{out_path} is the source pool this build reads from")
    record_dir = out_path.parent
    record_path = record_dir / PROVENANCE_NAME
    record = read_provenance(record_path)
    approve_output_file(out_path, record, record_dir, force)
    removable = approve_database_directory(
        db_dest, source_dbs, record, record_dir, force
    )
    # Kept for the downstream contract rather than for safety: the rest of the repository
    # and every generated project look for a directory spelled `databases`.
    if db_dest.exists() and db_dest.name != "databases":
        raise BuildRefused(
            f"{db_dest}: --databases must name a directory called 'databases', because "
            "everything downstream reads the databases under that name"
        )

    pool = read_jsonl(source_slice)
    pool_digest = sha256_of(source_slice)
    difficulties = derive_difficulties(pool, source_dbs, classifier_dir)
    cross_checked = (
        cross_check_difficulties(hardness_path, difficulties)
        if hardness_path is not None
        else 0
    )

    usable: list[tuple[int, dict[str, Any]]] = []
    empty_gold = 0
    for index, row in enumerate(pool):
        db_id = row["output"]["db_id"]
        if db_id != row["input"]["db_id"]:
            raise SystemExit(
                f"pool row {index} names {row['input']['db_id']} on its question and "
                f"{db_id} on its answer"
            )
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

    deduped, near_duplicates = drop_near_duplicate_questions(usable)
    by_band: dict[str, list[tuple[int, dict[str, Any]]]] = {band: [] for band in BANDS}
    for index, row in deduped:
        by_band[difficulties[index]].append((index, row))

    print(
        f"pool={len(pool)} dropped-empty-gold={empty_gold} "
        f"dropped-near-duplicate={near_duplicates} usable={sum(len(v) for v in by_band.values())}"
    )
    if hardness_path is not None:
        print(
            f"  cross-checked {cross_checked} recorded bands against the gold queries: agree"
        )

    grouped = {band: group_by_gold(rows) for band, rows in by_band.items()}
    for band in BANDS:
        print(
            f"  {band:<10} rows={len(by_band[band]):<4} distinct-gold-queries="
            f"{len(grouped[band])}"
        )
        if len(by_band[band]) < PER_BAND:
            raise SystemExit(
                f"band {band} has {len(by_band[band])} usable rows, need {PER_BAND}"
            )

    rng = random.Random(SEED)
    selected: list[dict[str, Any]] = []
    repeated_by_band: dict[str, int] = {}
    for band in BANDS:
        chosen, repeated = select_band(band, grouped[band], rng)
        repeated_by_band[band] = repeated
        if repeated:
            print(
                f"  NOTE {band}: only {len(grouped[band])} distinct gold queries are "
                f"available and {PER_BAND} rows are wanted, so {repeated} tuning rows are a "
                "second question for a gold already in this band. No holdout row is."
            )
        for index, row, split in chosen:
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
    # otherwise leave the extras behind and nothing downstream looks for extras. Only what
    # `removable` allows is deleted, and `removable` is what this script recorded putting
    # there -- see approve_database_directory.
    clear_recorded_entries(db_dest, removable)
    db_dest.mkdir(parents=True, exist_ok=True)
    for db_id in needed:
        copy_database(source_dbs / db_id / f"{db_id}.sqlite", db_dest / db_id, db_id)

    digest = sha256_of(out_path)
    splits = Counter(row["metadata"]["split"] for row in selected)
    bands = Counter(row["metadata"]["difficulty"] for row in selected)
    crossing = golds_crossing_the_split(selected)
    db_bytes = sum(
        path.stat().st_size for path in sorted(db_dest.rglob("*")) if path.is_file()
    )
    write_provenance(
        record_path,
        record_dir,
        source_slice=source_slice,
        pool_digest=pool_digest,
        pool_rows=len(pool),
        classifier_dir=classifier_dir,
        out_path=out_path,
        digest=digest,
        rows=len(selected),
        db_dest=db_dest,
        databases=needed,
        db_bytes=db_bytes,
        filters={
            "dropped_empty_gold": empty_gold,
            "dropped_near_duplicate_question": near_duplicates,
            "tuning_rows_repeating_a_gold_in_their_band": repeated_by_band,
        },
        counts={"bands": dict(bands), "splits": dict(splits)},
    )

    print(f"\nwrote {out_path} rows={len(selected)} sha256={digest}")
    print(f"  from pool  {source_slice.name} sha256={pool_digest}")
    print(f"  splits={dict(splits)}")
    print(f"  bands={dict(bands)}")
    print(f"  gold queries crossing the tuning/holdout line={crossing}")
    print(f"  tuning rows repeating a gold in their band={repeated_by_band}")
    print(f"  databases={len(needed)} bytes={db_bytes} -> {db_dest}")
    print(f"  provenance {record_path}")
    report_datasheet_drift(record_dir / "datasheet.yaml", digest, pool_digest)


def golds_crossing_the_split(rows: list[dict[str, Any]]) -> int:
    """Normalised gold queries that appear in both splits. The whole point is that it is 0."""
    where: dict[str, set[str]] = {}
    for row in rows:
        where.setdefault(normalised_gold(row["output"]), set()).add(
            row["metadata"]["split"]
        )
    return sum(1 for splits in where.values() if len(splits) > 1)


def write_provenance(
    record_path: Path,
    record_dir: Path,
    *,
    source_slice: Path,
    pool_digest: str,
    pool_rows: int,
    classifier_dir: Path,
    out_path: Path,
    digest: str,
    rows: int,
    db_dest: Path,
    databases: list[str],
    db_bytes: int,
    filters: dict[str, Any],
    counts: dict[str, Any],
) -> None:
    """What this build made, where, and out of what.

    Two jobs. It is the machine-readable copy of the numbers datasheet.yaml states by hand,
    so the two can be compared instead of trusted. And it is the permission slip: the next
    run may overwrite exactly what this file says this run wrote, and nothing else.

    Paths are recorded relative to this file so the record says nothing about whose machine
    built it. A destination that is not under this directory gets no record, and therefore
    no permission -- which is the safe direction.
    """

    def relative(path: Path) -> str | None:
        try:
            return path.relative_to(record_dir).as_posix()
        except ValueError:
            return None

    slice_rel = relative(out_path)
    db_rel = relative(db_dest)
    record: dict[str, Any] = {
        "format": PROVENANCE_FORMAT,
        "builder": Path(__file__).name,
        "seed": SEED,
        "source": {
            "slice": source_slice.name,
            "sha256": pool_digest,
            "rows": pool_rows,
        },
        "difficulty": {
            "derived_from": "the gold query of each row",
            "classifier": "vendored Spider Evaluator.eval_hardness",
            "classifier_sha256": {
                f"{name}.py": sha256_of(classifier_dir / f"{name}.py")
                for name in CLASSIFIER_MODULES
            },
        },
        "slice": {"path": slice_rel, "sha256": digest, "rows": rows},
        "databases": {
            "path": db_rel,
            "entries": databases if db_rel is not None else [],
            "count": len(databases),
            "bytes": db_bytes,
        },
        "filters": filters,
        "counts": counts,
    }
    record_path.write_text(
        json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )


def report_datasheet_drift(
    datasheet: Path, slice_digest: str, pool_digest: str
) -> None:
    """Say so, loudly, when the datasheet beside the data still describes the old data."""
    if not datasheet.is_file():
        return
    text = datasheet.read_text(encoding="utf-8")
    stale = [
        f"{label}: datasheet says {found.group(1) if found else 'nothing'}, this build made {expected}"
        for label, pattern, expected in (
            ("slice sha256", r"^\s*sha256:\s*([0-9a-f]{64})\s*$", slice_digest),
            ("pool sha256", r"^\s*pool_sha256:\s*([0-9a-f]{64})\s*$", pool_digest),
        )
        for found in [re.search(pattern, text, re.M)]
        if found is None or found.group(1) != expected
    ]
    if stale:
        print(f"\nWARNING: {datasheet.name} no longer describes the data beside it:")
        for line in stale:
            print(f"  {line}")
        print(
            f"  every number in it should be re-derived; {PROVENANCE_NAME} has the new ones"
        )


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
        "--classifier",
        type=Path,
        metavar="DIR",
        help=(
            "the vendored official Spider evaluation code that labels difficulty "
            f"(default: <source>/{CLASSIFIER_SUBDIR})"
        ),
    )
    parser.add_argument(
        "--hardness",
        type=Path,
        metavar="FILE",
        help=(
            "optional hardness.jsonl to CROSS-CHECK against the labels derived here; "
            "it is never a source of labels, and a disagreement stops the build"
        ),
    )
    parser.add_argument("--out", type=Path, default=HERE / "spider_300.jsonl")
    parser.add_argument("--databases", type=Path, default=HERE / "databases")
    parser.add_argument(
        "--force",
        action="store_true",
        help=(
            "overwrite the rows file and clear the databases directory even where no "
            f"{PROVENANCE_NAME} says this script created them. Deletes other people's files"
        ),
    )
    args = parser.parse_args(argv)
    source_root = args.source.resolve()
    classifier_dir = (
        args.classifier.resolve()
        if args.classifier is not None
        else source_root / CLASSIFIER_SUBDIR
    )
    build(
        source_root,
        classifier_dir,
        args.out,
        args.databases,
        args.hardness.resolve() if args.hardness is not None else None,
        args.force,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
