# SPDX-License-Identifier: Apache-2.0
"""The measurement harness does not publish over the evidence it was run to check.

`docs/measurements/score_bank.py` twice destroyed committed evidence on its way to
reporting that it could not measure anything: once by crashing at the first refusal, once
by promoting 26 empty rows over every card because a fault in *this repository's own*
`build.py` was recorded as the guide refusing something. Both are repaired. Neither repair
was defended by anything until this file existed -- the harness sits outside CI's
`black`/`ruff`/`mypy` targets and outside the suite, so all three fixes could be reverted
with every check still green, which is worse than the original defect: the next reader
would reasonably believe the guard was held.

So the two properties the repairs exist for are asserted here, against a scratch tree, by
running `main()`:

* a fault of ours ends the run on its own exit status and publishes **nothing**, even when
  publishing was explicitly asked for;
* a refusal by the guide is one row, the sweep continues, and the committed card of a run
  that produced none is left exactly as it was.

The guide is stood in for by a stub that publishes the three field constants the contract
check reads -- these tests are about the harness's own decisions, not about the guide, and
a real checkout would make the suite depend on somebody else's repository being present.
"""

from __future__ import annotations

import contextlib
import hashlib
import importlib.util
import io
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import types
import unittest
from pathlib import Path
from unittest import mock

REPO_ROOT = Path(__file__).resolve().parents[1]
HARNESS = REPO_ROOT / "docs" / "measurements" / "score_bank.py"
KNOBS = REPO_ROOT / "docs" / "measurements" / "agent-knobs"

# What the guide reads out of an --agent-knobs document, as three constants. The stub
# below publishes exactly these, so the contract check passes and the tests reach the
# decisions they are about. Kept beside the documents they describe: if the real documents
# grow a field, this fixture is where the test says so.
STUB_GUIDE = """
AGENT_KNOBS_DOCUMENT_FIELDS = frozenset({"knobs", "source", "build"})
DISCOVERED_KNOB_FIELDS = frozenset(
    {"values", "low", "high", "evidence", "source_lines"}
)
BUILD_CHECK_FIELDS = {
    "prompt": frozenset(
        {"present", "few_shot", "evidence", "determined", "reason", "source_lines"}
    ),
    "output-contract": frozenset(
        {"present", "evidence", "determined", "reason", "source_lines"}
    ),
    "control-flow": frozenset(
        {"loop", "bounded", "evidence", "determined", "reason", "source_lines"}
    ),
    "tools": frozenset(
        {
            "used",
            "declared",
            "unreachable",
            "evidence",
            "determined",
            "reason",
            "source_lines",
        }
    ),
}
CAP_CEILING = {"dataset-absent": 20, "evaluator-unvalidated": 45}
ACTION_FOR_CONDITION = {
    "dataset-absent": "get-data",
    "evaluator-unvalidated": "complete-calibration",
}
"""

# What the harness records of the stub above, which is the shape the real record carries.
STUB_CONDITIONS = {
    "dataset-absent": {"action": "get-data", "ceiling": 20},
    "evaluator-unvalidated": {"action": "complete-calibration", "ceiling": 45},
}


def load_harness() -> types.ModuleType:
    """The harness as a module, by path: `docs/measurements/` is not a package."""
    located = importlib.util.spec_from_file_location("_score_bank", HARNESS)
    assert located is not None and located.loader is not None
    module = importlib.util.module_from_spec(located)
    sys.modules[located.name] = module
    located.loader.exec_module(module)
    return module


def build_module() -> types.ModuleType:
    """`build.py` as a module, by path, registered before it runs.

    A dataclass looks its module up by name while the class is being made, which is why
    the registration comes first, as in `load_harness`.
    """
    located = importlib.util.spec_from_file_location("_build", REPO_ROOT / "build.py")
    assert located is not None and located.loader is not None
    builder = importlib.util.module_from_spec(located)
    sys.modules[located.name] = builder
    located.loader.exec_module(builder)
    return builder


def fingerprint(tree: Path) -> dict[str, str]:
    """Every file under a directory, by relative path and content digest."""
    return {
        str(found.relative_to(tree)): hashlib.sha256(found.read_bytes()).hexdigest()
        for found in sorted(tree.rglob("*"))
        if found.is_file()
    }


class TheSweepNamesEveryPreset(unittest.TestCase):
    """A preset the builder has and the sweep does not name is a card that never exists.

    The nine ported presets were added to both by hand; this pins the two lists to each
    other so the next preset cannot land in one without the other.
    """

    def test_the_sweep_and_the_builder_agree_on_the_presets(self) -> None:
        harness = load_harness()
        builder = build_module()
        # A preset may be named by the sweep's plain list or by a variant, which is
        # how one carries an option -- `slow-scorer` states the calibration budget it
        # is measured under rather than making every reproduction wait fifteen minutes
        # for the default. Either counts as named; neither is a way to go unmeasured.
        by_variant = {
            flags[index + 1]
            for _, flags, _ in harness.VARIANTS
            for index, flag in enumerate(flags)
            if flag == "--preset" and index + 1 < len(flags)
        }
        self.assertEqual(set(harness.PRESETS) | by_variant, set(builder.PRESETS))


# The cards whose readiness card is byte-identical to another's, written down so
# the set is a claim the suite checks rather than a paragraph somebody remembers
# to edit. Each one is a finding -- "the guide notices nothing here" -- and the
# documents say so in prose; this is the same statement in a form that goes red.
IDENTICAL_CARDS = (
    ("best-case", "sql-exec-stop"),
    ("checked", "grid-normalized-exact--code-sql"),
    ("fake-ruler", "wrong-wiring--calibrated"),
    (
        "fake-ruler--uncalibrated",
        "raw-export--fields-declared",
        "ready",
        "two-agents",
        "wrong-wiring",
    ),
    ("length-blind--uncalibrated", "opaque-scorer"),
    ("no-agent", "ready--without-agent-knobs"),
    ("no-knobs", "no-knobs--knobs-in-a-comment"),
)


class TheCommittedCardsAreWhatTheDocumentsSay(unittest.TestCase):
    """The two claims about `cards/` that prose was carrying alone.

    Both were stale at once: a preset could land with no card directory and no
    README row with the whole suite green, and the section that catalogues
    identical cards listed two pairs where there were six -- including a pair
    this repository's own nine-preset round created.
    """

    def card_bodies(self) -> dict[str, str]:
        """Each rendered card from its second line down, the way the documents compare them.

        The first line is the invocation, which names the read of the agent a run was
        scored with. Kept in, it hid two cards the guide rendered identically -- `no-knobs`
        and `no-knobs--knobs-in-a-comment`, scored with different reads of different
        agents -- because the two invocations differ by a file name.
        """
        cards = REPO_ROOT / "docs" / "measurements" / "cards"
        return {
            directory.name: (directory / "04-readiness-card.txt")
            .read_text(encoding="utf-8")
            .split("\n", 1)[1]
            for directory in sorted(cards.iterdir())
            if directory.is_dir() and (directory / "04-readiness-card.txt").is_file()
        }

    def test_every_preset_the_sweep_names_has_a_committed_card(self) -> None:
        harness = load_harness()
        published = {
            directory.name
            for directory in (REPO_ROOT / "docs" / "measurements" / "cards").iterdir()
            if directory.is_dir()
        }
        missing = sorted(set(harness.PRESETS) - published)
        self.assertEqual([], missing, "presets the sweep names with no card")

    def test_the_identical_cards_are_the_ones_written_down(self) -> None:
        bodies = self.card_bodies()
        by_body: dict[str, list[str]] = {}
        for name, body in bodies.items():
            by_body.setdefault(body, []).append(name)
        found = sorted(
            tuple(sorted(names)) for names in by_body.values() if len(names) > 1
        )
        self.assertEqual(
            sorted(tuple(sorted(group)) for group in IDENTICAL_CARDS),
            found,
            "the cards that are identical to another are not the ones recorded",
        )


# The presets whose own committed card cannot carry the condition `build.PRESET_CAPS` says
# they were built for, each with the run that does show it (or None) and the reason. Written
# down so each exception is a claim the suite checks in both directions: the preset's card
# must still NOT carry the condition -- the day it does, the reason here and the prose that
# repeats it are out of date -- and a run named as showing it must carry it.
NOT_ON_THEIR_OWN_CARD: dict[str, tuple[str | None, str]] = {
    "wrong-answers": (
        None,
        "the condition fires on the `no` verdicts of a row review, and the sweep passes "
        "no row review: writing one would be the sweep answering the question this "
        "preset asks (see score_bank.py)",
    ),
    "wrong-wiring": (
        "wrong-wiring--calibrated",
        "only probe answers expose a scorer that never reads the output, and the preset "
        "ships none; the calibrated variant does",
    ),
    "split-by-database": (
        None,
        "a finding about the guide: its family check reads the leading words of each "
        "question, which span every database, so a split along databases is not one it "
        "sees (docs/measurements/README.md)",
    ),
}


