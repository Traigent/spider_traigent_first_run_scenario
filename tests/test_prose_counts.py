# SPDX-License-Identifier: Apache-2.0
"""Every count written in prose is bound to the quantity it counts.

A count in a sentence is a claim, and it is the claim that goes stale most quietly: a round
that adds presets and runs updates the tables, because a test reads them, and leaves the
sentences around them saying the previous round's totals. This repository shipped a dozen
of those at once, and then a gate that caught only five lowercase phrasings, checked only
the total of an "N of the M" pair, and did not read `docs/` at all -- so "24 of the 32",
"**Twelve**" and "Thirty presets" all passed it, and "Five states write on that field"
stayed wrong for a round after a sixth state was added.

So the gate is built the other way round. It does not look for the phrasings somebody
remembered to list; it finds every count and asks what derives it.

**What is a count.** Three shapes, read from the prose of every tracked Markdown file
(`README.md`, `docs/**` and the rest), the notice and attribution files, and the comments and
docstrings of `build.py` and `docs/measurements/score_bank.py`, which narrate the bank as much
as the documents do:

1. a number in front of a noun this repository enumerates -- presets, states, runs, cards,
   variants, comparisons, starting points, groups, scorers, evaluators ("thirty-one preset
   runs", "the four `grid-*` runs", "a thirty-two-preset bank");
2. **both** numbers of every "N of the M" pair, whatever they count ("30 of the 32",
   "Fifteen of the forty-nine cards", "127 of the 300 gold queries");
3. every number written out as a word from ten up, because the documents write their
   collection totals in words and a total is often left without its noun ("Sixteen ship a
   project ...", "the seventeen before them").

Small anaphoric numbers -- "the two that do not", "both of them" -- refer to a list beside
them rather than to a collection, and are read only where a claim below binds them anyway.
Code spans and code blocks are quoted output, not the document's own sentences, and are
passed over, as `test_links.py` passes over them.

**What derives it.** Every count found must sit inside a registered claim -- a template
copied from the sentence, with each number replaced by the name of a quantity -- and every
quantity is computed here from the thing it counts: `build.PRESETS`, the sweep's lists,
`cards/results.json`, the committed cards, the slice, `spider/provenance.json`. A count no
claim covers fails as unregistered, because a count nobody derives is a count nobody checks.
A claim that no longer matches its document fails too, so the registry cannot keep approving
a sentence that has been rewritten.

**What cannot be derived here.** Two kinds, each written down with its reason: history (a
count as it stood on a named day, kept as a recorded value, because later rounds do not change
it) and the guide's own constants (read back out of the guide's source when
`TRAIGENT_FIRST_RUN_GUIDE` names a checkout at the pin, as the measurement job in CI does, and
reported as unchecked otherwise). Neither is a way to skip a count: each is a named value the
prose has to agree with.
"""

from __future__ import annotations

import ast
import collections
import dataclasses
import importlib.util
import io
import json
import os
import re
import sqlite3
import sys
import tokenize
import types
import unittest
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
TESTS = Path(__file__).resolve().parent
sys.path.insert(0, str(REPO_ROOT))
sys.path.insert(0, str(TESTS))

import build  # noqa: E402
from test_build import declaring_states  # noqa: E402
from test_links import git_files, strip_code  # noqa: E402
from test_score_bank import (  # noqa: E402
    IDENTICAL_CARDS,
    NOT_ON_THEIR_OWN_CARD,
    load_harness,
)

MEASUREMENTS = REPO_ROOT / "docs" / "measurements"
CARDS = MEASUREMENTS / "cards"

# ---------------------------------------------------------------------------------------
# Reading a number, however it is written.

UNITS = (
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen"
).split()
TENS = "twenty thirty forty fifty sixty seventy eighty ninety".split()
ORDINAL_UNITS = (
    "zeroth first second third fourth fifth sixth seventh eighth ninth tenth eleventh "
    "twelfth thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth "
    "nineteenth"
).split()
ORDINAL_TENS = (
    "twentieth thirtieth fortieth fiftieth sixtieth seventieth eightieth ninetieth"
).split()


def spelled_numbers() -> tuple[dict[str, int], dict[str, int]]:
    """Every English cardinal and ordinal below a hundred, as the documents write them.

    Generated rather than listed: the gate this replaces kept a table of the nine words
    the documents happened to use, so "Twelve" was not a number to it at all.
    """
    cardinals = {word: value for value, word in enumerate(UNITS)}
    ordinals = {word: value for value, word in enumerate(ORDINAL_UNITS)}
    for step, (tens, ordinal) in enumerate(zip(TENS, ORDINAL_TENS), start=2):
        cardinals[tens] = step * 10
        ordinals[ordinal] = step * 10
        for unit in range(1, 10):
            cardinals[f"{tens}-{UNITS[unit]}"] = step * 10 + unit
            ordinals[f"{tens}-{ORDINAL_UNITS[unit]}"] = step * 10 + unit
    return cardinals, ordinals


CARDINALS, ORDINALS = spelled_numbers()


def alternation(words: dict[str, int]) -> str:
    # Longest first, so "thirty-one" is read whole and never as "thirty" and a remainder.
    return "|".join(sorted(words, key=len, reverse=True))


CARDINAL = rf"(?:\d+|{alternation(CARDINALS)})"
ANY_NUMBER = rf"(?:\d+|{alternation(ORDINALS)}|{alternation(CARDINALS)})"


