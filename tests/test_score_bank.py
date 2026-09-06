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
import shutil
import subprocess
import sys
import tempfile
import types
import unittest
from pathlib import Path

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
"""


def load_harness() -> types.ModuleType:
    """The harness as a module, by path: `docs/measurements/` is not a package."""
    located = importlib.util.spec_from_file_location("_score_bank", HARNESS)
    assert located is not None and located.loader is not None
    module = importlib.util.module_from_spec(located)
    sys.modules[located.name] = module
    located.loader.exec_module(module)
    return module


def fingerprint(tree: Path) -> dict[str, str]:
    """Every file under a directory, by relative path and content digest."""
    return {
        str(found.relative_to(tree)): hashlib.sha256(found.read_bytes()).hexdigest()
        for found in sorted(tree.rglob("*"))
        if found.is_file()
    }


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
        self, score_one: object, publish: bool = False
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
        out, err = io.StringIO(), io.StringIO()
        original, sys.argv = sys.argv, argv
        try:
            with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
                status = self.harness.main()
        finally:
            sys.argv = original
        return status, out.getvalue(), err.getvalue()

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


if __name__ == "__main__":
    unittest.main()