# What each preset built for no condition is expected to carry, exactly. "Built for nothing"
# does not mean "an empty card": `two-agents` is `ready` with a second agent beside it, and
# carries `ready`'s unvalidated-scorer ceiling. Held with equality, so a guide revision that
# adds a condition to either -- or starts noticing the second agent -- fails by name.
BUILT_FOR_NOTHING_CARRIES: dict[str, frozenset[str]] = {
    "checked": frozenset(),
    "two-agents": frozenset({"evaluator-unvalidated"}),
}


def card_conditions(tag: str) -> set[str]:
    """The conditions a committed card carries, read from the card the guide printed."""
    reading = json.loads(
        (
            REPO_ROOT / "docs" / "measurements" / "cards" / tag / "05-readiness.json"
        ).read_text(encoding="utf-8")
    )
    return {cap["condition"] for cap in reading["caps"]}


class EveryPresetOpensOnTheStateItWasBuiltFor(unittest.TestCase):
    """The committed card of each preset, against what the preset was built to be.

    Re-measuring at a later guide revision republishes every card, and a preset that
    stopped reading as its state -- `mostly-synthetic-source` no longer raising
    `dataset-mostly-synthetic` because the guide moved its rung, say -- would arrive as
    one changed score among forty-nine. Here it is a named failure instead.
    """

    def test_every_preset_carries_the_conditions_it_was_built_for(self) -> None:
        revision = json.loads(
            (REPO_ROOT / "docs" / "measurements" / "cards" / "results.json").read_text(
                encoding="utf-8"
            )
        )["guide_revision"][:8]
        checked = 0
        for preset, conditions in sorted(build_module().PRESET_CAPS.items()):
            if not conditions or preset in NOT_ON_THEIR_OWN_CARD:
                continue
            with self.subTest(preset=preset):
                carried = card_conditions(preset)
                self.assertLessEqual(
                    set(conditions),
                    carried,
                    f"{preset} was built for {sorted(conditions)}; its card at "
                    f"{revision} carries {sorted(carried)}",
                )
                checked += 1
        self.assertGreater(checked, 0, "no card was read, so none was checked")

    def test_a_preset_built_for_nothing_carries_exactly_what_is_declared(self) -> None:
        caps = build_module().PRESET_CAPS
        self.assertEqual(
            {name for name, conditions in caps.items() if not conditions},
            set(BUILT_FOR_NOTHING_CARRIES),
            "every preset built for no condition declares what its card carries",
        )
        for preset, expected in sorted(BUILT_FOR_NOTHING_CARRIES.items()):
            with self.subTest(preset=preset):
                self.assertEqual(set(expected), card_conditions(preset))

    def test_every_exception_still_holds_and_says_where_it_shows(self) -> None:
        caps = build_module().PRESET_CAPS
        for preset, (shown_on, reason) in sorted(NOT_ON_THEIR_OWN_CARD.items()):
            with self.subTest(preset=preset):
                self.assertTrue(caps[preset], f"{preset} is built for no condition")
                self.assertTrue(reason.strip())
                self.assertFalse(
                    set(caps[preset]) & card_conditions(preset),
                    f"{preset}'s own card now carries {caps[preset]}, so the reason it "
                    f"was excused -- {reason!r} -- and the prose repeating it are stale",
                )
                if shown_on is not None:
                    self.assertLessEqual(set(caps[preset]), card_conditions(shown_on))


def committed_card(tag: str) -> dict[str, object]:
    """The readiness JSON a committed card holds."""
    return dict(
        json.loads(
            (
                REPO_ROOT
                / "docs"
                / "measurements"
                / "cards"
                / tag
                / "05-readiness.json"
            ).read_text(encoding="utf-8")
        )
    )


def card_caps(tag: str) -> dict[str, dict[str, object]]:
    """The caps a committed card carries, by condition."""
    caps = committed_card(tag)["caps"]
    assert isinstance(caps, list)
    return {cap["condition"]: cap for cap in caps}


# How `run_inputs` names the read of the agent a run is scored with when it is the one
# `AGENT_READS` keeps for the agent's state: each of those documents is written as the
# faithful read of its agent, so it follows from the agent and is not a second input. A run
# that names a read of its own has changed something the agent did not.
FAITHFUL_READ = "the faithful read of the agent"


def run_inputs(tag: str) -> dict[str, object]:
    """What one run is built and scored from: the components, the read, the options.

    Read from the sweep's own list and the builder's presets, so two runs can be compared
    on what actually differs between them rather than on what their names suggest. The
    read of the agent the guide is handed is one of them: the card is scored from it, so
    two runs that differ only in the read differ in what the card is scored from.
    """
    builder, harness = build_module(), load_harness()
    flags, options = next((f, o) for t, f, o in harness.sweep() if t == tag)
    chosen = dict(builder.PRESETS[flags[flags.index("--preset") + 1]])
    for name in ("agent", "dataset", "eval", "calibration"):
        if f"--{name}" in flags:
            chosen[name] = flags[flags.index(f"--{name}") + 1]
    chosen.setdefault("calibration", "none")
    options = dict(options)
    chosen["read"] = options.pop("agent_read", FAITHFUL_READ)
    return {**chosen, "options": tuple(sorted(options.items()))}


# The repairs the committed cards show, each as (the run before it, the run after it, the
# condition it removes, the action the card before it names for it). Each pair differs in
# the one thing the action is about -- the dataset, the agent, the scorer, or what a run
# declares about the file -- so the pair is the repair and nothing else.
REPAIRS: tuple[tuple[str, str, str, str], ...] = (
    ("no-data", "ready", "dataset-absent", "get-data"),
    ("no-labels", "ready", "dataset-no-expected-outputs", "label-data"),
    ("no-eval", "ready", "evaluator-absent", "connect-evaluator"),
    ("no-knobs", "ready", "agent-no-varying-knobs", "vary-knobs"),
    ("wrong-wiring--calibrated", "checked", "evaluator-invalid", "repair-evaluator"),
    ("fake-ruler", "checked", "evaluator-invalid", "repair-evaluator"),
    ("leaky-split", "ready", "dataset-tune-holdout-overlap", "resplit-dataset"),
    ("hand-written", "checked", "dataset-below-measurable-size", "add-examples"),
    (
        "raw-export",
        "raw-export--fields-declared",
        "dataset-shape-unrecognised",
        "read-dataset",
    ),
)

# Repairs that are not repairs, each keyed by its run and the run it is measured against.
# Most start where a repair in REPAIRS starts and change the one thing that repair is about,
# so that it looks done -- and leave it undone. One starts from another fake: the project
# is left exactly as that fake left it, and only the read of the agent the guide is handed
# changes. The guide HOLDS a fake when its card still carries the condition of the repair
# it imitates, with the ceiling and the block the card it is measured against carried.
FAKE_REPAIRS: dict[str, str] = {
    "no-data--empty-file": "no-data",
    "no-labels--blank-answers": "no-labels",
    "no-knobs--knobs-in-a-comment": "no-knobs",
    "no-knobs--knobs-in-a-comment--credited": "no-knobs--knobs-in-a-comment",
    "hand-written--padded": "hand-written",
}

# The fakes the guide does not hold, each with what its card shows. Checked in both
# directions: a fake listed here must still get through -- the day the guide holds it, the
# entry and the prose repeating it are stale -- and a fake not listed must be held.
UNGUARDED: dict[str, str] = {
    "no-knobs--knobs-in-a-comment--credited": (
        "a read that credits settings the agent names only in a comment, citing "
        "executable lines beside them, is not believed -- the agent pillar reads 0 and "
        "agent-no-varying-knobs stays at 45 -- but the guide treats a claim it cannot "
        "verify at the opening as advisory rather than as a finding that the agent has no "
        "setting ('this advisory opening ceiling remains while the cited source evidence "
        "is unverified'): the card stops blocking and its action is complete-calibration "
        "instead of vary-knobs, and it names a request-difference probe as the separate "
        "pre-call guard, which this bank does not run. The same agent read faithfully "
        "(no-knobs--knobs-in-a-comment) still blocks"
    ),
}


def repaired_by(fake: str) -> tuple[str, str, str, str]:
    """The entry of REPAIRS a fake imitates, following a fake that starts from a fake."""
    before = FAKE_REPAIRS[fake]
    while before in FAKE_REPAIRS:
        before = FAKE_REPAIRS[before]
    return next(entry for entry in REPAIRS if entry[0] == before)