def read_number(written: str) -> int | None:
    """The value of a number as written, or None if it is not one this gate can read."""
    written = written.strip("*_").lower()
    if written.isdigit():
        return int(written)
    return CARDINALS.get(written, ORDINALS.get(written))


# ---------------------------------------------------------------------------------------
# What counts as a count.

EMPHASIS = r"[*_]*"
# The collections this repository enumerates, and which grow.
COUNTED_NOUN = (
    r"(?:presets?|states?|runs?|cards?|variants?|comparisons?|starting\s+points?|"
    r"groups?|scorers?|evaluators?|choices?)"
)
# Words that end a noun phrase rather than qualify one: "one that no run" is a pronoun, not
# a count of runs, and "one thing its card asks for" is not a count of cards.
NOT_A_QUALIFIER = (
    r"(?:the|a|an|of|that|this|these|those|its|is|are|was|were|let|and|or|to|in|on|"
    r"for|per|by|at|as|with|from|thing|things|more|fewer|than|such|no|every|when)"
)
NOT_INSIDE_A_WORD = r"(?<![\w.#/$,-])"
COUNTED = re.compile(
    NOT_INSIDE_A_WORD + EMPHASIS
    # "the one choice worth understanding" is "the only", not a count of one.
    + rf"(?P<n>(?<!the )(?<!The )one\b|(?!one\b){CARDINAL})" + EMPHASIS
    # "six of its runs", but not "one of those states": "one of" is membership.
    + r"(?:(?<!one)\s+of\s+(?:the|its|these|those|all)\b)?"
    + rf"(?:-|\s+(?!{NOT_A_QUALIFIER}\b)[\w'\"-]+\s+|\s+){COUNTED_NOUN}\b",
    re.I,
)
PAIR = re.compile(
    NOT_INSIDE_A_WORD
    + EMPHASIS
    + rf"(?P<n>(?!one\b){CARDINAL})"
    + EMPHASIS
    + r"\s+(?:[\w-]+\s+)?(?:out\s+)?of\s+(?:the\s+|its\s+|these\s+|those\s+|all\s+)?"
    + EMPHASIS
    + rf"(?P<m>{CARDINAL})"
    + EMPHASIS
    + r"(?![\w]|\.\d)",
    re.I,
)
WRITTEN_OUT = re.compile(
    NOT_INSIDE_A_WORD
    + "(?P<n>"
    + alternation(
        {word: value for word, value in (CARDINALS | ORDINALS).items() if value >= 10}
    )
    + r")(?!\w)",
    re.I,
)
DETECTORS = (COUNTED, PAIR, WRITTEN_OUT)


# ---------------------------------------------------------------------------------------
# Which files are prose, and which part of each is read.

# Programs whose comments and docstrings narrate the bank. A comment is where "the four
# mostly states" sat, one state too many, beside the constant it described.
NARRATING_PROGRAMS = ("build.py", "docs/measurements/score_bank.py")
PROSE_FILES = ("NOTICE", "components/legal/ATTRIBUTION.txt")


def corpus() -> list[str]:
    """Every tracked file this gate reads, relative to the repository root.

    Tracked rather than globbed, like `test_links.py`: a new document is in scope the day
    it is committed, without anyone adding it to a list here.
    """
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
    """A program with everything but its comments and docstrings blanked out.

    Offsets and line numbers are kept, so a finding names the line a reader will open. The
    `#` that starts a comment is blanked too, so a sentence that runs across three comment
    lines reads as one sentence.
    """
    offsets = [0]
    for line in text.splitlines(keepends=True):
        offsets.append(offsets[-1] + len(line))

    def at(row: int, column: int) -> int:
        return offsets[row - 1] + column

    kept: list[tuple[int, int]] = []
    for token in tokenize.generate_tokens(io.StringIO(text).readline):
        if token.type == tokenize.COMMENT:
            kept.append((at(*token.start) + 1, at(*token.end)))
    for node in ast.walk(ast.parse(text)):
        if not isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            continue
        body = node.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            first = body[0]
            kept.append(
                (
                    at(first.lineno, first.col_offset),
                    at(first.end_lineno or first.lineno, first.end_col_offset or 0),
                )
            )
    out = ["\n" if character == "\n" else " " for character in text]
    for start, end in kept:
        out[start:end] = text[start:end]
    return "".join(out)


def without_code(text: str) -> str:
    """`test_links.strip_code`, with every offset kept, not only every line.

    `strip_code` replaces a line of a code block with an empty one, which keeps line
    numbers and moves every offset after it; the claims are matched against the text
    with its code still in it, so the two views have to agree character for character.
    A line it emptied is blanked here instead.
    """
    kept = []
    for original, stripped in zip(
        text.splitlines(keepends=True),
        strip_code(text).splitlines(keepends=True),
    ):
        if len(stripped) == len(original):
            kept.append(stripped)
        else:
            kept.append("".join("\n" if c == "\n" else " " for c in original))
    return "".join(kept)


def readable(name: str, text: str) -> str:
    """The text a claim is matched against: the prose, with its code spans still in it."""
    return python_prose(text) if name.endswith(".py") else text


# ---------------------------------------------------------------------------------------
# History: the presets in the order they arrived.
#
# Several sentences count the bank as it stood on a named day -- "the seventeen states there
# were then", "the nine presets ported on 2026-09-18", "6.8 GB at thirty-one". Those are not
# stale when the bank grows; they are history. They are still derived, from this record,
# which names every preset and is held to `build.PRESETS` below, so a new preset cannot land
# without saying which round brought it.
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


