# SPDX-License-Identifier: Apache-2.0
"""What `build.py demo` produces.

These tests are about the builder's own output. They deliberately do not assert what the
Traigent first-run guide does with a demo once it is built -- that is the guide's behaviour
to define and change, and pinning it here would make this repository's tests fail whenever
that repository makes a decision.
"""

from __future__ import annotations

import argparse
import collections
import dataclasses
import hashlib
import importlib.util
import json
import os
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import build  # noqa: E402

# The prompt a customer is given to start a run, byte for byte as the guide's README states it.
# The guide's README carried a three-line form for four days in September 2026 that also said
# where to clone; guide #550 put it back to these two lines, because the location rule is the
# assistant's (GUIDE.md) and not the customer's. This test pins what build.py prints and
# records, and nothing else.
EXPECTED_HANDOFF = (
    "Help me run my first Traigent optimization.\n"
    "Clone https://github.com/Traigent/traigent-first-run and follow GUIDE.md."
)

# How many rows the two smaller draws ship. Written out here rather than read back from
# build.py, because checking the builder's output against the builder's own constant passes
# whatever that constant is changed to and reports nothing. README publishes `mini` as 30 in
# its flag table, so it is a number a reader already relies on.
EXPECTED_MINI_ROWS = 30
EXPECTED_UNLABELED_ROWS = 40
# The smallest draw the repository offers, and the one the guide's own floor bites on: ten
# total leaves eight to tune on. Pinned because nothing else pins it -- `tiny` was added and
# its size was asserted only against the constant that produced it.
EXPECTED_TINY_ROWS = 10
# How many rows a damaged dataset draws before the damage is applied.
EXPECTED_DAMAGED_ROWS = 60

# The rows each smaller draw actually draws, as a hash of the row ids it ships in the order
# it ships them. Building `mini` twice and comparing the bytes is a producer agreeing with
# itself: it passes under any seed, and cannot fail across versions, which is the one thing
# its docstring claims. This is a literal, so changing SAMPLE_SEED -- or the draw, or the
# order -- fails here, which is what "everyone who builds one gets the same questions" means.
DRAWN_ROW_IDS_SHA256 = {
    "mini": "97f005c1b7cc92b1ce3f957f68feaad972839cb2f6c40a59e246872be5a944b8",
    "tiny": "ad65b1676fe15d2a606c20738e480d79ee2eee3824d1e7fbe117f6e26e5a8012",
    "unlabeled": "509b0564efc49f19a6b9a07c2e6a8d650f26999cfa5d7dcb0db8c545dd0202fe",
}

# The tuning/holdout split each smaller draw ships, per difficulty band, measured on the
# built dataset.jsonl rather than on the slice it was drawn from. HOLDOUT_SHARE = 0.0 -- a
# draw with nothing held back at all, so no winner can be checked against anything -- passed
# every test in this file, because nothing asserted the split of a draw.
EXPECTED_SPLIT_BY_BAND = {
    "mini": {
        ("easy", "holdout"): 2,
        ("easy", "tuning"): 6,
        ("hard", "holdout"): 2,
        ("hard", "tuning"): 6,
        ("medium", "holdout"): 1,
        ("medium", "tuning"): 6,
        ("very-hard", "holdout"): 1,
        ("very-hard", "tuning"): 6,
    },
    "tiny": {
        ("easy", "holdout"): 1,
        ("easy", "tuning"): 2,
        ("hard", "holdout"): 1,
        ("hard", "tuning"): 2,
        ("medium", "tuning"): 2,
        ("very-hard", "tuning"): 2,
    },
}

# The budget the sweep measures `slow-scorer` under, stated here rather than read out
# of the harness: a number taken from the thing it is checking agrees with it whatever
# it says. `docs/measurements/score_bank.py` passes this as `--timeout`, and one call
# of the shipped scorer has to outlast it.
SLOW_SCORER_CALIBRATION_BUDGET_SECONDS = 5

# Which starting state each preset is, written out here and imported from nowhere.
# `test_every_preset_passes` used to check build.py's presets against build.py's presets,
# which passes whatever they are changed to: `fake-ruler` shipping a working scorer, or
# `wrong-wiring` shipping the honest one, would have been invisible. The `venv` column is
# what `suite` builds -- none of the presets asks for an environment.
PRESET_TABLE = {
    #                    agent       dataset          eval           calibration  venv
    "agent-and-logs": ("ready", "unlabeled", "missing", "none", "none"),
    "best-case": ("ready", "ready", "exec-match", "present", "none"),
    "checked": ("ready", "ready", "exact-match", "present", "none"),
    "duplicated-data": ("ready", "duplicated", "exact-match", "none", "none"),
    "empty": ("missing", "missing", "missing", "none", "none"),
    "fake-ruler": ("ready", "ready", "broken", "present", "none"),
    "hand-written": ("ready", "tiny", "exact-match", "present", "none"),
    "logs-only": ("missing", "unlabeled", "missing", "none", "none"),
    "no-agent": ("missing", "ready", "exact-match", "none", "none"),
    "no-data": ("ready", "missing", "exact-match", "none", "none"),
    "no-eval": ("ready", "ready", "missing", "none", "none"),
    "no-knobs": ("no-knobs", "ready", "exact-match", "none", "none"),
    "no-labels": ("ready", "unlabeled", "exact-match", "none", "none"),
    "ready": ("ready", "ready", "exact-match", "none", "none"),
    "sql-exec-stop": ("ready", "ready", "exec-match", "none", "none"),
    "wrong-answers": ("ready", "wrong-answers", "exact-match", "none", "none"),
    "wrong-wiring": ("ready", "ready", "swapped", "none", "none"),
    "leaky-split": ("ready", "leaky", "exact-match", "none", "none"),
    "holdout-only": ("ready", "holdout-labelled", "exact-match", "none", "none"),
    "split-by-database": ("ready", "split-by-database", "exact-match", "none", "none"),
    "raw-export": ("ready", "raw-export", "exact-match", "none", "none"),
    "torn-lines": ("ready", "torn", "exact-match", "none", "none"),
    "undeclared-source": ("ready", "undeclared", "exact-match", "none", "none"),
    "mostly-undeclared-source": (
        "ready",
        "mostly-undeclared",
        "exact-match",
        "none",
        "none",
    ),
    "mostly-synthetic-source": (
        "ready",
        "mostly-synthetic",
        "exact-match",
        "none",
        "none",
    ),
    "synthetic-source": ("ready", "fully-synthetic", "exact-match", "none", "none"),
    "generated-answer-key": (
        "ready",
        "generated-answers",
        "exact-match",
        "none",
        "none",
    ),
    "mostly-generated-answer-key": (
        "ready",
        "mostly-generated-answers",
        "exact-match",
        "none",
        "none",
    ),
    "slow-scorer": ("ready", "ready", "slow", "present", "none"),
    "opaque-scorer": ("ready", "ready", "opaque", "none", "none"),
    "length-blind": ("ready", "ready", "length-blind", "present", "none"),
    "two-agents": ("two-agents", "ready", "exact-match", "none", "none"),
}

# The file each `--eval` state ships, so that a preset naming one scorer and shipping another
# is caught by the bytes rather than by the name recorded beside them.
EVALUATOR_FILENAMES = {
    "exact-match": "exact_match.py",
    "exec-match": "exec_match.py",
    "broken": "broken.py",
    "swapped": "swapped.py",
    "opaque": "opaque.py",
    "length-blind": "length_blind.py",
    "slow": "slow.py",
}

# And the same for the agents. Comparing the shipped file with `build.agent_file(...)` was
# comparing the builder's choice with the builder's choice: an `agent_file` that returns
# `agent_ready.py` for every state moves both sides of the assertion at once, and the arm
# with nothing to search would ship the tunable agent with the suite still green.
AGENT_FILENAMES = {
    "ready": "agent_ready.py",
    "no-knobs": "agent_no_knobs.py",
    # The tunable agent, byte for byte; what the state adds sits beside it.
    "two-agents": "agent_ready.py",
}

# What each evaluator honestly is. Recorded in every manifest by build.py and, until now,
# asserted nowhere -- a scorer that executes model output recorded as one that does not is a
# false statement about the one thing docs/eval-methods.md asks a reader to take on trust.
EXPECTED_EVALUATOR_METHOD = {
    "exact-match": "normalized-exact",
    "exec-match": "execution",
    "broken": "normalized-exact",
    "swapped": "normalized-exact",
    # None, on purpose, for both: a grader the project does not carry cannot be given a
    # method, and a comparison of lengths is not one of the methods the guide names.
    "opaque": None,
    "length-blind": None,
    # A method IS honest here: the comparison really is a normalised text match. What is
    # wrong with this scorer is what it costs, not what it compares.
    "slow": "normalized-exact",
}
# Whether each evaluator executes the model's output, as the manifest records it. `None`
# is "unknown", and it is honest for exactly one scorer: the one whose grader is not here.
EXPECTED_EXECUTES = {
    "exact-match": False,
    "exec-match": True,
    "broken": False,
    "swapped": False,
    "opaque": None,
    "length-blind": False,
    # It sleeps; it does not run the model's query.
    "slow": False,
}

# The version of the agent's dependency a project environment is built with. Written out
# here as well as read from build.AGENT_REQUIREMENT, because asserting that the environment
# printed *something* passes on any version at all, including one the guide does not install.
EXPECTED_AGENT_REQUIREMENT = "litellm==1.93.0"


def run_build(
    *args: str, env: dict[str, str] | None = None
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "build.py"), *args],
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )


def load_scorer(name: str) -> Any:
    """One of the shipped evaluators, by file name, with any round trip made free.

    `slow.py` sleeps per call to model a review service; its comparison is what is under
    test, so the sleep is set to zero here rather than waited out.
    """
    located = importlib.util.spec_from_file_location(
        f"_scorer_{name}", REPO_ROOT / "components" / "evaluator" / f"{name}.py"
    )
    assert located is not None and located.loader is not None
    scorer = importlib.util.module_from_spec(located)
    sys.modules[located.name] = scorer
    located.loader.exec_module(scorer)
    if hasattr(scorer, "SECONDS_PER_CALL"):
        scorer.SECONDS_PER_CALL = 0.0
    return scorer


def declaring_states() -> list[str]:
    """The dataset states whose rows say something different about themselves.

    Read off what `build.damage_rows` actually does to the declaration fields, not listed:
    two tests here each kept their own list of these states, and neither learned about
    `fully-synthetic` when it arrived.
    """
    rows = build.read_dataset()

    def declared(row: dict[str, Any]) -> dict[str, Any]:
        return {
            key: value
            for key, value in row["metadata"].items()
            if key in build.DECLARATION_ROW_FIELDS
        }

    return [
        state
        for state in build.DATASET_STATES
        if state != "missing"
        and any(
            declared(original) != declared(shipped)
            for original, shipped in zip(
                build.select_rows(rows, state),
                build.damage_rows(build.select_rows(rows, state), state),
            )
        )
    ]


def ascii_locale_env() -> dict[str, str]:
    """The environment of a container nobody set `LANG` in.

    Python then picks ASCII for `open()` without an explicit encoding, so any
    file reader that forgot one fails on the first non-ASCII byte. Two rows of
    the committed slice carry a typographic apostrophe, which makes this the
    ordinary shape of a fresh machine rather than an exotic one.
    """

    return {
        **os.environ,
        "LC_ALL": "C",
        "LANG": "C",
        "PYTHONUTF8": "0",
        "PYTHONCOERCECLOCALE": "0",
    }


def build_or_raise(*args: str) -> subprocess.CompletedProcess[str]:
    """A fixture build, refused loudly rather than asserted.

    Used from `setUpClass`, where a bare `assert` vanishes under `python -O` and the failure
    then surfaces further down as a FileNotFoundError about a path nobody can explain.
    """
    result = run_build(*args)
    if result.returncode != 0:
        raise RuntimeError(
            f"the fixture build `{' '.join(args)}` failed with {result.returncode}: "
            f"{result.stderr or result.stdout}"
        )
    return result


def rows_of(project: Path) -> list[dict]:
    return [
        json.loads(line)
        for line in (project / "dataset.jsonl").read_text().splitlines()
        if line
    ]


def slice_rows() -> dict[str, dict]:
    """The committed slice, by row id -- the truth a damaged dataset is damaged away from."""
    rows = {}
    for line in (REPO_ROOT / "spider" / "spider_300.jsonl").read_text().splitlines():
        if line.strip():
            row = json.loads(line)
            rows[row["metadata"]["id"]] = row
    return rows


def id_digest(rows: list[dict]) -> str:
    return hashlib.sha256(
        "\n".join(row["metadata"]["id"] for row in rows).encode("utf-8")
    ).hexdigest()


class Handoff(unittest.TestCase):
    def test_clone_handoff_is_exact(self) -> None:
        self.assertEqual(build.HANDOFF_CLONE, EXPECTED_HANDOFF)

    def test_local_handoff_points_at_the_copied_checkout(self) -> None:
        self.assertIn("./traigent-first-run/GUIDE.md", build.HANDOFF_LOCAL)
        self.assertNotIn("github.com", build.HANDOFF_LOCAL)

    def test_the_handoff_is_recorded_in_the_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            out = Path(workspace) / "demo"
            self.assertEqual(
                run_build("demo", "--preset", "ready", "--out", str(out)).returncode, 0
            )
            manifest = json.loads((out / "demo.json").read_text())
            self.assertEqual(manifest["handoff"], EXPECTED_HANDOFF)