class ARepairRemovesItsConditionAndAFakeOneDoesNot(unittest.TestCase):
    """What the cards say a repair does, and what they say a repair in name only does."""

    def test_every_repair_is_one_change_that_removes_its_condition(self) -> None:
        for before, after, condition, action in REPAIRS:
            with self.subTest(repair=f"{before} -> {after}"):
                changed = {
                    name
                    for name, value in run_inputs(before).items()
                    if run_inputs(after)[name] != value
                }
                self.assertEqual(1, len(changed), f"the pair differs in {changed}")
                had, has = card_caps(before), card_caps(after)
                self.assertIn(condition, had)
                self.assertEqual(action, had[condition]["action_kind"])
                self.assertEqual(action, committed_card(before)["recommended_action"])
                self.assertNotIn(condition, has)
                blocking = {name for name, cap in has.items() if cap["blocks"]}
                self.assertLessEqual(
                    blocking,
                    {name for name, cap in had.items() if cap["blocks"]},
                    "the repair left a blocking cap the project did not have",
                )

    def test_every_fake_changes_one_thing_and_it_is_what_its_repair_changes(
        self,
    ) -> None:
        for fake, before in FAKE_REPAIRS.items():
            with self.subTest(fake=fake):
                touched = {
                    name
                    for name, value in run_inputs(before).items()
                    if run_inputs(fake)[name] != value
                }
                self.assertEqual(1, len(touched), f"the fake changes {touched}")
                changed = next(iter(touched))
                repairs = [entry for entry in REPAIRS if entry[0] == before]
                if not repairs:
                    # A fake built on another fake changes what the guide is told about
                    # the project, not the project: the read, and nothing else.
                    self.assertIn(before, FAKE_REPAIRS, f"{before} starts no repair")
                    self.assertEqual("read", changed)
                for _, after, _, _ in repairs:
                    self.assertNotEqual(
                        run_inputs(before)[changed],
                        run_inputs(after)[changed],
                        "the fake touches something its repair does not",
                    )

    def test_the_guide_holds_every_fake_but_the_ones_written_down(self) -> None:
        self.assertLessEqual(set(UNGUARDED), set(FAKE_REPAIRS))
        for fake, before in FAKE_REPAIRS.items():
            condition = repaired_by(fake)[2]
            had, has = card_caps(before)[condition], card_caps(fake).get(condition)
            held = has is not None and (has["ceiling"], has["blocks"]) == (
                had["ceiling"],
                had["blocks"],
            )
            with self.subTest(fake=fake):
                if fake in UNGUARDED:
                    self.assertTrue(UNGUARDED[fake].strip())
                    self.assertFalse(
                        held,
                        f"the guide now holds {fake}, so the reason it was recorded as "
                        f"getting through -- {UNGUARDED[fake]!r} -- is stale",
                    )
                else:
                    self.assertTrue(
                        held,
                        f"{fake} got past the guide: {condition} is "
                        f"{'gone' if has is None else 'no longer the same cap'}; record "
                        "it in UNGUARDED with what the card shows",
                    )


# Every condition the pinned guide can raise and no committed card carries, with the reason.
# Checked both ways against `conditions` in results.json, which the sweep reads from the
# guide itself: a condition that reaches a card must come off this list, and a new one the
# guide adds is a failure until a run reaches it or it is written down here.
UNREACHED: dict[str, str] = {
    "dataset-unsound-expected-outputs": (
        "raised from the no verdicts of a row review, and the sweep passes none: writing "
        "one would be the sweep answering the question wrong-answers asks (score_bank.py)"
    ),
}


class EveryConditionTheGuideCanRaiseIsOnACard(unittest.TestCase):
    """The cap vocabulary at the pin, against the cards -- read from the guide, not listed."""

    def test_the_record_holds_the_guides_vocabulary(self) -> None:
        conditions = committed_results()["conditions"]
        self.assertIsInstance(conditions, dict, "results.json records no vocabulary")
        assert isinstance(conditions, dict)
        self.assertGreater(len(conditions), 0)
        for condition, entry in conditions.items():
            with self.subTest(condition=condition):
                self.assertTrue(entry["action"], "a condition with no remedy")

    def test_every_condition_is_on_a_card_or_written_down(self) -> None:
        conditions = committed_results()["conditions"]
        assert isinstance(conditions, dict)
        carried = {
            cap["condition"]
            for run in scored_runs()
            for cap in run["caps"]  # type: ignore[union-attr]
        }
        self.assertEqual(
            set(), carried - set(conditions), "a card the guide cannot write"
        )
        self.assertEqual(
            sorted(set(conditions) - carried),
            sorted(UNREACHED),
            "the conditions no card reaches are not the ones written down",
        )
        for condition, reason in UNREACHED.items():
            self.assertTrue(reason.strip(), condition)


def committed_results() -> dict[str, object]:
    """The committed `results.json`."""
    return dict(
        json.loads(
            (REPO_ROOT / "docs" / "measurements" / "cards" / "results.json").read_text(
                encoding="utf-8"
            )
        )
    )


def scored_runs() -> list[dict[str, object]]:
    """The rows of `results.json` that scored; a refused run's card is an older reading."""
    runs = committed_results()["runs"]
    assert isinstance(runs, list)
    return [run for run in runs if not run.get("refused")]


SCORE_ROW = re.compile(
    r"^\| `(?P<run>[a-z-]+)` \| (?P<score>\d+|refused) \| (?P<band>[A-Z ]+|--) \| "
    r"(?:`(?P<action>[a-z-]+)`|--) \|",
    re.MULTILINE,
)


def score_rows(document: Path, heading: str) -> list[tuple[str, str, str, str | None]]:
    """The (run, score, band, action) rows of the score tables in one section."""
    text = document.read_text(encoding="utf-8")
    section = text.split(heading, 1)[1]
    section = re.split(r"\n#{1,6} ", section, maxsplit=1)[0]
    return [
        (row["run"], row["score"], row["band"], row["action"])
        for row in SCORE_ROW.finditer(section)
    ]


class TheScoreTablesAreTheCards(unittest.TestCase):
    """Every score a table prints is read back off `results.json`, and every row is there.

    The README's tables were written by hand from the cards and checked by nothing: the
    round that added `synthetic-source` measured it, committed its cards, and left it out
    of the README while the text beside the tables still said thirty-two.
    """

    def results(self) -> dict[str, dict[str, object]]:
        record = json.loads(
            (REPO_ROOT / "docs" / "measurements" / "cards" / "results.json").read_text(
                encoding="utf-8"
            )
        )
        return {run["tag"]: run for run in record["runs"]}

    def assert_rows_match(self, rows: list[tuple[str, str, str, str | None]]) -> None:
        results = self.results()
        for run, score, band, action in rows:
            with self.subTest(run=run):
                measured = results[run]
                if measured.get("refused"):
                    self.assertEqual(("refused", "--", None), (score, band, action))
                else:
                    self.assertEqual(
                        (
                            measured["overall"],
                            measured["band"],
                            measured["recommended_action"],
                        ),
                        (int(score), band, action),
                    )

    def test_the_readme_tables_hold_every_preset_once_as_measured(self) -> None:
        rows = score_rows(
            REPO_ROOT / "README.md",
            "## Where each preset starts, and what the run has to do about it",
        )
        names = [run for run, _, _, _ in rows]
        self.assertEqual(len(names), len(set(names)), "a preset is listed twice")
        self.assertEqual(set(build_module().PRESETS), set(names))
        self.assert_rows_match(rows)

    def test_the_measurements_table_holds_every_run_once_as_measured(self) -> None:
        rows = score_rows(
            REPO_ROOT / "docs" / "measurements" / "README.md", "## Results"
        )
        names = [run for run, _, _, _ in rows]
        self.assertEqual(len(names), len(set(names)), "a run is listed twice")
        self.assertEqual(set(self.results()), set(names))
        self.assert_rows_match(rows)


class EveryCardRecordsTheBuildThatRan(unittest.TestCase):
    """`argv.json` is the command a reader re-runs, so it has to be the one that ran.

    It was rebuilt by hand beside the command that ran and left out the `demo`
    subcommand: every card recorded a build that exits 2, while `01-build.txt` beside it
    had the right one. The refused run is the one card the sweep deliberately leaves as
    it was -- an older reading it could not reproduce -- and is named, not skipped.
    """

    def test_every_recorded_build_is_the_transcripts_and_parses(self) -> None:
        cards = REPO_ROOT / "docs" / "measurements" / "cards"
        runs = json.loads((cards / "results.json").read_text(encoding="utf-8"))["runs"]
        parser = build_module().build_parser()
        checked = 0
        for run in runs:
            if run.get("refused"):
                continue
            with self.subTest(run=run["tag"]):
                recorded = json.loads(
                    (cards / run["tag"] / "argv.json").read_text(encoding="utf-8")
                )["build"]
                transcript = (cards / run["tag"] / "01-build.txt").read_text(
                    encoding="utf-8"
                )
                self.assertEqual("$ " + " ".join(recorded), transcript.splitlines()[0])
                self.assertEqual(["python3", "build.py"], recorded[:2])
                parsed = parser.parse_args(recorded[2:])
                self.assertEqual("demo", parsed.command)
                checked += 1
        self.assertEqual(checked, len([run for run in runs if not run.get("refused")]))
        self.assertGreater(checked, 0)