# ---------------------------------------------------------------------------------------
# The quantities.


@dataclasses.dataclass(frozen=True)
class Quantity:
    """A value, and where it came from -- which is what a failure has to name."""

    value: int
    source: str


@dataclasses.dataclass(frozen=True)
class GuideConstant:
    """A number the guide owns, quoted in this repository's prose.

    The guide's script at the pinned revision publishes it as a module constant (a length,
    for a sequence). `value` is the one the prose was written against, and
    `TheGuideAgrees` reads it back out of the guide when a checkout is named.
    """

    script: str
    name: str
    value: int


# Counts that are records rather than derivations, each with the reason it cannot be derived
# here. A recorded value is still a binding: the prose has to say this number.
RECORDED = {
    "cards committed on 2026-09-22": Quantity(
        37,
        "recorded: the cards that existed when the pin moved to d07b62cd on 2026-09-22, "
        "a count of that day which later rounds do not change",
    ),
    "starting points the bank could not separate at 6ec2b9c1": Quantity(
        3,
        "recorded: the findings the bank made at 6ec2b9c1, which the section that says "
        "so goes on to list",
    ),
    "settings the reader credited at 6ec2b9c1": Quantity(
        3, "recorded: a 6ec2b9c1 reading, in which the reader declined `temperature`"
    ),
    "rows an earlier draw left on their own answer": Quantity(
        5, "recorded: the defect the current derangement check was written against"
    ),
    "evaluation-pillar points the declaration was worth on 2026-09-02": Quantity(
        16, "recorded: the 2026-09-02 reading docs/eval-methods.md says it is quoting"
    ),
    "the sides of a comparison": Quantity(
        2, "recorded: a diff, like an identity between two cards, compares two things"
    ),
    "presets the eval-methods comparison sets side by side": Quantity(
        2, "recorded: the two bullets that follow the sentence"
    ),
    "the base of a ratio written 'N in ten'": Quantity(
        10, "recorded: the denominator of a ratio, not a count"
    ),
    "databases in Spider's development split": Quantity(
        20,
        "recorded: Spider 1.0's dev split, as spider/LICENSE-DATA states it; the "
        "754-row source file is not committed, so it cannot be recounted here",
    ),
    "tuning rows below which the guide caps a comparison": Quantity(
        10,
        "recorded: readiness.py at the pin raises dataset-below-measurable-size on "
        "`effective_n < 10`, a literal in its control flow rather than a constant a "
        "test could read",
    ),
}

GUIDE_CONSTANTS = {
    "configurations that earn the agent pillar whole": GuideConstant(
        "readiness.py", "SEARCH_SPACE_FULL", 12
    ),
    "bands on the guide's scale": GuideConstant("readiness.py", "BAND_ORDER", 5),
    "rows the guide holds out by default": GuideConstant(
        "readiness.py", "WALKTHROUGH_HOLDOUT_ROWS", 10
    ),
}


def load_module(path: Path, name: str) -> types.ModuleType:
    """A module by path, registered before it runs, as `load_harness` does."""
    located = importlib.util.spec_from_file_location(name, path)
    assert located is not None and located.loader is not None
    module = importlib.util.module_from_spec(located)
    sys.modules[located.name] = module
    located.loader.exec_module(module)
    return module


def table_presets(text: str, heading: str) -> list[str]:
    """The presets named in the first column of the first table under a heading."""
    after = text.split(heading, 1)[1]
    names: list[str] = []
    in_table = False
    for line in after.splitlines():
        if line.startswith("|"):
            in_table = True
            found = re.match(r"\|\s*`([a-z-]+)`\s*\|", line)
            if found:
                names.append(found.group(1))
        elif in_table:
            break
    return names


def gold_scalars(rows: list[dict[str, Any]]) -> list[object]:
    """The single value each gold query returns, for the ones that return exactly one."""
    values: list[object] = []
    for row in rows:
        database = row["metadata"]["db_id"]
        path = build.DATABASES_PATH / database / f"{database}.sqlite"
        connection = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
        try:
            result = connection.execute(row["output"]).fetchall()
        finally:
            connection.close()
        if len(result) == 1 and len(result[0]) == 1:
            values.append(result[0][0])
    return values


