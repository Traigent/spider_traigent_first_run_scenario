# SPDX-License-Identifier: Apache-2.0
"""The component files behave the way the repository says they do.

The claim that matters most here is which evaluator executes model output. That is the
difference between the two SQL scorers, it is what the manifest records, and it is the
thing a reader is most likely to take on trust.
"""

from __future__ import annotations

import ast
import importlib.util
import inspect
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

EVALUATOR_DIR = REPO_ROOT / "components" / "evaluator"
AGENT_DIR = REPO_ROOT / "components" / "agent"
SCORER_ARGUMENTS = ("output", "expected", "input_data", "metadata")
EXECUTION_MODULES = {"sqlite3", "subprocess", "socket", "requests", "httpx"}


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def imported_modules(path: Path) -> set[str]:
    names: set[str] = set()
    for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.add(node.module.split(".")[0])
    return names


class EveryComponentParses(unittest.TestCase):
    def test_components_are_valid_python(self) -> None:
        for path in sorted(EVALUATOR_DIR.glob("*.py")) + sorted(AGENT_DIR.glob("*.py")):
            with self.subTest(component=path.name):
                ast.parse(path.read_text(encoding="utf-8"), str(path))

    def test_every_state_the_cli_offers_has_a_file(self) -> None:
        for state, path in {**build.AGENT_FILES, **build.EVALUATOR_FILES}.items():
            if path is not None:
                self.assertTrue(
                    path.exists(), f"{state} names a file that is not there"
                )

    def test_scorers_take_the_arguments_the_guide_passes(self) -> None:
        for path in sorted(EVALUATOR_DIR.glob("*.py")):
            with self.subTest(evaluator=path.name):
                module = load(path, f"probe_{path.stem}")
                parameters = inspect.signature(module.score).parameters
                for argument in SCORER_ARGUMENTS:
                    self.assertIn(
                        argument, parameters, f"{path.name} cannot accept {argument}"
                    )


