# SPDX-License-Identifier: Apache-2.0
"""A count of this repository's own collections, written in prose, is derived from them.

A sentence that counts the bank -- its presets, its runs, its cards -- goes stale the moment
the bank grows, and nothing else reads it: the tables have tests, the sentences around them
did not. The first gate for this matched five lowercase phrasings, checked only the total of
an "N of the M" pair, and never read `docs/`, so "24 of the 32", "**Twelve**", "Thirty
presets" and "Five states write on that field" all passed it.

**What it checks, exactly.** A count is a number -- digits, or an English word up to
ninety-nine -- attached to a noun naming one of the collections this repository enumerates
and grows: presets, states, runs, cards, variants, comparisons, starting points, groups,
scorers, evaluators, choices. In "N of the M <noun>" both numbers are counts. It is read in
every tracked Markdown file, the notice and attribution files, and the comments and
docstrings of `build.py` and `docs/measurements/score_bank.py`. Code spans and code blocks
are quoted output and are skipped. Two uses of those nouns are not counts and are not read:
a bound ("at least one run") and a rate ("one card per step").

Every count found must sit inside a registered claim below: the sentence copied as a
template, each number replaced by the name of a quantity computed from the thing it counts
-- `build.PRESETS`, the sweep's lists, `cards/results.json`, the committed cards. A count no
claim covers fails as unregistered; a claim that no longer appears in its document fails as
stale; a quantity no claim uses fails as dead. A claim may also bind a count the detector
cannot see -- "Sixteen ship a project", whose noun is in the sentence before -- and that
count is then checked too.

**What it does not check.** A number before any other noun -- rows, databases, queries,
minutes, bands -- and any number a template keeps as literal text rather than as a
placeholder, such as "(61 rows)". Those describe the fixed slice or a measurement's
arithmetic rather than a collection that grows, and are outside this gate.

History is the one kind of count today's tree cannot recompute: "the seventeen states there
were then" is derived from `PRESET_ROUNDS`, a record of the rounds the presets arrived in that
is held to `build.PRESETS`, and the other two are recorded values with the reason beside them.
"""

from __future__ import annotations

import ast
import dataclasses
import io
import json
import re
import sys
import tokenize
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TESTS))

import test_score_bank as score_bank_tests  # noqa: E402
from test_build import declaring_states  # noqa: E402
from test_links import git_files, strip_code  # noqa: E402

import build  # noqa: E402

MEASUREMENTS = REPO_ROOT / "docs" / "measurements"
CARDS = MEASUREMENTS / "cards"

# ---------------------------------------------------------------------------------------
# Numbers, and what counts as a count.

UNITS = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()
# Generated rather than listed: the first gate kept the nine words the documents happened
# to use, so "Twelve" was not a number to it at all.
WORDS = {word: value for value, word in enumerate(UNITS)} | {
    f"{tens}-{UNITS[unit]}" if unit else tens: step * 10 + unit
    for step, tens in enumerate(TENS, start=2)
    for unit in range(10)
}
# Longest first, so "thirty-one" is read whole and never as "thirty" and a remainder.
NUMBER = r"(?:\d+|" + "|".join(sorted(WORDS, key=len, reverse=True)) + ")"


def read_number(written: str) -> int:
    written = written.lower()
    return int(written) if written.isdigit() else WORDS[written]


NOUN = (
    r"(?:presets?|states?|runs?|cards?|variants?|comparisons?|starting\s+points?|"
    r"groups?|scorers?|evaluators?|choices?)"
)
# A word between the number and the noun qualifies the noun ("two committed cards") unless
# it ends the phrase instead ("one that no run", "one thing its card asks for") or is itself
# a number ("in 2026 three states" counts three states, not 2026 of them).
NOT_A_QUALIFIER = (
    rf"(?:{NUMBER}|the|a|an|of|that|this|these|those|its|is|are|was|were|let|and|or|to|"
    r"in|on|for|per|by|at|as|with|from|thing|things|more|fewer|than|such|no|every|when)"
)
EMPHASIS = r"[*_]*"
COUNT = re.compile(
    # Not inside a word, a version, a date or an issue number; not the bound in "at least
    # one run"; not "the one choice", which means "the only".
    r"(?<![\w.#/$,-])(?<!at least )(?<!at most )(?<!up to )(?<!more than )"
    r"(?<!fewer than )(?:(?<!the )|(?!one\b))"
    + EMPHASIS
    + rf"(?P<n>{NUMBER})"
    + EMPHASIS
    # "Fifteen of the forty-nine cards": both are counts.
    + rf"(?:\s+of\s+(?:the\s+)?{EMPHASIS}(?P<m>{NUMBER}){EMPHASIS})?"
    # "six of its runs", "two committed cards", "a thirty-two-preset bank".
    + rf"(?:\s+of\s+(?:the|its)\s+|\s+(?!{NOT_A_QUALIFIER}\b)[\w'\"-]+\s+|\s+|-)" + NOUN
    # Not a rate: "one card per step" says how cards are made, not how many there are.
    + r"\b(?!\s+per\b)",
    re.I,
)