class DemoLayout(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workspace = tempfile.mkdtemp()
        cls.out = Path(cls.workspace) / "ready"
        build_or_raise("demo", "--preset", "ready", "--out", str(cls.out))
        cls.project = cls.out / "project"
        cls.manifest = json.loads((cls.out / "demo.json").read_text())

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.workspace, ignore_errors=True)

    def test_the_project_holds_what_a_project_holds(self) -> None:
        for name in (
            "agent.py",
            "evaluator.py",
            "dataset.jsonl",
            "catalog.json",
            "README.md",
            ".env.example",
            ".gitignore",
            # The data's terms travel with the data under this name. It used to be
            # `LICENSE-DATA`, which is what the repository calls its own copy of the
            # licence text; the project ships the attribution notice instead.
            "ATTRIBUTION.txt",
            "databases",
        ):
            self.assertTrue(
                (self.project / name).exists(), f"{name} is missing from the project"
            )
        self.assertFalse(
            (self.project / "LICENSE-DATA").exists(),
            "the project still ships the old licence file name as well",
        )

    def test_the_build_record_stays_out_of_the_project(self) -> None:
        """demo.json names the state each component was put in.

        A run where the agent can read that is not a test of anything, so the record sits
        beside the project rather than inside it.
        """
        self.assertTrue((self.out / "demo.json").exists())
        self.assertFalse((self.project / "demo.json").exists())

    def test_the_data_licence_travels_with_the_data(self) -> None:
        """The rows are CC BY-SA, and the terms have to arrive with them.

        Asserting the file exists is not the claim being made -- an empty
        `ATTRIBUTION.txt` satisfies it and redistributes third-party data with no
        attribution, no licence and no notice of modification, which is the licence
        breach the file is there to prevent. So the content is asserted: who the data is
        from, which licence it is under, and that this copy was changed.
        """
        notice = self.project / "ATTRIBUTION.txt"
        text = notice.read_text(encoding="utf-8")

        # Attribution: the work, its authors and where it came from.
        self.assertIn("Spider", text)
        self.assertIn("Yu", text)
        self.assertIn("EMNLP 2018", text)
        self.assertIn("https://yale-lily.github.io/spider", text)

        # The licence, by its identifier and not only by its friendly name -- the
        # identifier is what a machine-readable licence check reads.
        self.assertIn("CC BY-SA 4.0", text)
        self.assertIn("CC-BY-SA-4.0", text)
        self.assertIn("https://creativecommons.org/licenses/by-sa/4.0/", text)

        # The notice of modification the licence requires of an adapted copy.
        self.assertIn("THIS IS NOT THE SPIDER DATASET", text)
        self.assertIn("modified", text.casefold())

        # And it is the repository's one copy of that text, not a paraphrase written on
        # the way out.
        self.assertEqual(
            text,
            (REPO_ROOT / "components" / "legal" / "ATTRIBUTION.txt").read_text(
                encoding="utf-8"
            ),
        )
        self.assertEqual(self.manifest["data_licence"], "CC-BY-SA-4.0")

    def test_the_attribution_ships_with_the_data_and_only_with_it(self) -> None:
        """A project holding no rows and no databases has nothing to attribute."""
        with tempfile.TemporaryDirectory() as workspace:
            out = Path(workspace) / "demo"
            build_or_raise("demo", "--dataset", "missing", "--out", str(out))
            self.assertFalse((out / "project" / "ATTRIBUTION.txt").exists())

    def test_rows_are_flat_and_carry_their_database(self) -> None:
        rows = [
            json.loads(line)
            for line in (self.project / "dataset.jsonl").read_text().splitlines()
            if line
        ]
        self.assertEqual(len(rows), 300)
        for row in rows[:5]:
            self.assertIsInstance(row["input"], str)
            self.assertIsInstance(row["output"], str)
            self.assertIn("db_id", row["metadata"])

    def test_the_catalog_covers_every_question(self) -> None:
        """The agent is handed a question and nothing else, so it looks the database up."""
        rows = [
            json.loads(line)
            for line in (self.project / "dataset.jsonl").read_text().splitlines()
            if line
        ]
        catalog = json.loads((self.project / "catalog.json").read_text())
        self.assertEqual(set(catalog), {row["input"] for row in rows})
        for entry in catalog.values():
            self.assertIn("db_id", entry)
            self.assertIn("schema", entry)

    def test_only_the_databases_the_questions_need_are_copied(self) -> None:
        rows = [
            json.loads(line)
            for line in (self.project / "dataset.jsonl").read_text().splitlines()
            if line
        ]
        needed = {row["metadata"]["db_id"] for row in rows}
        shipped = {
            path.name
            for path in (self.project / "databases").iterdir()
            if path.is_dir()
        }
        self.assertEqual(shipped, needed)

    def test_every_shipped_file_is_hashed(self) -> None:
        recorded = {entry["path"] for entry in self.manifest["files"]}
        actual = {
            path.relative_to(self.project).as_posix()
            for path in self.project.rglob("*")
            if path.is_file()
        }
        self.assertEqual(recorded, actual)


class ComponentStates(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.workspace, ignore_errors=True)

    def make(self, *args: str) -> Path:
        out = Path(self.workspace) / f"demo{len(list(Path(self.workspace).iterdir()))}"
        result = run_build("demo", "--out", str(out), *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return out / "project"

    def test_a_missing_component_ships_no_file(self) -> None:
        self.assertFalse((self.make("--agent", "missing") / "agent.py").exists())
        self.assertFalse((self.make("--eval", "missing") / "evaluator.py").exists())
        self.assertFalse((self.make("--dataset", "missing") / "dataset.jsonl").exists())

    def test_a_missing_dataset_takes_the_databases_with_it(self) -> None:
        project = self.make("--dataset", "missing")
        self.assertFalse((project / "databases").exists())
        self.assertFalse((project / "catalog.json").exists())

    def test_the_mini_dataset_is_smaller_and_still_spans_difficulty(self) -> None:
        project = self.make("--dataset", "mini")
        rows = [
            json.loads(line)
            for line in (project / "dataset.jsonl").read_text().splitlines()
            if line
        ]
        self.assertEqual(len(rows), EXPECTED_MINI_ROWS)
        self.assertEqual(len({row["metadata"]["difficulty"] for row in rows}), 4)

    def test_the_smaller_draw_is_the_same_draw_every_time(self) -> None:
        """Two builds of the same dataset state ship byte-identical rows.

        `mini` and `unlabeled` are sampled, and the sample is seeded so that everyone who
        builds one gets the same questions. Without that, two people following the guide
        compare scores that were never measured on the same rows, and nothing in either
        project says so.
        """
        first = self.make("--dataset", "mini") / "dataset.jsonl"
        second = self.make("--dataset", "mini") / "dataset.jsonl"
        self.assertEqual(
            first.read_bytes(),
            second.read_bytes(),
            "two builds of --dataset mini drew different rows",
        )

    def test_unlabelled_rows_carry_no_answer(self) -> None:
        """No expected output, and therefore no split -- there is nothing to hold back."""
        project = self.make("--dataset", "unlabeled")
        rows = [
            json.loads(line)
            for line in (project / "dataset.jsonl").read_text().splitlines()
            if line
        ]
        self.assertEqual(len(rows), EXPECTED_UNLABELED_ROWS)
        for row in rows:
            self.assertNotIn("output", row)
            self.assertNotIn("split", row["metadata"])

    def test_the_agent_without_settings_ships_a_different_file(self) -> None:
        tunable = self.make("--agent", "ready") / "agent.py"
        fixed = self.make("--agent", "no-knobs") / "agent.py"
        self.assertNotEqual(tunable.read_text(), fixed.read_text())

    def test_the_manifest_says_which_evaluator_executes_model_output(self) -> None:
        for state, executes in (
            ("exact-match", False),
            ("exec-match", True),
            ("broken", False),
        ):
            out = self.make("--eval", state).parent
            evaluator = json.loads((out / "demo.json").read_text())["components"][
                "evaluator"
            ]
            self.assertEqual(evaluator["executes_candidate_output"], executes, state)


class ADemoCanBeBuiltWithoutACommandLine(unittest.TestCase):
    """Deciding a demo and writing one are two jobs, and only one of them refuses anything.

    `plan_demo` reads the command line and does every check; `write_demo` takes what it
    produced and writes it. That split is what makes these tests possible at all -- every
    other test here shells out to build.py, because until now the writer could not be
    reached without argparse.
    """

    def setUp(self) -> None:
        self.workspace = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.workspace, ignore_errors=True)

    def plan(self, **overrides: object) -> build.Plan:
        rows = build.select_rows(build.read_dataset(), "mini")
        defaults: dict[str, object] = {
            "out": Path(self.workspace) / "demo",
            "agent": "ready",
            "dataset": "mini",
            "evaluator": "exact-match",
            "calibration": "none",
            "provider": build.DEFAULT_PROVIDER,
            "rows": rows,
            "guide_source": None,
            "interpreter": None,
        }
        defaults.update(overrides)
        return build.Plan(**defaults)  # type: ignore[arg-type]

    def test_the_writer_needs_only_a_plan(self) -> None:
        plan = self.plan()
        plan.out.mkdir(parents=True)
        result = build.write_demo(plan)

        self.assertTrue(result["ok"])
        self.assertEqual(result["rows"], build.MINI_ROWS)
        self.assertTrue((plan.project / "agent.py").exists())
        self.assertTrue((plan.out / "demo.json").exists())

    def test_a_plan_answers_what_the_writer_would_have_had_to_work_out(self) -> None:
        """The things the writer used to derive from argparse are properties of the plan."""
        cloning = self.plan()
        self.assertEqual(cloning.handoff, EXPECTED_HANDOFF)
        self.assertEqual(cloning.project, cloning.out / "project")
        self.assertFalse(cloning.ships_calibration)

        copied = self.plan(guide_source=Path("/somewhere/traigent-first-run"))
        self.assertIn("./traigent-first-run/GUIDE.md", copied.handoff)

        without = self.plan(agent="missing", evaluator="missing")
        self.assertIsNone(without.agent_source)
        self.assertIsNone(without.evaluator_source)

    def test_a_plan_cannot_be_edited_after_it_is_checked(self) -> None:
        """Every refusal happens while the plan is made, so it must not change afterwards.

        The exception is named. `assertRaises(Exception)` passes on any unrelated
        AttributeError -- including the one a misspelled field name raises -- so it would
        have gone on passing over a Plan that had stopped being frozen.
        """
        plan = self.plan()
        with self.assertRaises(dataclasses.FrozenInstanceError):
            plan.dataset = "ready"  # type: ignore[misc]

    def test_a_plan_carries_the_databases_its_probes_need(self) -> None:
        """The project ships the rows' databases *and* the probes', not one or the other.

        A probe names its own row, which need not be one the dataset shipped. Asserting
        this against a built demo only bites when the draw happens to leave a probe's
        database out, and after the slice was re-cut both smaller draws happen to include
        all three -- so the union is asserted here, where a draw cannot make it vacuous.
        """
        rows = [
            row
            for row in build.select_rows(build.read_dataset(), "mini")
            if row["metadata"]["db_id"] == "car_1"
        ]
        self.assertTrue(rows, "the mini draw no longer holds a car_1 row")
        plan = self.plan(rows=rows, probe_databases=frozenset({"dog_kennels"}))
        self.assertEqual(plan.databases, ["car_1", "dog_kennels"])

        plan.out.mkdir(parents=True)
        build.write_demo(plan)
        shipped = {
            path.name
            for path in (plan.project / "databases").iterdir()
            if path.is_dir()
        }
        self.assertEqual(
            shipped,
            {"car_1", "dog_kennels"},
            "a database a probe needs was not copied into the project",
        )


