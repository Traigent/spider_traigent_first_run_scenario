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
import tomllib
import unittest
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
SPIDER_DIR = REPO_ROOT / "spider"
DATASET_PATH = SPIDER_DIR / "spider_300.jsonl"
DATABASES_PATH = SPIDER_DIR / "databases"
DATASHEET_PATH = SPIDER_DIR / "datasheet.yaml"
PROVENANCE_PATH = SPIDER_DIR / "provenance.json"
LICENCE_DATA_PATH = SPIDER_DIR / "LICENSE-DATA"
REUSE_PATH = SPIDER_DIR / "REUSE.toml"

EXPECTED_ROWS = 300
EXPECTED_DATABASES = 18
EXPECTED_BANDS = {"easy": 75, "medium": 75, "hard": 75, "very-hard": 75}
EXPECTED_SPLITS = {"tuning": 240, "holdout": 60}
EXPECTED_SEED = 42
# The licence the data travels under, as opposed to the Apache-2.0 the code carries.
DATA_LICENCE = "CC-BY-SA-4.0"
SHINGLE_SIZE = 3
SIMILARITY_THRESHOLD = 0.7
# The documented id format. Every id says which Spider dev row it came from, and the
# calibration cases name rows by exactly this spelling, so it is a format other files read
# and not only a label.
ID_PATTERN = r"^spider-dev-\d+$"


def load_rows() -> list[dict]:
    with DATASET_PATH.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def load_provenance() -> dict:
    with PROVENANCE_PATH.open(encoding="utf-8") as handle:
        return json.load(handle)


def datasheet_section(text: str, *keys: str) -> list[str]:
    """The lines nested under a key path in the datasheet.

    The repository has no YAML parser -- the test dependencies are a formatter, a
    linter and a type checker -- so the datasheet is read with regexes over its raw
    text. Doing that per section rather than per file is what makes it safe: `easy:`
    appears under slice.difficulty and again under band_supply, and a search over the
    whole file would silently read whichever came first.
    """
    lines = text.splitlines()
    for key in keys:
        pattern = re.compile(rf"^(\s*){re.escape(key)}:")
        for index, line in enumerate(lines):
            match = pattern.match(line)
            if match is None:
                continue
            indent = len(match.group(1))
            body = []
            for following in lines[index + 1 :]:
                stripped = following.lstrip()
                if stripped and len(following) - len(stripped) <= indent:
                    break
                body.append(following)
            lines = body
            break
        else:
            raise AssertionError(f"the datasheet has no {'.'.join(keys)} section")
    return lines


def datasheet_value(text: str, *keys: str) -> str:
    """One scalar read out of the datasheet section that owns it."""
    *parents, key = keys
    lines = datasheet_section(text, *parents) if parents else text.splitlines()
    for line in lines:
        match = re.match(rf"^\s*{re.escape(key)}:[ \t]*(\S+)[ \t]*$", line)
        if match is not None:
            return match.group(1)
    raise AssertionError(f"the datasheet records no {'.'.join(keys)}")