def counts_in(text: str) -> list[tuple[int, str]]:
    """Every count in some prose, as (offset, number as written).

    In "every one of the seventeen states" only the seventeen is a count: "one of" picks a
    member out of the collection rather than measuring it.
    """
    return [
        (match.start(group), match.group(group))
        for match in COUNT.finditer(text)
        for group in ("n", "m")
        if match.group(group) is not None
        and not (group == "n" and match.group("m") and read_number(match["n"]) == 1)
    ]


# ---------------------------------------------------------------------------------------
# Which files are prose, and which part of each is read.

# Programs whose comments and docstrings narrate the bank. A comment is where "the four
# mostly states" sat, one state too many, beside the constant it described.
NARRATING_PROGRAMS = ("build.py", "docs/measurements/score_bank.py")
PROSE_FILES = ("NOTICE", "components/legal/ATTRIBUTION.txt")


def corpus() -> list[str]:
    """Every tracked file this gate reads. Tracked, so a new document is in scope at once."""
    return sorted(
        name
        for name in git_files()
        if (
            name.endswith((".md", ".md.tmpl"))
            and not name.startswith("presentation/vendor/")
        )
        or name in PROSE_FILES
        or name in NARRATING_PROGRAMS
    )


def python_prose(text: str) -> str:
    """A program with all but its comments and docstrings blanked, offsets kept."""
    offsets = [0]
    for line in text.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))

    def at(row: int, column: int) -> int:
        return offsets[row - 1] + column

    # From after the `#`, so a sentence over three comment lines reads as one.
    kept = [
        (at(*token.start) + 1, at(*token.end))
        for token in tokenize.generate_tokens(io.StringIO(text).readline)
        if token.type == tokenize.COMMENT
    ]
    for node in ast.walk(ast.parse(text)):
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            if ast.get_docstring(node, clean=False) is not None:
                first = node.body[0]
                end = (first.end_lineno or first.lineno, first.end_col_offset or 0)
                kept.append((at(first.lineno, first.col_offset), at(*end)))
    out = ["\n" if character == "\n" else " " for character in text]
    for start, end in kept:
        out[start:end] = text[start:end]
    return "".join(out)


def without_code(text: str) -> str:
    """`test_links.strip_code` with every offset kept, not only every line.

    `strip_code` empties a line of a code block, which keeps line numbers and moves every
    offset after it; a claim is matched against the text with its code still in it, so the
    two views have to agree character for character.
    """
    return "".join(
        (
            stripped
            if len(stripped) == len(original)
            else "".join("\n" if character == "\n" else " " for character in original)
        )
        for original, stripped in zip(
            text.splitlines(keepends=True), strip_code(text).splitlines(keepends=True)
        )
    )


# ---------------------------------------------------------------------------------------
# History: the presets in the order they arrived, held to `build.PRESETS` below, so a new
# preset cannot land without saying which round brought it.
PRESET_ROUNDS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        "the first bank",
        (
            "ready",
            "checked",
            "no-eval",
            "no-labels",
            "no-knobs",
            "sql-exec-stop",
            "fake-ruler",
            "agent-and-logs",
            "logs-only",
            "no-agent",
            "no-data",
            "empty",
            "wrong-wiring",
            "duplicated-data",
            "wrong-answers",
            "hand-written",
            "best-case",
        ),
    ),
    (
        "ported on 2026-09-18",
        (
            "leaky-split",
            "holdout-only",
            "split-by-database",
            "raw-export",
            "torn-lines",
            "undeclared-source",
            "opaque-scorer",
            "length-blind",
            "two-agents",
        ),
    ),
    (
        "the provenance and cost round",
        (
            "mostly-undeclared-source",
            "mostly-synthetic-source",
            "generated-answer-key",
            "mostly-generated-answer-key",
            "slow-scorer",
        ),
    ),
    ("the provenance ladder's lower rung", ("synthetic-source",)),
)