class TheManifestRecordsTheVendor(unittest.TestCase):
    """Which vendor answers is a build choice, so the record of the build has to hold it.

    It is also the roster the guide's opening read scores the `model` setting from, and a
    manifest that restated it from somewhere else could disagree with the file that ships.
    """

    def setUp(self) -> None:
        self.workspace = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.workspace, ignore_errors=True)

    def test_each_provider_is_recorded_with_the_roster_that_shipped(self) -> None:
        for provider in build.PROVIDERS:
            with self.subTest(provider=provider):
                out = Path(self.workspace) / provider
                result = run_build(
                    "demo",
                    "--dataset",
                    "mini",
                    "--provider",
                    provider,
                    "--out",
                    str(out),
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                manifest = json.loads((out / "demo.json").read_text())
                agent = manifest["components"]["agent"]
                self.assertEqual(agent["provider"], provider)

                shipped = (out / "project" / "agent.py").read_text()
                # The second line here used to be the first written again -- `agent` is
                # the dict it was compared with, bound two lines above -- so the recorded
                # provider was checked once and counted twice. What was missing is the
                # other direction: the file that shipped is that provider's file.
                self.assertEqual(
                    shipped,
                    build.agent_file("ready", provider).read_text(),  # type: ignore[union-attr]
                    f"{provider}: the manifest records this vendor and another vendor's "
                    "agent shipped",
                )

                self.assertTrue(agent["models"], "no roster recorded")
                for model in agent["models"]:
                    self.assertIn(
                        f'"{model}"',
                        shipped,
                        f"{provider}: the manifest names a model the shipped agent does not",
                    )

    def test_the_provider_reaches_the_env_template_the_project_ships(self) -> None:
        """A `direct` demo must not hand over OpenRouter's keys.

        `.env.example` is copied by a different code path from the one that chooses the
        agent, and nothing joined them. A project whose agent demands OPENAI_API_KEY while
        its own template offers OPENROUTER_API_KEY refuses every model in its roster with
        a message naming a key the project never mentions -- and the run reads as the
        agent being broken.
        """
        for provider in build.PROVIDERS:
            with self.subTest(provider=provider):
                out = Path(self.workspace) / f"env-{provider}"
                build_or_raise(
                    "demo",
                    "--dataset",
                    "tiny",
                    "--provider",
                    provider,
                    "--out",
                    str(out),
                )
                shipped = (out / "project" / ".env.example").read_text()
                self.assertEqual(
                    shipped,
                    build.env_file(provider).read_text(),
                    f"{provider}: another vendor's env template shipped",
                )
                # The keys the shipped agent will actually ask for, read off the file that
                # ships rather than restated, must each be offered by the template beside
                # it.
                agent_source = (out / "project" / "agent.py").read_text()
                needed = re.findall(r'"([A-Z][A-Z0-9_]+_API_KEY)"', agent_source)
                self.assertTrue(needed, f"{provider}: the agent names no credential")
                offered = {
                    line.split("=", 1)[0]
                    for line in shipped.splitlines()
                    if "=" in line and not line.lstrip().startswith("#")
                }
                for name in sorted(set(needed)):
                    self.assertIn(
                        name,
                        offered,
                        f"{provider}: agent.py needs {name} and .env.example does not "
                        "offer it",
                    )

    def test_the_default_is_the_one_the_readme_documents(self) -> None:
        self.assertEqual(build.DEFAULT_PROVIDER, "openrouter")
        self.assertIn(build.DEFAULT_PROVIDER, build.PROVIDERS)


class Calibration(unittest.TestCase):
    """The probe answers a project keeps for checking its own scorer."""

    def setUp(self) -> None:
        self.workspace = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.workspace, ignore_errors=True)

    def make(self, *args: str) -> Path:
        out = Path(self.workspace) / f"demo{len(list(Path(self.workspace).iterdir()))}"
        result = run_build("demo", "--out", str(out), *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return out

    def test_none_by_default(self) -> None:
        project = self.make("--dataset", "mini") / "project"
        self.assertFalse((project / build.RUNS_DIRECTORY).exists())

    def test_present_ships_cases_for_the_chosen_scorer(self) -> None:
        for state in ("exact-match", "exec-match", "broken"):
            with self.subTest(evaluator=state):
                out = self.make(
                    "--dataset", "mini", "--eval", state, "--calibration", "present"
                )
                cases_path = (
                    out / "project" / build.RUNS_DIRECTORY / build.CALIBRATION_FILE
                )
                self.assertTrue(cases_path.exists())
                cases = json.loads(cases_path.read_text())
                self.assertGreaterEqual(
                    len(cases), 2, "calibration needs at least two cases"
                )
                for case in cases:
                    self.assertEqual(
                        sorted(case["probes"]),
                        ["bad", "equivalent_good", "good", "partial"],
                    )
                record = json.loads((out / "demo.json").read_text())["components"][
                    "evaluator"
                ]
                self.assertEqual(record["calibration"]["case_count"], len(cases))

    def test_the_probes_bring_their_databases_with_them(self) -> None:
        """A probe names its own row, which need not be one the dataset shipped.

        The smallest draw is used, because the smaller the draw the more likely it is to
        leave a probe's database out -- and the project must still ship it or calibration
        cannot run at all.

        This assertion is only as strong as the draw makes it. Whether the union of the
        rows' databases and the probes' is load-bearing *for this particular draw* is
        reported below rather than assumed, and the union itself is pinned where a draw
        cannot make it vacuous, in
        `ADemoCanBeBuiltWithoutACommandLine::test_a_plan_carries_the_databases_its_probes_need`.
        """
        out = self.make(
            "--dataset", "tiny", "--eval", "exec-match", "--calibration", "present"
        )
        project = out / "project"
        cases = json.loads(
            (project / build.RUNS_DIRECTORY / build.CALIBRATION_FILE).read_text()
        )
        shipped = {
            path.name for path in (project / "databases").iterdir() if path.is_dir()
        }
        probe_databases = {case["metadata"]["db_id"] for case in cases}
        for db_id in sorted(probe_databases):
            self.assertIn(db_id, shipped, f"probe names {db_id}, which was not copied")

        # And nothing else was copied: the project carries what its rows and its probes
        # name, and not the rest of the repository's databases.
        row_databases = {row["metadata"]["db_id"] for row in rows_of(project)}
        self.assertEqual(
            shipped,
            row_databases | probe_databases,
            "the project ships a database neither its rows nor its probes name",
        )

    def test_calibration_needs_something_to_calibrate(self) -> None:
        for args, expected in (
            (("--eval", "missing"), "evaluator"),
            (("--dataset", "missing"), "databases"),
            # A scorer that exists and has no probes is refused in its own words: its
            # grader is not here, so nothing could vouch for probe answers shipped for it.
            (("--eval", "opaque"), "nothing could vouch for the probes"),
        ):
            with self.subTest(args=args):
                # Named after the flag, not its value. Both subtests pass "missing", so
                # naming it after the value gave the two of them one shared path, where a
                # refusal to write over an existing directory would read as the refusal
                # this test is actually about.
                out = Path(self.workspace) / f"bad{args[0].lstrip('-')}"
                result = run_build(
                    "demo", "--out", str(out), "--calibration", "present", *args
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn(expected, result.stderr)


class EveryBuiltDemoPassesItsOwnCheck(unittest.TestCase):
    """`verify` is the gate that says a demo is fit to hand to an agent.

    A gate nobody has watched fail is not a gate, so this drives it in both directions: every
    preset as built must pass, and each thing it is supposed to catch must make it fail.
    """

    @classmethod
    def setUpClass(cls) -> None:
        # One demo, copied per test. Every test below wants the same undamaged starting
        # point and then breaks one thing in it; rebuilding for each was six builds of an
        # identical project.
        cls.workspace = tempfile.mkdtemp()
        cls.pristine = Path(cls.workspace) / "pristine"
        build_or_raise("demo", "--dataset", "tiny", "--out", str(cls.pristine))

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.workspace, ignore_errors=True)

    def damaged(self, break_it) -> list[str]:
        out = Path(tempfile.mkdtemp(dir=self.workspace)) / "demo"
        self.addCleanup(shutil.rmtree, out.parent, ignore_errors=True)
        shutil.copytree(self.pristine, out)
        break_it(out / "project")
        return build.verify_demo(out)

    def test_an_undamaged_copy_has_nothing_wrong_with_it(self) -> None:
        """The control. Every test below reads "verify found this" as evidence that the
        damage caused it, and that only follows if the undamaged copy is clean."""
        self.assertEqual(self.damaged(lambda project: None), [])

    def test_it_catches_a_label_that_says_this_is_a_test(self) -> None:
        problems = self.damaged(
            lambda project: (project / "agent.py").write_text(
                (project / "agent.py").read_text()
                + "\n# built from the sql-exec-stop preset\n"
            )
        )
        self.assertTrue(any("says this is a test" in p for p in problems), problems)

    def test_it_catches_every_tell_in_the_roster(self) -> None:
        """One tell exercised proved one tell. The roster is what the check is.

        A word dropped from FIXTURE_TELLS, or a state name that stops being matched, is
        exactly the kind of change nothing notices: the check still runs, still passes, and
        no longer looks for the thing it was widened for.
        """
        for tell in build.FIXTURE_TELLS + build.revealing_names():
            with self.subTest(tell=tell):
                problems = self.damaged(
                    lambda project, tell=tell: (project / "agent.py").write_text(
                        (project / "agent.py").read_text() + f"\n# note: {tell}\n"
                    )
                )
                self.assertTrue(
                    any(
                        repr(tell) in p and "says this is a test" in p for p in problems
                    ),
                    f"{tell!r} is in the roster and was not reported: {problems}",
                )

    def test_it_catches_a_tell_however_it_is_spelled(self) -> None:
        """Case, spaces, underscores and hyphens are all one spelling to the check.

        The leak the roster was widened for read "Spider Traigent First Run Scenario" --
        spaces and capitals -- against a list holding `spider_traigent`, and passed.
        """
        for spelling in (
            "Spider Traigent First Run Scenario",
            "SPIDER_TRAIGENT",
            "first-run-scenario",
            "Generated Demo",
            # A hyphenated label (see `revealing_names`) written with underscores instead --
            # the ordinary alternative spelling for a directory name, and not one the
            # roster's own literal-hyphen matching used to recognise.
            "sql_exec_stop",
        ):
            with self.subTest(spelling=spelling):
                problems = self.damaged(
                    lambda project, s=spelling: (project / "agent.py").write_text(
                        (project / "agent.py").read_text() + f"\n# {s}\n"
                    )
                )
                self.assertTrue(
                    any("says this is a test" in p for p in problems),
                    f"{spelling!r} was not recognised: {problems}",
                )

    def test_ordinary_english_is_not_a_tell(self) -> None:
        """The other direction, and the one that decides whether anyone reads the report.

        `holdout`, `tuning` and `difficulty` are real properties of the rows and appear in
        any honest description of them -- they occur thousands of times in a shipped
        project. So do ordinary words that happen to be inside a state name: an env
        template says to leave a key `empty`, and an agent's prompt style is called
        `direct`. A check that flags those teaches a reader to ignore it, and then it
        catches nothing at all.
        """
        for innocent in (
            "holdout",
            "tuning",
            "difficulty",
            "directly",
            "empty",
            "ready",
            "missing",
            "the answer is not in the catalog",
            "no database recorded for this question",
        ):
            with self.subTest(text=innocent):
                self.assertEqual(
                    build.tells_in(innocent, "a line of prose"),
                    [],
                    f"{innocent!r} is ordinary English and was reported as a tell",
                )

    def test_it_catches_the_building_repository_leaking_in(self) -> None:
        problems = self.damaged(
            lambda project: (project / "agent.py").write_text(
                (project / "agent.py").read_text() + f"\n# see {REPO_ROOT}/components\n"
            )
        )
        self.assertTrue(any("names the path" in p for p in problems), problems)

    def test_it_catches_the_guides_own_environment(self) -> None:
        problems = self.damaged(
            lambda project: (project / build.FORBIDDEN_VENV_NAME).mkdir()
        )
        self.assertTrue(any(build.FORBIDDEN_VENV_NAME in p for p in problems), problems)

    def test_it_catches_a_file_that_no_longer_matches_the_record(self) -> None:
        problems = self.damaged(
            lambda project: (project / "dataset.jsonl").write_text("{}\n")
        )
        self.assertTrue(
            any("does not match the record" in p for p in problems), problems
        )

    def test_it_catches_a_missing_database(self) -> None:
        def remove_one(project: Path) -> None:
            shutil.rmtree(sorted((project / "databases").iterdir())[0])

        problems = self.damaged(remove_one)
        self.assertTrue(any("is not here" in p for p in problems), problems)


class AProjectCanShipAWorkingEnvironment(unittest.TestCase):
    """`--venv ready` is a project that has been worked in, not an empty directory.

    An earlier version of this created an empty environment as scenery, and measurement
    showed it changed nothing anyone could observe. This one installs what the agent needs,
    so the project can actually run before the guide builds an environment of its own.

    Built once for the whole class. An environment is ~220 MB and a minute of pip, and
    every assertion below is about the same environment, so building three of them bought
    nothing but three copies of the same wheels.

    The demo is built in a directory named the way `suite` names one, because the demo's own
    path is written into the scripts inside its environment -- so the neutrality of that name
    is a property of the environment and can only be checked on one that exists.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.workspace = tempfile.mkdtemp()
        cls.out = Path(cls.workspace) / build.bank_directory("wrong-answers")
        build_or_raise(
            "demo", "--dataset", "tiny", "--venv", "ready", "--out", str(cls.out)
        )
        cls.project = cls.out / "project"
        cls.venv = cls.project / build.PROJECT_VENV
        cls.record = json.loads((cls.out / "demo.json").read_text())["components"][
            "project_venv"
        ]

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.workspace, ignore_errors=True)

    def test_the_environment_is_supported_and_the_agent_runs_from_it(self) -> None:
        self.assertEqual(self.record["path"], build.PROJECT_VENV)

        major, minor = (int(p) for p in self.record["python_version"].split(".")[:2])
        self.assertEqual(major, 3)
        self.assertGreaterEqual(minor, 11)
        self.assertLessEqual(minor, 13)

        python = self.venv / "bin" / "python"
        self.assertTrue(python.is_file())
        proof = subprocess.run(
            [
                str(python),
                "-c",
                "from importlib.metadata import version; print(version('litellm'))",
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proof.returncode, 0, proof.stderr)
        # The pinned version, not "it printed something". The guide installs this exact
        # pin, and a project carrying a different version of the same package is a project
        # that behaves differently from the one the guide is about to build -- which is
        # the whole reason the environment is installed rather than left empty.
        self.assertEqual(build.AGENT_REQUIREMENT, EXPECTED_AGENT_REQUIREMENT)
        self.assertEqual(
            proof.stdout.strip(),
            EXPECTED_AGENT_REQUIREMENT.split("==")[1],
            "the environment holds a different version of the agent's dependency",
        )
        self.assertEqual(self.record["installed"], [EXPECTED_AGENT_REQUIREMENT])

    def test_no_dedicated_environment_is_left_behind(self) -> None:
        """The guide reserves .venv-traigent as its fallback and stops that route if one already exists.

        A demo must not pre-empt it, so no combination of flags may make one. Asserted on a
        `--venv ready` build: it used to be asserted on a `--venv none` one, where no code path
        could have created an environment under any name, so it could not have failed.
        """
        self.assertFalse(
            (self.project / build.FORBIDDEN_VENV_NAME).exists(),
            "a demo must never carry the environment the guide creates",
        )
        self.assertEqual(
            list(self.project.rglob(build.FORBIDDEN_VENV_NAME)),
            [],
            "the environment the guide creates is somewhere inside the project",
        )
        self.assertTrue(
            self.venv.is_dir(), "the build made no environment, so this proved nothing"
        )

    def test_the_environment_does_not_record_where_it_was_built(self) -> None:
        """`pyvenv.cfg` keeps what the environment runs on and drops where it came from.

        `venv` writes `command` and `executable` into it, both holding the absolute path
        the environment was created at -- which in a bank is a directory name, and the
        leak this closed had `pyvenv.cfg` recording `.../bank/wrong-wiring/project/.venv`.
        """
        config = (self.venv / "pyvenv.cfg").read_text(encoding="utf-8")
        keys = {
            line.split("=", 1)[0].strip().casefold()
            for line in config.splitlines()
            if "=" in line
        }
        self.assertEqual(
            keys - build.VENV_CONFIG_KEYS,
            set(),
            "pyvenv.cfg holds a key that records how or where it was built",
        )
        self.assertNotIn(str(self.out), config)
        self.assertNotIn(str(REPO_ROOT), config)
        # It still has to be an environment that runs.
        self.assertIn("home", keys)
        self.assertIn("version", keys)

    def test_nothing_in_the_environment_names_a_starting_state(self) -> None:
        """`suite` names directories so that nothing inside a project can say what it is.

        The absolute path is written into every `bin/` script -- the shebang of each
        console script and `VIRTUAL_ENV` in each `activate` -- so a directory named after
        the state its demo was built in puts that state in files the project ships. This
        checks the property end to end on a real environment built under a real bank name.
        """
        for name in sorted(build.PRESETS):
            directory = build.bank_directory(name)
            self.assertEqual(
                build.tells_in(directory, "the bank directory"),
                [],
                f"{name} is built in a directory that says what it is",
            )
        self.assertEqual(
            len({build.bank_directory(name) for name in build.PRESETS}),
            len(build.PRESETS),
            "two presets share a bank directory",
        )

        for path in sorted((self.venv / "bin").iterdir()):
            if not path.is_file() or path.is_symlink():
                continue
            text = build.readable_text(path)
            if text is None:
                continue
            with self.subTest(script=path.name):
                self.assertEqual(
                    build.tells_in(text, path.name),
                    [],
                    "a script in the project's environment says what the demo is",
                )
                self.assertNotIn(str(REPO_ROOT), text)


class TheBankOfStartingStates(unittest.TestCase):
    """Every preset, built once, and checked against a table written out in this file.

    `test_every_preset_passes` used to be the only test of what a preset means, and it
    checked build.py's presets against build.py's presets: it read the manifest, compared it
    with `build.PRESETS`, and passed whatever either of them was changed to. Adding an
    undocumented preset, `fake-ruler` quietly shipping a working scorer, or `wrong-wiring`
    shipping the honest one, were all invisible to it.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.workspace = tempfile.mkdtemp()
        cls.root = Path(cls.workspace) / "bank"
        cls.suite_output = build_or_raise("suite", "--out", str(cls.root)).stdout
        cls.record = json.loads((cls.root / build.BANK_RECORD).read_text())
        cls.built = {entry["preset"]: entry for entry in cls.record["demos"]}

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.workspace, ignore_errors=True)

    def manifest(self, preset: str) -> dict:
        directory = self.built[preset]["directory"]
        return json.loads((self.root / directory / "demo.json").read_text())

    def project(self, preset: str) -> Path:
        return self.root / self.built[preset]["directory"] / "project"

    def test_the_bank_holds_exactly_the_presets_the_table_names(self) -> None:
        """Both directions, so neither list can grow or shrink alone."""
        self.assertEqual(set(build.PRESETS), set(PRESET_TABLE))
        self.assertEqual(set(self.built), set(PRESET_TABLE))
        self.assertEqual(self.record["failed"], [], "a preset failed to build")

    def test_every_preset_is_the_starting_state_the_table_says(self) -> None:
        for preset, (agent, dataset, evaluator, calibration, venv) in sorted(
            PRESET_TABLE.items()
        ):
            with self.subTest(preset=preset):
                components = self.manifest(preset)["components"]
                self.assertEqual(components["agent"]["state"], agent)
                self.assertEqual(components["dataset"]["state"], dataset)
                self.assertEqual(components["evaluator"]["state"], evaluator)
                self.assertEqual(
                    components["evaluator"]["calibration"] is not None,
                    calibration == "present",
                    "the probe answers a project keeps are not what the table says",
                )
                self.assertEqual(
                    components["project_venv"] is not None,
                    venv == "ready",
                    "the project's own environment is not what the table says",
                )

    def test_every_preset_ships_the_files_its_states_name(self) -> None:
        """The bytes, not the label beside them.

        A preset records the state it was built in and separately copies a file. Recording
        `broken` and copying the honest scorer is a demo that says it is the always-correct
        ruler and measures correctly -- and every assertion made against the manifest alone
        would still pass.
        """
        for preset, (agent, _, evaluator, _, _) in sorted(PRESET_TABLE.items()):
            with self.subTest(preset=preset):
                project = self.project(preset)
                shipped = project / "evaluator.py"
                if evaluator == "missing":
                    self.assertFalse(shipped.exists())
                else:
                    source = (
                        REPO_ROOT
                        / "components"
                        / "evaluator"
                        / EVALUATOR_FILENAMES[evaluator]
                    )
                    self.assertEqual(
                        shipped.read_bytes(),
                        source.read_bytes(),
                        f"{preset} records {evaluator} and ships something else",
                    )
                agent_shipped = project / "agent.py"
                if agent == "missing":
                    self.assertFalse(agent_shipped.exists())
                else:
                    provider = self.manifest(preset)["components"]["agent"]["provider"]
                    self.assertEqual(
                        agent_shipped.read_bytes(),
                        (
                            REPO_ROOT
                            / "components"
                            / "agent"
                            / provider
                            / AGENT_FILENAMES[agent]
                        ).read_bytes(),
                        f"{preset} records agent {agent} and ships something else",
                    )

    def test_every_manifest_records_what_its_evaluator_honestly_is(self) -> None:
        """`method` is written into every manifest and was asserted nowhere.

        It is the one-word answer to "how does this project decide an answer is right",
        and docs/eval-methods.md asks the reader to take it on trust.
        """
        for preset, (_, _, evaluator, _, _) in sorted(PRESET_TABLE.items()):
            with self.subTest(preset=preset):
                recorded = self.manifest(preset)["components"]["evaluator"]
                if evaluator == "missing":
                    self.assertIsNone(recorded["method"])
                    self.assertIsNone(recorded["executes_candidate_output"])
                    continue
                self.assertEqual(
                    recorded["method"], EXPECTED_EVALUATOR_METHOD[evaluator]
                )
                self.assertEqual(
                    recorded["executes_candidate_output"], EXPECTED_EXECUTES[evaluator]
                )

    def test_every_preset_passes(self) -> None:
        result = run_build("--format", "json", "verify", "--demo", str(self.root))
        self.assertEqual(result.returncode, 0, result.stdout)
        report = json.loads(result.stdout)
        self.assertTrue(report["ok"])
        self.assertEqual(len(report["checked"]), len(PRESET_TABLE))
        for entry in report["checked"]:
            self.assertEqual(entry["problems"], [], entry["demo"])

    def test_no_directory_in_the_bank_says_what_its_demo_is(self) -> None:
        """A demo's own path is written into its environment, so the name has to say
        nothing -- and the bank's own record, which does say, sits outside every project.

        The whole path is checked, not only the directory the bank chose: the agent is
        started in `project/`, and every component of the path above it is written into
        that project's own environment the moment one is built.
        """
        for preset in sorted(PRESET_TABLE):
            with self.subTest(preset=preset):
                project = self.project(preset)
                for path in sorted([project, *project.rglob("*")]):
                    relative = path.relative_to(self.root)
                    for part in relative.parts:
                        self.assertEqual(
                            build.tells_in(part, f"the name {relative}"),
                            [],
                            f"{relative} names a starting state",
                        )
        self.assertTrue((self.root / build.BANK_RECORD).is_file())
        for preset in PRESET_TABLE:
            self.assertFalse(
                (self.project(preset) / build.BANK_RECORD).exists(),
                "the bank's record is inside a project an agent reads",
            )
            self.assertFalse(
                (self.project(preset) / "demo.json").exists(),
                "a demo's own record is inside the project the agent reads",
            )

    def test_the_bank_is_full_of_the_words_that_are_not_tells(self) -> None:
        """The false-alarm side of the blinding check, measured rather than argued.

        `holdout`, `tuning` and `difficulty` are real properties of the rows and occur
        thousands of times across a bank. If any of them became a tell, `verify` would fail
        every preset at once -- which is the same as having no check, because the only way
        to get a green run back would be to stop believing it.
        """
        occurrences = 0
        for path in sorted(self.root.rglob("*")):
            if not path.is_file():
                continue
            text = build.readable_text(path)
            if text is None:
                continue
            lowered = text.casefold()
            occurrences += sum(
                lowered.count(word) for word in ("holdout", "tuning", "difficulty")
            )
        self.assertGreater(
            occurrences,
            1000,
            "these words should be all over a bank; if they are not, this test is no "
            "longer measuring the false-alarm risk it exists for",
        )
        for word in ("holdout", "tuning", "difficulty", "directly", "empty"):
            self.assertEqual(build.tells_in(word, "a word"), [], word)

    def test_the_printed_bank_says_which_directory_is_which(self) -> None:
        """`render_suite` is what an operator reads, and nothing executed it."""
        for preset, (agent, dataset, evaluator, _, _) in sorted(PRESET_TABLE.items()):
            with self.subTest(preset=preset):
                directory = build.bank_directory(preset)
                line = next(
                    (
                        row
                        for row in self.suite_output.splitlines()
                        if row.strip().startswith(directory)
                    ),
                    None,
                )
                self.assertIsNotNone(
                    line, f"{preset} is missing from what suite printed"
                )
                for field in (preset, agent, dataset, evaluator):
                    self.assertIn(field, line or "")
        self.assertIn(build.HANDOFF_CLONE.splitlines()[0], self.suite_output)
        self.assertIn(build.BANK_RECORD, self.suite_output)
        self.assertNotIn("FAILED", self.suite_output)
        # Every preset's own note is published by `list`, which is the other half of the
        # same record. Checked here so the two cannot describe different banks.
        listing = run_build("list")
        self.assertEqual(listing.returncode, 0, listing.stderr)
        for preset in PRESET_TABLE:
            self.assertIn(build.PRESET_NOTES[preset], listing.stdout)


