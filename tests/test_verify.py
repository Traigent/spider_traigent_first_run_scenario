# SPDX-License-Identifier: Apache-2.0
"""The two gates, driven in the direction that makes them gates.

`build.py verify` decides whether a built demo may be handed to an agent, and `build.py
check` is what CI runs over this repository's own components and data. Both were exercised
almost entirely in the passing direction: `verify` had five things it was watched to catch
out of the dozen it looks for, and `check` had no negative test at all -- nearly every one of
its `problems.append` branches had never been executed by anything.

A gate nobody has watched fail is not a gate. Everything here breaks one thing and asserts
that the specific problem comes back, and where a change would also trip a different check
the hash record is repaired first, so the assertion is about the check being tested and not
about a second one firing by accident.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import build  # noqa: E402

# What `check` says when each defect is put in front of it. Written out here, so a refusal
# that stops being reported -- or starts being reported as something else -- fails.
CHECK_MESSAGES = {
    "row_count": "expected 300 dataset rows",
    "duplicate_questions": "duplicate questions",
    "missing_database": "database missing",
    "not_flat": "is not flat",
    "no_metadata": "carries no metadata",
    "missing_metadata_field": "has no metadata",
    "component_missing": "component missing",
    "component_does_not_parse": "component does not parse",
    "calibration_missing": "calibration cases missing",
    "calibration_too_few": "at least two cases are required",
    "calibration_unknown_answer": "expects a query that is not",
    "calibration_unknown_database": "which is not committed",
    "template_placeholder": "which render_readme does not fill",
}


def run_build(*args: str, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str((cwd or REPO_ROOT) / "build.py"), *args],
        capture_output=True,
        text=True,
        check=False,
    )


def build_or_raise(*args: str) -> subprocess.CompletedProcess[str]:
    """A fixture build, refused loudly. A bare assert here vanishes under `python -O`."""
    result = run_build(*args)
    if result.returncode != 0:
        raise RuntimeError(
            f"the fixture build `{' '.join(args)}` failed with {result.returncode}: "
            f"{result.stderr or result.stdout}"
        )
    return result


def repair_record(out: Path, relative: str) -> None:
    """Make `demo.json` agree with what is now on disk at `relative`.

    Several of the things `verify` is supposed to catch are changes to a file that ships,
    and a changed file also stops matching its recorded hash. Repairing the record first is
    what makes the test about the check being tested: without it, "the hash moved" fires
    and the blinding scan, or the compile check, is never reached at all.
    """
    record = out / "demo.json"
    manifest = json.loads(record.read_text())
    path = out / build.PROJECT_SUBDIR / relative
    entry = {
        "path": relative,
        "sha256": build.sha256_of(path),
        "size": path.stat().st_size,
    }
    files = [f for f in manifest["files"] if f["path"] != relative]
    manifest["files"] = sorted(files + [entry], key=lambda f: f["path"])
    record.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")


class ADemoFixture(unittest.TestCase):
    """One built demo, copied per test and then broken in one specific way."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.workspace = tempfile.mkdtemp()
        cls.pristine = Path(cls.workspace) / "pristine"
        build_or_raise("demo", "--dataset", "tiny", "--out", str(cls.pristine))

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.workspace, ignore_errors=True)

    def copy(self, name: str = "demo") -> Path:
        holder = Path(tempfile.mkdtemp(dir=self.workspace))
        self.addCleanup(shutil.rmtree, holder, ignore_errors=True)
        out = holder / name
        shutil.copytree(self.pristine, out)
        return out