@dataclasses.dataclass(frozen=True)
class Quantity:
    """A value, and where it came from -- which is what a failure has to name."""

    value: int
    source: str


# The two counts that are records of a day rather than of the tree, with the reason.
RECORDED = {
    "cards committed on 2026-09-22": Quantity(
        37,
        "recorded: the cards that existed when the pin moved to d07b62cd on 2026-09-22",
    ),
    "starting points the bank could not separate at 6ec2b9c1": Quantity(
        3, "recorded: the findings the bank made at 6ec2b9c1, listed under that heading"
    ),
}

# The conditions that say a scorer is not a scorer: it is invalid, or it cannot be run.
NOT_A_SCORER = {"evaluator-invalid", "evaluator-unresolved"}
WRONG_ON_PURPOSE = "## Data that is wrong on purpose"
SCORE_TABLES = "## Where each preset starts, and what the run has to do about it"


def table_presets(text: str, heading: str) -> list[str]:
    """The presets named in the first column of the first table under a heading."""
    after = text.split(heading, 1)[1]
    table = after[after.index("\n|") :].split("\n\n", 1)[0]
    return re.findall(r"^\|\s*`([a-z-]+)`\s*\|", table, re.M)


def caps_on(tag: str) -> set[str]:
    """The conditions a committed card carries."""
    reading = json.loads((CARDS / tag / "05-readiness.json").read_text("utf-8"))
    return {cap["condition"] for cap in reading["caps"]}