class TheDamageIsReallyThere(unittest.TestCase):
    """The two damaged datasets ship damaged data.

    This is the largest hole the mutation review found: four separate mutations passed,
    among them `damage_rows` returning `list(rows)` -- a `wrong-answers` project shipping
    the correct answers, and a `duplicated-data` project with nothing duplicated. Both are
    presets whose entire purpose is the damage, and every test in this file was green.

    build.py checks these properties itself while it builds. They are checked again from
    outside, on the file that ships, because a check that lives inside the thing it checks
    disappears with it.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.workspace = tempfile.mkdtemp()
        cls.projects = {}
        for state in ("wrong-answers", "duplicated"):
            out = Path(cls.workspace) / state
            build_or_raise("demo", "--dataset", state, "--out", str(out))
            cls.projects[state] = out / "project"
        cls.truth = slice_rows()

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.workspace, ignore_errors=True)

    def test_every_wrong_answer_runs_and_answers_a_different_question(self) -> None:
        """The damage is a pairing that runs. That is what makes it worth shipping.

        An answer that does not execute makes the damage obvious for the wrong reason; an
        answer that returns nothing scores the same as one that is right about an empty
        table; and an answer that did not move is indistinguishable from a correct row,
        which makes "every answer answers a different question" false and the damage
        unmeasurable at the same time.
        """
        project = self.projects["wrong-answers"]
        rows = rows_of(project)
        self.assertEqual(len(rows), EXPECTED_DAMAGED_ROWS)

        kept = []
        for row in rows:
            row_id = row["metadata"]["id"]
            gold = self.truth[row_id]["output"]
            if row["output"] == gold:
                kept.append(row_id)
            db_id = row["metadata"]["db_id"]
            database = project / "databases" / db_id / f"{db_id}.sqlite"
            connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
            connection.text_factory = lambda raw: raw.decode("utf-8", "replace")
            try:
                returned = connection.execute(row["output"]).fetchall()
            except sqlite3.Error as error:
                self.fail(f"{row_id}: the shipped answer does not run: {error}")
            finally:
                connection.close()
            self.assertTrue(
                returned, f"{row_id}: the shipped answer returns no rows from {db_id}"
            )
        self.assertEqual(
            kept,
            [],
            f"{len(kept)} rows kept the answer they came with, so the project's claim "
            "that every answer moved is not true of what it ships",
        )

    def test_the_rotation_stays_inside_each_database(self) -> None:
        """An answer borrowed from another database does not even run.

        Rotating across all of them would make the damage obvious for exactly the reason
        the damage was designed not to be obvious. Within a database the shipped answers
        are a permutation of the answers those rows came with -- nothing invented, nothing
        deleted, only the pairing wrong.
        """
        rows = rows_of(self.projects["wrong-answers"])
        by_database: dict[str, list[dict]] = {}
        for row in rows:
            by_database.setdefault(row["metadata"]["db_id"], []).append(row)
        self.assertGreater(len(by_database), 1, "the draw uses one database")
        for db_id, group in sorted(by_database.items()):
            with self.subTest(db_id=db_id):
                self.assertGreaterEqual(
                    len(group),
                    2,
                    "a database contributing one row cannot be rotated -- that row would "
                    "keep its own answer",
                )
                self.assertEqual(
                    sorted(row["output"] for row in group),
                    sorted(
                        self.truth[row["metadata"]["id"]]["output"] for row in group
                    ),
                    f"{db_id}: the shipped answers are not a rearrangement of its own",
                )

    def test_the_damaged_draw_is_balanced_across_difficulty(self) -> None:
        rows = rows_of(self.projects["wrong-answers"])
        self.assertEqual(
            dict(Counter(row["metadata"]["difficulty"] for row in rows)),
            {"easy": 15, "hard": 15, "medium": 15, "very-hard": 15},
        )

    def test_the_committed_slice_is_never_touched(self) -> None:
        """Damage happens on the way into a demo, not to the file on disk.

        README states this and nothing checked it. Measured across a build rather than
        after one: the hash of `spider_300.jsonl` is taken, a damaged demo is built from
        it, and the hash is taken again. Comparing the file with itself afterwards is the
        same read twice and could not have failed.
        """
        before = build.sha256_of(build.DATASET_PATH)
        with tempfile.TemporaryDirectory() as workspace:
            out = Path(workspace) / "demo"
            build_or_raise("demo", "--dataset", "wrong-answers", "--out", str(out))
            shipped = rows_of(out / "project")
        self.assertEqual(
            build.sha256_of(build.DATASET_PATH),
            before,
            "building a damaged demo rewrote the committed slice",
        )
        # And the damage really did happen somewhere -- otherwise an unchanged file would
        # be trivially unchanged.
        for row in shipped:
            self.assertNotEqual(
                row["output"], self.truth[row["metadata"]["id"]]["output"]
            )

    def test_duplicated_repeats_exactly_half_of_the_rows(self) -> None:
        """The shape of a set assembled by appending an export to itself.

        Half the rows twice, question and answer both, so a score computed over it counts
        the same evidence more than once.
        """
        rows = rows_of(self.projects["duplicated"])
        self.assertEqual(len(rows), int(EXPECTED_DAMAGED_ROWS * 1.5))
        counts = Counter(row["metadata"]["id"] for row in rows)
        self.assertEqual(
            dict(Counter(counts.values())),
            {1: 30, 2: 30},
            "the repeated half is not exactly half",
        )
        # Repeated whole, not a question paired with a different answer.
        by_id: dict[str, list[dict]] = {}
        for row in rows:
            by_id.setdefault(row["metadata"]["id"], []).append(row)
        for row_id, group in by_id.items():
            self.assertEqual(
                len({json.dumps(row, sort_keys=True) for row in group}),
                1,
                f"{row_id} appears twice and the two copies differ",
            )
            self.assertEqual(group[0]["output"], self.truth[row_id]["output"])

    def test_the_duplicated_draw_keeps_its_difficulty_spread(self) -> None:
        """The repeated half is drawn across the bands, not sliced off the front.

        Sorted by `(difficulty, input)`, the front of a 60-row set is every easy row and
        every hard row: the repeat used to ship easy 30 / hard 30 / medium 15 /
        very-hard 15, a difficulty spread nothing in the project accounts for and the
        `duplicated` arm then differed from the others in two ways at once.
        """
        rows = rows_of(self.projects["duplicated"])
        self.assertEqual(
            dict(Counter(row["metadata"]["difficulty"] for row in rows)),
            {"easy": 23, "hard": 23, "medium": 22, "very-hard": 22},
        )

    def test_the_manifest_says_the_damage_is_this_repositorys(self) -> None:
        """The questions and answers are Spider's; what is wrong with them is not."""
        for state in ("wrong-answers", "duplicated"):
            with self.subTest(dataset=state):
                manifest = json.loads(
                    (self.projects[state].parent / "demo.json").read_text()
                )
                dataset = manifest["components"]["dataset"]
                self.assertEqual(dataset["damage"], state)
                self.assertEqual(dataset["state"], state)
                self.assertEqual(dataset["rows"], len(rows_of(self.projects[state])))

    def test_an_undamaged_dataset_records_no_damage(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            out = Path(workspace) / "demo"
            build_or_raise("demo", "--dataset", "tiny", "--out", str(out))
            manifest = json.loads((out / "demo.json").read_text())
            self.assertIsNone(manifest["components"]["dataset"]["damage"])


class TheSmallerDrawsAreTheDrawTheyClaimToBe(unittest.TestCase):
    """What a smaller dataset actually draws, asserted on the file that ships.

    Every number here was either unasserted or asserted against the constant that produced
    it. `HOLDOUT_SHARE = 0.0` -- every smaller draw shipping nothing held back, so no winner
    could be checked against anything -- passed the whole suite.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.workspace = tempfile.mkdtemp()
        cls.rows = {}
        for state in ("mini", "tiny", "unlabeled"):
            out = Path(cls.workspace) / state
            build_or_raise("demo", "--dataset", state, "--out", str(out))
            cls.rows[state] = rows_of(out / "project")
        cls.truth = slice_rows()

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.workspace, ignore_errors=True)

    def test_the_sizes_are_the_documented_ones(self) -> None:
        self.assertEqual(len(self.rows["mini"]), EXPECTED_MINI_ROWS)
        self.assertEqual(len(self.rows["tiny"]), EXPECTED_TINY_ROWS)
        self.assertEqual(len(self.rows["unlabeled"]), EXPECTED_UNLABELED_ROWS)

    def test_every_draw_keeps_a_holdout_in_the_same_proportion(self) -> None:
        """Held back within each band, so the holdout is as hard as the tuning data.

        Asserted on the built `dataset.jsonl`. The committed slice's own split is checked
        in test_dataset.py; what is checked here is that a draw taken out of it keeps one.
        """
        for state, expected in EXPECTED_SPLIT_BY_BAND.items():
            with self.subTest(dataset=state):
                measured = Counter(
                    (row["metadata"]["difficulty"], row["metadata"]["split"])
                    for row in self.rows[state]
                )
                self.assertEqual(dict(measured), expected)
                held = sum(
                    count
                    for (_, split), count in measured.items()
                    if split == "holdout"
                )
                self.assertGreater(
                    held, 0, f"{state} ships nothing to check a winner against"
                )

    def test_a_drawn_row_keeps_the_side_of_the_line_it_came_from(self) -> None:
        """A row labelled `tuning` in the slice ships labelled `tuning`.

        Swapping the two labels leaves every count in this file unchanged and makes the
        holdout a set the winner was tuned on -- the winner's-curse control, silently
        inverted.
        """
        for state in ("mini", "tiny"):
            for row in self.rows[state]:
                with self.subTest(dataset=state, row=row["metadata"]["id"]):
                    self.assertEqual(
                        row["metadata"]["split"],
                        self.truth[row["metadata"]["id"]]["metadata"]["split"],
                    )

    def test_the_smaller_draw_is_the_same_draw_every_time(self) -> None:
        """The rows drawn, pinned as a hash of their ids in the order they ship.

        This used to build `mini` twice with the same code and compare the bytes -- a
        producer agreeing with itself, which passes under any seed and cannot fail across
        versions, though the docstring claimed exactly that. The hash is a literal in this
        file, so changing SAMPLE_SEED, the draw or the order fails here, which is what
        "everyone who builds one gets the same questions" has to mean.
        """
        for state, digest in DRAWN_ROW_IDS_SHA256.items():
            with self.subTest(dataset=state):
                self.assertEqual(
                    id_digest(self.rows[state]),
                    digest,
                    f"--dataset {state} draws different rows than it used to",
                )

    def test_every_drawn_row_is_a_row_of_the_committed_slice(self) -> None:
        """Unchanged, not merely present: a draw invents nothing and edits nothing."""
        for state, rows in self.rows.items():
            for row in rows:
                with self.subTest(dataset=state, row=row["metadata"]["id"]):
                    original = self.truth[row["metadata"]["id"]]
                    self.assertEqual(row["input"], original["input"])
                    if "output" in row:
                        self.assertEqual(row["output"], original["output"])

    def test_the_unlabelled_draw_carries_no_answer_and_no_split(self) -> None:
        for row in self.rows["unlabeled"]:
            self.assertNotIn("output", row)
            self.assertNotIn("split", row["metadata"])
        self.assertEqual(
            dict(
                Counter(row["metadata"]["difficulty"] for row in self.rows["unlabeled"])
            ),
            {"easy": 10, "hard": 10, "medium": 10, "very-hard": 10},
        )


class WhatEachProjectHandsTheAgent(unittest.TestCase):
    """The files a project ships, read for content rather than for existence."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.workspace = tempfile.mkdtemp()
        cls.projects = {}
        for name, args in (
            ("ready", ("--preset", "ready")),
            ("tiny", ("--dataset", "tiny")),
            ("no-agent", ("--preset", "no-agent")),
            ("empty", ("--preset", "empty")),
            ("logs-only", ("--preset", "logs-only")),
            ("two-agents", ("--preset", "two-agents")),
            ("holdout-only", ("--preset", "holdout-only")),
            ("raw-export", ("--preset", "raw-export")),
        ):
            out = Path(cls.workspace) / name
            build_or_raise("demo", "--out", str(out), *args)
            cls.projects[name] = out / "project"

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.workspace, ignore_errors=True)

    def test_the_catalog_carries_the_real_schema_of_the_real_database(self) -> None:
        """`"schema" in entry` is satisfied by an empty string.

        The catalog is the only place the agent can learn what the database looks like --
        `input` is a bare question. An empty schema is an agent guessing at table and
        column names against a database it cannot see, and `schema_context` is the setting
        most likely to move a score, so the arm would measure nothing.
        """
        project = self.projects["tiny"]
        catalog = json.loads((project / "catalog.json").read_text())
        self.assertEqual(set(catalog), {row["input"] for row in rows_of(project)})
        for question, entry in sorted(catalog.items()):
            with self.subTest(question=question[:50]):
                db_id = entry["db_id"]
                schema = entry["schema"]
                self.assertTrue(schema.strip(), "the schema is empty")
                database = project / "databases" / db_id / f"{db_id}.sqlite"
                connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
                try:
                    real = {
                        name.casefold()
                        for (name,) in connection.execute(
                            "select name from sqlite_master where type='table' "
                            "and name not like 'sqlite_%'"
                        )
                    }
                finally:
                    connection.close()
                declared = {
                    match.group(1).strip("\"`[]'").casefold()
                    for match in re.finditer(
                        r"CREATE TABLE\s+([^\s(]+)", schema, re.IGNORECASE
                    )
                }
                self.assertEqual(
                    declared,
                    real,
                    f"{db_id}: the catalog and the database disagree about which tables "
                    "exist",
                )

    def test_the_project_readme_describes_this_project(self) -> None:
        """Nothing read the README, so writing it empty passed.

        It is the first file a fresh agent opens, every line of it is derived from what was
        actually written, and in a project deliberately built with something missing a
        fixed description would hand over the very thing the run is supposed to discover.
        """
        for name, project in sorted(self.projects.items()):
            with self.subTest(preset=name):
                readme = (project / "README.md").read_text()
                self.assertGreater(len(readme), 400, "the README says almost nothing")
                self.assertIn("# Text-to-SQL", readme)
                self.assertIn(EXPECTED_HANDOFF, readme)
                self.assertNotIn("{{", readme, "a template placeholder was not filled")

                # The table lists every file that is there, and nothing that is not.
                listed = set(re.findall(r"^\| `([^`]+)` \|", readme, re.MULTILINE))
                on_disk = {
                    path.relative_to(project).as_posix()
                    for path in project.rglob("*")
                    if path.is_file()
                }
                self.assertIn("README.md", listed)
                self.assertIn(".env.example", listed)
                for entry in sorted(listed):
                    if entry.endswith("/"):
                        self.assertTrue(
                            (project / entry.rstrip("/")).is_dir(),
                            f"the README lists {entry} and it is not there",
                        )
                    else:
                        self.assertIn(
                            entry,
                            on_disk,
                            f"the README lists {entry} and it is not there",
                        )
                # A directory entry stands for everything under it, the way
                # `databases/` always has and `sql_explainer/` now does.
                directories = tuple(entry for entry in listed if entry.endswith("/"))
                for path in sorted(on_disk):
                    if path.startswith(directories):
                        continue
                    self.assertIn(
                        path,
                        listed,
                        f"{path} is in the project and the README does not mention it",
                    )

    def test_the_readme_says_what_is_there_and_not_what_is_not(self) -> None:
        """Each section is written only when the thing it describes is present."""
        ready = (self.projects["ready"] / "README.md").read_text()
        self.assertIn(
            "300 rows, each a question with the query that answers it.", ready
        )
        self.assertIn("18 SQLite databases", ready)
        self.assertIn("Spider", ready)
        self.assertIn("CC BY-SA 4.0", ready)
        self.assertIn("ATTRIBUTION.txt", ready)

        tiny = (self.projects["tiny"] / "README.md").read_text()
        self.assertIn(
            f"{EXPECTED_TINY_ROWS} rows, each a question with the query that answers it.",
            tiny,
        )

        # No agent: the README must not claim the project answers questions -- in the
        # opening line as well as in the section further down. The opening is the first
        # sentence a fresh agent reads, and a fixed one described a project that answers
        # questions in projects holding nothing to answer them with.
        no_agent = (self.projects["no-agent"] / "README.md").read_text()
        no_agent_opening = no_agent.split("## What is here")[0]
        self.assertIn("There is no agent here yet", no_agent)
        self.assertNotIn("`agent.py`", no_agent)
        self.assertNotIn(
            "Answers questions about a database by writing the SQL",
            no_agent_opening,
            "the opening claims the project answers questions and there is nothing here "
            "that could",
        )
        self.assertIn(
            "Questions about a database, and the SQL that answers them.",
            no_agent_opening,
        )

        # No agent and no rows: not even a claim that there are questions.
        empty_opening = (
            (self.projects["empty"] / "README.md")
            .read_text()
            .split("## What is here")[0]
        )
        self.assertIn("A place for something that turns a question", empty_opening)
        self.assertNotIn("Answers questions about a database", empty_opening)

        # No agent, and questions with no answers: questions, and no claim of answers.
        logs_opening = (
            (self.projects["logs-only"] / "README.md")
            .read_text()
            .split("## What is here")[0]
        )
        self.assertIn("Questions about a database.", logs_opening)
        self.assertNotIn("the SQL that answers them", logs_opening)
        self.assertNotIn("Answers questions about a database", logs_opening)

        # No rows: no data section, and nothing quoting a question that is not there.
        empty = (self.projects["empty"] / "README.md").read_text()
        self.assertNotIn("## The data", empty)
        self.assertNotIn("dataset.jsonl", empty)
        self.assertNotIn("Spider", empty)

        # Unlabelled rows: questions, and no claim that the answers are here.
        logs_only = (self.projects["logs-only"] / "README.md").read_text()
        self.assertIn("rows, each a question.", logs_only)
        self.assertNotIn("the query that answers it", logs_only)
        self.assertNotIn("metadata.split", logs_only)

        # Answers on some rows and not others: how many, and not "each".
        holdout_only = (self.projects["holdout-only"] / "README.md").read_text()
        self.assertIn(
            "30 rows, each a question; 6 of them carry the query that answers it.",
            holdout_only,
        )
        self.assertNotIn("each a question with the query", holdout_only)

        # Rows under Spider's own key names: the question quoted in the opening is read
        # from the key the rows actually use, not from one they do not carry.
        raw_export = (self.projects["raw-export"] / "README.md").read_text()
        first = rows_of(self.projects["raw-export"])[0]
        self.assertIn(first["question"], raw_export.split("## What is here")[0])
        self.assertIn('"question":', raw_export)
        self.assertIn('"query":', raw_export)

        # Two agents: the note and the second directory are in the table, and the
        # opening still describes the first agent, which is the one the note names.
        two_agents = (self.projects["two-agents"] / "README.md").read_text()
        self.assertIn("| `PROJECT.md` |", two_agents)
        self.assertIn("| `sql_explainer/` |", two_agents)
        self.assertIn("20 queries to run it on", two_agents)
        self.assertIn(
            "Answers questions about a database by writing the SQL", two_agents
        )

    def test_the_first_question_shown_is_shown_without_its_answer(self) -> None:
        """A project whose answers have been re-paired would announce the damage.

        The opening quotes one of the questions. Printing the row's answer beside it puts
        whatever that row holds on the first screen.
        """
        with tempfile.TemporaryDirectory() as workspace:
            out = Path(workspace) / "demo"
            build_or_raise("demo", "--dataset", "wrong-answers", "--out", str(out))
            readme = (out / "project" / "README.md").read_text()
            opening = readme.split("## What is here")[0]
            rows = rows_of(out / "project")
            self.assertIn(rows[0]["input"], opening)
            self.assertNotIn(rows[0]["output"], opening)