class EveryRunDeclaresTheOriginItsStateStandsFor(unittest.TestCase):
    """The origin a card was scored under is read from the build record, never assumed.

    The sweep declared `brought` for every agent and every evaluator it measured, which
    is the right answer for every state but the ones a customer disclaims -- and a
    disclaimed component scored as `brought` is a card missing the one cap it exists for.
    """

    def test_every_committed_card_declared_the_builders_origin(self) -> None:
        builder = build_module()
        harness = load_harness()
        runs: dict[str, tuple[tuple[str, ...], dict[str, object]]] = {
            preset: (("--preset", preset), {}) for preset in harness.PRESETS
        }
        runs.update(
            {tag: (arguments, options) for tag, arguments, options in harness.VARIANTS}
        )
        runs.update({tag: (("--preset", "checked"), {}) for tag, _, _ in harness.GRID})
        # The refused run's card is the older reading the sweep leaves in place; it
        # predates the origin flags and no measurement at the pin replaces it.
        runs.pop("best-case--off-method-calibration")
        cards = REPO_ROOT / "docs" / "measurements" / "cards"
        checked = 0
        for tag, (arguments, options) in sorted(runs.items()):
            readiness = json.loads(
                (cards / tag / "argv.json").read_text(encoding="utf-8")
            )["readiness"]
            preset = builder.PRESETS[arguments[arguments.index("--preset") + 1]]

            def chosen(flag: str, default: str) -> str:
                return (
                    arguments[arguments.index(flag) + 1]
                    if flag in arguments
                    else default
                )

            agent = chosen("--agent", preset["agent"])
            evaluator = chosen("--eval", preset["eval"])
            expected = {
                # The agent's origin is declared only when the run passes an agent read.
                "--agent-origin": (
                    builder.AGENT_ORIGINS[agent]
                    if options.get("agent_knobs", True)
                    else None
                ),
                "--evaluator-origin": builder.EVALUATOR_FACTS.get(evaluator, {}).get(
                    "origin"
                ),
            }
            for flag, origin in expected.items():
                with self.subTest(run=tag, flag=flag):
                    declared = (
                        readiness[readiness.index(flag) + 1]
                        if flag in readiness
                        else None
                    )
                    self.assertEqual(origin, declared)
                    checked += 1
        self.assertEqual(2 * len(runs), checked)

    def test_a_record_with_no_origin_is_a_fault_of_ours(self) -> None:
        harness = load_harness()
        with self.assertRaises(harness.HarnessFault) as caught:
            harness.declared_origin({"path": "agent.py"}, "ready")
        self.assertIn("declares no valid origin", str(caught.exception))

    def test_the_readiness_call_declares_the_origin_the_record_does(self) -> None:
        """The harness, not a committed card: the call is built from the record.

        The card test reads `argv.json` files already on disk, so a harness that went
        back to declaring `brought` for everything would pass it until the next sweep.
        This builds the call itself, for both origins and both components.
        """
        harness = load_harness()
        room = Path("/room")
        for origin in ("brought", "generated"):
            with self.subTest(origin=origin):
                call = harness.readiness_command(
                    scripts=Path("/guide"),
                    room=room,
                    project=Path("/project"),
                    agent={"state": "ready", "path": "agent.py", "origin": origin},
                    evaluator={"path": "evaluator.py", "origin": origin},
                    calibrated=True,
                    declared="normalized-exact",
                    task_kind="code-sql",
                    tag="probe",
                )
                for flag in ("--agent-origin", "--evaluator-origin"):
                    self.assertEqual(origin, call[call.index(flag) + 1])
        with self.assertRaises(harness.HarnessFault):
            harness.readiness_command(
                scripts=Path("/guide"),
                room=room,
                project=Path("/project"),
                agent=None,
                evaluator={"path": "evaluator.py", "origin": "Generated"},
                calibrated=False,
                declared=None,
                task_kind="code-sql",
                tag="probe",
            )


class TheSweepStatesTheBudgetItMeasuresUnder(unittest.TestCase):
    """`slow-scorer` is measured under a stated `--timeout`, and that is a claim.

    With no `--timeout` the guide budgets this calibration at 900 seconds, and
    the scorer reaches that only when all fifteen minutes have run -- which every
    reproduction of the sweep would then wait out. The sweep passes a small budget
    instead. Deleting that branch
    leaves the variant reading the default, the card's recorded
    `timeout_seconds` no longer describing the run that produced it, and
    nothing red.
    """

    def test_the_slow_scorer_variant_carries_a_timeout(self) -> None:
        harness = load_harness()
        options = {tag: opts for tag, _, opts in harness.VARIANTS}
        self.assertIn("slow-scorer", options)
        self.assertIn("calibration_timeout", options["slow-scorer"])
        self.assertGreater(options["slow-scorer"]["calibration_timeout"], 0)

    def test_the_recorded_card_was_taken_under_that_budget(self) -> None:
        options = {tag: opts for tag, _, opts in load_harness().VARIANTS}
        budget = options["slow-scorer"]["calibration_timeout"]
        calibration = json.loads(
            (
                REPO_ROOT
                / "docs"
                / "measurements"
                / "cards"
                / "slow-scorer"
                / "03-calibration.json"
            ).read_text(encoding="utf-8")
        )
        self.assertEqual(budget, calibration.get("timeout_seconds"))
        self.assertTrue(
            calibration.get("timed_out"),
            "the card is the evidence that this preset reaches the timeout",
        )


