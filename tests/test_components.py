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
import sqlite3
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
# One agent per vendor, because the guide's opening read credits the model setting only from
# values it can see in the agent's own source. The behaviour tests use the default vendor;
# the ones that matter across all three say so.
DEFAULT_PROVIDER_DIR = AGENT_DIR / build.DEFAULT_PROVIDER


def every_agent():
    for provider in build.PROVIDERS:
        for state in ("ready", "no_knobs"):
            yield provider, state, AGENT_DIR / provider / f"agent_{state}.py"


SCORER_ARGUMENTS = ("output", "expected", "input_data", "metadata")
EXECUTION_MODULES = {"sqlite3", "subprocess", "socket", "requests", "httpx"}

# The rosters README.md publishes in its `--provider` table, written out here rather than
# read back from the agents. Read back, the assertion is the roster compared with itself and
# it passes whatever the roster is changed to -- which is how `len(MODELS) >= 2` let a model
# be dropped from a three-model roster with the suite still green. The manifest records this
# list and the guide's opening read scores the `model` setting from it, so both ends of the
# count matter: a shorter roster is a smaller search space and a longer one is a claim the
# README does not make.
DOCUMENTED_ROSTERS = {
    ("openrouter", "ready"): (
        "openrouter/qwen/qwen3-coder",
        "openrouter/openai/gpt-oss-120b",
        "openrouter/meta-llama/llama-3.3-70b-instruct",
    ),
    # One model, because one model is what it calls. It used to carry the full three-model
    # roster it never read, which made its demo.json indistinguishable from a tunable
    # agent's -- the arm with nothing to search recorded a search space of three.
    ("openrouter", "no_knobs"): ("openrouter/qwen/qwen3-coder",),
    ("direct", "ready"): (
        "gpt-4o-mini",
        "gpt-4o",
        "anthropic/claude-3-5-haiku-latest",
    ),
    ("direct", "no_knobs"): ("gpt-4o-mini",),
}

# Which credential names each vendor's env template has to declare, written out here for the
# same reason. `--provider direct` shipping OpenRouter's template is a project whose agent
# refuses every model in its own roster, and the two files are copied by separate code paths.
DOCUMENTED_CREDENTIALS = {
    "openrouter": ("OPENROUTER_API_KEY",),
    "direct": ("OPENAI_API_KEY", "ANTHROPIC_API_KEY"),
}


def split_rendered_names(text: str) -> list[str]:
    """A rendered column list split on the commas that are not inside a quoted name.

    `compact_schema` quotes any name that is not a bare identifier, and a quoted name may
    hold a comma. Splitting on every comma is the same mistake the renderer itself was
    fixed for, one level up.
    """
    parts: list[str] = []
    current: list[str] = []
    inside = False
    index = 0
    while index < len(text):
        character = text[index]
        if character == '"':
            if inside and index + 1 < len(text) and text[index + 1] == '"':
                current.append('""')
                index += 2
                continue
            inside = not inside
        if character == "," and not inside:
            parts.append("".join(current))
            current = []
        else:
            current.append(character)
        index += 1
    parts.append("".join(current))
    return [part.strip() for part in parts if part.strip()]