class TheCalibrationCasesNameRealRows(unittest.TestCase):
    """A probe points at a row of the slice, and at one row rather than at several.

    `check` tests only that a case's `expected` is *some* recorded answer, so a case whose
    gold string still exists while its `row_id` points at a deleted row and its `question`
    no longer matches passed silently and shipped. That is not a hypothetical: it happened
    during the re-cut, and nothing said so.
    """

    def test_every_case_names_one_row_and_describes_that_row(self) -> None:
        rows = slice_rows()
        for state, source in sorted(build.CALIBRATION_SOURCES.items()):
            cases = json.loads(source.read_text(encoding="utf-8"))
            self.assertGreaterEqual(len(cases), 2, f"{source.name} ships too few cases")
            for case in cases:
                with self.subTest(evaluator=state, case=case["name"]):
                    row_id = case["metadata"]["row_id"]
                    self.assertIn(
                        row_id,
                        rows,
                        f"{source.name}: names a row the slice does not hold",
                    )
                    row = rows[row_id]
                    question = case["input_data"]
                    if isinstance(question, dict):
                        question = question["question"]
                    self.assertEqual(
                        question,
                        row["input"],
                        "the case's question is not that row's question",
                    )
                    self.assertEqual(
                        case["expected"],
                        row["output"],
                        "the case's expected answer is not that row's answer",
                    )
                    self.assertEqual(
                        case["metadata"]["db_id"],
                        row["metadata"]["db_id"],
                        "the case names a different database than its row",
                    )
                    self.assertEqual(
                        case["metadata"]["split"], row["metadata"]["split"]
                    )

    def test_every_case_names_a_committed_database(self) -> None:
        for state, source in sorted(build.CALIBRATION_SOURCES.items()):
            for case in json.loads(source.read_text(encoding="utf-8")):
                db_id = case["metadata"]["db_id"]
                with self.subTest(evaluator=state, db_id=db_id):
                    self.assertTrue(
                        (
                            REPO_ROOT
                            / "spider"
                            / "databases"
                            / db_id
                            / f"{db_id}.sqlite"
                        ).is_file()
                    )