class EveryStepRunsBoundedAndWithoutTheShell(unittest.TestCase):
    """Each step the sweep runs has a budget above the guide's, and none of the shell.

    The steps run code that is not the sweep's -- the builder, the guide's scripts, and
    through the calibrator the project's own evaluator -- and each used to inherit every
    variable the operator had exported, with no limit on how long it could hold the sweep.
    """

    def setUp(self) -> None:
        self.harness = load_harness()
        self.room = Path(tempfile.mkdtemp(prefix="score-bank-step-"))
        self.addCleanup(shutil.rmtree, self.room, True)

    def test_the_bound_sits_above_every_budget_the_guide_gives_itself(self) -> None:
        """The guide's timeout is the finding; this bound may never be what fires first."""
        harness = self.harness
        self.assertEqual(
            harness.STEP_TIMEOUT_SECONDS,
            harness.GUIDE_CALIBRATION_CEILING_SECONDS + harness.STEP_HEADROOM_SECONDS,
        )
        self.assertEqual(900, harness.GUIDE_CALIBRATION_CEILING_SECONDS)
        self.assertGreater(harness.STEP_HEADROOM_SECONDS, 0)
        # A guided run of `slow-scorer` passes no `--timeout`: the guide's 900 seconds
        # decide, and the step is still being waited on when they run out.
        self.assertEqual(
            harness.STEP_TIMEOUT_SECONDS, harness.calibration_step_seconds(None)
        )
        # The sweep's own `slow-scorer` states five seconds; its calibrator stops itself
        # at five and the step bound is five plus the same headroom.
        budget = {tag: opts for tag, _, opts in harness.VARIANTS}["slow-scorer"][
            "calibration_timeout"
        ]
        self.assertEqual(
            budget + harness.STEP_HEADROOM_SECONDS,
            harness.calibration_step_seconds(budget),
        )

    def test_the_measurement_job_outlasts_one_step(self) -> None:
        """CI's limit is above one step's, so the sweep's own diagnostic is what a hang
        prints rather than a bare cancellation of the job around it."""
        workflow = (REPO_ROOT / ".github" / "workflows" / "ci.yml").read_text("utf-8")
        job = workflow.split("\n  measurements:\n", 1)[1]
        found = re.search(r"^    timeout-minutes: (\d+)$", job, re.M)
        assert found, "the measurement job states no timeout"
        self.assertGreater(int(found.group(1)) * 60, self.harness.STEP_TIMEOUT_SECONDS)

    def test_a_step_past_its_budget_is_killed_with_what_it_started(self) -> None:
        """Ours, loud, and nothing left running: the calibrator's worker is a child."""
        marker = self.room / "the-worker-outlived-the-step"
        worker = self.room / "worker.py"
        worker.write_text(
            "import pathlib, sys, time\n"
            "time.sleep(3)\n"
            "pathlib.Path(sys.argv[1]).write_text('alive')\n",
            encoding="utf-8",
        )
        child = (
            "import subprocess, sys, time\n"
            f"subprocess.Popen([sys.executable, {str(worker)!r}, {str(marker)!r}])\n"
            "time.sleep(60)\n"
        )
        started = time.monotonic()
        with self.assertRaises(self.harness.StepTimedOut) as caught:
            self.harness.capture(
                [sys.executable, "-c", child],
                self.room,
                self.room / "step.txt",
                seconds=1,
            )
        self.assertLess(time.monotonic() - started, 30)
        self.assertIsInstance(caught.exception, self.harness.HarnessFault)
        self.assertNotIsInstance(caught.exception, self.harness.GuideRefused)
        self.assertIn("1-second budget", str(caught.exception))
        time.sleep(4)
        self.assertFalse(marker.exists(), "the step's own child kept running")

    def test_a_step_that_stops_itself_inside_the_budget_is_read_as_before(self) -> None:
        """The `slow-scorer` shape: the calibrator reaches ITS timeout and says so."""
        answer = '{"timed_out": true, "timeout_seconds": 1}'
        done = self.harness.capture_json(
            [
                sys.executable,
                "-c",
                f"import sys, time; time.sleep(1); print({answer!r}); sys.exit(1)",
            ],
            self.room,
            self.room / "03-calibration-stderr.txt",
            self.room / "03-calibration.json",
            seconds=self.harness.calibration_step_seconds(1),
        )
        self.assertEqual(1, done.returncode)
        self.assertEqual(
            {"timed_out": True, "timeout_seconds": 1},
            self.harness.decoded(done, "calibrate_evaluator.py"),
        )

    def test_a_step_sees_only_the_variables_it_is_given(self) -> None:
        planted = {
            "OPENROUTER_API_KEY": "sk-or-planted",
            "TRAIGENT_API_KEY": "tg-planted",
            "POSTGRES_CONNECTION_STRING": "postgresql://planted",
            "VIRTUAL_ENV": "/planted/venv",
        }
        with mock.patch.dict(os.environ, planted):
            done = self.harness.capture_json(
                [
                    sys.executable,
                    "-c",
                    "import json, os; print(json.dumps(dict(os.environ)))",
                ],
                self.room,
                self.room / "stderr.txt",
                self.room / "out.json",
            )
            seen = json.loads(done.stdout)
            self.assertEqual([], sorted(set(planted) & set(seen)))
            # LC_CTYPE is the interpreter's own: PEP 538 sets it in a child started
            # under the C locale. HOME and PYTHONUSERBASE are the sweep's own values
            # (the test below). Nothing else may appear that was not passed.
            self.assertLessEqual(
                set(seen),
                set(self.harness.STEP_ENVIRONMENT)
                | {"LC_CTYPE", "HOME", "PYTHONUSERBASE"},
            )
            for name in self.harness.STEP_ENVIRONMENT:
                if name in os.environ:
                    self.assertEqual(os.environ[name], seen.get(name), name)

    def test_a_step_gets_a_home_of_its_own_and_the_same_packages(self) -> None:
        """Not the operator's HOME: nothing under it is found by its default name.

        A library that looks for `~/.netrc`, `~/.aws/credentials` or its own config under
        HOME finds an empty directory. What the operator installed with `pip --user` is
        still importable, because the user site the sweep's own interpreter uses is named
        explicitly -- the SDK is found only there on some machines.
        """
        probe = (
            "import importlib.util, json, os, site\n"
            "print(json.dumps({'home': os.environ.get('HOME'),"
            " 'listing': sorted(os.listdir(os.environ['HOME'])),"
            " 'user_site': site.getusersitepackages(),"
            " 'traigent': importlib.util.find_spec('traigent') is not None}))\n"
        )
        done = self.harness.capture_json(
            [sys.executable, "-c", probe],
            self.room,
            self.room / "stderr.txt",
            self.room / "out.json",
        )
        seen = json.loads(done.stdout)
        self.assertNotEqual(str(Path.home()), seen["home"])
        self.assertEqual([], seen["listing"], "the step's HOME is not an empty one")
        self.assertEqual(
            importlib.util.find_spec("traigent") is not None, seen["traigent"]
        )
        import site

        if site.ENABLE_USER_SITE:
            self.assertEqual(site.getusersitepackages(), seen["user_site"])

    def test_what_one_step_leaves_in_its_home_the_next_does_not_find(self) -> None:
        """A HOME per step, not per sweep: a config written by one step is gone by the next.

        The calibrator imports the project's evaluator, and whatever it writes under HOME
        would otherwise be in the HOME of every step after it, the readiness step included.
        """
        leave = (
            "import os, pathlib\n"
            "pathlib.Path(os.environ['HOME'], '.probe-config').write_text('x')\n"
            "print(os.environ['HOME'])\n"
        )
        first = self.harness.capture_json(
            [sys.executable, "-c", leave],
            self.room,
            self.room / "first.txt",
            self.room / "first.out",
        )
        look = "import json, os; print(json.dumps(os.listdir(os.environ['HOME'])))"
        second = self.harness.capture_json(
            [sys.executable, "-c", look],
            self.room,
            self.room / "second.txt",
            self.room / "second.out",
        )
        self.assertEqual(0, first.returncode, first.stderr)
        self.assertTrue(first.stdout.strip(), "the first step named no HOME")
        self.assertEqual([], json.loads(second.stdout))
        self.assertFalse(
            Path(first.stdout.strip()).exists(), "a step's HOME outlived the step"
        )

    def test_a_step_leaves_no_name_behind_for_its_home(self) -> None:
        """The HOME a step is given is named while its output is written, and no longer.

        Kept, every step of a sweep would add a dead name to the list each write is
        rewritten through, a few hundred of them by the end of the bank.
        """
        before = list(self.harness.PATH_NAMES)
        self.harness.capture(
            [sys.executable, "-c", "print('done')"], self.room, self.room / "step.txt"
        )
        self.harness.capture_json(
            [sys.executable, "-c", "print('{}')"],
            self.room,
            self.room / "stderr.txt",
            self.room / "out.json",
        )
        self.assertEqual(before, self.harness.PATH_NAMES)

    def test_a_home_path_a_step_prints_is_written_as_home(self) -> None:
        """What the step says about its own HOME reaches the log already neutral."""
        self.harness.capture(
            [sys.executable, "-c", "import os; print(os.environ['HOME'] + '/x')"],
            self.room,
            self.room / "step.txt",
        )
        written = (self.room / "step.txt").read_text(encoding="utf-8")
        self.assertIn("$HOME/x", written)
        self.assertNotIn("score-bank-home-", written)

    def test_a_home_path_on_stderr_or_resolved_is_written_as_home(self) -> None:
        """Stderr is neutral too, and so is HOME as the step resolves it.

        Shaped like macOS, where /var links to /private/var: the resolved path is the
        made one with a prefix in front, so the made path ends it. Replacing the shorter
        spelling first would leave `/private$HOME` behind.
        """
        link = self.room / "tmp-link"
        real = Path(str(self.room / "private") + str(link))
        real.mkdir(parents=True)
        link.symlink_to(real, target_is_directory=True)
        self.assertTrue(str(real).endswith(str(link)))
        step = (
            "import os, sys\n"
            "print('{}')\n"
            "print(os.environ['HOME'] + '/said', file=sys.stderr)\n"
            "print(os.path.realpath(os.environ['HOME']) + '/resolved', file=sys.stderr)\n"
        )
        with mock.patch.object(tempfile, "tempdir", str(link)):
            self.harness.capture_json(
                [sys.executable, "-c", step],
                self.room,
                self.room / "stderr.txt",
                self.room / "out.json",
            )
        written = (self.room / "stderr.txt").read_text(encoding="utf-8")
        self.assertIn("\n$HOME/said\n", written)
        self.assertIn("\n$HOME/resolved\n", written)
        self.assertNotIn("private$HOME", written)
        self.assertNotIn("score-bank-home-", written)

    def test_a_home_path_a_killed_step_printed_is_written_as_home(self) -> None:
        """The partial output of a step killed for time is neutral as well."""
        step = (
            "import os, time\n"
            "print(os.environ['HOME'] + '/before-the-hang', flush=True)\n"
            "time.sleep(60)\n"
        )
        log = self.room / "killed.txt"
        with self.assertRaises(self.harness.StepTimedOut):
            self.harness.capture(
                [sys.executable, "-c", step], self.room, log, seconds=1
            )
        written = log.read_text(encoding="utf-8")
        self.assertIn("$HOME/before-the-hang", written)
        self.assertNotIn("score-bank-home-", written)

    def test_an_interrupt_ends_the_step_and_what_it_started(self) -> None:
        """Ctrl-C at the sweep reaches the step, whose session is otherwise its own.

        The step may be the calibrator running the project's evaluator with
        --allow-execution, so an operator stopping the sweep has to stop that too.
        """
        marker = self.room / "the-step-outlived-the-interrupt"
        worker = self.room / "worker.py"
        worker.write_text(
            "import pathlib, sys, time\n"
            "time.sleep(3)\n"
            "pathlib.Path(sys.argv[1]).write_text('alive')\n",
            encoding="utf-8",
        )
        operator = (
            "import importlib.util, os, signal, sys, threading\n"
            f"spec = importlib.util.spec_from_file_location('h', {str(HARNESS)!r})\n"
            "harness = importlib.util.module_from_spec(spec)\n"
            "sys.modules['h'] = harness\n"
            "spec.loader.exec_module(harness)\n"
            "threading.Timer(0.5, os.kill, (os.getpid(), signal.SIGINT)).start()\n"
            "from pathlib import Path\n"
            f"room = Path({str(self.room)!r})\n"
            "harness.capture([sys.executable, str(room / 'worker.py'),"
            f" {str(marker)!r}], room, room / 'step.txt')\n"
        )
        started = time.monotonic()
        stopped = subprocess.run(
            [sys.executable, "-c", operator],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            timeout=60,
        )
        self.assertNotEqual(0, stopped.returncode, stopped.stdout)
        self.assertIn("KeyboardInterrupt", stopped.stdout)
        self.assertLess(time.monotonic() - started, 30)
        time.sleep(4)
        self.assertFalse(marker.exists(), "the step kept running after Ctrl-C")

    def test_a_step_that_finishes_leaves_nothing_of_its_own_running(self) -> None:
        """A child the step started and never waited for goes with the step."""
        marker = self.room / "an-orphan-kept-running"
        worker = self.room / "orphan.py"
        worker.write_text(
            "import pathlib, sys, time\n"
            "time.sleep(2)\n"
            "pathlib.Path(sys.argv[1]).write_text('alive')\n",
            encoding="utf-8",
        )
        step = (
            "import subprocess, sys\n"
            f"subprocess.Popen([sys.executable, {str(worker)!r}, {str(marker)!r}],"
            " stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)\n"
            "print('done')\n"
        )
        done = self.harness.capture(
            [sys.executable, "-c", step], self.room, self.room / "step.txt"
        )
        self.assertEqual(0, done.returncode)
        time.sleep(3)
        self.assertFalse(marker.exists(), "a process the step started outlived it")

    def test_a_killed_step_leaves_what_it_said_in_its_log(self) -> None:
        """The partial output is the only evidence of why it hung, so it is kept."""
        step = (
            "import sys, time\n"
            "print('reached the second phase', flush=True)\n"
            "print('x' * 9000, flush=True)\n"
            "time.sleep(60)\n"
        )
        log = self.room / "03-calibration-stderr.txt"
        with self.assertRaises(self.harness.StepTimedOut):
            self.harness.capture_json(
                [sys.executable, "-c", step],
                self.room,
                log,
                self.room / "03-calibration.json",
                seconds=1,
            )
        written = log.read_text(encoding="utf-8")
        self.assertIn("reached the second phase", written)
        self.assertIn("characters dropped]", written)
        self.assertIn("killed after 1 seconds", written)
        self.assertLess(len(written), self.harness.KILLED_OUTPUT_LIMIT + 1000)