class VerifySeesWhatTheProjectHolds(ADemoFixture):
    """The blinding scan, in the places it used to have no eyes."""

    def test_a_clean_copy_has_nothing_wrong_with_it(self) -> None:
        """The control every test below rests on."""
        self.assertEqual(build.verify_demo(self.copy()), [])

    def test_it_reads_a_file_with_no_extension(self) -> None:
        """`NOTICE` has no suffix, and the scan used to read only known ones.

        That is not a hypothetical gap: it is how one file naming the repository that
        produced it sat in all seventeen projects while `verify` reported every one of them
        clean. The scan now reads a file by what it holds, so an extensionless file with a
        tell in it is caught like any other.
        """
        out = self.copy()
        notice = out / build.PROJECT_SUBDIR / "NOTICE"
        notice.write_text(
            "This project was produced by the spider_traigent_first_run_scenario "
            "repository.\n"
        )
        repair_record(out, "NOTICE")
        problems = build.verify_demo(out)
        self.assertTrue(
            any("says this is a test" in p and "NOTICE" in p for p in problems),
            problems,
        )
        self.assertFalse(
            any("does not match the record" in p for p in problems),
            "the record was repaired, so only the blinding scan should have fired",
        )

    def test_it_reads_the_attribution_notice(self) -> None:
        """`.txt` was never in the old suffix list, and this is the file every project has.

        `ATTRIBUTION.txt` ships with every project that ships rows -- seventeen presets, one
        file, copied verbatim -- so it is both the most likely place for a leak to survive
        and the least likely to be looked at again. The hash is repaired first so that only
        the blinding scan can be what catches it.
        """
        out = self.copy()
        notice = out / build.PROJECT_SUBDIR / build.ATTRIBUTION_NAME
        notice.write_text(
            notice.read_text() + "\nGenerated demo -- see build.py for how.\n"
        )
        repair_record(out, build.ATTRIBUTION_NAME)
        problems = build.verify_demo(out)
        self.assertTrue(
            any(
                "says this is a test" in p and build.ATTRIBUTION_NAME in p
                for p in problems
            ),
            problems,
        )
        self.assertEqual(
            [p for p in problems if "does not match the record" in p],
            [],
            "the record was repaired, so only the blinding scan should have fired",
        )

    def test_it_reads_the_name_of_a_file_and_not_only_its_contents(self) -> None:
        """A file called FIXTURE_NOTES.md says what it says whether or not it is empty."""
        out = self.copy()
        planted = out / build.PROJECT_SUBDIR / "fixture_notes.md"
        planted.write_text("Some ordinary notes about the questions in here.\n")
        repair_record(out, "fixture_notes.md")
        problems = build.verify_demo(out)
        self.assertTrue(
            any("the name" in p and "fixture" in p for p in problems), problems
        )

    def test_it_notices_a_file_added_after_the_build(self) -> None:
        """Walking the record alone can only find what went missing.

        A file added to the project afterwards was invisible to it, and the demo still
        passed -- which is exactly what a leaked note, an editor backup or a stray copy of
        the guide looks like.
        """
        out = self.copy()
        (out / build.PROJECT_SUBDIR / "notes.md").write_text("a few ordinary notes\n")
        problems = build.verify_demo(out)
        self.assertIn("notes.md is on disk and not in the record", problems)

    def test_it_notices_a_file_removed_after_the_build(self) -> None:
        out = self.copy()
        (out / build.PROJECT_SUBDIR / "catalog.json").unlink()
        problems = build.verify_demo(out)
        self.assertTrue(
            any("catalog.json is in the record and not on disk" in p for p in problems),
            problems,
        )

    def test_it_finds_the_guides_own_environment_nested_inside_the_project(
        self,
    ) -> None:
        """Anywhere inside, not only at the top.

        `--guide local` copies a whole checkout into `project/traigent-first-run/`, and one
        that brought this directory with it left a demo the guide refuses to run -- it
        creates that directory itself and stops if it already exists -- while this check
        said the project was clean.
        """
        out = self.copy()
        nested = (
            out
            / build.PROJECT_SUBDIR
            / build.GUIDE_DIRECTORY
            / build.FORBIDDEN_VENV_NAME
        )
        nested.mkdir(parents=True)
        problems = build.verify_demo(out)
        self.assertTrue(
            any(
                build.FORBIDDEN_VENV_NAME in p
                and build.GUIDE_DIRECTORY in p
                and "the project contains" in p
                for p in problems
            ),
            problems,
        )

    def test_it_catches_an_agent_that_does_not_compile(self) -> None:
        """A project that cannot start tests the guide's patience, not its judgement.

        The record is repaired first, so the only check left that can report this is the
        one that compiles the two files an agent is handed.
        """
        out = self.copy()
        agent = out / build.PROJECT_SUBDIR / "agent.py"
        agent.write_text(agent.read_text() + "\ndef run(  :\n")
        repair_record(out, "agent.py")
        problems = build.verify_demo(out)
        self.assertTrue(
            any(p.startswith("agent.py does not compile") for p in problems), problems
        )
        self.assertEqual([p for p in problems if "record" in p], [], problems)

    def test_it_catches_an_evaluator_that_does_not_compile(self) -> None:
        out = self.copy()
        evaluator = out / build.PROJECT_SUBDIR / "evaluator.py"
        evaluator.write_text("def score(:\n")
        repair_record(out, "evaluator.py")
        problems = build.verify_demo(out)
        self.assertTrue(
            any(p.startswith("evaluator.py does not compile") for p in problems),
            problems,
        )

    def test_it_catches_a_symbolic_link(self) -> None:
        out = self.copy()
        link = out / build.PROJECT_SUBDIR / "elsewhere.py"
        link.symlink_to(REPO_ROOT / "build.py")
        problems = build.verify_demo(out)
        self.assertTrue(any("is a symbolic link" in p for p in problems), problems)

    def test_it_catches_rows_the_catalog_does_not_cover(self) -> None:
        out = self.copy()
        catalog = out / build.PROJECT_SUBDIR / "catalog.json"
        catalog.write_text("{}\n")
        repair_record(out, "catalog.json")
        problems = build.verify_demo(out)
        self.assertIn("a question is not in the catalog the agent reads", problems)

    def test_it_reports_a_malformed_dataset_rather_than_raising(self) -> None:
        """A checker that raises on bad input fails exactly when it is needed."""
        out = self.copy()
        dataset = out / build.PROJECT_SUBDIR / "dataset.jsonl"
        dataset.write_text("not json at all\n")
        repair_record(out, "dataset.jsonl")
        problems = build.verify_demo(out)
        self.assertTrue(
            any("the rows or the catalog cannot be read" in p for p in problems),
            problems,
        )

    def test_it_catches_the_build_record_inside_the_project(self) -> None:
        out = self.copy()
        shutil.copy2(out / "demo.json", out / build.PROJECT_SUBDIR / "demo.json")
        problems = build.verify_demo(out)
        self.assertIn(
            "the build record is inside the project the agent reads", problems
        )