class TheNineNewStatesShipWhatTheyClaim(unittest.TestCase):
    """Each of the nine ported starting states, read off the bytes that ship.

    Every one of these is a state whose whole point is one specific thing being wrong or
    unusual, and build.py records that thing in `demo.json`. A record is a claim; these
    read the file beside it and check the claim is true of what an agent would open.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.workspace = tempfile.mkdtemp()
        cls.outs = {}
        for preset in (
            "leaky-split",
            "holdout-only",
            "split-by-database",
            "raw-export",
            "torn-lines",
            "undeclared-source",
            "opaque-scorer",
            "length-blind",
            "two-agents",
            "ready",
        ):
            # Built under the neutral name `suite` would give it: a directory named after
            # the preset is a tell, and `verify` says so -- which the last test here
            # relies on being true of every other path.
            out = Path(cls.workspace) / build.bank_directory(preset)
            build_or_raise("demo", "--preset", preset, "--out", str(out))
            cls.outs[preset] = out
        cls.truth = slice_rows()

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.workspace, ignore_errors=True)

    def project(self, preset: str) -> Path:
        return self.outs[preset] / "project"

    def dataset(self, preset: str) -> dict:
        return json.loads((self.outs[preset] / "demo.json").read_text())["components"][
            "dataset"
        ]

    def lines(self, preset: str) -> list[str]:
        return [
            line
            for line in (self.project(preset) / "dataset.jsonl")
            .read_text(encoding="utf-8")
            .split("\n")
            if line
        ]

    # ------------------------------------------------------------------ leaky-split

    def test_leaky_emits_six_tuning_rows_a_second_time_as_held_out_rows(self) -> None:
        rows = rows_of(self.project("leaky-split"))
        ready = rows_of(self.project("ready"))
        self.assertEqual(len(rows), 306)
        self.assertEqual(rows[:300], ready, "the first 300 rows are not the ready rows")
        copies = rows[300:]
        self.assertEqual(len(copies), 6)
        by_input = {row["input"]: row for row in ready}
        for copy in copies:
            with self.subTest(row=copy["metadata"]["id"]):
                original = by_input[copy["input"]]
                self.assertEqual(original["metadata"]["split"], "tuning")
                self.assertEqual(copy["metadata"]["split"], "holdout")
                self.assertEqual(copy["output"], original["output"])
                self.assertEqual(
                    copy["metadata"]["id"], original["metadata"]["id"] + "-holdout"
                )
        # Both sides of the line hold the same question: that is the leak.
        tuning = {r["input"] for r in rows if r["metadata"]["split"] == "tuning"}
        holdout = {r["input"] for r in rows if r["metadata"]["split"] == "holdout"}
        self.assertEqual(len(tuning & holdout), 6)
        self.assertEqual(
            Counter(c["metadata"]["difficulty"] for c in copies),
            {"easy": 2, "hard": 2, "medium": 1, "very-hard": 1},
        )
        record = self.dataset("leaky-split")
        self.assertEqual(record["damage"], "leaky")
        self.assertEqual(
            sorted(record["damage_detail"]["leaked_ids"]),
            sorted(c["metadata"]["id"][: -len("-holdout")] for c in copies),
        )
        self.assertEqual(record["split_counts"], {"holdout": 66, "tuning": 240})

    # ------------------------------------------------------------------ holdout-only

    def test_holdout_labelled_keeps_answers_on_the_held_out_rows_only(self) -> None:
        rows = rows_of(self.project("holdout-only"))
        self.assertEqual(len(rows), EXPECTED_MINI_ROWS)
        self.assertEqual(id_digest(rows), DRAWN_ROW_IDS_SHA256["mini"])
        labelled = 0
        for row in rows:
            with self.subTest(row=row["metadata"]["id"]):
                if row["metadata"]["split"] == "holdout":
                    labelled += 1
                    self.assertEqual(
                        row["output"], self.truth[row["metadata"]["id"]]["output"]
                    )
                else:
                    self.assertNotIn("output", row)
        self.assertEqual(labelled, 6)
        record = self.dataset("holdout-only")
        self.assertFalse(record["labelled"])
        self.assertEqual(record["labelled_rows"], 6)
        self.assertEqual(record["damage"], "holdout-labelled")

    # ------------------------------------------------------------------ split-by-database

    def test_split_by_database_holds_out_whole_databases(self) -> None:
        rows = rows_of(self.project("split-by-database"))
        self.assertEqual(len(rows), 300)
        self.assertEqual(
            [r["metadata"]["id"] for r in rows],
            [r["metadata"]["id"] for r in rows_of(self.project("ready"))],
        )
        sides: dict[str, set[str]] = {}
        for row in rows:
            sides.setdefault(row["metadata"]["db_id"], set()).add(
                row["metadata"]["split"]
            )
            self.assertEqual(row["output"], self.truth[row["metadata"]["id"]]["output"])
        for db_id, splits in sorted(sides.items()):
            self.assertEqual(len(splits), 1, f"{db_id} sits on both sides of the line")
        held = sorted(db for db, s in sides.items() if s == {"holdout"})
        # Pinned as a literal: the cut is seeded, and everyone who builds this state
        # has to hold out the same databases.
        self.assertEqual(
            held,
            [
                "cre_Doc_Template_Mgt",
                "flight_2",
                "orchestra",
                "real_estate_properties",
                "singer",
            ],
        )
        held_rows = sum(1 for r in rows if r["metadata"]["split"] == "holdout")
        self.assertEqual(held_rows, 61)
        self.assertGreaterEqual(held_rows / len(rows), 0.15)
        self.assertLessEqual(held_rows / len(rows), 0.25)
        record = self.dataset("split-by-database")
        self.assertEqual(record["damage_detail"]["held_out_databases"], held)

    # ------------------------------------------------------------------ raw-export

    def test_raw_export_writes_spiders_own_key_names(self) -> None:
        rows = [json.loads(line) for line in self.lines("raw-export")]
        self.assertEqual(len(rows), 300)
        for row in rows:
            with self.subTest(row=row["metadata"]["id"]):
                self.assertEqual(
                    sorted(row), ["db_id", "metadata", "query", "question"]
                )
                original = self.truth[row["metadata"]["id"]]
                self.assertEqual(row["question"], original["input"])
                self.assertEqual(row["query"], original["output"])
                self.assertEqual(row["db_id"], original["metadata"]["db_id"])
                self.assertEqual(row["metadata"], original["metadata"])
        catalog = json.loads((self.project("raw-export") / "catalog.json").read_text())
        self.assertEqual(set(catalog), {row["question"] for row in rows})
        record = self.dataset("raw-export")
        self.assertEqual(record["fields"], {"input": "question", "output": "query"})
        self.assertTrue(record["labelled"])

    # ------------------------------------------------------------------ torn-lines

    def test_torn_cuts_exactly_two_lines_and_records_which(self) -> None:
        lines = self.lines("torn-lines")
        self.assertEqual(len(lines), EXPECTED_MINI_ROWS)
        torn = []
        whole = []
        for number, line in enumerate(lines, 1):
            try:
                whole.append(json.loads(line))
            except ValueError:
                torn.append(number)
        self.assertEqual(torn, [10, 20])
        self.assertNotIn(1, torn)
        self.assertEqual(len(whole), 28)
        record = self.dataset("torn-lines")
        self.assertEqual(record["damage"], "torn")
        self.assertEqual(record["damage_detail"]["torn_lines"], torn)
        # The 28 whole rows are the mini draw's rows, unchanged, minus the two cut ones.
        mini = build.select_rows(build.read_dataset(), "mini")
        expected = [
            build.project_row(row, "torn")
            for number, row in enumerate(mini, 1)
            if number not in torn
        ]
        self.assertEqual(whole, expected)
        # And each torn line is the front of the row it was cut from.
        for number in torn:
            self.assertTrue(
                json.dumps(
                    build.project_row(mini[number - 1], "torn"),
                    ensure_ascii=False,
                    sort_keys=True,
                ).startswith(lines[number - 1])
            )

    # ------------------------------------------------------------------ undeclared-source

    def test_undeclared_writes_a_provenance_word_the_guide_does_not_know(self) -> None:
        rows = rows_of(self.project("undeclared-source"))
        ready = rows_of(self.project("ready"))
        self.assertEqual(len(rows), 300)
        for row, original in zip(rows, ready):
            with self.subTest(row=row["metadata"]["id"]):
                self.assertEqual(row["metadata"]["provenance"], "spider-dev")
                restored = {
                    **row,
                    "metadata": {**row["metadata"], "provenance": "real"},
                }
                self.assertEqual(restored, original)
        self.assertEqual(
            self.dataset("undeclared-source")["damage_detail"],
            {"provenance": "spider-dev", "slice_says": "real"},
        )
        # The committed slice still says `real`, which docs/dataset.md explains.
        self.assertTrue(
            all(row["metadata"]["provenance"] == "real" for row in self.truth.values())
        )

    # ------------------------------------------------------------------ opaque-scorer

    def test_opaque_ships_a_scorer_that_imports_a_library_the_project_lacks(
        self,
    ) -> None:
        shipped = (self.project("opaque-scorer") / "evaluator.py").read_text()
        self.assertIn("from sqlgrade.compare import QueryGrader", shipped)
        self.assertEqual(
            shipped,
            (REPO_ROOT / "components" / "evaluator" / "opaque.py").read_text(),
        )
        self.assertFalse(
            (self.project("opaque-scorer") / build.RUNS_DIRECTORY).exists(),
            "probe answers shipped for a scorer nothing here has ever run",
        )
        record = json.loads((self.outs["opaque-scorer"] / "demo.json").read_text())[
            "components"
        ]["evaluator"]
        self.assertIsNone(record["method"])
        self.assertIsNone(record["executes_candidate_output"])
        self.assertIsNone(record["calibration"])
        # Nothing the project ships resolves the import.
        self.assertFalse(
            list(self.project("opaque-scorer").rglob("sqlgrade*")),
            "the project carries the library the scorer is supposed to be missing",
        )

    def test_opaque_refuses_to_ship_probes(self) -> None:
        out = Path(self.workspace) / "opaque_with_probes"
        result = run_build(
            "demo", "--eval", "opaque", "--calibration", "present", "--out", str(out)
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("nothing could vouch for the probes", result.stderr)
        self.assertFalse(out.exists(), "a refused build left a directory behind")

    # ------------------------------------------------------------------ length-blind

    def test_length_blind_ships_the_length_scorer_and_the_text_probes(self) -> None:
        project = self.project("length-blind")
        shipped = (project / "evaluator.py").read_text()
        self.assertEqual(
            shipped,
            (REPO_ROOT / "components" / "evaluator" / "length_blind.py").read_text(),
        )
        self.assertIn("abs(len(produced) - len(recorded))", shipped)
        probes = project / build.RUNS_DIRECTORY / build.CALIBRATION_FILE
        self.assertTrue(probes.is_file())
        self.assertEqual(
            probes.read_bytes(),
            (
                REPO_ROOT / "components" / "calibration" / "exact_match.json"
            ).read_bytes(),
        )
        record = json.loads((self.outs["length-blind"] / "demo.json").read_text())[
            "components"
        ]["evaluator"]
        self.assertIsNone(record["method"])
        self.assertIs(record["executes_candidate_output"], False)
        self.assertEqual(record["calibration"]["case_count"], 4)

    # ------------------------------------------------------------------ two-agents

    def test_two_agents_ships_the_tunable_agent_and_a_second_one_beside_it(
        self,
    ) -> None:
        project = self.project("two-agents")
        provider = build.DEFAULT_PROVIDER
        self.assertEqual(
            (project / "agent.py").read_bytes(),
            (
                REPO_ROOT / "components" / "agent" / provider / "agent_ready.py"
            ).read_bytes(),
        )
        sibling = project / "sql_explainer"
        self.assertEqual(
            sorted(p.name for p in sibling.iterdir()),
            ["agent.py", "dataset.jsonl", "evaluator.py"],
        )
        self.assertEqual(
            (sibling / "agent.py").read_bytes(),
            (
                REPO_ROOT / "components" / "explainer" / provider / "agent.py"
            ).read_bytes(),
        )
        self.assertEqual(
            (sibling / "evaluator.py").read_bytes(),
            (REPO_ROOT / "components" / "explainer" / "evaluator.py").read_bytes(),
        )
        note = (project / "PROJECT.md").read_text()
        self.assertEqual(
            note, (REPO_ROOT / "components" / "explainer" / "PROJECT.md").read_text()
        )
        self.assertIn("`agent.py`", note)
        self.assertIn("`sql_explainer/`", note)
        self.assertIn("the one to work on", note)

        rows = rows_of(sibling)
        self.assertEqual(len(rows), 20)
        golds = {row["output"] for row in self.truth.values()}
        for row in rows:
            with self.subTest(row=row["metadata"]["id"]):
                self.assertNotIn("output", row)
                self.assertIn(row["input"], golds)
                self.assertEqual(
                    row["input"], self.truth[row["metadata"]["id"]]["output"]
                )
                self.assertEqual(
                    sorted(row["metadata"]), ["db_id", "difficulty", "id", "provenance"]
                )
        self.assertEqual(
            Counter(r["metadata"]["difficulty"] for r in rows),
            {"easy": 5, "hard": 5, "medium": 5, "very-hard": 5},
        )
        record = json.loads((self.outs["two-agents"] / "demo.json").read_text())[
            "components"
        ]["agent"]
        self.assertEqual(record["state"], "two-agents")
        self.assertEqual(record["path"], "agent.py")
        self.assertEqual(
            record["second_agent"],
            {
                "directory": "sql_explainer",
                "path": "sql_explainer/agent.py",
                "evaluator": "sql_explainer/evaluator.py",
                "dataset": "sql_explainer/dataset.jsonl",
                "rows": 20,
                "labelled": False,
                "models": ["openrouter/qwen/qwen3-coder"],
                "note": "PROJECT.md",
            },
        )
        # The first agent's roster is the tunable one's, and the second's is its own.
        self.assertEqual(len(record["models"]), 3)

    def test_a_second_agent_draws_from_the_rows_before_damage(self) -> None:
        """`duplicated` repeats ids and `leaky` mints `-holdout` copies; neither may reach
        the second agent's file, whose damage no record describes."""
        for state in ("duplicated", "leaky"):
            with self.subTest(dataset=state):
                out = Path(self.workspace) / f"two_agents_{state}"
                result = run_build(
                    "demo",
                    "--agent",
                    "two-agents",
                    "--dataset",
                    state,
                    "--out",
                    str(out),
                )
                self.assertEqual(result.returncode, 0, result.stderr)
                rows = [
                    json.loads(line)
                    for line in (out / "project" / "sql_explainer" / "dataset.jsonl")
                    .read_text()
                    .splitlines()
                ]
                ids = [row["metadata"]["id"] for row in rows]
                self.assertEqual(len(ids), len(set(ids)), ids)
                self.assertFalse(
                    [name for name in ids if name.endswith("-holdout")], ids
                )
                self.assertEqual(len(rows), build.SECOND_AGENT_ROWS)

    def test_a_mostly_state_declares_on_most_of_the_rows_and_not_all(self) -> None:
        """ "Mostly" is the whole difference, and nothing was checking it.

        The guide's provenance and answer-key ladders each have a rung at more
        than half, which is why these states exist beside the all-rows ones.
        Rewriting `mostly-undeclared` to touch all three hundred rows made it a
        duplicate of `undeclared` with the suite green and the README still
        reading "180 of the 300"; so did moving `MOSTLY_SHARE`, and so did
        replacing the band-balanced draw with the front of the list.
        """

        # Whether 180 of 300 sits above the rung the guide's two ladders put at "more
        # than half" is the guide's to say, and it says it on the committed card:
        # `tests/test_score_bank.py` holds each `mostly-` preset's card to the
        # `dataset-mostly-*` condition `build.PRESET_CAPS` says it was built for, and
        # the measurement job re-takes those cards at the pinned guide. A copy of the
        # guide's 0.5 here would agree with itself whatever the guide did. What is
        # checked here is this repository's half: how many rows the state touches.
        for state, declared_key, declared_value in (
            ("mostly-undeclared", "provenance", build.UNDECLARED_PROVENANCE),
            ("mostly-synthetic", "provenance", build.SYNTHETIC_PROVENANCE),
            (
                "mostly-generated-answers",
                build.GENERATED_ANSWER_KEY,
                build.GENERATED_ANSWER_PROVENANCE,
            ),
        ):
            with self.subTest(dataset=state):
                out = Path(self.workspace) / f"mostly_{state}"
                if not out.exists():
                    built = run_build("demo", "--dataset", state, "--out", str(out))
                    self.assertEqual(built.returncode, 0, built.stderr)
                rows = [
                    json.loads(line)
                    for line in (out / "project" / "dataset.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                    if line.strip()
                ]
                touched = [
                    row
                    for row in rows
                    if row["metadata"].get(declared_key) == declared_value
                ]
                self.assertEqual(180, len(touched), "the declared count moved")
                self.assertEqual(300, len(rows))
                self.assertLess(
                    len(touched),
                    len(rows),
                    "touching every row makes this the all-rows state under a "
                    "different name",
                )
                bands = collections.Counter(
                    row["metadata"]["difficulty"] for row in touched
                )
                self.assertEqual(
                    1,
                    len(set(bands.values())),
                    f"the draw is meant to be band-balanced and reads {dict(bands)}",
                )

    def test_all_rows_states_really_declare_on_all_of_them(self) -> None:
        """The other end of the same pair, for the same reason."""

        out = Path(self.workspace) / "all_generated_answers"
        if not out.exists():
            built = run_build(
                "demo", "--dataset", "generated-answers", "--out", str(out)
            )
            self.assertEqual(built.returncode, 0, built.stderr)
        rows = [
            json.loads(line)
            for line in (out / "project" / "dataset.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if line.strip()
        ]
        self.assertEqual(
            len(rows),
            sum(
                1
                for row in rows
                if row["metadata"].get(build.GENERATED_ANSWER_KEY)
                == build.GENERATED_ANSWER_PROVENANCE
            ),
        )

    def test_the_answer_key_field_is_one_the_guide_reads(self) -> None:
        """A declaration in a field nothing reads declares nothing.

        `preflight.py`'s `row_output_provenance` looks at `output_provenance` and
        `output_source`, at the row's top level or inside `metadata`. Renaming
        this constant to anything else leaves both answer-key states writing a
        field the guide never opens -- their cards would quietly stop reading 74
        and nothing in the suite would notice.
        """

        self.assertIn(
            build.GENERATED_ANSWER_KEY, ("output_provenance", "output_source")
        )

    def test_the_slow_scorer_is_slow_enough_to_reach_the_timeout(self) -> None:
        """The state is "too slow for the budget", so the two have to relate.

        `SECONDS_PER_CALL` set to zero leaves a preset called `slow-scorer` that
        is not slow, and a committed card recording `timed_out: true` that can
        no longer be reproduced -- with nothing red.
        """

        located = importlib.util.spec_from_file_location(
            "_slow_timing", REPO_ROOT / "components" / "evaluator" / "slow.py"
        )
        assert located is not None and located.loader is not None
        scorer = importlib.util.module_from_spec(located)
        sys.modules[located.name] = scorer
        located.loader.exec_module(scorer)
        cases = json.loads(
            (REPO_ROOT / "components" / "calibration" / "slow.json").read_text(
                encoding="utf-8"
            )
        )
        # The guide makes at least one call per shipped probe, and more: a
        # deterministic case gets supplemental probes on top of the four in the
        # file. Counting only the four is the conservative direction -- if even
        # that exceeds the budget, the real run does too.
        calls = sum(len(case["probes"]) for case in cases)
        self.assertGreater(
            calls * scorer.SECONDS_PER_CALL,
            SLOW_SCORER_CALIBRATION_BUDGET_SECONDS,
            "checking this scorer has to outlast the budget the sweep allows, or "
            "the timeout the committed card records is not reached",
        )

    def test_the_slow_scorer_keeps_the_case_inside_a_quoted_value(self) -> None:
        """The rule `exact_match.py` states, applied to the scorer beside it.

        "Case inside a quoted string is kept, because 'France' and 'france' are
        different values even though SELECT and select are the same keyword."
        The first version of the slow scorer folded the whole query in one
        `translate`, which is the tempting one-liner and re-introduced exactly
        the behaviour that docstring argues down -- on the same example.
        """

        located = importlib.util.spec_from_file_location(
            "_slow", REPO_ROOT / "components" / "evaluator" / "slow.py"
        )
        assert located is not None and located.loader is not None
        scorer = importlib.util.module_from_spec(located)
        sys.modules[located.name] = scorer
        located.loader.exec_module(scorer)
        scorer.SECONDS_PER_CALL = 0.0

        recorded = "SELECT name FROM singer WHERE country != 'France'"
        self.assertEqual(
            0.0,
            scorer.score("SELECT name FROM singer WHERE country != 'france'", recorded),
            "a filter on a different value is not the same answer",
        )
        self.assertEqual(
            1.0,
            scorer.score(
                "select  NAME from SINGER where COUNTRY != 'France' ;", recorded
            ),
            "keyword case, spacing and a trailing semicolon still do not matter",
        )

    def test_the_slow_scorer_keeps_the_spacing_inside_a_quoted_value(self) -> None:
        """The same rule for whitespace: 'New  York' and 'New York' are two values.

        The case fix above folded only outside quotes and then collapsed whitespace
        across the whole query, inside quotes included -- the same defect one
        character class over, and a filter that matches no row scored 1.0.
        """

        scorer = load_scorer("slow")
        recorded = "SELECT name FROM city WHERE name = 'New York'"
        self.assertEqual(
            0.0,
            scorer.score("SELECT name FROM city WHERE name = 'New  York'", recorded),
            "a filter on a different value is not the same answer",
        )
        self.assertEqual(
            1.0,
            scorer.score(
                "SELECT  name\nFROM city   WHERE name = 'New York' ;", recorded
            ),
            "spacing outside the quoted value still does not matter",
        )

    def test_the_slow_scorer_accepts_nothing_the_text_comparator_rejects(
        self,
    ) -> None:
        """The mechanism, rather than one more instance of it.

        `slow.py` states the weaker comparison: whitespace, keyword case and a
        trailing semicolon, and nothing about quoting. So wherever it says two
        queries are the same, the text comparator -- whose docstring owns the rule
        about quoted values -- has to say so too. Both defects the slow scorer has
        shipped were exactly this: an answer it accepted and `exact_match.py`
        refused. Held here over every quoted value in the slice, re-spaced and
        re-cased inside the quotes, with a control that the comparison outside
        them still passes.
        """

        slow = load_scorer("slow")
        exact = load_scorer("exact_match")
        quoted = re.compile(r"(['\"])([^'\"]+)\1")
        inside = 0
        for row in build.read_dataset():
            recorded = row["output"]
            found = quoted.search(recorded)
            if not found:
                continue
            value = found.group(2)
            respaced = (
                value.replace(" ", "  ") if " " in value else f"{value[0]} {value[1:]}"
            )
            variants = [respaced]
            if value.swapcase() != value:
                variants.append(value.swapcase())
            for variant in variants:
                candidate = (
                    recorded[: found.start(2)] + variant + recorded[found.end(2) :]
                )
                with self.subTest(row=row["metadata"]["id"], candidate=candidate):
                    self.assertEqual(0.0, exact.score(candidate, recorded))
                    self.assertEqual(
                        0.0,
                        slow.score(candidate, recorded),
                        "the slow scorer accepts a changed quoted value",
                    )
                    inside += 1
            if len(quoted.findall(recorded)) != 1:
                continue
            # Everything outside the one quoted value re-spaced and upper-cased, the
            # value itself untouched: both comparators have to call that the same.
            outside = (
                "  "
                + recorded[: found.start()].upper().replace(" ", "   ")
                + found.group(0)
                + recorded[found.end() :].upper()
                + ("" if recorded.rstrip().endswith(";") else " ;")
            )
            with self.subTest(row=row["metadata"]["id"], control=outside):
                self.assertEqual(1.0, exact.score(outside, recorded))
                self.assertEqual(1.0, slow.score(outside, recorded))
        self.assertGreater(
            inside, 0, "no quoted value was changed, so none was checked"
        )

    def test_a_probe_called_equivalent_returns_the_same_rows(self) -> None:
        """A text probe's claim is checkable by running it, so run it.

        `equivalent_good` asserts that a re-spelling of the recorded query is
        the same answer. Nothing was checking that against the database, and a
        probe file written by the same hand as the scorer agrees with the
        scorer by construction: the first `slow.json` declared four such
        probes, three of which returned different rows -- one of them none at
        all, and one re-admitting the French singer a `!= 'France'` filter
        exists to exclude. Both the scorer and its probes said 1.0.
        """

        databases = REPO_ROOT / "spider" / "databases"
        checked = 0
        for name in ("exact_match.json", "slow.json"):
            cases = json.loads(
                (REPO_ROOT / "components" / "calibration" / name).read_text(
                    encoding="utf-8"
                )
            )
            for case in cases:
                database = case["metadata"]["db_id"]
                path = databases / database / f"{database}.sqlite"
                self.assertTrue(path.is_file(), f"{name}: no database for {database}")
                connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
                try:
                    expected = connection.execute(case["expected"]).fetchall()
                    for probe in ("good", "equivalent_good"):
                        with self.subTest(
                            file=name, row=case["metadata"]["row_id"], probe=probe
                        ):
                            rows = connection.execute(case["probes"][probe]).fetchall()
                            self.assertEqual(
                                expected,
                                rows,
                                f"{name}: {probe} for {case['metadata']['row_id']} is "
                                f"declared the same answer and returns different rows",
                            )
                            checked += 1
                finally:
                    connection.close()
        self.assertGreater(checked, 0, "no probe was executed, so nothing was checked")

    def test_every_damage_detail_field_is_checked_against_the_rows(self) -> None:
        """A record that restates a constant can restate the wrong one.

        Three of `damage_detail`'s fields are read off the rows that ship, and
        those are pinned elsewhere. The rest were restated from the constants
        that produced them, and could be falsified one at a time with the whole
        suite green -- `labelled_split: "tuning"` on a `holdout-labelled` demo
        is the exact inverse of the file beside it. `docs/isolation.md` says
        `demo.json` records what was done to the rows, so every field is read
        back out of the bytes here.
        """

        def rows_of(out: Path) -> list[dict[str, object]]:
            lines = (
                (out / "project" / "dataset.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            )
            return [json.loads(line) for line in lines if line.strip()]

        def detail_of(out: Path) -> dict[str, object]:
            manifest = json.loads((out / "demo.json").read_text(encoding="utf-8"))
            return manifest["components"]["dataset"]["damage_detail"]

        with self.subTest(dataset="holdout-labelled"):
            out = self.outs["holdout-only"]
            detail = detail_of(out)
            labelled = {
                row["metadata"]["split"] for row in rows_of(out) if "output" in row
            }
            self.assertEqual({detail["labelled_split"]}, labelled)

        with self.subTest(dataset="raw-export"):
            out = self.outs["raw-export"]
            detail = detail_of(out)
            rows = rows_of(out)
            self.assertTrue(
                all(key in rows[0] for key in detail["keys"].values()), rows[0]
            )
            for name in detail["top_level"]:
                self.assertIn(name, rows[0])

        with self.subTest(dataset="torn"):
            out = self.outs["torn-lines"]
            detail = detail_of(out)
            raw = (
                (out / "project" / "dataset.jsonl")
                .read_text(encoding="utf-8")
                .splitlines()
            )
            # Each torn line is a prefix of the row it was cut from, so the row
            # is recoverable from the slice by that prefix -- and then the cut
            # can be pinned from BOTH sides. An upper bound on the torn line's
            # length passes for any LARGER `cut_at` as happily as for the right
            # one, which is how a falsified `cut_at` stayed green.
            whole = [
                json.dumps(
                    build.project_row(row, "torn"), ensure_ascii=False, sort_keys=True
                )
                for row in self.truth.values()
            ]
            for number in detail["torn_lines"]:
                cut = raw[number - 1]
                with self.assertRaises(ValueError):
                    json.loads(cut)
                originals = [line for line in whole if line.startswith(cut)]
                self.assertEqual(1, len(originals), f"line {number} matches no row")
                self.assertEqual(int(len(originals[0]) * detail["cut_at"]), len(cut))

        with self.subTest(dataset="undeclared"):
            out = self.outs["undeclared-source"]
            detail = detail_of(out)
            self.assertEqual(
                {detail["provenance"]},
                {row["metadata"]["provenance"] for row in rows_of(out)},
            )
            self.assertNotEqual(detail["provenance"], detail["slice_says"])

        with self.subTest(dataset="leaky"):
            out = self.outs["leaky-split"]
            detail = detail_of(out)
            copies = [
                row
                for row in rows_of(out)
                if str(row["metadata"]["id"]).endswith(detail["copy_id_suffix"])
            ]
            self.assertTrue(copies)
            self.assertEqual(
                {detail["copy_split"]},
                {row["metadata"]["split"] for row in copies},
            )

        for state, preset, key, value in (
            ("mostly-undeclared", "mostly-undeclared-source", "provenance", None),
            ("mostly-synthetic", "mostly-synthetic-source", "provenance", None),
            ("generated-answers", "generated-answer-key", "output_provenance", None),
            (
                "mostly-generated-answers",
                "mostly-generated-answer-key",
                "output_provenance",
                None,
            ),
        ):
            with self.subTest(dataset=state):
                out = Path(self.workspace) / f"damage_detail_{state}"
                if not out.exists():
                    built = run_build("demo", "--preset", preset, "--out", str(out))
                    self.assertEqual(built.returncode, 0, built.stderr)
                detail = detail_of(out)
                rows = rows_of(out)
                declared = detail.get("provenance") or detail.get("output_provenance")
                counted = sum(1 for row in rows if row["metadata"].get(key) == declared)
                self.assertEqual(detail["declared_rows"], counted)
                self.assertEqual(detail["of_rows"], len(rows))
                self.assertNotEqual(
                    detail["slice_says"],
                    declared,
                    "the record says the slice already read this, which it did not",
                )

        with self.subTest(dataset="wrong-answers"):
            out = Path(self.workspace) / "damage_detail_wrong_answers"
            built = run_build("demo", "--preset", "wrong-answers", "--out", str(out))
            self.assertEqual(built.returncode, 0, built.stderr)
            detail = detail_of(out)
            truth = {
                identifier: row["output"]
                for identifier, row in self.truth.items()
                if "output" in row
            }
            kept = sum(
                1
                for row in rows_of(out)
                if row.get("output") == truth.get(row["metadata"]["id"])
            )
            self.assertEqual(detail["rows_keeping_their_answer"], kept)
            self.assertEqual(
                1,
                len(
                    {
                        row["metadata"]["db_id"]
                        for row in rows_of(out)
                        if row["metadata"]["id"] == rows_of(out)[0]["metadata"]["id"]
                    }
                ),
                "the rotation is declared to stay within " + detail["rotated_within"],
            )

    def test_verify_reads_the_project_as_utf_8_whatever_the_locale_says(self) -> None:
        """`build.py verify --demo` is the README's first-screen command.

        Every writer here passes `encoding="utf-8"`; `verify_demo` was the one
        reader that did not, so on a machine with `LANG` unset it read the rows
        as ASCII and failed on the typographic apostrophe two of them carry.
        `UnicodeDecodeError` is a `ValueError`, so the existing handler caught
        it and reported a correct project as damaged -- and the `torn` state
        makes "lines that are not JSON" a real condition, so the environment
        failure wore the exact costume of the feature.
        """

        out = Path(self.workspace) / "locale_verify"
        built = run_build("demo", "--preset", "ready", "--out", str(out))
        self.assertEqual(built.returncode, 0, built.stderr)

        result = run_build("verify", "--demo", str(out), env=ascii_locale_env())

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)

    def test_a_second_agent_may_not_ship_an_answer_the_dataset_withholds(self) -> None:
        """The second agent's input IS the row's gold query.

        Drawn from the whole slice, `--dataset unlabeled` shipped forty rows with
        no answers and the gold query for twenty of them in a file beside them,
        under the same ids -- a project blind to nothing at all, which `verify`
        called `ok`. The refusal is keyed on whether a row ships its answer, not
        on a list of state names, so a labelling state added later is covered.
        """
        for state, withheld in (("unlabeled", "40"), ("holdout-labelled", "24")):
            with self.subTest(dataset=state):
                out = Path(self.workspace) / f"two_agents_withheld_{state}"
                result = run_build(
                    "demo",
                    "--agent",
                    "two-agents",
                    "--dataset",
                    state,
                    "--out",
                    str(out),
                )
                self.assertEqual(result.returncode, 2, result.stdout)
                self.assertIn("withholds the answer on", result.stderr)
                self.assertIn(withheld, result.stderr)
                self.assertFalse(out.exists(), f"{out} was left behind")

    def test_every_metadata_key_is_classified_as_structure_or_declaration(
        self,
    ) -> None:
        """A field in neither set is a field nobody decided about.

        The second agent mirrors declarations and not structure, so the split
        decides what a sibling file repeats. Deriving one side from the other
        swept the row's whole CREATE TABLE block into a file with no use for
        it; naming both sides only helps while every key is in one of them.
        """

        # Every state that ships rows, not only the ones already known to declare:
        # a state that writes a field in neither set is exactly the one a list of
        # "declaring" states -- read off the fields already named -- would miss.
        seen: set[str] = set()
        for state in build.DATASET_STATES:
            if state == "missing":
                continue
            with self.subTest(dataset=state):
                out = Path(self.workspace) / f"classified_{state}"
                if not out.exists():
                    built = run_build("demo", "--dataset", state, "--out", str(out))
                    self.assertEqual(built.returncode, 0, built.stderr)
                unreadable = 0
                for line in (
                    (out / "project" / "dataset.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                ):
                    if not line.strip():
                        continue
                    try:
                        row = json.loads(line)
                    except json.JSONDecodeError:
                        unreadable += 1
                        continue
                    seen |= set(row["metadata"])
                self.assertEqual(
                    build.TORN_LINES if state == "torn" else 0,
                    unreadable,
                    "only the lines `torn` cuts short may fail to parse",
                )
        unclassified = sorted(
            seen - build.STRUCTURAL_ROW_FIELDS - build.DECLARATION_ROW_FIELDS
        )
        self.assertEqual(
            [],
            unclassified,
            "these metadata keys ship and are in neither named set, so nothing "
            "has decided whether a second file should repeat them",
        )
        self.assertTrue(seen & build.DECLARATION_ROW_FIELDS, "nothing was read")

    def test_a_second_agent_repeats_every_declaration_not_just_provenance(
        self,
    ) -> None:
        """The mirror is over the class, because the class grew.

        The first version of this mirror named `provenance`, which was the only
        declaration there was. `generated-answers` then declared on
        `output_provenance` and the contradiction came straight back: one SQL
        string in two files, one saying a model wrote the answer and one saying
        nothing, with `verify` reporting `ok`.
        """

        states = declaring_states()
        self.assertTrue(states, "no state writes a declaration, so nothing was checked")
        for state in states:
            with self.subTest(dataset=state):
                out = Path(self.workspace) / f"two_agents_declarations_{state}"
                built = run_build(
                    "demo",
                    "--agent",
                    "two-agents",
                    "--dataset",
                    state,
                    "--out",
                    str(out),
                )
                self.assertEqual(built.returncode, 0, built.stderr)
                shipped = {
                    row["metadata"]["id"]: row["metadata"]
                    for row in (
                        json.loads(line)
                        for line in (out / "project" / "dataset.jsonl")
                        .read_text(encoding="utf-8")
                        .splitlines()
                        if line.strip()
                    )
                }
                sibling = [
                    json.loads(line)
                    for line in (out / "project" / "sql_explainer" / "dataset.jsonl")
                    .read_text(encoding="utf-8")
                    .splitlines()
                    if line.strip()
                ]
                self.assertTrue(sibling)
                for row in sibling:
                    beside = shipped[row["metadata"]["id"]]
                    for key, value in beside.items():
                        if key not in build.DECLARATION_ROW_FIELDS:
                            continue
                        self.assertEqual(
                            value,
                            row["metadata"].get(key),
                            f"{state}: the two files disagree about {key} for "
                            f"{row['metadata']['id']}",
                        )

    def test_a_second_agent_declares_the_provenance_the_dataset_declares(self) -> None:
        """`undeclared` rewrites every row's provenance; the sibling must follow.

        The draw is taken before the damage, which is right for a repeated id and
        wrong for a rewritten field: a second file saying `real` for twenty ids
        contradicted, inside one project, the one thing that state exists to say.
        """
        out = Path(self.workspace) / "two_agents_undeclared"
        result = run_build(
            "demo",
            "--agent",
            "two-agents",
            "--dataset",
            "undeclared",
            "--out",
            str(out),
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        sibling = [
            json.loads(line)
            for line in (out / "project" / "sql_explainer" / "dataset.jsonl")
            .read_text()
            .splitlines()
        ]
        self.assertEqual(
            {build.UNDECLARED_PROVENANCE},
            {row["metadata"]["provenance"] for row in sibling},
        )

    def test_a_second_agent_needs_rows_to_draw_from(self) -> None:
        out = Path(self.workspace) / "two_agents_no_rows"
        result = run_build(
            "demo", "--agent", "two-agents", "--dataset", "missing", "--out", str(out)
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("second agent", result.stderr)

    # ------------------------------------------------------------------ all nine

    def test_every_preset_builds_and_passes_verify(self) -> None:
        """Every preset in the bank, not only the ones this class builds as fixtures.

        The name said "every" while the loop covered the ten presets `setUpClass`
        happens to build, so twenty-one of them -- including all five from the
        provenance and cost round -- were never handed to `verify_demo`. Since
        `verify` is what scans a project against the blinding roster, that gap
        was between the claim and the thing the claim is about.
        """

        # A neutral name: `verify` scans the demo's own PATH against the roster,
        # and a directory called "verify_every_preset" trips it on the word this
        # repository blinds. The check catching the test's own scratch directory
        # is the check doing its job.
        room = Path(self.workspace) / "bank"
        room.mkdir(exist_ok=True)
        for preset in sorted(build.PRESETS):
            with self.subTest(preset=preset):
                out = self.outs.get(preset)
                if out is None:
                    # Built under the neutral name a bank would give it, because a
                    # directory named after the preset is itself a tell.
                    out = room / build.bank_directory(preset)
                    if not out.exists():
                        built = run_build("demo", "--preset", preset, "--out", str(out))
                        self.assertEqual(built.returncode, 0, built.stderr)
                self.assertEqual(build.verify_demo(out), [])

    def test_every_new_state_name_is_a_tell(self) -> None:
        """The nine names are hyphenated, so they joined the tell roster. That a shipped
        project carries none of them is `test_every_preset_builds_and_passes_verify`'s job: `verify`
        scans every file against the roster this test pins."""
        for name in (
            "leaky-split",
            "holdout-only",
            "split-by-database",
            "raw-export",
            "torn-lines",
            "undeclared-source",
            "opaque-scorer",
            "length-blind",
            "two-agents",
            "holdout-labelled",
        ):
            self.assertIn(name, build.revealing_names(), f"{name} is not a tell")


class Guards(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.workspace, ignore_errors=True)

    def test_it_will_not_write_over_something(self) -> None:
        out = Path(self.workspace) / "taken"
        out.mkdir()
        result = run_build("demo", "--out", str(out))
        self.assertEqual(result.returncode, 2)
        self.assertIn("already exists", result.stderr)

    def test_it_will_not_build_inside_a_checkout(self) -> None:
        """A demo inside a Git working tree gets read as part of that project."""
        checkout = Path(self.workspace) / "some-repo"
        (checkout / ".git").mkdir(parents=True)
        result = run_build("demo", "--out", str(checkout / "demo"))
        self.assertEqual(result.returncode, 2)
        self.assertIn("Git working tree", result.stderr)

    def test_a_local_guide_needs_a_checkout_to_copy(self) -> None:
        result = run_build(
            "demo", "--out", str(Path(self.workspace) / "d"), "--guide", "local"
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("--guide-src", result.stderr)

    def test_a_guide_source_is_checked_before_anything_is_copied(self) -> None:
        empty = Path(self.workspace) / "not-the-guide"
        empty.mkdir()
        result = run_build(
            "demo",
            "--out",
            str(Path(self.workspace) / "d"),
            "--guide",
            "local",
            "--guide-src",
            str(empty),
        )
        self.assertEqual(result.returncode, 2)
        self.assertIn("GUIDE.md", result.stderr)


class RepositoryCheck(unittest.TestCase):
    def test_check_passes_on_this_repository(self) -> None:
        result = run_build("--format", "json", "check")
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(json.loads(result.stdout)["problems"], [])

    def test_every_preset_names_real_states(self) -> None:
        for name, preset in build.PRESETS.items():
            self.assertIn(preset["agent"], build.AGENT_STATES, name)
            self.assertIn(preset["dataset"], build.DATASET_STATES, name)
            self.assertIn(preset["eval"], build.EVALUATOR_FILES, name)
            self.assertIn(name, build.PRESET_NOTES, f"{name} has no description")
            self.assertIn(
                name, build.PRESET_CAPS, f"{name} says nothing it was built for"
            )
        self.assertEqual(set(build.PRESETS), set(build.PRESET_CAPS))


class EveryChoiceIsNamedWhereTheChoicesAreListed(unittest.TestCase):
    """A state the lists leave out is one a reader never learns exists.

    `--eval`'s help was written by hand and named every scorer but `slow`; the README's
    flag table named every dataset state but `fully-synthetic`. Each list is held to the
    choices the parser actually accepts, which is the only list that cannot be wrong.
    """

    def commands(self) -> dict[str, argparse.ArgumentParser]:
        parser = build.build_parser()
        found: dict[str, argparse.ArgumentParser] = {"": parser}
        for action in parser._actions:
            if isinstance(action, argparse._SubParsersAction):
                found.update(action.choices)
        return found

    def test_a_help_that_enumerates_names_exactly_the_choices(self) -> None:
        checked = 0
        for command, parser in self.commands().items():
            for action in parser._actions:
                if not action.choices or not action.help or " | " not in action.help:
                    continue
                if isinstance(action, argparse._SubParsersAction):
                    continue
                listed = [
                    re.split(r"[\s:(]", piece.strip(), maxsplit=1)[0]
                    for piece in action.help.split(";")[0].split(" | ")
                ]
                checked += 1
                with self.subTest(command=command, option=action.option_strings):
                    self.assertEqual(list(action.choices), listed)
        self.assertGreaterEqual(checked, 3, "--agent, --dataset and --eval enumerate")

    def test_the_readme_flag_table_names_exactly_the_choices(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        table = readme.split("## Choosing what the project starts with", 1)[1]
        demo = self.commands()["demo"]
        accepted = {
            option: list(action.choices)
            for action in demo._actions
            if action.choices
            for option in action.option_strings
        }
        checked = 0
        for row in re.finditer(r"^\| `(--[a-z-]+)` \| (.+) \|$", table, re.MULTILINE):
            flag, values = row.groups()
            named = [
                found.group(1)
                for found in (
                    re.match(r"`([^`]+)`", item.strip()) for item in values.split(" · ")
                )
                if found
            ]
            checked += 1
            with self.subTest(flag=flag):
                self.assertIn(flag, accepted, "the table documents a flag demo lacks")
                self.assertEqual(sorted(accepted[flag]), sorted(named))
        self.assertGreaterEqual(checked, 3, "the table was not read")

    def test_the_scorer_document_names_every_scorer(self) -> None:
        """`docs/eval-methods.md` is where a reader learns what each `--eval` is.

        It counted "two real scorers and four others" for a round after `slow` arrived,
        and never mentioned it: a document that enumerates the choices has to name them.
        """
        document = (REPO_ROOT / "docs" / "eval-methods.md").read_text(encoding="utf-8")
        for state in build.EVALUATOR_FILES:
            if state == "missing":
                continue
            with self.subTest(eval=state):
                self.assertTrue(
                    f"`{state}`" in document,
                    f"docs/eval-methods.md never names {state}",
                )


if __name__ == "__main__":
    unittest.main()
