# SPDX-License-Identifier: Apache-2.0
"""The committed Spider slice is what it says it is.

These are the claims the repository makes about its own data, checked against the bytes.
The expensive one -- running all 300 recorded queries -- is the point of the file: a slice
whose answers do not run, or run and return nothing, grades every attempt wrong or every
attempt right, and either way the numbers from it mean nothing.
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import unittest
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SPIDER_DIR = REPO_ROOT / "spider"
DATASET_PATH = SPIDER_DIR / "spider_300.jsonl"
DATABASES_PATH = SPIDER_DIR / "databases"
DATASHEET_PATH = SPIDER_DIR / "datasheet.yaml"

EXPECTED_ROWS = 300
EXPECTED_DATABASES = 18
EXPECTED_BANDS = {"easy": 75, "medium": 75, "hard": 75, "very-hard": 75}
EXPECTED_SPLITS = {"tuning": 240, "holdout": 60}
SHINGLE_SIZE = 3
SIMILARITY_THRESHOLD = 0.7


def load_rows() -> list[dict]:
    with DATASET_PATH.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def shingles(text: str) -> set[tuple[str, ...]]:
    words = re.findall(r"[a-z0-9]+", text.lower())
    if len(words) < SHINGLE_SIZE:
        return {tuple(words)}
    return {
        tuple(words[i : i + SHINGLE_SIZE]) for i in range(len(words) - SHINGLE_SIZE + 1)
    }


class SliceShape(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = load_rows()

    def test_row_count(self) -> None:
        self.assertEqual(len(self.rows), EXPECTED_ROWS)

    def test_rows_are_flat(self) -> None:
        """input and output are text.

        The first-run tooling reads both fields as text and serialises anything else. A
        nested input puts the whole CREATE TABLE block inside the row's identity, which
        makes every row from one database look like a near-duplicate of every other.
        """
        for index, row in enumerate(self.rows):
            self.assertIsInstance(row["input"], str, f"row {index} input is not text")
            self.assertIsInstance(row["output"], str, f"row {index} output is not text")

    def test_questions_are_unique(self) -> None:
        questions = [row["input"] for row in self.rows]
        duplicates = [q for q, count in Counter(questions).items() if count > 1]
        self.assertEqual(duplicates, [], f"duplicate questions: {duplicates[:3]}")

    def test_no_near_duplicate_questions(self) -> None:
        """No two questions are paraphrases of each other.

        The readiness check applies this same test and marks the data less diverse when it
        finds a pair, so the slice is built without any.
        """
        prepared = [
            (row["metadata"]["id"], shingles(row["input"])) for row in self.rows
        ]
        collisions = []
        for position, (left_id, left) in enumerate(prepared):
            for right_id, right in prepared[position + 1 :]:
                union = left | right
                if union and len(left & right) / len(union) >= SIMILARITY_THRESHOLD:
                    collisions.append((left_id, right_id))
        self.assertEqual(collisions, [], f"near-duplicate questions: {collisions[:3]}")

    def test_ids_are_present_and_unique(self) -> None:
        ids = [row["metadata"]["id"] for row in self.rows]
        self.assertTrue(all(ids), "every row needs a stable id")
        self.assertEqual(len(set(ids)), len(ids), "ids are not unique")

    def test_metadata_fields(self) -> None:
        for row in self.rows:
            metadata = row["metadata"]
            self.assertEqual(
                sorted(metadata),
                ["db_id", "difficulty", "id", "provenance", "schema", "split"],
            )
            self.assertEqual(metadata["provenance"], "real")

    def test_difficulty_bands(self) -> None:
        """All four bands, evenly.

        The readiness check penalises data that does not span difficulty, and a set that is
        mostly easy questions makes every configuration look similar.
        """
        self.assertEqual(
            Counter(r["metadata"]["difficulty"] for r in self.rows),
            Counter(EXPECTED_BANDS),
        )

    def test_splits(self) -> None:
        self.assertEqual(
            Counter(r["metadata"]["split"] for r in self.rows), Counter(EXPECTED_SPLITS)
        )

    def test_split_is_balanced_within_each_band(self) -> None:
        """The held-out questions are as hard as the ones tuned on.

        Splitting across bands rather than within them can hold out only easy questions,
        and a winner checked against those has not been checked against anything.
        """
        per_band = Counter(
            (row["metadata"]["difficulty"], row["metadata"]["split"])
            for row in self.rows
        )
        for band in EXPECTED_BANDS:
            self.assertEqual(per_band[(band, "tuning")], 60, band)
            self.assertEqual(per_band[(band, "holdout")], 15, band)


class SliceRunsAgainstItsDatabases(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.rows = load_rows()

    def test_every_database_is_committed(self) -> None:
        needed = sorted({row["metadata"]["db_id"] for row in self.rows})
        self.assertEqual(len(needed), EXPECTED_DATABASES)
        for db_id in needed:
            self.assertTrue(
                (DATABASES_PATH / db_id / f"{db_id}.sqlite").exists(),
                f"database {db_id} is referenced by the data and not committed",
            )

    def test_no_unused_databases(self) -> None:
        needed = {row["metadata"]["db_id"] for row in self.rows}
        committed = {path.name for path in DATABASES_PATH.iterdir() if path.is_dir()}
        self.assertEqual(
            committed - needed, set(), "databases committed that no question uses"
        )

    def test_every_recorded_query_runs_and_returns_rows(self) -> None:
        """Each recorded answer executes, and returns something.

        A query that returns no rows is gradeable by accident under execution scoring: any
        wrong answer that also returns nothing matches it and is marked correct.
        """
        failures, empty = [], []
        for row in self.rows:
            db_id = row["metadata"]["db_id"]
            connection = sqlite3.connect(
                str(DATABASES_PATH / db_id / f"{db_id}.sqlite")
            )
            connection.text_factory = lambda raw: raw.decode("utf-8", "replace")
            try:
                if not connection.execute(row["output"]).fetchall():
                    empty.append(row["metadata"]["id"])
            except sqlite3.Error as error:
                failures.append((row["metadata"]["id"], str(error)))
            finally:
                connection.close()
        self.assertEqual(
            failures, [], f"recorded queries that do not run: {failures[:3]}"
        )
        self.assertEqual(
            empty, [], f"recorded queries that return no rows: {empty[:3]}"
        )

    def test_schema_text_matches_the_real_database(self) -> None:
        """The schema shown to the model is the schema of the database it is graded on."""
        actual: dict[str, set[str]] = {}
        for row in self.rows:
            db_id = row["metadata"]["db_id"]
            if db_id not in actual:
                connection = sqlite3.connect(
                    str(DATABASES_PATH / db_id / f"{db_id}.sqlite")
                )
                actual[db_id] = {
                    name.lower()
                    for (name,) in connection.execute(
                        "select name from sqlite_master where type='table'"
                    )
                }
                connection.close()
            declared = {
                match.group(1).strip("\"`[]'").lower()
                for match in re.finditer(
                    r"CREATE TABLE\s+([^\s(]+)", row["metadata"]["schema"], re.I
                )
            }
            missing = declared - actual[db_id]
            self.assertEqual(
                missing,
                set(),
                f"{row['metadata']['id']}: {db_id} has no {sorted(missing)}",
            )


class DatasheetMatchesTheData(unittest.TestCase):
    def test_recorded_hash_is_current(self) -> None:
        """The datasheet's hash is the hash of the file beside it.

        The datasheet is where the licence and the provenance are recorded. If it can drift
        from the data it describes, it stops being evidence of anything.
        """
        text = DATASHEET_PATH.read_text(encoding="utf-8")
        recorded = re.search(r"^\s*sha256:\s*([0-9a-f]{64})\s*$", text, re.M)
        self.assertIsNotNone(recorded, "the datasheet records no sha256 for the slice")
        self.assertEqual(
            recorded.group(1),
            hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest(),
            "the datasheet's hash is not the hash of spider_300.jsonl",
        )

    def test_licence_is_recorded(self) -> None:
        text = DATASHEET_PATH.read_text(encoding="utf-8")
        self.assertIn("CC-BY-SA-4.0", text)
        self.assertTrue((SPIDER_DIR / "LICENSE-DATA").exists())


if __name__ == "__main__":
    unittest.main()