def measure() -> dict[str, Quantity]:
    """Every quantity a claim may name, each computed from the thing it counts."""
    sweep = score_bank_tests.load_harness()
    runs = json.loads((CARDS / "results.json").read_text(encoding="utf-8"))["runs"]
    scored = [run for run in runs if not run.get("refused")]
    presets, caps = build.PRESETS, build.PRESET_CAPS
    wrong = table_presets(
        (REPO_ROOT / "README.md").read_text("utf-8"), WRONG_ON_PURPOSE
    )
    ported = PRESET_ROUNDS[1][1]
    opened = [
        name for name in ported if caps[name] and set(caps[name]) <= caps_on(name)
    ]
    not_scorers = {
        presets[name]["eval"]
        for name, built in caps.items()
        if set(built) & NOT_A_SCORER
    }
    methods = {
        facts["method"]
        for state, facts in build.EVALUATOR_FACTS.items()
        if state not in not_scorers and facts["method"]
    }
    shipping = [name for name, spec in presets.items() if spec["dataset"] != "missing"]
    declaring = declaring_states()
    unread = [
        run["tag"]
        for run in scored
        if json.loads(
            (CARDS / run["tag"] / "05-readiness.json").read_text("utf-8")
        ).get("band_limited_by_unread_answers")
    ]
    rounds = "PRESET_ROUNDS"
    by_caps = "build.PRESET_CAPS against each committed card"
    found = dict(RECORDED)
    for name, value, source in (
        ("presets", len(presets), "build.PRESETS"),
        ("presets that ship rows", len(shipping), "build.PRESETS, dataset not missing"),
        ("presets that ship no rows", len(presets) - len(shipping), "build.PRESETS"),
        ("presets in the first bank", len(PRESET_ROUNDS[0][1]), rounds),
        ("presets ported on 2026-09-18", len(ported), rounds),
        (
            "presets added after the port",
            sum(len(names) for _, names in PRESET_ROUNDS[2:]),
            rounds,
        ),
        (
            "presets in the score tables",
            len(score_bank_tests.score_rows(REPO_ROOT / "README.md", SCORE_TABLES)),
            "the score tables in README.md, held to build.PRESETS",
        ),
        (
            "presets once the provenance and cost round landed",
            sum(len(names) for _, names in PRESET_ROUNDS[:3]),
            rounds,
        ),
        ("presets in the wrong-on-purpose table", len(wrong), "that table, README.md"),
        (
            "presets in that table that are broken",
            len([name for name in wrong if name != "split-by-database"]),
            "that table, less split-by-database, the control it names",
        ),
        (
            "ported presets that opened on the cap they were built for",
            len(opened),
            by_caps,
        ),
        (
            "ported presets that did not",
            len([name for name in ported if caps[name]]) - len(opened),
            by_caps,
        ),
        (
            "ported presets built for no cap",
            len([name for name in ported if not caps[name]]),
            "build.PRESET_CAPS",
        ),
        (
            "presets built for no condition",
            len([name for name in caps if not caps[name]]),
            "build.PRESET_CAPS",
        ),
        (
            "presets whose own card cannot show their condition",
            len(score_bank_tests.NOT_ON_THEIR_OWN_CARD),
            "NOT_ON_THEIR_OWN_CARD in tests/test_score_bank.py",
        ),
        (
            "mostly states",
            len(
                [state for state in build.DATASET_STATES if state.startswith("mostly-")]
            ),
            "build.DATASET_STATES",
        ),
        (
            "states that write a declaration",
            len(declaring),
            f"build.damage_rows over build.DATASET_STATES ({', '.join(declaring)})",
        ),
        ("presets the sweep names", len(sweep.PRESETS), "score_bank.PRESETS"),
        ("runs", len(runs), "cards/results.json"),
        (
            "comparisons",
            len([run for run in runs if run["tag"] not in presets]),
            "results.json, the runs not named for a preset",
        ),
        (
            "variant comparisons",
            len([tag for tag, _, _ in sweep.VARIANTS if tag not in presets]),
            "score_bank.VARIANTS not named for a preset",
        ),
        ("grid runs", len(sweep.GRID), "score_bank.GRID"),
        (
            "cards",
            len([entry for entry in CARDS.iterdir() if entry.is_dir()]),
            "the directories under cards/",
        ),
        (
            "refused runs",
            len(runs) - len(scored),
            "results.json, runs carrying `refused`",
        ),
        (
            "variants that declare the field names",
            len(
                [tag for tag, _, options in sweep.VARIANTS if "input_field" in options]
            ),
            "score_bank.VARIANTS",
        ),
        (
            "cards identical to another",
            sum(len(group) for group in score_bank_tests.IDENTICAL_CARDS),
            "IDENTICAL_CARDS in tests/test_score_bank.py, which is held to the cards",
        ),
        (
            "groups of identical cards",
            len(score_bank_tests.IDENTICAL_CARDS),
            "the same",
        ),
        (
            "runs held back by the unread answer key",
            len(unread),
            "band_limited_by_unread_answers on each card",
        ),
        (
            "execution-evaluator cards",
            len(
                [
                    run
                    for run in scored
                    if run["declared_evaluator_method"] == "execution"
                ]
            ),
            "results.json declared_evaluator_method",
        ),
        (
            "cards whose action is label-data",
            len([run for run in scored if run["recommended_action"] == "label-data"]),
            "results.json recommended_action",
        ),
        (
            "scoring methods",
            len(methods),
            f"the methods of the evaluators that score ({', '.join(sorted(methods))})",
        ),
        (
            "scorers that are not scorers",
            len(not_scorers),
            f"the evaluators of presets built for {' or '.join(sorted(NOT_A_SCORER))} "
            f"({', '.join(sorted(not_scorers))})",
        ),
        (
            "scorers with no honest method",
            len(
                [
                    facts
                    for facts in build.EVALUATOR_FACTS.values()
                    if not facts["method"]
                ]
            ),
            "build.EVALUATOR_FACTS",
        ),
    ):
        assert name not in found, f"quantity {name!r} is defined twice"
        found[name] = Quantity(value, source)
    return found