class WhichScorerExecutesModelOutput(unittest.TestCase):
    """The manifest's `executes_candidate_output` has to be true of the source."""

    def test_the_text_comparison_reaches_nothing(self) -> None:
        source = EVALUATOR_DIR / "exact_match.py"
        self.assertEqual(imported_modules(source) & EXECUTION_MODULES, set())
        for node in ast.walk(ast.parse(source.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                self.assertNotIn(
                    node.func.id, ("exec", "eval", "compile", "__import__")
                )

    def test_the_execution_scorer_really_does_execute(self) -> None:
        self.assertIn("sqlite3", imported_modules(EVALUATOR_DIR / "exec_match.py"))

    def test_the_manifest_facts_match_the_source(self) -> None:
        for state, facts in build.EVALUATOR_FACTS.items():
            source = build.EVALUATOR_FILES[state]
            executes = bool(imported_modules(source) & EXECUTION_MODULES)
            self.assertEqual(
                facts["executes_candidate_output"],
                executes,
                f"{state} is recorded as executes_candidate_output={facts['executes_candidate_output']} "
                f"and its source says otherwise",
            )


class TextComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.scorer = load(EVALUATOR_DIR / "exact_match.py", "exact_probe")

    def score(self, output: str, expected: str) -> float:
        return self.scorer.score(
            output=output, expected=expected, input_data=None, metadata=None
        )

    def test_spacing_and_case_of_keywords_do_not_matter(self) -> None:
        self.assertEqual(
            self.score("SELECT  name   FROM singer;", "select name from singer"), 1.0
        )

    def test_quote_style_does_not_matter(self) -> None:
        self.assertEqual(
            self.score(
                'SELECT a FROM t WHERE c = "France"',
                "SELECT a FROM t WHERE c = 'France'",
            ),
            1.0,
        )

    def test_the_case_of_a_value_does_matter(self) -> None:
        """France and france are different values, even though SELECT and select are not."""
        self.assertEqual(
            self.score(
                "SELECT a FROM t WHERE c = 'france'",
                "SELECT a FROM t WHERE c = 'France'",
            ),
            0.0,
        )

    def test_a_differently_written_equivalent_query_is_marked_wrong(self) -> None:
        """The documented limit of comparing text. It under-counts correct answers."""
        self.assertEqual(self.score("SELECT b, a FROM t", "SELECT a, b FROM t"), 0.0)

    def test_a_row_with_no_answer_raises_rather_than_scoring_zero(self) -> None:
        """Grading against a missing answer would mark every attempt wrong and look real."""
        with self.assertRaises(ValueError):
            self.score("SELECT 1", "")


class ExecutionComparison(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.workspace = tempfile.mkdtemp()
        out = Path(cls.workspace) / "demo"
        result = subprocess.run(
            [
                sys.executable,
                str(REPO_ROOT / "build.py"),
                "demo",
                "--dataset",
                "mini",
                "--eval",
                "exec-match",
                "--out",
                str(out),
            ],
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 0, result.stderr
        cls.project = out / "project"
        cls.scorer = load(cls.project / "evaluator.py", "exec_probe")
        rows = [
            json.loads(line)
            for line in (cls.project / "dataset.jsonl").read_text().splitlines()
            if line
        ]
        cls.row = rows[0]

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.workspace, ignore_errors=True)

    def score(self, output: str) -> float:
        return self.scorer.score(
            output=output,
            expected=self.row["output"],
            input_data=self.row["input"],
            metadata=self.row["metadata"],
        )

    def test_the_recorded_query_scores_full_marks(self) -> None:
        self.assertEqual(self.score(self.row["output"]), 1.0)

    def test_a_query_written_differently_still_scores_on_its_rows(self) -> None:
        """This is what execution scoring buys, and why it exists at all."""
        self.assertEqual(self.score(f"SELECT * FROM ({self.row['output']})"), 1.0)

    def test_a_query_that_does_not_run_scores_zero(self) -> None:
        self.assertEqual(self.score("SELCT broken FROM"), 0.0)

    def test_a_row_with_no_database_raises(self) -> None:
        """Running against a different database returns a confident wrong score."""
        with self.assertRaises(KeyError):
            self.scorer.score(
                output="SELECT 1", expected="SELECT 1", input_data=None, metadata={}
            )


class AlwaysCorrectScorer(unittest.TestCase):
    def test_it_marks_anything_correct(self) -> None:
        scorer = load(EVALUATOR_DIR / "broken.py", "broken_probe")
        for output in ("SELECT 1", "", "not sql at all"):
            self.assertEqual(
                scorer.score(
                    output=output,
                    expected="SELECT name FROM singer",
                    input_data=None,
                    metadata=None,
                ),
                1.0,
            )


class Agents(unittest.TestCase):
    def test_both_agents_answer_a_question(self) -> None:
        for path in sorted(AGENT_DIR.glob("*.py")):
            with self.subTest(agent=path.name):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                functions = {
                    node.name for node in tree.body if isinstance(node, ast.FunctionDef)
                }
                self.assertIn("run", functions, f"{path.name} has no run()")

    def test_the_tunable_agent_declares_four_settings(self) -> None:
        module = load(AGENT_DIR / "agent_ready.py", "agent_probe")
        self.assertGreaterEqual(len(module.MODELS), 2)
        self.assertEqual(len(module.SCHEMA_CONTEXTS), 3)
        self.assertEqual(len(module.PROMPT_STYLES), 2)
        self.assertEqual(len(module.TEMPERATURES), 2)

    def test_each_setting_changes_the_request(self) -> None:
        """A setting that does not change what is sent is not a setting."""
        module = load(AGENT_DIR / "agent_ready.py", "agent_probe_prompt")
        schema = "CREATE TABLE singer (\nid INTEGER,\nname TEXT,\ncountry TEXT\n);"
        module._catalog = {
            "How many singers are there?": {"db_id": "concert_singer", "schema": schema}
        }
        base = {
            "model": "gpt-4o-mini",
            "schema_context": "none",
            "prompt_style": "direct",
            "temperature": 0.0,
        }
        question = "How many singers are there?"
        rendered = {
            name: module.build_prompt(question, {**base, **change})
            for name, change in {
                "base": {},
                "schema_tables": {"schema_context": "tables"},
                "schema_full": {"schema_context": "full"},
                "planning": {"prompt_style": "query_plan_cot"},
            }.items()
        }
        self.assertEqual(
            len(set(rendered.values())),
            len(rendered),
            "two settings produce the same request",
        )
        self.assertNotIn("singer(", rendered["base"])
        self.assertIn("singer(id, name, country)", rendered["schema_tables"])
        self.assertIn("CREATE TABLE singer", rendered["schema_full"])

    def test_the_fixed_agent_ignores_its_configuration(self) -> None:
        source = (AGENT_DIR / "agent_no_knobs.py").read_text(encoding="utf-8")
        self.assertNotIn(
            "config.get", source, "this agent is supposed to have nothing to vary"
        )

    def test_an_unknown_question_raises_rather_than_guessing(self) -> None:
        module = load(AGENT_DIR / "agent_ready.py", "agent_probe_missing")
        module._catalog = {}
        with self.assertRaises(KeyError):
            module.build_prompt(
                "a question nobody recorded", {"schema_context": "full"}
            )


if __name__ == "__main__":
    unittest.main()