def committed_databases() -> set[str]:
    return {path.name for path in DATABASES_PATH.iterdir() if path.is_dir()}


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
        """Every row carries a stable id in the documented `spider-dev- followed by digits` form.

        Asserting only that the id is truthy would accept any string at all, and the
        calibration cases point at rows by this spelling -- an id in some other shape would
        name a row nothing can find.
        """
        ids = [row["metadata"]["id"] for row in self.rows]
        for index, row_id in enumerate(ids):
            self.assertRegex(str(row_id), ID_PATTERN, f"row {index} has id {row_id!r}")
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
        """The schema shown to the model is the schema of the database it is graded on.

        The comparison is one-directional -- declared tables must exist -- so it also
        asserts that something was declared at all. A row whose schema string was blank
        declares nothing, contradicts nothing, and would otherwise pass this test while
        handing the model no schema to write SQL against.
        """
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
            self.assertNotEqual(
                declared,
                set(),
                f"{row['metadata']['id']}: schema text declares no tables",
            )
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
        """LICENSE-DATA carries attribution, the licence itself, and the changes made.

        CC BY-SA 4.0 is satisfied by what the file says, not by the file being there:
        who the data is from, which licence it travels under, and what was altered. A
        LICENSE-DATA that is present and empty redistributes someone else's data with
        no attribution and no licence -- which is exactly what the old `.exists()`
        check would have called licensed.
        """
        datasheet = DATASHEET_PATH.read_text(encoding="utf-8")
        self.assertEqual(datasheet_value(datasheet, "license"), DATA_LICENCE)
        licence = LICENCE_DATA_PATH.read_text(encoding="utf-8")
        self.assertIn("Yu, Tao", licence, "LICENSE-DATA names no Spider author")
        self.assertIn("EMNLP 2018", licence, "LICENSE-DATA cites no publication")
        self.assertIn(DATA_LICENCE, licence, "LICENSE-DATA carries no SPDX identifier")
        self.assertIn(
            "Creative Commons Attribution-ShareAlike 4.0 International",
            licence,
            "LICENSE-DATA does not name the licence in full",
        )
        self.assertIn(
            "Attribution-ShareAlike 4.0 International Public License",
            licence,
            "LICENSE-DATA does not reproduce the licence text",
        )
        self.assertIn(
            "Changes made to the original",
            licence,
            "LICENSE-DATA records no notice of modification",
        )
        self.assertIn("This is an adaptation", licence)

    def test_reuse_manifest_agrees_with_the_datasheet(self) -> None:
        """The machine-readable licensing says what the prose says.

        A licence scanner reads REUSE.toml and never opens the datasheet. The rows file
        and the databases are the two things here that cannot carry a header of their
        own, so if the manifest drifts -- or stops covering them -- the repository tells
        a scanner Apache-2.0 for data that is CC BY-SA 4.0.
        """
        manifest = tomllib.loads(REUSE_PATH.read_text(encoding="utf-8"))
        declared = {
            annotation["path"]: annotation["SPDX-License-Identifier"]
            for annotation in manifest["annotations"]
        }
        datasheet_licence = datasheet_value(
            DATASHEET_PATH.read_text(encoding="utf-8"), "license"
        )
        for path in (DATASET_PATH.name, "databases/**", LICENCE_DATA_PATH.name):
            self.assertEqual(
                declared.get(path),
                datasheet_licence,
                f"REUSE.toml does not license {path} the way the datasheet does",
            )