class HarnessTestCase(unittest.TestCase):
    """A scratch guide, a scratch `cards/`, and the harness pointed at both."""

    def setUp(self) -> None:
        if shutil.which("git") is None:
            self.skipTest("the harness pins a guide revision, which needs git")
        self.room = Path(tempfile.mkdtemp(prefix="score-bank-test-"))
        self.addCleanup(shutil.rmtree, self.room, True)

        self.scripts = self.room / "guide" / "skills" / "traigent-first-run" / "scripts"
        self.scripts.mkdir(parents=True)
        (self.scripts / "readiness.py").write_text(STUB_GUIDE, encoding="utf-8")
        guide = self.room / "guide"
        for argv in (
            ["git", "init", "--quiet", "-b", "main"],
            ["git", "add", "-A"],
            [
                "git",
                "-c",
                "user.email=nobody@example.invalid",
                "-c",
                "user.name=test",
                "commit",
                "--quiet",
                "-m",
                "stub guide",
            ],
        ):
            subprocess.run(argv, cwd=guide, check=True, stdout=subprocess.DEVNULL)
        self.revision = subprocess.run(
            ["git", "-C", str(guide), "rev-parse", "HEAD"],
            stdout=subprocess.PIPE,
            text=True,
            check=True,
        ).stdout.strip()

        # A stand-in for the committed evidence: one directory per run with a file in it,
        # plus the results table beside them. Nothing in these tests may change any of it
        # unless the test says publishing was asked for.
        self.cards = self.room / "cards"
        for tag in ("empty", "ready", "best-case--off-method-calibration"):
            (self.cards / tag).mkdir(parents=True)
            (self.cards / tag / "04-readiness-card.txt").write_text(
                f"the committed card for {tag}\n", encoding="utf-8"
            )
            (self.cards / tag / "argv.json").write_text("{}\n", encoding="utf-8")
        (self.cards / "results.json").write_text(
            '{"guide_revision": "committed"}\n', encoding="utf-8"
        )

        self.harness = load_harness()
        self.harness.CARDS = self.cards
        self.harness.KNOBS = KNOBS
        self.workspace = self.room / "workspace"

    def run_sweep(
        self, score_one: object, publish: bool = False, *extra: str
    ) -> tuple[int, str, str]:
        """`main()` with the per-run measurement replaced, and its output captured."""
        self.harness.score_one = score_one
        argv = [
            "score_bank.py",
            "--guide",
            str(self.room / "guide"),
            "--revision",
            self.revision,
            "--workspace",
            str(self.workspace),
        ]
        if publish:
            argv.append("--publish")
        argv.extend(extra)
        out, err = io.StringIO(), io.StringIO()
        # Kept, so a test that expects `main()` to exit through argparse can still read
        # what it said on the way out.
        self.said, self.complained = out, err
        original, sys.argv = sys.argv, argv
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                status = self.harness.main()
        finally:
            sys.argv = original
        return status, out.getvalue(), err.getvalue()

    def refusing(self, refuse: str) -> object:
        """A measurement that refuses one tag and scores every other."""

        def score_one(
            tag: str,
            flags: tuple[str, ...],
            scripts: Path,
            workspace: Path,
            staging: Path,
            **options: object,
        ) -> dict[str, object]:
            room = staging / tag
            room.mkdir(parents=True, exist_ok=True)
            (room / "01-build.txt").write_text("built\n", encoding="utf-8")
            if tag == refuse:
                raise self.harness.GuideRefused(
                    "calibrate_evaluator.py", 2, "Refusing to calibrate: ..."
                )
            (room / "04-readiness-card.txt").write_text("a card\n", encoding="utf-8")
            (room / "argv.json").write_text("{}\n", encoding="utf-8")
            return self.scored(tag)

        return score_one

    def scored(self, tag: str) -> dict[str, object]:
        """The shape `score_one` returns for a run that scored."""
        return {
            "tag": tag,
            "overall": 45,
            "band": "PARTIAL",
            "recommended_action": "proceed",
            "status": "ok",
            "confidence": "low",
            "pillars": {"agent": 0},
            "caps": [],
            "declared_evaluator_method": None,
            "declared_task_kind": "code-sql",
            "calibration_ran": False,
            "calibration_passed": None,
        }


class AFaultOfOursPublishesNothing(HarnessTestCase):
    """The harm this file exists to keep dead: 203 files, destroyed by our own bug."""

    def test_a_broken_builder_ends_the_run_and_leaves_the_cards_alone(self) -> None:
        before = fingerprint(self.cards)
        attempted = []

        def explode(
            tag: str, flags: tuple[str, ...], *rest: object, **options: object
        ) -> dict[str, object]:
            attempted.append(tag)
            raise self.harness.HarnessFault(
                f"build.py exited 1 building {tag!r}: spider dataset checksum mismatch"
            )

        # Publishing is asked for explicitly: a fault of ours outranks the request.
        status, said, complained = self.run_sweep(explode, publish=True)

        self.assertEqual(status, 3, "a fault of ours has its own exit status")
        self.assertIn("HARNESS FAULT", complained)
        self.assertNotIn(
            "REFUSED", said, "our bug is not the guide declining something"
        )
        self.assertEqual(
            fingerprint(self.cards),
            before,
            "the committed evidence was rewritten by a sweep that measured nothing",
        )
        self.assertEqual(
            len(attempted), 1, "the sweep carried on past a fault it could not measure"
        )

    def test_a_step_that_times_out_ends_the_sweep_and_publishes_nothing(self) -> None:
        """Killed is not refused: no row for it, and no card moved."""
        before = fingerprint(self.cards)

        def hang(tag: str, *rest: object, **options: object) -> dict[str, object]:
            raise self.harness.StepTimedOut(
                ["python3", "$GUIDE/calibrate_evaluator.py"], 960
            )

        status, said, complained = self.run_sweep(hang, publish=True)
        self.assertEqual(status, 3)
        self.assertIn("calibrate_evaluator.py ran past the sweep's", complained)
        self.assertNotIn("REFUSED", said)
        self.assertEqual(fingerprint(self.cards), before)

    def test_a_failing_builder_is_a_harness_fault_at_the_raise_site(self) -> None:
        """Not through a stub: the real `score_one`, with a real `build.py` refusal.

        The test above replaces the measurement, so it holds `main()` to publishing
        nothing -- but it cannot see the raise site change class underneath it. This one
        runs the builder for real (it exits in milliseconds on an unknown preset) and
        holds that site to the type: ours, not the guide's.
        """
        with self.assertRaises(self.harness.HarnessFault) as caught:
            self.harness.score_one(
                "no-such-preset",
                ("--preset", "no-such-preset-at-all"),
                self.scripts,
                self.workspace,
                self.room / "staging",
            )
        self.assertNotIsInstance(caught.exception, self.harness.GuideRefused)
        self.assertIn("build.py", str(caught.exception))

    def test_an_unreadable_file_of_ours_is_ours_and_not_a_refusal(self) -> None:
        """The seam, checked where it was last found: `ours()` says whose fault it is."""
        broken = self.room / "not-json.json"
        broken.write_text("{ this is not json", encoding="utf-8")
        with self.assertRaises(self.harness.HarnessFault):
            self.harness.ours(broken, "a file of ours")


