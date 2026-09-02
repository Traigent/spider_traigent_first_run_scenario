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

# The prompt a customer is given to start a run. The same two lines are copied byte for byte
# into six other product files: traigent-first-run/README.md; the scenarios repo's README.md,
# GUIDE.md and skills/traigent-first-run-scenarios/SKILL.md; its presentation/src/content.ts;
# and traigent-web/public/agent-setup/prompt.md. traigent-web/src/components/LeadFunnel.jsx
# builds the same two lines with the repository URL interpolated.
#
# Only traigent-web pins any of them, and not in separate files: its
# scripts/tests/customer_journey.test.mjs asserts both public/agent-setup/prompt.md and
# LeadFunnel.jsx against one shared literal in that one file, and its
# scripts/funnel_component.test.mjs asserts the rendered copy button against a second literal
# of its own. The five copies in traigent-first-run and traigent-first-run-scenarios, the
# customer-facing README among them, are pinned nowhere. So this is not the fifth of five
# independent pins: it covers what build.py prints and records, and nothing else.
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
        """Every refusal happens while the plan is made, so it must not change afterwards."""
        plan = self.plan()
        with self.assertRaises(Exception):
            plan.dataset = "ready"  # type: ignore[misc]


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
                self.assertEqual(manifest["components"]["agent"]["provider"], provider)

                shipped = (out / "project" / "agent.py").read_text()
                self.assertTrue(agent["models"], "no roster recorded")
                for model in agent["models"]:
                    self.assertIn(
                        f'"{model}"',
                        shipped,
                        f"{provider}: the manifest names a model the shipped agent does not",
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


if __name__ == "__main__":
    unittest.main()