def measure() -> dict[str, Quantity]:
    """Every quantity a claim may name, each computed from the thing it counts."""
    sweep = load_harness()
    runs = json.loads((CARDS / "results.json").read_text(encoding="utf-8"))["runs"]
    scored = [run for run in runs if not run.get("refused")]
    card_directories = sorted(entry for entry in CARDS.iterdir() if entry.is_dir())
    readings = {
        entry.name: json.loads(
            (entry / "05-readiness.json").read_text(encoding="utf-8")
        )
        for entry in card_directories
        if (entry / "05-readiness.json").is_file()
    }
    rows = build.read_dataset()
    readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    wrong_on_purpose = table_presets(readme, "## Data that is wrong on purpose")
    provenance = json.loads(
        (REPO_ROOT / "spider" / "provenance.json").read_text(encoding="utf-8")
    )
    datasheet = (REPO_ROOT / "spider" / "datasheet.yaml").read_text(encoding="utf-8")
    ready_preflight = {
        check["check"]: check
        for check in json.loads(
            (CARDS / "ready" / "02-preflight.json").read_text(encoding="utf-8")
        )
    }
    knobs = json.loads(
        (MEASUREMENTS / "agent-knobs" / "ready.json").read_text(encoding="utf-8")
    )

    found: dict[str, Quantity] = dict(RECORDED)

    def put(name: str, value: int, source: str) -> None:
        assert name not in found, f"quantity {name!r} is defined twice"
        found[name] = Quantity(value, source)

    # The presets, now and as they arrived.
    presets = build.PRESETS
    with_rows = [name for name, spec in presets.items() if spec["dataset"] != "missing"]
    put("presets", len(presets), "build.PRESETS")
    put("presets that ship rows", len(with_rows), "build.PRESETS, dataset not missing")
    put(
        "presets that ship no rows",
        len(presets) - len(with_rows),
        "build.PRESETS, dataset missing",
    )
    put("presets in the first bank", len(PRESET_ROUNDS[0][1]), "PRESET_ROUNDS")
    put("presets ported on 2026-09-18", len(PRESET_ROUNDS[1][1]), "PRESET_ROUNDS")
    put(
        "presets once the provenance and cost round landed",
        sum(len(names) for _, names in PRESET_ROUNDS[:3]),
        "PRESET_ROUNDS",
    )
    put(
        "presets in the wrong-on-purpose table",
        len(wrong_on_purpose),
        "the table under README.md's 'Data that is wrong on purpose'",
    )
    put(
        "presets in that table that are broken",
        len([name for name in wrong_on_purpose if name != "split-by-database"]),
        "the same table, less split-by-database, the control it names",
    )
    put(
        "ported presets that opened on the cap they were built for",
        len(
            [
                name
                for name in PRESET_ROUNDS[1][1]
                if build.PRESET_CAPS[name]
                and set(build.PRESET_CAPS[name])
                <= {cap["condition"] for cap in readings[name]["caps"]}
            ]
        ),
        "build.PRESET_CAPS against each committed card",
    )
    put(
        "ported presets that did not",
        len(
            [
                name
                for name in PRESET_ROUNDS[1][1]
                if build.PRESET_CAPS[name]
                and not set(build.PRESET_CAPS[name])
                <= {cap["condition"] for cap in readings[name]["caps"]}
            ]
        ),
        "build.PRESET_CAPS against each committed card",
    )
    put(
        "ported presets built for no cap",
        len([name for name in PRESET_ROUNDS[1][1] if not build.PRESET_CAPS[name]]),
        "build.PRESET_CAPS",
    )
    put(
        "presets built for no condition",
        len([name for name, caps in build.PRESET_CAPS.items() if not caps]),
        "build.PRESET_CAPS",
    )
    put(
        "presets whose own card cannot show their condition",
        len(NOT_ON_THEIR_OWN_CARD),
        "NOT_ON_THEIR_OWN_CARD in tests/test_score_bank.py",
    )

    # The states a project is built from.
    put(
        "mostly states",
        len([state for state in build.DATASET_STATES if state.startswith("mostly-")]),
        "build.DATASET_STATES",
    )
    declaring = declaring_states()
    put(
        "states that write a declaration",
        len(declaring),
        f"build.damage_rows over build.DATASET_STATES ({', '.join(declaring)})",
    )

    # The sweep and what it produced.
    preset_runs = [run for run in runs if run["tag"] in presets]
    put("presets the sweep names", len(sweep.PRESETS), "score_bank.PRESETS")
    put(
        "presets the sweep names only through a variant",
        len(set(presets) - set(sweep.PRESETS)),
        "build.PRESETS less score_bank.PRESETS",
    )
    put("preset runs", len(preset_runs), "results.json, the runs named for a preset")
    put("comparisons", len(runs) - len(preset_runs), "results.json, the other runs")
    put(
        "variant comparisons",
        len([tag for tag, _, _ in sweep.VARIANTS if tag not in presets]),
        "score_bank.VARIANTS not named for a preset",
    )
    put("grid runs", len(sweep.GRID), "score_bank.GRID")
    put("cards", len(card_directories), "the directories under cards/")
    put(
        "refused runs", len(runs) - len(scored), "results.json, runs carrying `refused`"
    )
    put(
        "variants that declare the field names",
        len([tag for tag, _, options in sweep.VARIANTS if "input_field" in options]),
        "score_bank.VARIANTS",
    )
    put(
        "cards identical to another",
        sum(len(group) for group in IDENTICAL_CARDS),
        "IDENTICAL_CARDS in tests/test_score_bank.py, which is held to the cards",
    )
    put("groups of identical cards", len(IDENTICAL_CARDS), "the same")
    put(
        "runs held back by the unread answer key",
        len(
            [
                name
                for name, reading in readings.items()
                if reading.get("band_limited_by_unread_answers")
            ]
        ),
        "band_limited_by_unread_answers in each card's 05-readiness.json",
    )
    put(
        "execution-evaluator cards",
        len([run for run in scored if run["declared_evaluator_method"] == "execution"]),
        "results.json declared_evaluator_method",
    )
    put(
        "cards whose action is label-data",
        len([run for run in scored if run["recommended_action"] == "label-data"]),
        "results.json recommended_action",
    )
    put(
        "bands the presets open in",
        len({run["band"] for run in preset_runs if run["band"]}),
        "results.json, the preset runs",
    )
    thin = {
        tag: [
            subscore["measured"]
            for pillar in readings[tag]["pillars"]
            if pillar["name"] == "evaluation"
            for subscore in pillar["subscores"]
        ]
        for tag in ("best-case", "sql-exec-stop")
    }
    assert thin["best-case"] == thin["sql-exec-stop"], thin
    put(
        "evaluation checks measured for the execution scorer",
        sum(thin["best-case"]),
        "the evaluation pillar of the best-case and sql-exec-stop cards",
    )
    put("evaluation checks", len(thin["best-case"]), "the same pillar")
    family = ready_preflight["dataset-split-family"]["metrics"]
    put(
        "input forms on both sides of ready's split",
        family["shared_families"],
        "cards/ready/02-preflight.json",
    )
    put("recurring input forms in ready", family["families"], "the same")
    put(
        "agent settings",
        len(knobs["knobs"]),
        "docs/measurements/agent-knobs/ready.json",
    )

    # The scorers.
    methods = {
        facts["method"] for facts in build.EVALUATOR_FACTS.values() if facts["method"]
    }
    put("scoring methods", len(methods), f"build.EVALUATOR_FACTS {sorted(methods)}")
    put(
        "scorers the broken-scorer presets ship",
        len(
            {
                presets[name]["eval"]
                for name in wrong_on_purpose
                if presets[name]["dataset"] == "ready"
            }
        ),
        "the scorers of the wrong-on-purpose table's presets whose data is intact",
    )
    put(
        "scorers with no honest method",
        len([facts for facts in build.EVALUATOR_FACTS.values() if not facts["method"]]),
        "build.EVALUATOR_FACTS",
    )

    # The rows.
    databases = {row["metadata"]["db_id"] for row in rows}
    held = build.held_out_databases(build.resplit_by_database(rows))
    put("rows in the slice", len(rows), "spider/spider_300.jsonl")
    put("databases in the slice", len(databases), "spider/spider_300.jsonl")
    put("databases split-by-database holds out", len(held), "build.resplit_by_database")
    put(
        "databases split-by-database tunes on",
        len(databases) - len(held),
        "build.resplit_by_database",
    )
    mostly = {
        sum(
            1
            for row in build.damage_rows(list(rows), state)
            if row["metadata"].get(key) == value
        )
        for state, key, value in (
            ("mostly-undeclared", "provenance", build.UNDECLARED_PROVENANCE),
            ("mostly-synthetic", "provenance", build.SYNTHETIC_PROVENANCE),
            (
                "mostly-generated-answers",
                build.GENERATED_ANSWER_KEY,
                build.GENERATED_ANSWER_PROVENANCE,
            ),
        )
    }
    assert len(mostly) == 1, mostly
    put("rows a mostly state declares on", mostly.pop(), "build.damage_rows")
    duplicated_draw = build.select_rows(rows, "duplicated")
    put("rows in the duplicated draw", len(duplicated_draw), "build.select_rows")
    put(
        "rows duplicated-data repeats",
        len(build.damage_rows(duplicated_draw, "duplicated")) - len(duplicated_draw),
        "build.damage_rows",
    )
    rotated_draw = build.select_rows(rows, "wrong-answers")
    put("rows in the wrong-answers draw", len(rotated_draw), "build.select_rows")
    put(
        "rows wrong-answers leaves on their own answer",
        sum(
            1
            for before, after in zip(
                rotated_draw, build.damage_rows(rotated_draw, "wrong-answers")
            )
            if before["output"] == after["output"]
        ),
        "build.damage_rows",
    )
    put("rows hand-written ships", build.TINY_ROWS, "build.TINY_ROWS")
    put(
        "rows the second agent ships",
        build.SECOND_AGENT_ROWS,
        "build.SECOND_AGENT_ROWS",
    )
    scalars = gold_scalars(rows)
    put(
        "gold queries that return one value",
        len(scalars),
        "every gold query, run against its database",
    )
    put(
        "rows the best constant answer matches",
        max(collections.Counter(map(repr, scalars)).values()),
        "the same",
    )
    put(
        "single-value answers in ten",
        round(10 * len(scalars) / len(rows)),
        "the same, as a ratio",
    )
    holdout_per_database = collections.Counter(
        row["metadata"]["db_id"]
        for row in rows
        if row["metadata"]["split"] == "holdout"
    )
    put(
        "databases with two or fewer held-out rows",
        len([name for name in databases if holdout_per_database[name] <= 2]),
        "spider/spider_300.jsonl",
    )
    put(
        "databases with no held-out rows",
        len([name for name in databases if holdout_per_database[name] == 0]),
        "spider/spider_300.jsonl",
    )
    put(
        "rows dropped for an empty gold",
        provenance["filters"]["dropped_empty_gold"],
        "spider/provenance.json",
    )
    put(
        "rows in the source pool",
        provenance["source"]["rows"],
        "spider/provenance.json",
    )
    before = re.search(
        r"Before the re-cut, (\d+) of the (\d+) holdout rows\s+\(\d+%\) had a gold "
        r"query\s+byte-identical to a tuning row's -- (\d+) of the (\d+) very-hard rows",
        datasheet,
    )
    assert before, "spider/datasheet.yaml no longer records the old holdout overlap"
    for name, group in (
        ("held-out rows that shared a gold before the re-cut", 1),
        ("held-out rows before the re-cut", 2),
        ("very-hard held-out rows that shared a gold before the re-cut", 3),
        ("very-hard held-out rows before the re-cut", 4),
    ):
        put(name, int(before.group(group)), "spider/datasheet.yaml known_flaws")
    connected = ast.parse(
        (REPO_ROOT / "first-run-runners" / "connected" / "run_connected.py").read_text(
            encoding="utf-8"
        )
    )
    trials = [
        node.value.value
        for node in connected.body
        if isinstance(node, ast.Assign)
        and isinstance(node.value, ast.Constant)
        and any(
            isinstance(target, ast.Name) and target.id == "MAX_TRIALS"
            for target in node.targets
        )
    ]
    assert len(trials) == 1, trials
    put("trials the connected run asks for", trials[0], "run_connected.py MAX_TRIALS")

    for name, constant in GUIDE_CONSTANTS.items():
        put(
            name,
            constant.value,
            f"the guide's {constant.script} {constant.name}, as the prose quotes it",
        )
    return found