# ---------------------------------------------------------------------------------------
# The claims. A template is the sentence as written, code spans and emphasis included, with
# each number replaced by the quantity it counts; whitespace matches any whitespace, so a
# line break is a space.
CLAIMS: dict[str, tuple[str, ...]] = {
    "README.md": (
        "-- {presets that ship rows} of the {presets} presets get it, and the "
        "{presets that ship no rows} that do not are `empty` and `no-data`",
        "in every one of the {presets in the first bank} states there were then",
        "So a {presets}-preset bank with environments",
        "6.8 GB at {presets once the provenance and cost round landed} and 3.7 GB at "
        "{presets in the first bank})",
        "**{presets in the wrong-on-purpose table}** of the {presets} presets sit in "
        "this table. {presets in that table that are broken} ship a project",
        "because the {scoring methods} scoring methods disagree",
        "including how the {scoring methods} methods are graded, `slow`, which is right "
        "and too slow to check, and the {scorers that are not scorers} scorers beside "
        "them that are not scorers at all",
        "read the table as {presets in the score tables} starting points",
        "(the {execution-evaluator cards} execution-evaluator cards changed",
        "and the {cards whose action is label-data} cards whose action is `label-data`",
        "these {presets in the score tables} presets are the ones",
        "The {presets ported on 2026-09-18} ported on 2026-09-18 and the "
        "{presets added after the port} added after them for provenance and cost",
        "### {starting points the bank could not separate at 6ec2b9c1} starting points "
        "the opening gate does not separate",
        "from the {presets ported on 2026-09-18} presets ported on 2026-09-18",
        "| the {scoring methods} scoring methods, the slow scorer, the "
        "{scorers that are not scorers} scorers that are not scorers,",
    ),
    "build.py": (
        'the {mostly states} "mostly" states touch',
        "{presets built for no condition} presets are built for no condition",
        "{presets whose own card cannot show their condition} are built for a condition",
    ),
    "docs/dataset.md": (
        "{states that write a declaration} states write such a declaration",
    ),
    "docs/eval-methods.md": (
        "{scoring methods} of the choices are the real scoring methods",
        "The other {scorers that are not scorers} -- `broken`, `swapped`, `opaque` and "
        "`length-blind` --",
    ),
    "docs/isolation.md": (
        "in every one of the {presets in the first bank} states there were then",
        "the {presets ported on 2026-09-18} ported presets added",
    ),
    "docs/measurements/README.md": (
        "The {presets ported on 2026-09-18} presets ported on 2026-09-18 were measured "
        "by the same sweep as the {presets in the first bank} before them, and those "
        "{presets in the first bank} came back",
        "all {cards committed on 2026-09-22} cards that existed on that day",
        "**{refused runs} run cannot be measured at `d07b62cd`.**",
        "stands between {runs held back by the unread answer key} of its runs and their "
        "band",
        "Every one of `build.py`'s {presets} presets is run once: "
        "{presets the sweep names} by name,",
        "Then come the {comparisons} comparisons the documentation makes -- "
        "{variant comparisons} variants and the {grid runs} `grid-*` runs -- for "
        "{runs} runs in all:",
        "| the {presets the sweep names} presets |",
        "## What the {presets ported on 2026-09-18} ported presets measured",
        "{ported presets that opened on the cap they were built for} of the "
        "{presets ported on 2026-09-18} opened on the cap they were built for. "
        "{ported presets that did not} did not, and {ported presets built for no cap} "
        "was built for a question",
        "**The {scorers with no honest method} scorers that cannot be given a method",
        "{cards identical to another} of the {cards} cards fall into the "
        "{groups of identical cards} groups below",
        "**byte-identical**. {scorers with no honest method} scorers that cannot be "
        "given a method honestly",
    ),
    "docs/measurements/score_bank.py": (
        "At HEAD {refused runs} run cannot score",
        "ends 1 with that {refused runs} run refused",
        "except by {variants that declare the field names} variant",
        "is true on {runs held back by the unread answer key} cards -- `checked`, "
        "`wrong-answers--calibrated` and the {grid runs} `grid-*` runs",
    ),
}

PLACEHOLDER = re.compile(r"\{([^{}]+)\}")


def compile_claim(template: str) -> tuple[re.Pattern[str], list[str]]:
    """A template as a pattern, and the quantity each of its groups names."""
    pieces = PLACEHOLDER.split(template)
    pattern = "".join(
        (
            rf"(?P<q{index // 2}>{NUMBER})"
            if index % 2
            else r"\s+".join(map(re.escape, re.split(r"\s+", piece)))
        )
        for index, piece in enumerate(pieces)
    )
    return re.compile(pattern, re.I), pieces[1::2]


