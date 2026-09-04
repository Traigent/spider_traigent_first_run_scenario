# SPDX-License-Identifier: Apache-2.0
"""What `build.py demo` produces.

These tests are about the builder's own output. They deliberately do not assert what the
Traigent first-run guide does with a demo once it is built -- that is the guide's behaviour
to define and change, and pinning it here would make this repository's tests fail whenever
that repository makes a decision.
"""

from __future__ import annotations

import dataclasses
import hashlib
import json
import re
import shutil
import sqlite3
import subprocess
import sys
import tempfile
import unittest
from collections import Counter
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
}

# The file each `--eval` state ships, so that a preset naming one scorer and shipping another
# is caught by the bytes rather than by the name recorded beside them.
EVALUATOR_FILENAMES = {
    "exact-match": "exact_match.py",
    "exec-match": "exec_match.py",
    "broken": "broken.py",
    "swapped": "swapped.py",
}

# And the same for the agents. Comparing the shipped file with `build.agent_file(...)` was
# comparing the builder's choice with the builder's choice: an `agent_file` that returns
# `agent_ready.py` for every state moves both sides of the assertion at once, and the arm
# with nothing to search would ship the tunable agent with the suite still green.
AGENT_FILENAMES = {
    "ready": "agent_ready.py",
    "no-knobs": "agent_no_knobs.py",
}

# What each evaluator honestly is. Recorded in every manifest by build.py and, until now,
# asserted nowhere -- a scorer that executes model output recorded as one that does not is a
# false statement about the one thing docs/eval-methods.md asks a reader to take on trust.
EXPECTED_EVALUATOR_METHOD = {
    "exact-match": "normalized-exact",
    "exec-match": "execution",
    "broken": "normalized-exact",
    "swapped": "normalized-exact",
}

# The version of the agent's dependency a project environment is built with. Written out
# here as well as read from build.AGENT_REQUIREMENT, because asserting that the environment
# printed *something* passes on any version at all, including one the guide does not install.
EXPECTED_AGENT_REQUIREMENT = "litellm==1.93.0"


def run_build(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(REPO_ROOT / "build.py"), *args],
        capture_output=True,
        text=True,
        check=False,
    )


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
        """The guide creates .venv-traigent itself, and stops if it already exists.

        A demo that ships one cannot be run at all, so no combination of flags may make
        one. Asserted on a `--venv ready` build: it used to be asserted on a `--venv none`
        one, where no code path could have created an environment under any name, so it
        could not have failed.
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
                    recorded["executes_candidate_output"], evaluator == "exec-match"
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
        all seventeen presets at once -- which is the same as having no check, because the
        only way to get a green run back would be to stop believing it.
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
                for path in sorted(on_disk):
                    if path.startswith("databases/"):
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