def unquoted(name: str) -> str:
    """The name a rendered identifier refers to, with its quoting removed.

    The quoting is the fix, not the value: `official_ratings_(millions)` unquoted is read as
    a call to a function called `official_ratings_` and fails on the column it names, and
    `18_49_Rating_Share` in `tvshow.TV_series` is not even a token. So the comparison with
    the database's own column list is made on the names, and the quoting is checked by
    executing the line instead.
    """
    name = name.strip()
    if len(name) >= 2 and name.startswith('"') and name.endswith('"'):
        return name[1:-1].replace('""', '"')
    return name.strip("`[]'")


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
        for path in sorted(EVALUATOR_DIR.glob("*.py")) + [
            p for _, _, p in every_agent()
        ]:
            with self.subTest(component=path.name):
                ast.parse(path.read_text(encoding="utf-8"), str(path))

    def test_every_state_the_cli_offers_has_a_file(self) -> None:
        for state, path in build.EVALUATOR_FILES.items():
            if path is not None:
                self.assertTrue(
                    path.exists(), f"{state} names a file that is not there"
                )
        for provider, state, path in every_agent():
            self.assertTrue(
                path.exists(), f"{provider}/{state} names a file that is not there"
            )
        for provider in build.PROVIDERS:
            self.assertTrue(
                build.env_file(provider).exists(), f"{provider} has no env template"
            )

    def test_every_file_in_components_is_a_state_the_cli_offers(self) -> None:
        """The other direction, which nothing checked.

        Walking CLI state -> file can only find a state whose file went missing. A component
        left behind after a state was renamed is invisible to it: the directory sits there,
        `check` compiles nothing of it, no preset reaches it, and one such directory did
        exist. A file in `components/` that no flag can select is either dead or a state
        somebody forgot to wire up, and both are worth being told about.
        """
        components = REPO_ROOT / "components"

        def entries(directory: Path, pattern: str = "*") -> set[str]:
            """What is really in a component directory.

            `__pycache__` is written by this file's own module loader and by any earlier
            run, so it is not evidence of a component -- but every other name is.
            """
            return {
                path.name
                for path in directory.glob(pattern)
                if not path.name.startswith("__")
            }

        self.assertEqual(
            sorted(
                name for name in entries(components) if (components / name).is_dir()
            ),
            ["agent", "calibration", "env", "evaluator", "legal", "readme"],
            "components/ holds a directory nothing in build.py reads",
        )
        named_evaluators = {
            path.name for path in build.EVALUATOR_FILES.values() if path is not None
        }
        self.assertEqual(
            entries(components / "evaluator", "*.py"),
            named_evaluators,
            "an evaluator file is not reachable through --eval",
        )
        self.assertEqual(
            sorted(
                name
                for name in entries(components / "agent")
                if (components / "agent" / name).is_dir()
            ),
            sorted(build.PROVIDERS),
            "an agent directory is not reachable through --provider",
        )
        for provider in build.PROVIDERS:
            expected = {
                build.agent_file(state, provider).name  # type: ignore[union-attr]
                for state in build.AGENT_STATES
                if build.agent_file(state, provider) is not None
            }
            self.assertEqual(
                entries(components / "agent" / provider, "*.py"),
                expected,
                f"{provider} holds an agent file no --agent state names",
            )
        self.assertEqual(
            entries(components / "env"),
            {build.env_file(provider).name for provider in build.PROVIDERS},
            "an env template is not reachable through --provider",
        )
        self.assertEqual(
            entries(components / "calibration"),
            {path.name for path in build.CALIBRATION_SOURCES.values()},
            "a calibration file no --eval state ships",
        )

    def test_each_env_template_declares_exactly_its_vendor_keys(self) -> None:
        """The template a `--provider` demo ships has to be that provider's.

        `direct` shipping OpenRouter's template is a project whose own `agent.py` refuses
        every model in its own roster with a message naming a key the project never
        mentions. The two files are chosen by separate code paths, and the credential names
        are written out here rather than read back off the agent so that changing both at
        once still has to be a decision.
        """
        for provider in build.PROVIDERS:
            with self.subTest(provider=provider):
                declared = {
                    line.split("=", 1)[0]
                    for line in build.env_file(provider).read_text().splitlines()
                    if "=" in line and not line.lstrip().startswith("#")
                }
                for name in DOCUMENTED_CREDENTIALS[provider]:
                    self.assertIn(name, declared, f"{provider}'s template omits {name}")
                for other, names in DOCUMENTED_CREDENTIALS.items():
                    if other == provider:
                        continue
                    for name in names:
                        if name in DOCUMENTED_CREDENTIALS[provider]:
                            continue
                        self.assertNotIn(
                            name,
                            declared,
                            f"{provider}'s template asks for {name}, which belongs to "
                            f"{other}",
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
        # Raised rather than asserted: `python -O` drops a bare assert, and the build
        # failure then surfaces three lines down as a FileNotFoundError about a path
        # nobody can explain.
        if result.returncode != 0:
            raise RuntimeError(f"the fixture build failed: {result.stderr}")
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


class TheVendorVariantsDoNotDrift(unittest.TestCase):
    """One agent per vendor, and they must stay one agent.

    The roster has to be a literal in each agent's own source, because the guide's opening
    read credits a setting only from values it can see there -- so the file is duplicated
    three times. Duplicated files diverge: this repository has already shipped a fix to one
    agent's reply handling and not the other, and the untunable arm then scored lower for a
    reason that had nothing to do with having no settings. Everything below the header must
    therefore be the same bytes in all three.
    """

    BODY_STARTS_AT = "_catalog = None"

    def body(self, path: Path) -> str:
        source = path.read_text(encoding="utf-8")
        self.assertIn(self.BODY_STARTS_AT, source, f"{path} has no recognisable body")
        return source[source.index(self.BODY_STARTS_AT) :]

    def test_each_agent_is_one_agent_across_vendors(self) -> None:
        for state in ("agent_ready", "agent_no_knobs"):
            with self.subTest(agent=state):
                bodies = {
                    provider: self.body(AGENT_DIR / provider / f"{state}.py")
                    for provider in build.PROVIDERS
                }
                reference = bodies[build.DEFAULT_PROVIDER]
                for provider, body in bodies.items():
                    self.assertEqual(
                        body,
                        reference,
                        f"{state} for {provider} has drifted from {build.DEFAULT_PROVIDER}",
                    )

    def test_every_variant_names_its_own_vendor_and_credentials(self) -> None:
        """The header is the part that is allowed to differ, so it has to be right."""
        for provider, state, path in every_agent():
            with self.subTest(provider=provider, agent=state):
                module = load(path, f"vendor_probe_{provider}_{state}")
                self.assertTrue(module.CREDENTIALS, "no credential names declared")
                for name in module.CREDENTIALS:
                    self.assertRegex(name, r"^[A-Z][A-Z0-9_]+$")
                self.assertTrue(module.MODELS, "no models declared")
                for model in module.MODELS:
                    self.assertTrue(model.strip(), "an empty model id")
                declared = set(build.env_file(provider).read_text().split())
                for name in module.CREDENTIALS:
                    self.assertTrue(
                        any(line.startswith(f"{name}=") for line in declared),
                        f"{provider}: the agent needs {name} and the env template omits it",
                    )


class TheScorerAndTheAgentAgreeAboutWhatTheModelSends(unittest.TestCase):
    """The three defects that made a knob unwinnable or a table imaginary.

    Each of these shipped once. Each is the kind that a green suite and a plausible-looking
    result would have hidden: the run completes, the numbers come out, and they are wrong
    for a reason that has nothing to do with the agent being measured.
    """

    def test_a_planned_answer_is_not_marked_wrong_for_its_plan(self) -> None:
        """`query_plan_cot` asks the model to think in SQL comments before answering.

        The text comparator used to keep those comments and weld them onto the query, so an
        answer identical to the recorded one scored 0.0 whenever the plan setting was on --
        on the default scorer, in most presets. A sweep would have concluded that planning
        hurts, with confidence, from a bug in the ruler.
        """
        scorer = load(EVALUATOR_DIR / "exact_match.py", "cot_probe")
        gold = "SELECT avg(age) FROM Dogs"
        for plan in (
            f"-- one table, one aggregate\n{gold}",
            f"/* one table, one aggregate */ {gold}",
            f"-- step one\n-- step two\n{gold}",
        ):
            with self.subTest(plan=plan.splitlines()[0]):
                self.assertEqual(
                    scorer.score(
                        output=plan, expected=gold, input_data=None, metadata=None
                    ),
                    1.0,
                )

    def test_the_compact_schema_describes_tables_that_exist(self) -> None:
        """The `tables` view is checked against the databases, not against itself.

        It used to be built by splitting on every comma, so `DECIMAL(19,4)` produced a
        column called `4)` and a composite key leaked its column list out as columns. Eleven
        tables across nine databases described something that was not there, and
        `schema_context` is the setting most likely to move a score.

        Naming the right columns is only half of it. A name the model cannot select is as
        useless as one that does not exist, so every rendered line is also prepared against
        the real database: `official_ratings_(millions)` unquoted parses as a call to a
        function called `official_ratings_` and fails with `no such column: millions`, and
        `tvshow.TV_series` holds `18_49_Rating_Share`, which unquoted is not a token at all.
        Executability is the property this test was reaching for; the column comparison
        alone passed on both of those.
        """
        agent = load(DEFAULT_PROVIDER_DIR / "agent_ready.py", "schema_probe")
        schemas: dict[str, str] = {}
        for line in (
            (REPO_ROOT / "spider" / "spider_300.jsonl").read_text().splitlines()
        ):
            row = json.loads(line)
            schemas.setdefault(row["metadata"]["db_id"], row["metadata"]["schema"])

        checked = 0
        for db_id, schema in sorted(schemas.items()):
            connection = sqlite3.connect(
                str(REPO_ROOT / "spider" / "databases" / db_id / f"{db_id}.sqlite")
            )
            try:
                real = {
                    name.lower(): [
                        column[1]
                        for column in connection.execute(f'PRAGMA table_info("{name}")')
                    ]
                    for (name,) in connection.execute(
                        "select name from sqlite_master where type='table' "
                        "and name not like 'sqlite_%'"
                    )
                }
                for rendered in agent.compact_schema(schema).splitlines():
                    written_table, _, columns = rendered.partition("(")
                    written_columns = split_rendered_names(columns.rstrip(")"))
                    table = unquoted(written_table)
                    named = [unquoted(c) for c in written_columns]
                    truth = real.get(table.lower())
                    checked += 1
                    self.assertIsNotNone(truth, f"{db_id}: no table called {table}")
                    self.assertEqual(
                        [c.lower() for c in named],
                        [c.lower() for c in truth or []],
                        f"{db_id}.{table} is described with columns it does not have",
                    )
                    # The line as written, handed to the database that has to accept it.
                    # LIMIT 0 because what is being tested is that SQLite parses and binds
                    # every name in it, not what the table holds.
                    statement = (
                        f"SELECT {', '.join(written_columns)} "
                        f"FROM {written_table.strip()} LIMIT 0"
                    )
                    try:
                        connection.execute(statement)
                    except sqlite3.Error as error:
                        self.fail(
                            f"{db_id}: the compact view renders a line the database "
                            f"refuses: {statement!r} -- {error}"
                        )
                # Counting only what the parser emitted cannot see a table it dropped, so
                # the rendered set is compared with the database's own list of tables.
                self.assertEqual(
                    {
                        unquoted(line.partition("(")[0]).lower()
                        for line in agent.compact_schema(schema).splitlines()
                    },
                    set(real),
                    f"{db_id}: the compact view and the database disagree on which tables "
                    "exist",
                )
            finally:
                connection.close()
        self.assertEqual(
            checked,
            74,
            "every table of every committed database should have been checked",
        )

    def test_the_execution_scorer_cannot_change_the_database(self) -> None:
        """A scorer that runs model-written SQL must not be able to write.

        SQLite runs DDL outside the transaction Python opens for INSERT/UPDATE/DELETE, so a
        hallucinated `DROP TABLE` used to succeed permanently -- and every later row on that
        database then failed and blamed the recorded answer for it.
        """
        with tempfile.TemporaryDirectory() as workspace:
            out = Path(workspace) / "demo"
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
            self.assertEqual(result.returncode, 0, result.stderr)
            project = out / "project"
            scorer = load(project / "evaluator.py", "write_probe")
            db_id = sorted(
                d.name for d in (project / "databases").iterdir() if d.is_dir()
            )[0]
            database = project / "databases" / db_id / f"{db_id}.sqlite"

            def tables() -> list[str]:
                connection = sqlite3.connect(str(database))
                try:
                    return sorted(
                        name
                        for (name,) in connection.execute(
                            "select name from sqlite_master where type='table'"
                        )
                    )
                finally:
                    connection.close()

            before = tables()
            attacks = {
                "drop": f"DROP TABLE {before[0]}",
                "create": "CREATE TABLE zzz_injected (a int)",
                "delete": f"DELETE FROM {before[0]}",
                "attach": f"ATTACH DATABASE '{project / 'zzz.sqlite'}' AS z",
                "vacuum": f"VACUUM INTO '{project / 'zzz_vacuum.sqlite'}'",
            }
            for name, sql in attacks.items():
                with self.subTest(attack=name):
                    self.assertEqual(
                        scorer.score(
                            output=sql,
                            expected="SELECT 1",
                            input_data=None,
                            metadata={"db_id": db_id},
                        ),
                        0.0,
                    )
                    self.assertEqual(tables(), before, f"{name} changed the database")
            self.assertEqual(
                sorted(path.name for path in project.glob("zzz*")),
                [],
                "the scorer wrote a file of its own",
            )


class TheMisWiredScorer(unittest.TestCase):
    """A scorer that reads the wrong two of its four arguments.

    The failure it produces is the mirror of the always-correct one: every row scores the
    same, so no configuration can be told from any other. Zero everywhere rather than one
    everywhere, which is easier to notice and no less useless.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.scorer = load(EVALUATOR_DIR / "swapped.py", "swapped_probe")

    def test_it_cannot_tell_a_right_answer_from_a_wrong_one(self) -> None:
        gold = "SELECT count(*) FROM singer"
        question = "How many singers are there?"
        right = self.scorer.score(
            output=gold, expected=gold, input_data=question, metadata=None
        )
        wrong = self.scorer.score(
            output="SELECT 1", expected=gold, input_data=question, metadata=None
        )
        self.assertEqual(right, wrong, "it distinguished them, which it must not")

    def test_it_never_reads_what_the_model_produced(self) -> None:
        gold = "SELECT count(*) FROM singer"
        scores = {
            self.scorer.score(
                output=output, expected=gold, input_data="a question", metadata=None
            )
            for output in (gold, "SELECT 1", "", "not sql at all", None)
        }
        self.assertEqual(len(scores), 1, "its answer depended on the output")

    def test_it_still_refuses_a_row_with_no_recorded_answer(self) -> None:
        """Being mis-wired is not a licence to grade against nothing."""
        with self.assertRaises(ValueError):
            self.scorer.score(
                output="SELECT 1", expected="", input_data="q", metadata=None
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


class ProbesBelongToTheScorerTheyShipWith(unittest.TestCase):
    """Each scorer separates the probe answers that ship with it, and `broken` does not.

    docs/eval-methods.md states this as a measurement -- exact-match passes, exec-match
    passes, broken fails -- and says handing either real scorer the other's probes would
    measure the wrong thing. Nothing ran a shipped scorer over its shipped probes, so the
    pairing in build.py could point one at another's cases and calibration would still read
    as having passed.

    Built through `build.py demo` rather than read out of components/, because the execution
    scorer needs the databases a real project has beside it.
    """

    @classmethod
    def setUpClass(cls) -> None:
        cls.workspace = tempfile.mkdtemp()
        cls.scorers = {}
        cls.cases = {}
        for state in ("exact-match", "exec-match", "broken"):
            out = Path(cls.workspace) / state
            result = subprocess.run(
                [
                    sys.executable,
                    str(REPO_ROOT / "build.py"),
                    "demo",
                    "--dataset",
                    "mini",
                    "--eval",
                    state,
                    "--calibration",
                    "present",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=False,
            )
            if result.returncode != 0:
                raise RuntimeError(f"the {state} fixture build failed: {result.stderr}")
            project = out / "project"
            cls.scorers[state] = load(
                project / "evaluator.py", f"calibrated_{state.replace('-', '_')}"
            )
            cls.cases[state] = json.loads(
                (project / build.RUNS_DIRECTORY / build.CALIBRATION_FILE).read_text()
            )

    @classmethod
    def tearDownClass(cls) -> None:
        shutil.rmtree(cls.workspace, ignore_errors=True)

    def probe(self, scorer: str, case: dict, name: str) -> float:
        return self.scorers[scorer].score(
            output=case["probes"][name],
            expected=case["expected"],
            input_data=case["input_data"],
            metadata=case["metadata"],
        )

    def check_it_separates_right_from_wrong(self, state: str) -> None:
        cases = self.cases[state]
        self.assertGreaterEqual(
            len(cases), 2, f"{state} ships too few cases to calibrate"
        )
        for case in cases:
            with self.subTest(evaluator=state, case=case["name"]):
                self.assertEqual(
                    self.probe(state, case, "good"),
                    1.0,
                    "the recorded answer is not marked right",
                )
                self.assertEqual(
                    self.probe(state, case, "equivalent_good"),
                    1.0,
                    "an answer this scorer counts as equivalent is not marked right",
                )
                self.assertEqual(
                    self.probe(state, case, "bad"),
                    0.0,
                    "a wrong answer is not marked wrong",
                )

    def test_the_text_comparison_passes_its_own_probes(self) -> None:
        self.check_it_separates_right_from_wrong("exact-match")

    def test_the_execution_scorer_passes_its_own_probes(self) -> None:
        self.check_it_separates_right_from_wrong("exec-match")

    def test_the_always_correct_scorer_fails_its_own_probes(self) -> None:
        """`broken` ships probes so that calibration catches it, which means failing them.

        A full mark for the wrong-answer probe is the failure, and it is the reason cases
        ship for a scorer that is not one.
        """
        cases = self.cases["broken"]
        self.assertGreaterEqual(
            len(cases), 2, "broken ships too few cases to calibrate"
        )
        for case in cases:
            with self.subTest(case=case["name"]):
                self.assertEqual(
                    self.probe("broken", case, "bad"),
                    1.0,
                    "broken marked a wrong answer wrong, so calibration would not catch it",
                )

    def test_the_execution_probes_are_not_the_text_comparison_probes(self) -> None:
        """The execution cases are equivalents the text comparison marks wrong.

        That is the difference between the two sets. The execution probes are queries
        written differently that return the same rows -- an alias, an `IN` with one element,
        an implicit ASC -- and the text comparison rejects every one of them, which is the
        limit it is documented to have. The text comparison's own probes are re-spellings
        that the execution scorer also accepts, so giving the execution scorer that set
        instead leaves everything above green. This is what sees it.
        """
        for case in self.cases["exec-match"]:
            with self.subTest(case=case["name"]):
                self.assertEqual(
                    self.scorers["exact-match"].score(
                        output=case["probes"]["equivalent_good"],
                        expected=case["expected"],
                        input_data=case["input_data"],
                        metadata=case["metadata"],
                    ),
                    0.0,
                    "the text comparison accepts this probe, so it is not an execution probe",
                )


class Agents(unittest.TestCase):
    def test_both_agents_answer_a_question(self) -> None:
        for _, _, path in every_agent():
            with self.subTest(agent=path.name):
                tree = ast.parse(path.read_text(encoding="utf-8"))
                functions = {
                    node.name for node in tree.body if isinstance(node, ast.FunctionDef)
                }
                self.assertIn("run", functions, f"{path.name} has no run()")

    def test_the_tunable_agent_declares_four_settings(self) -> None:
        module = load(DEFAULT_PROVIDER_DIR / "agent_ready.py", "agent_probe")
        self.assertEqual(
            tuple(module.MODELS), DOCUMENTED_ROSTERS[(build.DEFAULT_PROVIDER, "ready")]
        )
        self.assertEqual(len(module.SCHEMA_CONTEXTS), 3)
        self.assertEqual(len(module.PROMPT_STYLES), 2)
        self.assertEqual(len(module.TEMPERATURES), 2)

    def test_every_roster_is_the_one_the_readme_publishes(self) -> None:
        """Bounded at both ends, against a list written here and read from nowhere.

        `len(MODELS) >= 2` is satisfied by dropping a model from a three-model roster, and
        the manifest would then record a smaller search space than the README advertises
        with nothing to notice it. The roster is also what the guide's opening read scores
        the `model` setting from, so it is a published fact and not an implementation
        detail.
        """
        for provider, state, path in every_agent():
            with self.subTest(provider=provider, agent=state):
                module = load(path, f"roster_probe_{provider}_{state}")
                documented = DOCUMENTED_ROSTERS[(provider, state)]
                self.assertEqual(
                    tuple(module.MODELS),
                    documented,
                    f"{provider}/{state} ships a roster the README does not publish",
                )
                self.assertEqual(
                    sorted(module.MODEL_CREDENTIALS),
                    sorted(documented),
                    f"{provider}/{state}: a model in the roster has no credential name, "
                    "or a credential name names a model that is not in the roster",
                )

    def prepared(self, name: str):
        """The agent, with a known database and the provider call captured."""
        module = load(DEFAULT_PROVIDER_DIR / "agent_ready.py", name)
        schema = "CREATE TABLE singer (\nid INTEGER,\nname TEXT,\ncountry TEXT\n);"
        question = "How many singers are there?"
        module._catalog = {question: {"db_id": "concert_singer", "schema": schema}}
        sent: list[tuple[str, str, float]] = []

        def capture(model, prompt, temperature):
            sent.append((model, prompt, temperature))
            return "SELECT count(*) FROM singer"

        module.call_model = capture
        return module, question, sent

    def test_each_setting_changes_the_request(self) -> None:
        """A setting that does not change what is sent is not a setting.

        Driven through run() with the provider call stubbed, so what is asserted is the
        request that would actually go out rather than a helper's return value.
        """
        module, question, sent = self.prepared("agent_probe_request")
        base = {
            "model": next(iter(module.MODELS)),
            "schema_context": "none",
            "prompt_style": "direct",
            "temperature": 0.0,
        }
        changes = {
            "base": {},
            "model": {"model": list(module.MODELS)[1]},
            "schema_tables": {"schema_context": "tables"},
            "schema_full": {"schema_context": "full"},
            "planning": {"prompt_style": "query_plan_cot"},
            "temperature": {"temperature": 0.7},
        }
        for change in changes.values():
            module.run(question, {**base, **change})

        self.assertEqual(
            len(set(sent)), len(changes), "two settings send the same request"
        )
        rendered = dict(zip(changes, sent))
        self.assertIn("singer(id, name, country)", rendered["schema_tables"][1])
        self.assertIn("CREATE TABLE singer", rendered["schema_full"][1])

    def test_the_none_arm_sends_no_schema_at_all(self) -> None:
        """schema_context='none' is the control arm, and has to be empty.

        Not "no schema, but a sentence saying so" -- a sentence is content the model reads,
        and then the setting is partly measuring that sentence rather than measuring what
        showing a schema is worth. The request must differ by the schema and nothing else.
        """
        module, question, sent = self.prepared("agent_probe_control")
        base = {
            "model": next(iter(module.MODELS)),
            "prompt_style": "direct",
            "temperature": 0.0,
        }
        module.run(question, {**base, "schema_context": "none"})
        module.run(question, {**base, "schema_context": "full"})
        control, shown = sent[0][1], sent[1][1]

        for word in ("schema", "Schema", "CREATE TABLE", "singer("):
            self.assertNotIn(word, control, f"the control arm mentions {word!r}")
        self.assertIn(control, shown, "the two arms differ by more than the schema")

    def prepared_fixed(self, name: str):
        """The agent with no settings, with a known database and the request recorded.

        Both agents now reach their vendor through the same `call_model`, so both can be
        recorded the same way -- no faking a provider package.
        """
        module = load(DEFAULT_PROVIDER_DIR / "agent_no_knobs.py", name)
        schema = "CREATE TABLE singer (\nid INTEGER,\nname TEXT,\ncountry TEXT\n);"
        question = "How many singers are there?"
        module._catalog = {question: {"db_id": "concert_singer", "schema": schema}}
        sent: list[tuple[str, str, float]] = []

        def capture(model, prompt, temperature):
            sent.append((model, prompt, temperature))
            return "SELECT count(*) FROM singer"

        module.call_model = capture
        return module, question, sent

    def test_the_fixed_agent_ignores_its_configuration(self) -> None:
        """Every configuration produces the same request, because there is nothing to vary.

        This is the arm with no settings, and what makes it that arm is what goes out, not
        how the file is spelled. Reading the source for a phrase would pass an agent that
        reaches into its configuration by some other route, so this drives run() with the
        provider call recorded and compares the requests themselves.

        The configurations name settings this agent does not have, and one model id it does
        not carry -- which is the point: an agent that quietly honoured any of them would
        send more than one distinct request. It used to be driven with `MODELS[1]`, which
        only worked because the file carried a three-model roster it never read; the roster
        is now the one model it calls, so the invariance is asserted against values chosen
        for being outside it.
        """
        module, question, sent = self.prepared_fixed("agent_probe_fixed")
        self.assertEqual(
            len(module.MODELS),
            1,
            "the agent with nothing to search declares a roster it could search",
        )
        only_model = module.MODELS[0]
        configurations = (
            {},
            {"model": only_model},
            {"model": "a-model-this-agent-does-not-carry"},
            {"model": only_model, "temperature": 0.7},
            {"schema_context": "none", "prompt_style": "query_plan_cot"},
            {"schema_context": "full", "prompt_style": "direct", "temperature": 1.0},
        )
        for configuration in configurations:
            module.run(question, configuration)

        self.assertEqual(
            len(sent),
            len(configurations),
            "the agent did not send one request per configuration",
        )
        self.assertEqual(
            len(set(sent)),
            1,
            "a setting changed what the agent with no settings sends",
        )
        # And the one request it sends is the one its own roster names, at the one
        # temperature it runs at -- an invariant request built out of a model id from
        # nowhere would satisfy the count above and answer from a model nobody chose.
        model, prompt, temperature = sent[0]
        self.assertEqual(model, only_model)
        self.assertIn(question, prompt)
        self.assertIsInstance(temperature, float)

    def test_an_unsupported_setting_value_raises(self) -> None:
        """Answering under a setting the agent does not have would be a quiet wrong result."""
        module, question, _ = self.prepared("agent_probe_values")
        with self.assertRaises(ValueError):
            module.run(question, {"model": "some-model-we-never-configured"})
        with self.assertRaises(ValueError):
            module.run(question, {"schema_context": "some-view-that-does-not-exist"})

    def test_an_unknown_question_raises_rather_than_guessing(self) -> None:
        module = load(DEFAULT_PROVIDER_DIR / "agent_ready.py", "agent_probe_missing")
        module._catalog = {}
        with self.assertRaises(KeyError):
            module.build_prompt(
                "a question nobody recorded", {"schema_context": "full"}
            )


if __name__ == "__main__":
    unittest.main()