class VerifyReadsTheDemosOwnPath(ADemoFixture):
    """The demo's own location is not private to the demo.

    `venv` writes it into `pyvenv.cfg`, into `VIRTUAL_ENV` in every `activate` script and
    into the shebang of every console script, so a directory named after the state its demo
    was built in has that name inside files the project ships. Both remedies are reported,
    and which one depends on whether an environment is there -- an environment cannot be
    fixed by renaming the directory it records.
    """

    def test_a_telling_path_is_reported_with_the_remedy_that_works(self) -> None:
        out = self.copy(name="wrong-answers")
        problems = build.verify_demo(out)
        self.assertTrue(
            any("the path this demo sits at" in p for p in problems), problems
        )
        self.assertTrue(
            any("Rename the directory" in p for p in problems),
            "a demo with no environment can simply be moved",
        )
        self.assertFalse(
            any("Build it somewhere else" in p for p in problems), problems
        )

    def test_a_telling_path_under_an_environment_cannot_be_renamed_away(self) -> None:
        out = self.copy(name="wrong-answers")
        # The remedy turns on whether the project has an environment, and nothing else --
        # so the branch is reached with a directory rather than with 220 MB of wheels.
        (out / build.PROJECT_SUBDIR / build.PROJECT_VENV).mkdir()
        problems = build.verify_demo(out)
        self.assertTrue(
            any("the path this demo sits at" in p for p in problems), problems
        )
        self.assertTrue(
            any("Build it somewhere else" in p for p in problems),
            "the environment has this path written into every script in it",
        )
        self.assertFalse(any("Rename the directory" in p for p in problems), problems)

    def test_a_neutral_path_is_not_reported(self) -> None:
        """The check has to be quiet on the names `suite` actually chooses."""
        out = self.copy(name=build.bank_directory("wrong-answers"))
        self.assertEqual(build.verify_demo(out), [])

    def test_a_telling_path_is_reported_however_the_words_are_joined(self) -> None:
        """A hyphen is not the only way somebody writes a compound directory name.

        `revealing_names` matches its labels literally, hyphens and all, on purpose: a
        space would turn `no-agent` into the ordinary phrase an agent file writes by
        accident. But an underscore joins words exactly the way a hyphen does -- nobody
        writes `wrong_answers` by accident -- and a check that only recognised the hyphen
        spelling let the commonest alternative directory-naming convention straight through.
        """
        out = self.copy(name="wrong_answers")
        problems = build.verify_demo(out)
        self.assertTrue(
            any("the path this demo sits at" in p for p in problems), problems
        )
        self.assertTrue(any("'wrong-answers'" in p for p in problems), problems)