# ---------------------------------------------------------------------------------------
# The claims: every sentence that counts, with each number replaced by what it counts.
#
# A template is copied from the sentence as written, code spans and emphasis included, and
# whitespace in it matches any whitespace, so a line break is a space. Enough of the sentence
# is kept that the template names one place; every number the detectors find inside it has
# to be one of its placeholders.
CLAIMS: dict[str, tuple[str, ...]] = {
    "README.md": (
        "-- {presets that ship rows} of the {presets} presets get it, and the "
        "{presets that ship no rows} that do not are `empty` and `no-data`",
        "in every one of the {presets in the first bank} states there were then",
        "| `hand-written` | {rows hand-written ships} examples, and probes kept",
        "So a {presets}-preset bank with environments",
        "6.8 GB at {presets once the provenance and cost round landed} and 3.7 GB at "
        "{presets in the first bank})",
        "**{presets in the wrong-on-purpose table}** of the {presets} presets sit in "
        "this table. {presets in that table that are broken} ship a project",
        "the {presets in the wrong-on-purpose table}, `split-by-database`, is not wrong",
        "the held-out side is {databases split-by-database holds out} whole databases "
        "(61 rows) and the tuning side the other {databases split-by-database tunes on}.",
        "the same word on {rows a mostly state declares on} of the {rows in the slice} "
        "rows",
        "the same declaration on {rows a mostly state declares on} of the "
        "{rows in the slice}.",
        "because {rows duplicated-data repeats} of the {rows in the duplicated draw} "
        "appear twice",
        "**{rows wrong-answers leaves on their own answer} of "
        "{rows in the wrong-answers draw}** rows keep the answer",
        "wrong in {rows an earlier draw left on their own answer} rows of "
        "{rows in the wrong-answers draw} while",
        "## The {scoring methods} SQL evaluators",
        "because the {scoring methods} scorers disagree",
        "including how the {scoring methods} scorers are graded, and the "
        "{scorers with no honest method} scorers beside them that are not scorers",
        "read the table as {presets} starting points",
        "(the {execution-evaluator cards} execution-evaluator cards changed",
        "and the {cards whose action is label-data} cards whose action is `label-data`",
        "| more examples than {rows hand-written ships} |",
        "**{bands the presets open in} of the {bands on the guide's scale} bands",
        "these {presets} presets are the ones",
        "measured on {evaluation checks measured for the execution scorer} checks of "
        "{evaluation checks}, and a pillar",
        "credits a {configurations that earn the agent pillar whole}-configuration space",
        "### {starting points the bank could not separate at 6ec2b9c1} starting points "
        "the opening gate does not separate",
        "Each is a `diff` over {the sides of a comparison} committed cards",
        "from the {presets ported on 2026-09-18} presets ported on 2026-09-18",
        "each a `diff` over {the sides of a comparison} committed cards",
        "({input forms on both sides of ready's split} of "
        "{recurring input forms in ready} on `ready`)",
        "{rows the second agent ships} gold queries as an unlabelled",
        "credited **{settings the reader credited at 6ec2b9c1} of the {agent settings}**",
        "at least {configurations that earn the agent pillar whole} distinct "
        "configurations",
        "measured on {evaluation checks measured for the execution scorer} checks of "
        "{evaluation checks}; the two projects",
        "**{gold queries that return one value} of the {rows in the slice} gold queries "
        "(42.3%)",
        "scores {rows the best constant answer matches} of {rows in the slice} (2.3%)",
        "| the {scoring methods} SQL scorers, the {scorers with no honest method} that "
        "are not,",
    ),
    "build.py": (
        "fewer than {tuning rows below which the guide caps a comparison} rows. "
        "{rows hand-written ships} total leaves",
        'the {mostly states} "mostly" states touch',
        "{presets built for no condition} presets are built for no condition",
        "{presets whose own card cannot show their condition} are built for a condition",
    ),
    "docs/dataset.md": (
        "{states that write a declaration} states write on that field",
        "{databases in the slice} of {databases in Spider's development split} "
        "databases, {rows dropped for an empty gold} of {rows in the source pool} rows "
        "dropped",
        "**{held-out rows that shared a gold before the re-cut} of the "
        "{held-out rows before the re-cut} holdout rows (25%)** had a gold "
        "byte-identical to a tuning row's -- "
        "{very-hard held-out rows that shared a gold before the re-cut} of the "
        "{very-hard held-out rows before the re-cut} very-hard rows",
        "**{gold queries that return one value} of the {rows in the slice} gold queries",
        "scores **{rows the best constant answer matches} of {rows in the slice}, 2.3%**",
        "on {single-value answers in ten} rows in "
        "{the base of a ratio written 'N in ten'} that is all",
        "**{databases with two or fewer held-out rows} of the {databases in the slice} "
        "databases hold two or fewer holdout rows, and "
        "{databases with no held-out rows} hold none at all**",
    ),
    "docs/eval-methods.md": (
        "{scoring methods} of the choices are the real scoring methods",
        "The other {scorers the broken-scorer presets ship} -- `broken`, `swapped`, "
        "`opaque` and `length-blind` --",
        "So the {presets the eval-methods comparison sets side by side} presets ask "
        "different questions",
        "**{evaluation-pillar points the declaration was worth on 2026-09-02} points of "
        "evaluation pillar**",
        "this project can reach, not "
        "{evaluation-pillar points the declaration was worth on 2026-09-02}.",
        "The {scoring methods} scorers get different probes",
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
        "{presets the sweep names} presets, then the comparisons the documentation "
        "makes. {presets the sweep names only through a variant} preset the sweep names "
        "only through a variant",
        "so this table has {preset runs} preset runs -- one for each of `build.py`'s "
        "{presets} presets -- and {comparisons} comparisons: "
        "{variant comparisons} variants and the {grid runs} `grid-*` runs:",
        "| the {presets the sweep names} presets |",
        "## What the {presets ported on 2026-09-18} ported presets measured",
        "where {the sides of a comparison} starting states produce the same card",
        "{ported presets that opened on the cap they were built for} of the "
        "{presets ported on 2026-09-18} opened on the cap they were built for. "
        "{ported presets that did not} did not, and {ported presets built for no cap} "
        "was built for a question",
        "({input forms on both sides of ready's split} of "
        "{recurring input forms in ready} on `ready`)",
        "**The {scorers with no honest method} scorers that are not scorers",
        "{cards identical to another} of the {cards} cards fall into the "
        "{groups of identical cards} groups below",
        "**byte-identical**. {scorers with no honest method} scorers that cannot be "
        "given a method honestly",
        "E = 59, {evaluation checks measured for the execution scorer} of "
        "{evaluation checks} checks measured",
    ),
    "docs/measurements/score_bank.py": (
        "At HEAD {refused runs} run cannot score",
        "ends 1 with that {refused runs} run refused",
        "except by {variants that declare the field names} variant",
        "is true on {runs held back by the unread answer key} cards -- `checked`, "
        "`wrong-answers--calibrated` and the {grid runs} `grid-*` runs",
    ),
    "first-run-runners/README.md": (
        "cut a {trials the connected run asks for}-trial search at seven",
        "on the guide's default {rows the guide holds out by default}.",
    ),
}


