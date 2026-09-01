# SPDX-License-Identifier: Apache-2.0
"""What `build.py demo` produces.

These tests are about the builder's own output. They deliberately do not assert what the
Traigent first-run guide does with a demo once it is built -- that is the guide's behaviour
to define and change, and pinning it here would make this repository's tests fail whenever
that repository makes a decision.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import build  # noqa: E402

# The prompt a customer is given to start a run. It is pinned byte for byte in four other
# places across the product, each with its own test and no shared file between them. This is
# the fifth pin: if one of them drifts, the ones that did not drift say so.
EXPECTED_HANDOFF = (
    "Help me run my first Traigent optimization.\n"
    "Clone https://github.com/Traigent/traigent-first-run and follow GUIDE.md."
)


def run_build(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "build.py"), *args],
        capture_output=True,
        text=True,
        check=False,
    )


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
        result = run_build("demo", "--preset", "ready", "--out", str(cls.out))
        assert result.returncode == 0, result.stderr
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
            "LICENSE-DATA",
            "databases",
        ):
            self.assertTrue(
                (self.project / name).exists(), f"{name} is missing from the project"
            )

    def test_the_build_record_stays_out_of_the_project(self) -> None:
        """demo.json names the state each component was put in.

        A run where the agent can read that is not a test of anything, so the record sits
        beside the project rather than inside it.
        """
        self.assertTrue((self.out / "demo.json").exists())
        self.assertFalse((self.project / "demo.json").exists())

    def test_no_dedicated_environment_is_left_behind(self) -> None:
        """The guide creates .venv-traigent itself, and stops if it already exists.

        A demo that ships one cannot be run at all, so no combination of flags may make one.
        """
        self.assertFalse((self.project / ".venv-traigent").exists())

    def test_the_data_licence_travels_with_the_data(self) -> None:
        self.assertTrue((self.project / "LICENSE-DATA").exists())
        self.assertIn("CC BY-SA 4.0", (self.project / "LICENSE-DATA").read_text())
        self.assertEqual(self.manifest["data_licence"], "CC-BY-SA-4.0")

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
        self.assertEqual(len(rows), build.MINI_ROWS)
        self.assertEqual(len({row["metadata"]["difficulty"] for row in rows}), 4)

    def test_unlabelled_rows_carry_no_answer(self) -> None:
        """No expected output, and therefore no split -- there is nothing to hold back."""
        project = self.make("--dataset", "unlabeled")
        rows = [
            json.loads(line)
            for line in (project / "dataset.jsonl").read_text().splitlines()
            if line
        ]
        self.assertEqual(len(rows), build.UNLABELED_ROWS)
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

        `mini` copies only the databases its 30 rows use, so without this the exec-match
        probes point at a database that is not in the project and calibration cannot run.
        """
        out = self.make(
            "--dataset", "mini", "--eval", "exec-match", "--calibration", "present"
        )
        project = out / "project"
        cases = json.loads(
            (project / build.RUNS_DIRECTORY / build.CALIBRATION_FILE).read_text()
        )
        shipped = {
            path.name for path in (project / "databases").iterdir() if path.is_dir()
        }
        for case in cases:
            db_id = case["metadata"]["db_id"]
            self.assertIn(db_id, shipped, f"probe names {db_id}, which was not copied")

    def test_calibration_needs_something_to_calibrate(self) -> None:
        for args, expected in (
            (("--eval", "missing"), "evaluator"),
            (("--dataset", "missing"), "databases"),
        ):
            with self.subTest(args=args):
                out = Path(self.workspace) / f"bad{args[1]}"
                result = run_build(
                    "demo", "--out", str(out), "--calibration", "present", *args
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn(expected, result.stderr)


class Environments(unittest.TestCase):
    def setUp(self) -> None:
        self.workspace = tempfile.mkdtemp()
        self.addCleanup(shutil.rmtree, self.workspace, ignore_errors=True)

    def make(self, name: str, *args: str) -> dict:
        out = Path(self.workspace) / name
        result = run_build("demo", "--out", str(out), *args)
        self.assertEqual(result.returncode, 0, result.stderr)
        return json.loads((out / "demo.json").read_text())

    def test_by_default_the_project_has_no_environment(self) -> None:
        self.assertIsNone(
            self.make("plain", "--dataset", "mini")["components"]["project_venv"]
        )

    def test_a_compatible_environment_is_supported_and_inside_the_project(self) -> None:
        manifest = self.make(
            "compat", "--dataset", "mini", "--existing-venv", "one-compatible"
        )
        record = manifest["components"]["project_venv"]
        self.assertEqual(record["path"], build.PROJECT_VENV_NAME)
        major, minor = (int(part) for part in record["python_version"].split(".")[:2])
        self.assertEqual(major, 3)
        self.assertGreaterEqual(minor, 11)
        self.assertLessEqual(minor, 13)

    @unittest.skipIf(
        shutil.which(build.OLD_PYTHON) is None, f"{build.OLD_PYTHON} is not installed"
    )
    def test_an_old_environment_is_actually_old(self) -> None:
        manifest = self.make(
            "old", "--dataset", "mini", "--existing-venv", "old-python"
        )
        major, minor = (
            int(part)
            for part in manifest["components"]["project_venv"]["python_version"].split(
                "."
            )[:2]
        )
        self.assertEqual((major, minor), (3, 10))

    def test_no_environment_choice_produces_a_dedicated_one(self) -> None:
        for state in ("none", "one-compatible"):
            out = Path(self.workspace) / f"guard-{state}"
            self.assertEqual(
                run_build(
                    "demo",
                    "--out",
                    str(out),
                    "--dataset",
                    "mini",
                    "--existing-venv",
                    state,
                ).returncode,
                0,
            )
            self.assertFalse(
                (out / "project" / build.FORBIDDEN_VENV_NAME).exists(), state
            )


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
            self.assertIn(preset["agent"], build.AGENT_FILES, name)
            self.assertIn(preset["dataset"], build.DATASET_STATES, name)
            self.assertIn(preset["eval"], build.EVALUATOR_FILES, name)
            self.assertIn(name, build.PRESET_NOTES, f"{name} has no description")


if __name__ == "__main__":
    unittest.main()