class VerifyOverAWholeBank(unittest.TestCase):
    """`verify --demo <root>` reads every directory under the root, not only the good ones."""

    def test_a_demo_with_no_record_stays_in_the_report(self) -> None:
        """A build interrupted before it wrote `demo.json` leaves exactly this.

        Filtering those out dropped the broken demo from the report while the run still
        read as a passing gate -- the worst possible failure for a gate, because the answer
        it gives is "everything I looked at was fine" and it chose what to look at.
        """
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace) / "bank"
            root.mkdir()
            build_or_raise("demo", "--dataset", "tiny", "--out", str(root / "one"))
            (root / "two").mkdir()

            result = run_build("--format", "json", "verify", "--demo", str(root))
            self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
            report = json.loads(result.stdout)
            self.assertFalse(report["ok"])
            checked = {entry["demo"]: entry["problems"] for entry in report["checked"]}
            self.assertEqual(sorted(checked), ["one", "two"])
            self.assertEqual(checked["one"], [])
            self.assertTrue(
                any("no build record" in p for p in checked["two"]), checked["two"]
            )

    def test_an_empty_root_is_refused_rather_than_reported_as_passing(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace) / "bank"
            root.mkdir()
            result = run_build("verify", "--demo", str(root))
            self.assertEqual(result.returncode, 2)
            self.assertIn("holds no built demo", result.stderr)

    def test_a_root_that_is_not_there_is_refused(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            result = run_build("verify", "--demo", str(Path(workspace) / "nothing"))
            self.assertEqual(result.returncode, 2)
            self.assertIn("no directory at", result.stderr)


class ARepositoryFixture(unittest.TestCase):
    """A copy of this repository's own inputs, broken one way at a time.

    `check` is the CI gate over the components and the committed data, and it reads them
    through module-level paths -- so it is driven the way CI drives it, as `build.py` inside
    a copied tree, rather than by monkey-patching constants.
    """

    COPIED = ("build.py", "components", "spider")

    @classmethod
    def setUpClass(cls) -> None:
        cls.workspace = tempfile.mkdtemp()
        cls.pristine = Path(cls.workspace) / "pristine"
        cls.pristine.mkdir()
        for name in cls.COPIED:
            source = REPO_ROOT / name
            if source.is_dir():
                shutil.copytree(
                    source,
                    cls.pristine / name,
                    ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
                )
            else:
                shutil.copy2(source, cls.pristine / name)

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.workspace, ignore_errors=True)

    def repository(self) -> Path:
        holder = Path(tempfile.mkdtemp(dir=self.workspace))
        self.addCleanup(shutil.rmtree, holder, ignore_errors=True)
        copy = holder / "repo"
        shutil.copytree(self.pristine, copy)
        return copy

    def check(self, repository: Path) -> tuple[int, dict]:
        result = run_build("--format", "json", "check", cwd=repository)
        self.assertNotEqual(
            result.returncode, 2, f"check refused instead of reporting: {result.stderr}"
        )
        return result.returncode, json.loads(result.stdout)

    def rows_of(self, repository: Path) -> list[dict]:
        return [
            json.loads(line)
            for line in (repository / "spider" / "spider_300.jsonl")
            .read_text()
            .splitlines()
            if line.strip()
        ]

    def write_rows(self, repository: Path, rows: list[dict]) -> None:
        (repository / "spider" / "spider_300.jsonl").write_text(
            "".join(
                json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n"
                for row in rows
            ),
            encoding="utf-8",
        )

    def assertReports(self, repository: Path, expected: str) -> None:
        code, report = self.check(repository)
        self.assertEqual(code, 1, f"check passed a repository with {expected!r} in it")
        self.assertFalse(report["ok"])
        self.assertTrue(
            any(expected in problem for problem in report["problems"]),
            f"{expected!r} was not reported; got {report['problems']}",
        )