# ---------------------------------------------------------------------------------------
# The check.

PLACEHOLDER = re.compile(r"\{([^{}]+)\}")


def compile_claim(template: str) -> tuple[re.Pattern[str], list[str]]:
    """A template as a pattern, and the quantity each of its groups names."""
    pattern = ""
    names: list[str] = []
    for index, piece in enumerate(PLACEHOLDER.split(template)):
        if index % 2:
            names.append(piece)
            pattern += rf"(?P<q{len(names) - 1}>{ANY_NUMBER})"
        else:
            pattern += r"\s+".join(re.escape(word) for word in re.split(r"\s+", piece))
    return re.compile(pattern, re.I), names


def line_of(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


def problems_in(
    name: str, text: str, claims: tuple[str, ...], quantities: dict[str, Quantity]
) -> tuple[list[str], int]:
    """What is wrong with one document's counts, and how many counts were checked."""
    shown = readable(name, text)
    found: list[str] = []
    covered: set[int] = set()
    checked = 0
    for template in claims:
        pattern, names = compile_claim(template)
        matches = list(pattern.finditer(shown))
        if not matches:
            found.append(
                f"{name}: a registered claim no longer appears in the document, so the "
                f"count it bound is no longer checked: {template!r}"
            )
            continue
        for match in matches:
            for index, quantity_name in enumerate(names):
                written = match.group(f"q{index}")
                start = match.start(f"q{index}")
                covered.add(start)
                where = f"{name}:{line_of(shown, start)}"
                quantity = quantities.get(quantity_name)
                value = read_number(written)
                if quantity is None:
                    found.append(f"{where}: no quantity is called {quantity_name!r}")
                elif value is None:
                    found.append(
                        f"{where}: {written!r} is not a number this gate reads"
                    )
                else:
                    checked += 1
                    if value != quantity.value:
                        found.append(
                            f"{where} says {written!r} for {quantity_name!r}, and there "
                            f"are {quantity.value} ({quantity.source})"
                        )
    scanned = without_code(shown)
    for detector in DETECTORS:
        for match in detector.finditer(scanned):
            for group in ("n", "m"):
                if group not in detector.groupindex or match.group(group) is None:
                    continue
                start = match.start(group)
                if start in covered:
                    continue
                covered.add(start)
                context = " ".join(
                    scanned[max(0, start - 60) : match.end() + 40].split()
                )
                found.append(
                    f"{name}:{line_of(scanned, start)}: {match.group(group)!r} is a count "
                    f"no claim derives ({context!r}); register the sentence in "
                    "tests/test_prose_counts.py CLAIMS with the quantity it counts"
                )
    return found, checked


class EveryProseCountIsBound(unittest.TestCase):
    """The whole corpus, against the registry and the quantities."""

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
        self.assertGreaterEqual(
            checked,
            registered,
            "a registered count was not read, so it was not checked",
        )

    def test_every_claim_names_a_document_this_gate_reads(self) -> None:
        self.assertEqual([], sorted(set(CLAIMS) - set(corpus())))

    def test_every_quantity_is_one_some_claim_uses(self) -> None:
        """A quantity nothing names is a derivation nobody reads -- usually a lost claim."""
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
        self.assertEqual(
            set(build.PRESETS),
            set(arrived),
            "PRESET_ROUNDS is the record the history sentences are derived from; a "
            "preset missing from it has no round, and one missing from build.PRESETS "
            "is a round that did not happen",
        )

    def test_the_wrong_on_purpose_table_names_real_presets(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        named = table_presets(readme, "## Data that is wrong on purpose")
        self.assertTrue(named)
        self.assertEqual([], sorted(set(named) - set(build.PRESETS)))
        self.assertIn("split-by-database", named, "the control the sentence names")

    def test_the_runs_are_the_sweeps_and_the_cards_are_the_runs(self) -> None:
        """Three places count the runs, and they are held to each other here."""
        sweep = load_harness()
        runs = json.loads((CARDS / "results.json").read_text(encoding="utf-8"))["runs"]
        self.assertEqual(
            len(runs), len(sweep.PRESETS) + len(sweep.VARIANTS) + len(sweep.GRID)
        )
        self.assertEqual(len(runs), self.quantities["cards"].value)
        self.assertEqual(
            len(runs),
            self.quantities["preset runs"].value + self.quantities["comparisons"].value,
        )


class TheGuideAgrees(unittest.TestCase):
    """The guide's constants the prose quotes, read back out of the guide.

    Only where a checkout is named: the suite does not depend on another repository being
    present. The measurement job in CI has the guide at the pin anyway, and sets
    `TRAIGENT_FIRST_RUN_GUIDE` so the quotes are checked there.
    """

    def test_every_quoted_guide_constant_is_the_guides(self) -> None:
        checkout = os.environ.get("TRAIGENT_FIRST_RUN_GUIDE")
        if not checkout:
            self.skipTest(
                f"TRAIGENT_FIRST_RUN_GUIDE names no guide checkout, so the "
                f"{len(GUIDE_CONSTANTS)} guide constants the prose quotes went unchecked"
            )
        scripts = Path(checkout) / "skills" / "traigent-first-run" / "scripts"
        loaded: dict[str, types.ModuleType] = {}
        for quantity, constant in GUIDE_CONSTANTS.items():
            with self.subTest(quantity=quantity):
                if constant.script not in loaded:
                    loaded[constant.script] = load_module(
                        scripts / constant.script, f"_guide_{constant.script[:-3]}"
                    )
                value = getattr(loaded[constant.script], constant.name)
                read = len(value) if isinstance(value, (list, tuple)) else value
                self.assertEqual(constant.value, read, quantity)


# ---------------------------------------------------------------------------------------
# The gate, against the edits it exists to catch. Each is applied to the real document in
# memory, and each has to fail for the right reason: the quantity named, and its true value.


def mutated(name: str, old: str, new: str) -> str:
    text = (REPO_ROOT / name).read_text(encoding="utf-8")
    assert old in text, f"{old!r} is not in {name}"
    return text.replace(old, new, 1)


class TheGateCatchesWhatTheLastOneMissed(unittest.TestCase):
    quantities: dict[str, Quantity]

    @classmethod
    def setUpClass(cls) -> None:
        cls.quantities = measure()

    def assert_caught(self, name: str, old: str, new: str, expected: str) -> None:
        found, _ = problems_in(
            name, mutated(name, old, new), CLAIMS[name], self.quantities
        )
        self.assertTrue(found, f"{new!r} in {name} passed")
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

    def test_a_capitalised_total_in_the_measurements_readme(self) -> None:
        self.assert_caught(
            "docs/measurements/README.md",
            "Thirty-one presets",
            "Thirty presets",
            "'Thirty' for 'presets the sweep names', and there are 31",
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
            "## Data that is wrong on purpose\n",
            "## Data that is wrong on purpose\n\nForty-two presets are here.\n",
            "'Forty-two' is a count no claim derives",
        )

    def test_a_rewritten_sentence_retires_its_claim_loudly(self) -> None:
        self.assert_caught(
            "docs/dataset.md",
            "Six states write",
            "Several states write",
            "a registered claim no longer appears in the document",
        )


class TheDetectorsReadCountsAndNotIdioms(unittest.TestCase):
    """A false red is how a gate gets deleted, so the idioms are held down too."""

    def flagged(self, text: str) -> list[str]:
        return [
            match.group(group)
            for detector in DETECTORS
            for match in detector.finditer(without_code(text))
            for group in ("n", "m")
            if group in detector.groupindex and match.group(group)
        ]

    def test_counts_are_flagged(self) -> None:
        for text, number in (
            ("the four `grid-*` runs", "four"),
            ("six of its runs", "six"),
            ("a thirty-two-preset bank", "thirty-two"),
            ("Sixteen ship a project", "Sixteen"),
            ("the seventeenth, a control", "seventeenth"),
            ("25 of the 73 rows", "73"),
            ("**Seventeen** of the thirty-two presets", "Seventeen"),
            ("Five states write on that field", "Five"),
            ("Two of the choices are real scorers", "Two"),
        ):
            with self.subTest(text=text):
                self.assertIn(number, self.flagged(text))

    def test_idioms_are_not(self) -> None:
        for text in (
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
                self.assertEqual([], self.flagged(text))


if __name__ == "__main__":
    unittest.main()