def problems_in(
    name: str, text: str, claims: tuple[str, ...], quantities: dict[str, Quantity]
) -> tuple[list[str], int]:
    """What is wrong with one document's counts, and how many counts were checked."""
    if name.endswith(".py"):
        text = python_prose(text)
    found: list[str] = []
    covered: set[int] = set()
    checked = 0
    for template in claims:
        pattern, names = compile_claim(template)
        matches = list(pattern.finditer(text))
        if not matches:
            found.append(
                f"{name}: a registered claim no longer appears in the document, so the "
                f"count it bound is no longer checked: {template!r}"
            )
        for match in matches:
            for index, quantity in enumerate(names):
                written, start = match.group(f"q{index}"), match.start(f"q{index}")
                covered.add(start)
                where = f"{name}:{text.count(chr(10), 0, start) + 1}"
                if quantity not in quantities:
                    found.append(f"{where}: no quantity is called {quantity!r}")
                    continue
                checked += 1
                if read_number(written) != quantities[quantity].value:
                    found.append(
                        f"{where} says {written!r} for {quantity!r}, and there are "
                        f"{quantities[quantity].value} ({quantities[quantity].source})"
                    )
    scanned = without_code(text)
    for start, written in counts_in(scanned):
        if start not in covered:
            context = " ".join(scanned[max(0, start - 60) : start + 60].split())
            found.append(
                f"{name}:{scanned.count(chr(10), 0, start) + 1}: {written!r} is a count "
                f"no claim derives ({context!r}); register the sentence in "
                "tests/test_prose_counts.py CLAIMS with the quantity it counts"
            )
    return found, checked