class CheckRefusesABrokenRepository(ARepositoryFixture):
    def test_the_copy_itself_passes(self) -> None:
        """The control. Every test below reads a failure as caused by its own defect."""
        code, report = self.check(self.repository())
        self.assertEqual(code, 0, report)
        self.assertEqual(report["problems"], [])
        self.assertEqual(report["dataset"]["rows"], 300)

    def test_a_short_slice(self) -> None:
        repository = self.repository()
        self.write_rows(repository, self.rows_of(repository)[:-1])
        self.assertReports(repository, CHECK_MESSAGES["row_count"])

    def test_a_repeated_question(self) -> None:
        repository = self.repository()
        rows = self.rows_of(repository)
        rows[1]["input"] = rows[0]["input"]
        self.write_rows(repository, rows)
        self.assertReports(repository, CHECK_MESSAGES["duplicate_questions"])

    def test_a_database_the_rows_name_and_the_repository_does_not_hold(self) -> None:
        repository = self.repository()
        rows = self.rows_of(repository)
        db_id = rows[0]["metadata"]["db_id"]
        shutil.rmtree(repository / "spider" / "databases" / db_id)
        self.assertReports(repository, CHECK_MESSAGES["missing_database"])

    def test_a_row_that_is_not_flat(self) -> None:
        """`input` and `output` are text. A field that is not corrupts the first-run
        tooling's duplicate and split analysis, and it is reported rather than raised.

        Driven with a value that is not text but is still hashable. A value that is not --
        a nested object, or a list -- makes `cmd_check` raise `TypeError: unhashable type`
        from `gold_queries = {row["output"] for row in rows}` before the loop that would
        have reported it, which is the same defect the loop below already carries a comment
        about, one line class down. That is a defect in build.py rather than in this test,
        it is recorded rather than pinned here, and the fix is to build `questions` and
        `gold_queries` out of `sound` like everything else.
        """
        for field in ("input", "output"):
            with self.subTest(field=field):
                repository = self.repository()
                rows = self.rows_of(repository)
                rows[0][field] = 12345
                self.write_rows(repository, rows)
                self.assertReports(repository, CHECK_MESSAGES["not_flat"])

    def test_a_row_with_no_metadata(self) -> None:
        repository = self.repository()
        rows = self.rows_of(repository)
        del rows[0]["metadata"]
        self.write_rows(repository, rows)
        self.assertReports(repository, CHECK_MESSAGES["no_metadata"])

    def test_a_row_missing_a_metadata_field(self) -> None:
        """Reported, not raised. Reaching into a bad row turned the one command whose job
        is to describe a bad row into a KeyError traceback."""
        for field in ("db_id", "difficulty", "split"):
            with self.subTest(field=field):
                repository = self.repository()
                rows = self.rows_of(repository)
                del rows[0]["metadata"][field]
                self.write_rows(repository, rows)
                self.assertReports(repository, f"has no metadata {field}")

    def test_a_component_that_is_not_there(self) -> None:
        repository = self.repository()
        (repository / "components" / "evaluator" / "broken.py").unlink()
        self.assertReports(repository, CHECK_MESSAGES["component_missing"])

    def test_a_component_that_does_not_parse(self) -> None:
        repository = self.repository()
        (repository / "components" / "evaluator" / "swapped.py").write_text(
            "def score(:\n"
        )
        self.assertReports(repository, CHECK_MESSAGES["component_does_not_parse"])

    def test_an_env_template_that_is_not_there(self) -> None:
        repository = self.repository()
        (repository / "components" / "env" / "direct.env.example").unlink()
        self.assertReports(repository, CHECK_MESSAGES["component_missing"])

    def test_the_attribution_notice_that_is_not_there(self) -> None:
        """Every project that ships rows ships this file, so a build without it is a build
        that redistributes CC BY-SA data with no attribution at all."""
        repository = self.repository()
        (repository / "components" / "legal" / "ATTRIBUTION.txt").unlink()
        self.assertReports(repository, CHECK_MESSAGES["component_missing"])

    def test_a_readme_template_asking_for_something_nothing_fills(self) -> None:
        repository = self.repository()
        template = repository / "components" / "readme" / "DEMO_README.md.tmpl"
        template.write_text(template.read_text() + "\n{{SOMETHING_NOBODY_FILLS}}\n")
        self.assertReports(repository, CHECK_MESSAGES["template_placeholder"])

    def test_calibration_cases_that_are_not_there(self) -> None:
        repository = self.repository()
        (repository / "components" / "calibration" / "exec_match.json").unlink()
        self.assertReports(repository, CHECK_MESSAGES["calibration_missing"])

    def test_too_few_calibration_cases_to_calibrate_with(self) -> None:
        repository = self.repository()
        source = repository / "components" / "calibration" / "exec_match.json"
        cases = json.loads(source.read_text())
        source.write_text(json.dumps(cases[:1], indent=2))
        self.assertReports(repository, CHECK_MESSAGES["calibration_too_few"])

    def test_a_calibration_case_expecting_an_answer_the_slice_does_not_hold(
        self,
    ) -> None:
        repository = self.repository()
        source = repository / "components" / "calibration" / "exact_match.json"
        cases = json.loads(source.read_text())
        cases[0]["expected"] = "SELECT nothing FROM nowhere"
        source.write_text(json.dumps(cases, indent=2))
        self.assertReports(repository, CHECK_MESSAGES["calibration_unknown_answer"])

    def test_a_calibration_case_naming_a_database_that_is_not_committed(self) -> None:
        repository = self.repository()
        source = repository / "components" / "calibration" / "exact_match.json"
        cases = json.loads(source.read_text())
        cases[0]["metadata"]["db_id"] = "a_database_nobody_committed"
        source.write_text(json.dumps(cases, indent=2))
        self.assertReports(repository, CHECK_MESSAGES["calibration_unknown_database"])

    def test_the_slice_that_is_not_there_is_refused_rather_than_reported(self) -> None:
        """No data at all is not a problem to list -- there is nothing to list it about."""
        repository = self.repository()
        (repository / "spider" / "spider_300.jsonl").unlink()
        result = run_build("--format", "json", "check", cwd=repository)
        self.assertEqual(result.returncode, 2)
        self.assertIn("the Spider slice is missing", result.stdout)