class AGuideRefusalIsOneRow(HarnessTestCase):
    """The other half: the guide declining is a finding, and costs one row."""

    def test_without_publish_the_committed_cards_are_untouched(self) -> None:
        before = fingerprint(self.cards)
        status, said, _ = self.run_sweep(
            self.refusing("best-case--off-method-calibration")
        )

        self.assertEqual(
            status, 1, "the guide refused a run, so the sweep is not clean"
        )
        self.assertIn("cards/ not rewritten", said)
        self.assertEqual(
            fingerprint(self.cards),
            before,
            "a plain run replaced the committed evidence",
        )

    def test_publish_promotes_the_runs_that_scored_and_keeps_the_one_that_did_not(
        self,
    ) -> None:
        refused = "best-case--off-method-calibration"
        kept = fingerprint(self.cards / refused)
        status, said, _ = self.run_sweep(self.refusing(refused), publish=True)

        self.assertEqual(status, 1)
        self.assertEqual(
            fingerprint(self.cards / refused),
            kept,
            "the refused run's committed card was replaced by the partial output of a "
            "run that produced no card -- the four files this loses cannot be remade",
        )
        self.assertIn(f"cards/{refused}/ left as it was", said)
        self.assertEqual(
            (self.cards / "ready" / "04-readiness-card.txt").read_text(
                encoding="utf-8"
            ),
            "a card\n",
            "a run that scored was not promoted",
        )
        table = json.loads((self.cards / "results.json").read_text(encoding="utf-8"))
        self.assertEqual(table["guide_revision"], self.revision)
        rows = {row["tag"]: row for row in table["runs"]}
        self.assertEqual(rows[refused]["refused"]["step"], "calibrate_evaluator.py")
        self.assertIsNone(rows[refused]["overall"])


class TheContractCheckStopsBeforeAnythingIsBuilt(HarnessTestCase):
    """A disagreement is a property of the pair, so no run happens at all."""

    def test_a_revision_that_does_not_read_source_lines_refuses_up_front(self) -> None:
        (self.scripts / "readiness.py").write_text(
            STUB_GUIDE.replace(', "source_lines"', "").replace(
                '\n            "source_lines",', ""
            ),
            encoding="utf-8",
        )
        before = fingerprint(self.cards)
        attempted = []

        def unreachable(
            tag: str, *rest: object, **options: object
        ) -> dict[str, object]:  # pragma: no cover - the point is that it never runs
            attempted.append(tag)
            return self.scored(tag)

        status, _, complained = self.run_sweep(unreachable, publish=True)

        self.assertEqual(status, 2)
        self.assertEqual(attempted, [], "the sweep built something it could not score")
        self.assertIn("does not read", complained)
        self.assertEqual(fingerprint(self.cards), before)

    def test_a_guide_that_publishes_no_field_list_says_the_check_did_not_run(
        self,
    ) -> None:
        (self.scripts / "readiness.py").write_text("", encoding="utf-8")
        status, _, complained = self.run_sweep(
            self.refusing_nothing(),
        )
        self.assertEqual(status, 0)
        self.assertIn("went unchecked", complained, "a gate that no-ops says so")
        self.assertIn("results.json records none", complained)
        table = json.loads(
            (self.workspace / "cards-staging" / "results.json").read_text("utf-8")
        )
        self.assertIsNone(table["conditions"])

    def refusing_nothing(self) -> object:
        def score_one(
            tag: str,
            flags: tuple[str, ...],
            scripts: Path,
            workspace: Path,
            staging: Path,
            **options: object,
        ) -> dict[str, object]:
            (staging / tag).mkdir(parents=True, exist_ok=True)
            return self.scored(tag)

        return score_one


class TheComparisonIsWithTheWholeRecord(HarnessTestCase):
    """`--compare`: agreement with every card and with the refusals, or exit 4.

    The committed record here is made the way the real one is -- a `--publish` of a sweep
    in which one run is refused -- and then measured again.
    """

    REFUSED = "best-case--off-method-calibration"

    def setUp(self) -> None:
        super().setUp()
        self.harness.PINNED_REVISION = self.revision
        self.harness.recorded_environment = lambda: {"guide": self.revision}
        self.harness.environment_mismatch = lambda recorded: []
        status, _, _ = self.run_sweep(self.refusing(self.REFUSED), publish=True)
        self.assertEqual(status, 1, "the record is made with one refused run")

    def test_a_measurement_that_reproduces_the_record_agrees(self) -> None:
        before = fingerprint(self.cards)
        status, said, _ = self.run_sweep(
            self.refusing(self.REFUSED), False, "--compare"
        )
        self.assertEqual(status, 0, said)
        runs = json.loads((self.cards / "results.json").read_text(encoding="utf-8"))[
            "runs"
        ]
        self.assertIn(f"compared {len(runs) - 1} cards byte for byte", said)
        self.assertIn(f"refusals compared as recorded: {self.REFUSED}", said)
        self.assertEqual(fingerprint(self.cards), before, "a comparison published")

    def test_a_changed_card_is_a_difference_and_is_named(self) -> None:
        (self.cards / "ready" / "04-readiness-card.txt").write_text(
            "a card someone edited\n", encoding="utf-8"
        )
        status, said, _ = self.run_sweep(
            self.refusing(self.REFUSED), False, "--compare"
        )
        self.assertEqual(status, 4)
        self.assertIn(
            "ready/04-readiness-card.txt: line 1 was 'a card someone edited', "
            "now 'a card'",
            said,
        )

    def test_a_refusal_the_record_does_not_hold_is_a_difference(self) -> None:
        status, said, _ = self.run_sweep(self.refusing("ready"), False, "--compare")
        self.assertEqual(status, 4)
        self.assertIn("results.json: line", said)
        self.assertIn(
            "ready/04-readiness-card.txt: committed, and not produced now", said
        )

    def test_a_card_no_run_produces_is_a_difference(self) -> None:
        (self.cards / "a-run-nobody-measures").mkdir()
        status, said, _ = self.run_sweep(
            self.refusing(self.REFUSED), False, "--compare"
        )
        self.assertEqual(status, 4)
        self.assertIn("a-run-nobody-measures/: a committed card no run", said)

    def test_comparing_nothing_is_not_agreement(self) -> None:
        empty = '{"guide_revision": "x", "runs": []}\n'
        staging = self.room / "empty-staging"
        staging.mkdir()
        (staging / "results.json").write_text(empty, encoding="utf-8")
        for entry in list(self.cards.iterdir()):
            if entry.is_dir():
                shutil.rmtree(entry)
        (self.cards / "results.json").write_text(empty, encoding="utf-8")
        differences, compared, _ = self.harness.compare_with_record(staging)
        self.assertEqual(compared, 0)
        self.assertIn(
            "compared 0 cards where the record has 0 that scored; a comparison of "
            "nothing agrees with everything",
            differences,
        )