class EveryProseCountIsBound(unittest.TestCase):
    quantities: dict[str, Quantity]

    @classmethod
    def setUpClass(cls) -> None:
        cls.quantities = measure()

    def test_every_count_written_in_prose_matches_what_it_counts(self) -> None:
        problems: list[str] = []
        checked = 0
        for name in corpus():
            found, counted = problems_in(
                name,
                (REPO_ROOT / name).read_text(encoding="utf-8"),
                CLAIMS.get(name, ()),
                self.quantities,
            )
            problems += found
            checked += counted
        self.assertEqual([], problems, "\n".join(problems))
        registered = sum(
            len(PLACEHOLDER.findall(template))
            for templates in CLAIMS.values()
            for template in templates
        )
        self.assertGreaterEqual(checked, registered, "a registered count went unread")

    def test_every_claim_names_a_document_this_gate_reads(self) -> None:
        self.assertEqual([], sorted(set(CLAIMS) - set(corpus())))

    def test_every_quantity_is_one_some_claim_uses(self) -> None:
        used = {
            name
            for templates in CLAIMS.values()
            for template in templates
            for name in PLACEHOLDER.findall(template)
        }
        self.assertEqual([], sorted(set(self.quantities) - used))

    def test_the_history_accounts_for_every_preset_once(self) -> None:
        arrived = [name for _, names in PRESET_ROUNDS for name in names]
        self.assertEqual(len(arrived), len(set(arrived)), "a preset arrived twice")
        self.assertEqual(set(build.PRESETS), set(arrived))

    def test_the_wrong_on_purpose_table_names_real_presets(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        named = table_presets(readme, WRONG_ON_PURPOSE)
        self.assertTrue(named)
        self.assertEqual([], sorted(set(named) - set(build.PRESETS)))
        self.assertIn("split-by-database", named, "the control the sentence names")

    def test_the_runs_are_the_sweeps_and_the_cards_are_the_runs(self) -> None:
        sweep = score_bank_tests.load_harness()
        runs = self.quantities["runs"].value
        self.assertEqual(
            runs, len(sweep.PRESETS) + len(sweep.VARIANTS) + len(sweep.GRID)
        )
        self.assertEqual(runs, self.quantities["cards"].value)
        self.assertEqual(
            runs, len(build.PRESETS) + self.quantities["comparisons"].value
        )


class TheMeasurementJobOutlastsTheSweep(unittest.TestCase):
    """CI's time limit for the measurement job, against the running time the documents
    state -- one figure, kept in the README, so the workflow's comment cannot go stale
    beside it again."""

    def test_the_job_timeout_leaves_room_over_the_stated_sweep_time(self) -> None:
        readme = (MEASUREMENTS / "README.md").read_text(encoding="utf-8")
        stated = re.search(
            rf"The whole sweep takes ({NUMBER}) to ({NUMBER}) minutes", readme, re.I
        )
        assert stated, "docs/measurements/README.md no longer states the sweep's time"
        slowest = read_number(stated.group(2))
        workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8")
        job = workflow.split("\n  measurements:\n", 1)[1]
        timeout = re.search(r"^    timeout-minutes: (\d+)$", job, re.M)
        assert timeout, "the measurement job states no timeout"
        self.assertGreaterEqual(
            int(timeout.group(1)),
            2 * slowest,
            "the job's limit leaves no room over the sweep's stated running time",
        )


class TheGateCatchesWhatTheFirstOneMissed(unittest.TestCase):
    """Each edit applied to the real document in memory, failing for the right reason."""

    quantities: dict[str, Quantity]

    @classmethod
    def setUpClass(cls) -> None:
        cls.quantities = measure()

    def assert_caught(self, name: str, old: str, new: str, expected: str) -> None:
        text = (REPO_ROOT / name).read_text(encoding="utf-8")
        self.assertTrue(old in text, f"{old!r} is not in {name}")
        found, _ = problems_in(
            name, text.replace(old, new, 1), CLAIMS[name], self.quantities
        )
        self.assertIn(expected, "\n".join(found))

    def test_the_numerator_of_a_pair(self) -> None:
        self.assert_caught(
            "README.md",
            "30 of the 32",
            "24 of the 32",
            "'24' for 'presets that ship rows', and there are 30",
        )

    def test_a_count_in_emphasis(self) -> None:
        self.assert_caught(
            "README.md",
            "**Seventeen**",
            "**Twelve**",
            "'Twelve' for 'presets in the wrong-on-purpose table', and there are 17",
        )

    def test_a_total_whose_noun_is_in_the_clause_before(self) -> None:
        self.assert_caught(
            "docs/measurements/README.md",
            "thirty-one by name",
            "thirty by name",
            "'thirty' for 'presets the sweep names', and there are 31",
        )

    def test_the_numerator_written_out(self) -> None:
        self.assert_caught(
            "docs/measurements/README.md",
            "Fifteen of the",
            "Nine of the",
            "'Nine' for 'cards identical to another', and there are 15",
        )

    def test_a_state_count_in_docs(self) -> None:
        self.assert_caught(
            "docs/dataset.md",
            "Six states write",
            "Five states write",
            "'Five' for 'states that write a declaration', and there are 6",
        )

    def test_a_count_in_a_comment(self) -> None:
        self.assert_caught(
            "build.py",
            'the three "mostly" states',
            'the four "mostly" states',
            "'four' for 'mostly states', and there are 3",
        )

    def test_a_count_nobody_registered(self) -> None:
        self.assert_caught(
            "README.md",
            f"{WRONG_ON_PURPOSE}\n",
            f"{WRONG_ON_PURPOSE}\n\nForty-two presets are here.\n",
            "'Forty-two' is a count no claim derives",
        )

    def test_a_rewritten_sentence_retires_its_claim_loudly(self) -> None:
        self.assert_caught(
            "docs/dataset.md",
            "Six states write",
            "Several states write",
            "a registered claim no longer appears in the document",
        )


class TheDetectorReadsCountsAndNotIdioms(unittest.TestCase):
    """A false red is how a gate gets deleted, so ordinary sentences are held down too."""

    def test_counts_are_found_and_the_right_token_is_named(self) -> None:
        for text, numbers in (
            ("the four `grid-*` runs", ["four"]),
            ("six of its runs", ["six"]),
            ("a thirty-two-preset bank", ["thirty-two"]),
            ("25 of the 73 cards", ["25", "73"]),
            ("**Seventeen** of the thirty-two presets", ["Seventeen", "thirty-two"]),
            ("Five states write on that field", ["Five"]),
            ("Two of the choices are real scorers", ["Two"]),
            ("One run cannot be measured", ["One"]),
            ("in 2026 three states arrived", ["three"]),
            ("every one of the seventeen states", ["seventeen"]),
        ):
            with self.subTest(text=text):
                self.assertEqual(
                    numbers, [written for _, written in counts_in(without_code(text))]
                )

    def test_ordinary_sentences_are_not_counts(self) -> None:
        for text in (
            "at least one run is refused",
            "one card per step",
            "one scorer per project",
            "it waits fifteen minutes",
            "a twenty minutes timeout",
            "ten thousand questions",
            "the fifteenth release",
            "Step 3 of 5",
            "25 of the 73 rows",
            "the Traigent Guided First Run",
            "one of those states",
            "one that no run in this bank clears",
            "one thing its card asks for",
            "recommends one of two repairs",
            "the guide's 0.27.0 pin",
            "guide #556 let the run",
            "`--eval` is the one choice worth understanding",
        ):
            with self.subTest(text=text):
                self.assertEqual([], counts_in(without_code(text)))


if __name__ == "__main__":
    unittest.main()