class DatasheetAgreesWithProvenance(unittest.TestCase):
    """The hand-written datasheet against the file the builder writes.

    The datasheet says of the source hash that "provenance.json records this same
    sha256 ... the two can be compared", and until these tests existed nothing
    compared them. A number retyped into the datasheet, or a provenance.json left
    behind by an older build, is then a claim about the data that no longer describes
    it -- and the source pool hash in particular is the only handle anyone has on where
    the rows came from, because the 754-row pool itself is not committed.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.datasheet = DATASHEET_PATH.read_text(encoding="utf-8")
        cls.provenance = load_provenance()
        cls.rows = load_rows()

    def test_source_pool_hash_agrees_with_provenance(self) -> None:
        """One hash names the pool the slice was drawn from, in both files."""
        self.assertEqual(
            datasheet_value(self.datasheet, "source", "pool_sha256"),
            self.provenance["source"]["sha256"],
            "datasheet source.pool_sha256 is not provenance source.sha256",
        )

    def test_slice_hash_agrees_three_ways(self) -> None:
        """Datasheet, provenance.json and the bytes on disk name the same slice.

        Two of the three agreeing is not enough: a stale provenance.json beside a
        current datasheet describes a build that no longer exists.
        """
        actual = hashlib.sha256(DATASET_PATH.read_bytes()).hexdigest()
        self.assertEqual(
            datasheet_value(self.datasheet, "slice", "sha256"),
            actual,
            "the datasheet's hash is not the hash of spider_300.jsonl",
        )
        self.assertEqual(
            self.provenance["slice"]["sha256"],
            actual,
            "provenance.json's hash is not the hash of spider_300.jsonl",
        )

    def test_row_count_and_seed_agree_with_provenance(self) -> None:
        """The size and the seed are the same number everywhere they are written.

        The seed is the whole reproducibility claim: run the builder with it and the
        same 300 rows come back. A seed recorded in one place and used in another
        reproduces nothing.
        """
        self.assertEqual(
            int(datasheet_value(self.datasheet, "slice", "n")), EXPECTED_ROWS
        )
        self.assertEqual(self.provenance["slice"]["rows"], EXPECTED_ROWS)
        self.assertEqual(len(self.rows), EXPECTED_ROWS)
        self.assertEqual(
            int(datasheet_value(self.datasheet, "slice", "seed")), EXPECTED_SEED
        )
        self.assertEqual(self.provenance["seed"], EXPECTED_SEED)

    def test_band_and_split_counts_agree_with_provenance(self) -> None:
        """The advertised shape of the slice is its actual shape, in all three places.

        A reader who plans a run off the datasheet's 15-per-band holdout, on data that
        is not shaped that way, is choosing a winner against something other than what
        they think they are.
        """
        declared_bands = {
            band: int(datasheet_value(self.datasheet, "slice", "difficulty", band))
            for band in EXPECTED_BANDS
        }
        self.assertEqual(declared_bands, dict(self.provenance["counts"]["bands"]))
        self.assertEqual(
            declared_bands,
            dict(Counter(row["metadata"]["difficulty"] for row in self.rows)),
        )
        declared_splits = {
            split: int(datasheet_value(self.datasheet, "slice", "splits", split))
            for split in EXPECTED_SPLITS
        }
        self.assertEqual(declared_splits, dict(self.provenance["counts"]["splits"]))
        self.assertEqual(
            declared_splits,
            dict(Counter(row["metadata"]["split"] for row in self.rows)),
        )

    def test_database_count_and_size_agree_with_provenance_and_disk(self) -> None:
        """18 databases and 917,504 bytes is measured, not asserted by hand.

        The size is the number a reader uses to decide whether cloning this repository
        is reasonable, and the count is what makes execution work from a bare clone.
        Both are written down twice and neither was checked against the directory.
        """
        on_disk = sorted(committed_databases())
        size = sum(
            (DATABASES_PATH / db_id / f"{db_id}.sqlite").stat().st_size
            for db_id in on_disk
        )
        self.assertEqual(len(on_disk), EXPECTED_DATABASES)
        self.assertEqual(
            int(datasheet_value(self.datasheet, "databases", "count")), len(on_disk)
        )
        self.assertEqual(self.provenance["databases"]["count"], len(on_disk))
        self.assertEqual(
            int(datasheet_value(self.datasheet, "databases", "size_bytes")),
            size,
            "the datasheet's size_bytes is not the size of databases/",
        )
        self.assertEqual(
            self.provenance["databases"]["bytes"],
            size,
            "provenance.json's databases.bytes is not the size of databases/",
        )
        self.assertEqual(
            int(datasheet_value(self.datasheet, "databases", "size_kb")), size // 1024
        )

    def test_provenance_lists_the_databases_used_and_committed(self) -> None:
        """provenance.json's database list is the one the rows need and the repo ships.

        A list that names a database the rows do not use, or omits one they do, is a
        record of a different build than the one that produced these bytes.
        """
        entries = self.provenance["databases"]["entries"]
        self.assertEqual(len(set(entries)), len(entries), "entries repeat a db_id")
        used = {row["metadata"]["db_id"] for row in self.rows}
        self.assertEqual(
            set(entries), used, "provenance.json's entries are not the db_ids in use"
        )
        self.assertEqual(
            set(entries),
            committed_databases(),
            "provenance.json's entries are not the databases committed",
        )


if __name__ == "__main__":
    unittest.main()