class APartialSweepTouchesOnlyWhatItNames(HarnessTestCase):
    """`--only`: the runs named, their cards, their rows -- and nothing else moves.

    A partial `--publish` has to leave the table a whole one would write wherever the runs
    it did not repeat still reproduce, or the CI comparison of the whole bank fails on a
    table that was never re-measured. So the record here is made by a whole `--publish`,
    as the real one is, and then touched by partial ones.
    """

    REFUSED = "best-case--off-method-calibration"

    def setUp(self) -> None:
        super().setUp()
        self.harness.PINNED_REVISION = self.revision
        self.harness.recorded_environment = lambda: {"guide": self.revision}
        self.harness.environment_mismatch = lambda recorded: []
        status, _, _ = self.run_sweep(self.refusing(self.REFUSED), publish=True)
        self.assertEqual(status, 1, "the record is made with one refused run")

    def results(self) -> dict[str, object]:
        return dict(json.loads((self.cards / "results.json").read_text("utf-8")))

    def scoring(self, overall: int) -> object:
        """A measurement that scores every run it is asked for, at `overall`."""
        attempted: list[str] = []

        def score_one(
            tag: str,
            flags: tuple[str, ...],
            scripts: Path,
            workspace: Path,
            staging: Path,
            **options: object,
        ) -> dict[str, object]:
            attempted.append(tag)
            room = staging / tag
            room.mkdir(parents=True, exist_ok=True)
            # The same files `refusing` writes for a run that scored, which is how the
            # record in `setUp` was made.
            (room / "01-build.txt").write_text("built\n", encoding="utf-8")
            (room / "04-readiness-card.txt").write_text("a card\n", encoding="utf-8")
            (room / "argv.json").write_text("{}\n", encoding="utf-8")
            return {**self.scored(tag), "overall": overall}

        self.attempted = attempted
        return score_one

    def test_only_the_named_runs_are_measured_in_the_sweeps_order(self) -> None:
        status, _, _ = self.run_sweep(
            self.scoring(45), False, "--only", "ready", "empty"
        )
        self.assertEqual(status, 0)
        self.assertEqual(["empty", "ready"], self.attempted)

    def test_a_run_the_sweep_does_not_make_is_refused_before_anything_runs(
        self,
    ) -> None:
        with self.assertRaises(SystemExit) as caught:
            self.run_sweep(self.scoring(45), False, "--only", "no-such-run")
        self.assertEqual(caught.exception.code, 2)
        self.assertIn(
            "--only names runs the sweep does not make: no-such-run",
            self.complained.getvalue(),
        )
        self.assertEqual([], self.attempted)

    def test_the_guides_vocabulary_is_recorded_with_the_runs(self) -> None:
        self.assertEqual(STUB_CONDITIONS, self.results()["conditions"])

    def test_a_partial_publish_puts_its_rows_in_and_leaves_the_rest(self) -> None:
        before_rows = self.results()["runs"]
        untouched = {
            name: digest
            for name, digest in fingerprint(self.cards).items()
            if not name.startswith("ready/") and name != "results.json"
        }
        status, _, _ = self.run_sweep(self.scoring(77), True, "--only", "ready")
        self.assertEqual(status, 0)
        after_rows = self.results()["runs"]
        assert isinstance(before_rows, list) and isinstance(after_rows, list)
        self.assertEqual(
            [row["tag"] for row in before_rows], [row["tag"] for row in after_rows]
        )
        for was, now in zip(before_rows, after_rows):
            if now["tag"] == "ready":
                self.assertEqual(77, now["overall"])
            else:
                self.assertEqual(was, now)
        self.assertEqual(
            untouched,
            {
                name: digest
                for name, digest in fingerprint(self.cards).items()
                if not name.startswith("ready/") and name != "results.json"
            },
        )

    def test_a_partial_publish_of_what_reproduces_leaves_the_table_as_it_was(
        self,
    ) -> None:
        """The property the CI comparison of the whole bank depends on."""
        table = (self.cards / "results.json").read_bytes()
        status, _, _ = self.run_sweep(self.scoring(45), True, "--only", "ready")
        self.assertEqual(status, 0)
        self.assertEqual(table, (self.cards / "results.json").read_bytes())

    def test_a_partial_publish_will_not_mix_two_revisions(self) -> None:
        table = self.results()
        table["guide_revision"] = "another-revision"
        (self.cards / "results.json").write_text(json.dumps(table), encoding="utf-8")
        before = fingerprint(self.cards)
        status, _, complained = self.run_sweep(
            self.scoring(45), True, "--only", "ready"
        )
        self.assertEqual(status, 3)
        self.assertIn("two revisions", complained)
        self.assertEqual(before, fingerprint(self.cards))

    def test_a_partial_publish_needs_the_environment_the_cards_were_taken_in(
        self,
    ) -> None:
        """Else it rewrites some cards under another interpreter, and the record then
        disagrees with itself about which one it was measured on -- which is the error
        `--recorded-environment` and CI's whole-bank comparison stop on."""
        self.harness.environment_mismatch = lambda recorded: [
            "python is 3.13.0 here and 3.12.3 on the committed cards"
        ]
        before = fingerprint(self.cards)
        with self.assertRaises(SystemExit) as caught:
            self.run_sweep(self.scoring(45), True, "--only", "ready")
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("3.13.0 here", self.complained.getvalue())
        self.assertEqual([], self.attempted, "it built something before refusing")
        self.assertEqual(before, fingerprint(self.cards))

    def test_the_recorded_environment_is_not_a_subset(self) -> None:
        """`--only` means nothing to it, so naming runs there is refused, not ignored."""
        with self.assertRaises(SystemExit) as caught:
            self.run_sweep(
                self.scoring(45), False, "--recorded-environment", "--only", "x"
            )
        self.assertEqual(caught.exception.code, 2)
        self.assertIn("--only", self.complained.getvalue())

    def test_a_partial_compare_reads_only_the_runs_it_names(self) -> None:
        status, said, _ = self.run_sweep(
            self.scoring(45), False, "--compare", "--only", "ready"
        )
        self.assertEqual(status, 0, said)
        self.assertIn("compared 1 cards byte for byte", said)
        # A card the comparison was not asked about is not its business ...
        (self.cards / "empty" / "04-readiness-card.txt").write_text(
            "edited\n", encoding="utf-8"
        )
        status, said, _ = self.run_sweep(
            self.scoring(45), False, "--compare", "--only", "ready"
        )
        self.assertEqual(status, 0, said)
        # ... and a card it was asked about is, and so is the row.
        (self.cards / "ready" / "04-readiness-card.txt").write_text(
            "edited\n", encoding="utf-8"
        )
        status, said, _ = self.run_sweep(
            self.scoring(46), False, "--compare", "--only", "ready"
        )
        self.assertEqual(status, 4)
        self.assertIn("ready/04-readiness-card.txt: line 1 was 'edited'", said)
        self.assertIn("results.json row ready:", said)

    def test_a_partial_compare_of_a_run_the_record_lacks_is_a_difference(
        self,
    ) -> None:
        table = self.results()
        runs = table["runs"]
        assert isinstance(runs, list)
        table["runs"] = [row for row in runs if row["tag"] != "ready"]
        (self.cards / "results.json").write_text(json.dumps(table), encoding="utf-8")
        status, said, _ = self.run_sweep(
            self.scoring(45), False, "--compare", "--only", "ready"
        )
        self.assertEqual(status, 4)
        self.assertIn("no committed row for ready", said)


class TheComparisonNeedsTheRecordedEnvironment(HarnessTestCase):
    """Preflight writes the interpreter and the SDK into every card."""

    def record(self, python: str, traigent: str | None) -> None:
        self.harness.PINNED_REVISION = self.revision
        runs = [
            {"tag": "ready"},
            {"tag": "empty"},
            {"tag": "x", "refused": {"step": "calibrate_evaluator.py"}},
        ]
        (self.cards / "results.json").write_text(
            json.dumps({"guide_revision": self.revision, "runs": runs}),
            encoding="utf-8",
        )
        for tag, version in (("ready", python), ("empty", "3.12.3")):
            (self.cards / tag / "02-preflight.json").write_text(
                json.dumps(
                    [
                        {"check": "python-version", "detail": version},
                        {
                            "check": "sdk-version",
                            "metrics": {"installed": traigent} if traigent else None,
                        },
                    ]
                ),
                encoding="utf-8",
            )

    def test_the_environment_is_read_from_the_cards(self) -> None:
        self.record("3.12.3", "0.26.0")
        recorded = self.harness.recorded_environment()
        self.assertEqual(recorded["python"], "3.12.3")
        self.assertEqual(recorded["traigent"], "0.26.0")
        self.assertEqual(recorded["guide"], self.revision)
        self.assertEqual(
            "litellm==" + recorded["litellm"], build_module().AGENT_REQUIREMENT
        )

    def test_cards_that_disagree_about_it_are_ours_to_fix(self) -> None:
        self.record("3.11.9", "0.26.0")
        with self.assertRaises(self.harness.HarnessFault) as caught:
            self.harness.recorded_environment()
        self.assertIn("do not agree on one python", str(caught.exception))

    def test_another_interpreter_is_refused_before_anything_is_built(self) -> None:
        self.record("3.12.3", "0.26.0")
        self.harness.recorded_environment = lambda: {
            "guide": self.revision,
            "python": "0.0.0",
            "traigent": "0.26.0",
            "litellm": "1.93.0",
        }
        attempted: list[str] = []

        def unreachable(tag: str, *rest: object, **options: object) -> object:
            attempted.append(tag)  # pragma: no cover - the point is that it never runs
            return self.scored(tag)

        with self.assertRaises(SystemExit) as caught:
            self.run_sweep(unreachable, False, "--compare")
        self.assertEqual(caught.exception.code, 2)
        self.assertEqual(attempted, [])


if __name__ == "__main__":
    unittest.main()