class WhatTheCommandsPrint(unittest.TestCase):
    """The text renderers, which nothing had ever executed.

    `list` was never run by any test, so `cmd_list` and `render_list` could raise and CI
    would stay green. `check` was only ever run with `--format json`, and `verify` likewise,
    so `render_check` and `render_verify` were in the same position -- three functions on
    the path an operator actually uses, and none of them on any path a test used.
    """

    def test_list_prints_every_preset_and_every_state(self) -> None:
        result = run_build("list")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("PRESET", result.stdout)
        for preset, note in build.PRESET_NOTES.items():
            self.assertIn(preset, result.stdout)
            self.assertIn(note, result.stdout)
        for flag, states in (
            ("agent", build.AGENT_STATES),
            ("provider", build.PROVIDERS),
            ("dataset", build.DATASET_STATES),
            ("calibration", build.CALIBRATION_STATES),
            ("guide", build.GUIDE_MODES),
            ("venv", build.VENV_STATES),
        ):
            self.assertIn(f"--{flag}: {', '.join(states)}", result.stdout)

    def test_list_reports_the_same_thing_as_json(self) -> None:
        text = run_build("list")
        encoded = run_build("--format", "json", "list")
        self.assertEqual(text.returncode, 0, text.stderr)
        self.assertEqual(encoded.returncode, 0, encoded.stderr)
        report = json.loads(encoded.stdout)
        self.assertEqual(
            {entry["name"] for entry in report["presets"]}, set(build.PRESETS)
        )
        # Which evaluator executes model output is published here as well as recorded in
        # every manifest, and the two have to be the same answer.
        self.assertEqual(report["evaluators"], build.EVALUATOR_FACTS)

    def test_check_prints_what_it_measured(self) -> None:
        result = run_build("check")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("300 rows", result.stdout)
        self.assertIn("difficulty", result.stdout)
        self.assertIn("splits", result.stdout)
        self.assertIn(build.sha256_of(build.DATASET_PATH), result.stdout)
        self.assertIn("OK", result.stdout)
        self.assertNotIn("PROBLEM", result.stdout)

    def test_verify_prints_a_line_for_each_demo_it_looked_at(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            root = Path(workspace) / "bank"
            root.mkdir()
            build_or_raise("demo", "--dataset", "tiny", "--out", str(root / "one"))
            good = run_build("verify", "--demo", str(root))
            self.assertEqual(good.returncode, 0, good.stderr)
            self.assertIn("ok  one", good.stdout)
            self.assertIn("OK", good.stdout)

            (root / "one" / build.PROJECT_SUBDIR / "stray.md").write_text("hello\n")
            bad = run_build("verify", "--demo", str(root))
            self.assertEqual(bad.returncode, 1, bad.stdout)
            self.assertIn("stray.md is on disk and not in the record", bad.stdout)
            self.assertIn("PROBLEMS ABOVE", bad.stdout)

    def test_demo_prints_where_to_point_the_agent(self) -> None:
        with tempfile.TemporaryDirectory() as workspace:
            out = Path(workspace) / "demo"
            result = build_or_raise("demo", "--dataset", "tiny", "--out", str(out))
            self.assertIn(str(out / "project"), result.stdout)
            self.assertIn("point the agent here", result.stdout)
            self.assertIn(build.HANDOFF_CLONE.splitlines()[0], result.stdout)
            # And it says to keep the record away from the agent, which is the one thing an
            # operator has to do by hand.
            self.assertIn("demo.json", result.stdout)


class ACopiedGuideCheckout(unittest.TestCase):
    """`--guide local` copies a checkout into the project the agent is started in.

    The success path had no coverage at all: `copy_guide` copying nothing would have passed,
    while the handoff tells the agent to read `./traigent-first-run/GUIDE.md` -- a file that
    would not be there. Only the two refusals were tested.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.workspace = tempfile.mkdtemp()
        cls.checkout = Path(cls.workspace) / "guide"
        (cls.checkout / "skills" / "first-run").mkdir(parents=True)
        (cls.checkout / "GUIDE.md").write_text("# Guide\n\nRun the optimization.\n")
        (cls.checkout / "README.md").write_text("# Read me\n")
        (cls.checkout / "AGENTS.md").write_text("# Agents\n")
        (cls.checkout / "CLAUDE.md").write_text("# Claude\n")
        (cls.checkout / ".env.example").write_text("TRAIGENT_API_KEY=\n")
        (cls.checkout / "skills" / "first-run" / "SKILL.md").write_text("# Skill\n")
        # Copied only if the ignore patterns fail to hold.
        (cls.checkout / "skills" / "__pycache__").mkdir()
        (cls.checkout / "skills" / "__pycache__" / "x.pyc").write_bytes(b"\x00\x01")
        # A file the copy is not asked for, so that "everything under the checkout" and
        # "the paths GUIDE_PATHS names" can be told apart.
        (cls.checkout / "Makefile").write_text("all:\n\techo hi\n")

        environment = {
            **os.environ,
            "GIT_AUTHOR_NAME": "fixture",
            "GIT_AUTHOR_EMAIL": "fixture@example.invalid",
            "GIT_COMMITTER_NAME": "fixture",
            "GIT_COMMITTER_EMAIL": "fixture@example.invalid",
        }
        for command in (
            ["git", "init", "-q"],
            ["git", "add", "-A"],
            ["git", "commit", "-q", "-m", "fixture"],
        ):
            done = subprocess.run(
                command,
                cwd=cls.checkout,
                capture_output=True,
                text=True,
                check=False,
                env=environment,
            )
            if done.returncode != 0:
                raise RuntimeError(
                    f"the guide fixture checkout could not be made: {done.stderr}"
                )
        cls.sha = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=cls.checkout,
            capture_output=True,
            text=True,
            check=True,
        ).stdout.strip()

        cls.out = Path(cls.workspace) / "demo"
        cls.printed = build_or_raise(
            "demo",
            "--dataset",
            "tiny",
            "--guide",
            "local",
            "--guide-src",
            str(cls.checkout),
            "--out",
            str(cls.out),
        ).stdout
        cls.project = cls.out / build.PROJECT_SUBDIR
        cls.manifest = json.loads((cls.out / "demo.json").read_text())

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.workspace, ignore_errors=True)

    def test_the_guide_lands_where_the_handoff_says_it_will(self) -> None:
        """The handoff points at `./traigent-first-run/GUIDE.md`, relative to the project."""
        self.assertEqual(self.manifest["handoff"], build.HANDOFF_LOCAL)
        for line in build.HANDOFF_LOCAL.splitlines():
            self.assertIn(line, self.printed)
        self.assertIn(build.HANDOFF_LOCAL, (self.project / "README.md").read_text())
        guide = self.project / build.GUIDE_DIRECTORY / "GUIDE.md"
        self.assertTrue(guide.is_file(), "the handoff names a file that is not there")
        self.assertEqual(guide.read_text(), (self.checkout / "GUIDE.md").read_text())

    def test_every_path_the_checkout_has_is_copied_and_nothing_else(self) -> None:
        destination = self.project / build.GUIDE_DIRECTORY
        for name in build.GUIDE_PATHS:
            with self.subTest(path=name):
                self.assertTrue(
                    (destination / name).exists(),
                    f"{name} is in the checkout and was not copied",
                )
        self.assertFalse(
            (destination / "Makefile").exists(),
            "the copy took a path GUIDE_PATHS does not name",
        )
        self.assertEqual(
            list(destination.rglob("__pycache__")),
            [],
            "compiled bytecode was copied into the project",
        )
        self.assertEqual(
            (destination / "skills" / "first-run" / "SKILL.md").read_text(), "# Skill\n"
        )

    def test_the_record_names_the_commit_the_guide_was_at(self) -> None:
        """Refused rather than written as null: a run has to be tie-able to a guide."""
        record = self.manifest["components"]["guide"]
        self.assertEqual(record["directory"], build.GUIDE_DIRECTORY)
        self.assertEqual(record["git_sha"], self.sha)
        self.assertEqual(record["source"], str(self.checkout))
        self.assertEqual(sorted(record["paths"]), sorted(build.GUIDE_PATHS))

    def test_the_copied_guide_is_in_the_projects_own_record(self) -> None:
        """Everything in the project is hashed, the copied checkout included."""
        recorded = {entry["path"] for entry in self.manifest["files"]}
        for name in ("GUIDE.md", "skills/first-run/SKILL.md"):
            self.assertIn(f"{build.GUIDE_DIRECTORY}/{name}", recorded)

    def test_a_demo_with_a_copied_guide_still_passes_verify(self) -> None:
        self.assertEqual(build.verify_demo(self.out), [])

    def test_a_checkout_carrying_the_guides_own_environment_is_refused(self) -> None:
        """Copying it in would hand over a demo the guide refuses to run."""
        with tempfile.TemporaryDirectory() as workspace:
            tainted = Path(workspace) / "guide"
            shutil.copytree(self.checkout, tainted)
            (tainted / "skills" / build.FORBIDDEN_VENV_NAME).mkdir()
            result = run_build(
                "demo",
                "--dataset",
                "tiny",
                "--guide",
                "local",
                "--guide-src",
                str(tainted),
                "--out",
                str(Path(workspace) / "demo"),
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn(build.FORBIDDEN_VENV_NAME, result.stderr)

    def test_a_guide_source_with_no_commits_is_refused(self) -> None:
        """`"git_sha": null` is what a checkout with no commits, a machine with no git and
        a `rev-parse` that failed all look like."""
        with tempfile.TemporaryDirectory() as workspace:
            fresh = Path(workspace) / "guide"
            shutil.copytree(self.checkout, fresh, ignore=shutil.ignore_patterns(".git"))
            subprocess.run(
                ["git", "init", "-q"],
                cwd=fresh,
                capture_output=True,
                text=True,
                check=True,
            )
            result = run_build(
                "demo",
                "--dataset",
                "tiny",
                "--guide",
                "local",
                "--guide-src",
                str(fresh),
                "--out",
                str(Path(workspace) / "demo"),
            )
            self.assertEqual(result.returncode, 2)
            self.assertIn("could not read the commit", result.stderr)


if __name__ == "__main__":
    unittest.main()
