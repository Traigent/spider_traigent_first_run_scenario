#!/usr/bin/env python3
"""Re-measure the opening readiness card for every preset, and keep the evidence.

The score table in ../../README.md is produced by this script and by nothing else. It
builds each preset, runs the first-run guide's own `preflight.py`, `calibrate_evaluator.py`
and `readiness.py` over it in the order `SKILL.md`'s opening gate prescribes, and writes
every invocation and every output as a card. Nothing under `cards/` is named `.log`: the
repository's `.gitignore` excludes that suffix, and evidence that is not committed is not
evidence.

    python3 docs/measurements/score_bank.py --guide ~/code/traigent-first-run

**`--compare` is the check, made mechanical.** It re-measures into the workspace, publishes
nothing, and compares what it produced with the committed record byte for byte: every card of
every run that scored, and `results.json` whole, so a run the record says was refused has to be
refused again, at the same step and in the same words. It exits 0 only when all of that agrees,
and it refuses to compare nothing. The cards carry the interpreter and the SDK they were
measured with -- preflight records both -- so a comparison run anywhere else would report the
machine rather than the guide; `--compare` checks the environment first and says what to
install. `--recorded-environment` prints that environment for a CI job to set up.

**It does not touch `cards/` unless asked.** The cards are committed evidence, and the
commonest reason to run this script is to check them rather than to replace them, so a plain
run writes into the workspace and says where. `--publish` is the regeneration: it replaces the
committed directory of every run that produced a card, and leaves alone the directory of any
run that did not -- a refused run's staged output is the two or three files it reached before
the refusal, and moving that over a committed card deletes the card itself.

**`--only RUN ...` makes the named runs and no others.** With `--compare` it compares their
cards, their rows of `results.json` and the guide's recorded vocabulary; with `--publish` it
replaces their cards and puts their rows into the committed `results.json` in the order a
whole sweep writes them, leaving every other row exactly as it was -- and, like `--compare`, only in the environment
the committed cards record. Adding a run then costs
its own build rather than the bank's, and the whole-bank `--compare` in CI is what checks
that everything it did not repeat still reproduces.

**It records what the guide can say.** `results.json` carries `conditions` beside the runs:
every cap condition the pinned `readiness.py` can raise, with the remedy and the ranked
ceiling it gives each, read from the guide's own tables by the same probe that reads its
document contracts. The suite holds the cards to it -- every condition is on a card or is
named as unreached, with the reason.

Standard library only, like `build.py`. It needs a checkout of the guide, because the
scripts it runs are the guide's, and it never reaches the network.

**Every step runs bounded and without the shell.** A step is given `STEP_ENVIRONMENT`, an
empty HOME of its own that is removed when it ends, and the user site this interpreter
imports from, and nothing else of the environment this script was started in -- no provider
key, no database URL -- because it runs code that is not this script's, the project's own
evaluator included, and because preflight writes what it finds there into the card. It runs
in a process group of its own, which is killed once the step's output is read, on Ctrl-C,
and once it outlasts `STEP_TIMEOUT_SECONDS`: the guide's own calibration ceiling plus the
headroom the guide's harness allows the same command. A kill for time writes what the step
said into its log, ends the sweep on exit 3 and publishes nothing; it is never a row.

**It pins the revision.** `PINNED_REVISION` below is the commit every figure under `cards/`
was measured at, and the run refuses a checkout sitting on anything else rather than quietly
scoring against a moved target. The revision used is recorded in `cards/results.json`.
A table that silently re-measures against whatever HEAD happens to be is not reproducible,
which is the whole point of this directory.

**Exit status.** 0 when every run scored; 1 when the guide refused one or more of them;
2 when the documents and the guide disagree before anything is built; 3 when something of
*ours* broke -- our builder, our probe -- which is never a row and never publishes; and, with
`--compare`, 4 when the fresh measurement differs from the committed one (a recorded refusal
repeated exactly is agreement, not a difference).
At HEAD one run cannot score: the guide refuses to calibrate an executing scorer, which is
exactly what `best-case--off-method-calibration` asks it to do, so a complete and correct
sweep ends 1 with that one run refused. Nothing should key on exit 0 alone; read the
refused list the run prints and `results.json` beside it.

What it decides, and why each decision is here rather than in the reader's head:

`--evaluator-method` is taken from `demo.json`, which is the record of what the evaluator
component actually is. A real run declares that from its own reading of the file; this
script cannot read, so it uses the builder's record and says so. The same goes for
`--task-kind code-sql`: every project in this bank produces SQL. Where the record holds no
method -- `opaque`, whose grader is a library the project does not carry, and
`length-blind`, whose comparison of lengths is not one of the methods the guide names --
no `--evaluator-method` is passed at all, which is what a run that could not honestly
declare one does; `readiness.py` answers an undeclared method with `evaluator-unresolved`
unless calibration has spoken for the file.

`--agent-origin` and `--evaluator-origin` are taken from `demo.json` the same way. The guide
has a run declare them on every readiness call -- `brought` for the customer's own,
`generated` for one the run created or relies on in their place, including a pre-existing
file the customer disclaims -- and the record says which each component is: `brought`
everywhere but the `disclaimed` states, whose README disclaims the file.

`--input-field` and `--expected-field` are not passed, except by one variant. The rows
are written under `input` and `output` everywhere but `raw-export`, which uses Spider's
own `question` and `query`; the preset is scored as the tools read it unaided, and
`raw-export--fields-declared` scores the same project with the two names declared, which
is what an assistant that had opened the file would pass.

`--agent-knobs` is the coding assistant's own read of the agent's source, and the guide is
explicit that the opening score requires it wherever an agent was found. No assistant is
running here, so the two documents under `agent-knobs/` stand in for one. They were written
by hand against the two agent components and they cite real lines on the real call path --
which is why the figures are faithful, and also why another honest read could move them.

`--calibration` runs only where the demo ships probe answers AND the guide's opening gate
allows it: `references/component-creation.md` opens calibration "if the verdict is sufficient
and the complete path does not execute candidate-generated code or SQL". A scorer that runs
model-written SQL fails that gate, so `best-case` is scored without calibration, and the
`--evaluator-method execution` declaration alone makes `readiness.py` raise
`evaluator-calibration-refused` -- a cap with no ceiling and no block, a disclosure rather
than a bound -- without any `--calibration-scope-refused` flag. The
`best-case--off-method-calibration` run in VARIANTS asks the calibration tool to score that
evaluator anyway; at the pinned revision the tool refuses (exit 2) to import a scorer whose
walk reaches a SQL engine, so that run is recorded as refused and its committed card is the
older reading.

`--row-review` is not passed. The guide asks for one at the opening gate and it is the
assistant's own read of every row; a hand-written stand-in for it would be this script
deciding, row by row, whether each answer answers its question -- which is exactly the
judgement the `wrong-answers` preset exists to test. Leaving it off keeps the table
mechanical, and the omission is a property of this table rather than of the guide. It
also puts one condition out of this bank's reach on purpose:
`dataset-unsound-expected-outputs` fires when a row review carries `no` verdicts past a
share, so a table that passes no review cannot raise it, and passing one here would be
the script answering the question `wrong-answers` asks. It is reached only where a row
review exists -- a guided run in which an assistant has read the rows and written its
verdicts -- which is a different kind of evidence from this table. The guide
also holds the top two bands at WORKABLE until a row review has entered, and that hold is
what caps this bank's ceiling: `band_limited_by_unread_answers` is true on six cards --
`checked`, `wrong-answers--calibrated` and the four `grid-*` runs -- which are exactly the
runs that climb past 74 without a review. They read WORKABLE with `review-answer-key` rather
than STRONG, and `docs/measurements/README.md` says the same thing beside the table.
"""

from __future__ import annotations

import argparse
import ast
import contextlib
import importlib.metadata
import json
import os
import pathlib
import shutil
import signal
import site
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Any, Sequence

# The guide commit every figure under cards/ was measured at. Changing this is a deliberate
# re-measurement, never a side effect of somebody's checkout having moved. WORKING_REVISION is
# the revision the documents under agent-knobs/ validate at; the two name the same commit
# since the 2026-09-15 regeneration, so no --revision override is needed, and they are kept
# separate for the next time the guide's document contract moves ahead of the pin. Both
# moved from 5ce65540 to d07b62cd on 2026-09-22: the guide's `skills/` tree is byte-identical
# across that commit, and the republished cards came back identical but for the revision
# recorded in results.json, which is what made the move free to make.
PINNED_REVISION = "d07b62cd4abb6ecb6d2edcdcb2d535f02bb2c199"
WORKING_REVISION = "d07b62cd4abb6ecb6d2edcdcb2d535f02bb2c199"

HERE = Path(__file__).resolve().parent
REPO_ROOT = HERE.parent.parent
CARDS = HERE / "cards"
KNOBS = HERE / "agent-knobs"

# The presets in the order the score table lists them: by opening score.
PRESETS = (
    "empty",
    "logs-only",
    "no-data",
    "agent-and-logs",
    "fake-ruler",
    "no-labels",
    "duplicated-data",
    "no-eval",
    "no-knobs",
    "ready",
    "sql-exec-stop",
    "no-agent",
    "wrong-answers",
    "wrong-wiring",
    "hand-written",
    "checked",
    "best-case",
    "raw-export",
    "length-blind",
    "torn-lines",
    "opaque-scorer",
    "holdout-only",
    "leaky-split",
    "undeclared-source",
    "mostly-undeclared-source",
    "mostly-synthetic-source",
    "synthetic-source",
    "generated-answer-key",
    "mostly-generated-answer-key",
    "split-by-database",
    "two-agents",
    "split-by-question-form",
    "disclaimed-agent",
    "disclaimed-scorer",
)

# The comparisons the documentation makes, each built from flags rather than a preset so
# the pair being compared differs in exactly one thing.
VARIANTS: tuple[tuple[str, tuple[str, ...], dict[str, Any]], ...] = (
    (
        "best-case--off-method-calibration",
        ("--preset", "best-case"),
        {"force_execution_calibration": True},
    ),
    (
        "wrong-answers--calibrated",
        ("--preset", "wrong-answers", "--calibration", "present"),
        {},
    ),
    (
        "wrong-wiring--calibrated",
        ("--preset", "wrong-wiring", "--calibration", "present"),
        {},
    ),
    (
        "fake-ruler--uncalibrated",
        ("--preset", "fake-ruler", "--calibration", "none"),
        {},
    ),
    (
        "ready--without-agent-knobs",
        ("--preset", "ready"),
        {"agent_knobs": False},
    ),
    (
        "raw-export--fields-declared",
        ("--preset", "raw-export"),
        {"input_field": "question", "expected_field": "query"},
    ),
    (
        "length-blind--uncalibrated",
        ("--preset", "length-blind", "--calibration", "none"),
        {},
    ),
    # The four provenance states, calibrated. Uncalibrated they all read 45 --
    # `evaluator-unvalidated` is the lower ceiling and it hides every one of
    # them -- so the rung each state actually sits on is only visible once the
    # scorer has been checked. That is the whole point of the pairs: the
    # declaration a customer makes about their own rows is worth a different
    # number depending on how much of the file it covers, and the uncalibrated
    # runs cannot show it.
    (
        "undeclared-source--calibrated",
        ("--preset", "undeclared-source", "--calibration", "present"),
        {},
    ),
    (
        "mostly-undeclared-source--calibrated",
        ("--preset", "mostly-undeclared-source", "--calibration", "present"),
        {},
    ),
    (
        "mostly-synthetic-source--calibrated",
        ("--preset", "mostly-synthetic-source", "--calibration", "present"),
        {},
    ),
    (
        "synthetic-source--calibrated",
        ("--preset", "synthetic-source", "--calibration", "present"),
        {},
    ),
    (
        "generated-answer-key--calibrated",
        ("--preset", "generated-answer-key", "--calibration", "present"),
        {},
    ),
    (
        "mostly-generated-answer-key--calibrated",
        ("--preset", "mostly-generated-answer-key", "--calibration", "present"),
        {},
    ),
    (
        "slow-scorer",
        ("--preset", "slow-scorer"),
        {"calibration_timeout": 5},
    ),
    # The origin and task-family states, calibrated, for the same reason as the
    # provenance pairs: their ceilings (65, 74, 50) all sit above the 45 the unchecked
    # evaluator holds every uncalibrated card at, so only the calibrated run shows the
    # rung each one is on.
    (
        "disclaimed-agent--calibrated",
        ("--preset", "disclaimed-agent", "--calibration", "present"),
        {},
    ),
    (
        "disclaimed-scorer--calibrated",
        ("--preset", "disclaimed-scorer", "--calibration", "present"),
        {},
    ),
    (
        "split-by-question-form--calibrated",
        ("--preset", "split-by-question-form", "--calibration", "present"),
        {},
    ),
)

# The four combinations of declared method and declared task kind, all on the same
# unchanged text comparator, from `--preset checked`.
GRID: tuple[tuple[str, str, str], ...] = (
    ("grid-exact--code-sql", "exact", "code-sql"),
    ("grid-normalized-exact--structured", "normalized-exact", "structured"),
    ("grid-normalized-exact--code-sql", "normalized-exact", "code-sql"),
    ("grid-exact--structured", "exact", "structured"),
)


def sweep() -> list[tuple[str, tuple[str, ...], dict[str, Any]]]:
    """Every run, as (tag, build flags, options), in the order `results.json` lists them.

    One list for the whole sweep, a partial one and the merge a partial `--publish` makes,
    so a run cannot be measured under one set of flags and filed under another.
    """
    return (
        [(preset, ("--preset", preset), {}) for preset in PRESETS]
        + [(tag, flags, dict(options)) for tag, flags, options in VARIANTS]
        + [
            (tag, ("--preset", "checked"), {"method": declared, "task_kind": kind})
            for tag, declared, kind in GRID
        ]
    )


class MeasurementError(RuntimeError):
    """A step that has to succeed did not.

    The two subclasses below answer the only question this script's error handling has
    ever needed to ask, and the question is *whose fault it was* rather than *which step
    it happened at*. A step allow-list was tried and was wrong the moment a step was
    added to it: keyed on `readiness.py`, it let a fault in this repository's own
    `build.py` through as a refusal and published 26 empty rows over the committed
    evidence. Whose fault it was is a property of the raise site, which is where it is
    known, so it is recorded there and nowhere else has to guess.
    """


class GuideRefused(MeasurementError):
    """A guide script declined, in its own words. A finding, not a fault.

    This is the ordinary outcome of measuring a tool that is allowed to refuse: the
    guide declines a calibration, or rejects an `--agent-knobs` document, writes its
    reason to stderr and exits non-zero, and the JSON the next step would read is not
    there. That is a finding about the run, so it costs one row rather than the whole
    bank -- which is what a bare `json.loads` of a refusal used to cost: a
    `JSONDecodeError` at the readiness step threw away every run already measured,
    including the ones that had nothing wrong with them.

    Raised at exactly one site, `decoded()`, and only for the guide's own scripts.
    """

    def __init__(self, step: str, exit_code: int, reason: str) -> None:
        super().__init__(f"{step} exited {exit_code}: {reason}")
        self.step = step
        self.exit_code = exit_code
        self.reason = reason


class HarnessFault(MeasurementError):
    """Something of ours broke: our builder, our probe, our own inputs.

    It never becomes a row. A row saying `refused` reads as the tool declining
    something, and that vocabulary must not be able to describe our own bugs -- a
    checksum failure in `build.py` recorded as 26 refusals is a table saying the guide
    rejected this repository, which is false and was published as evidence.
    """


class StepTimedOut(HarnessFault):
    """A step outlasted the sweep's own budget for one step, and was killed.

    Not a refusal: the guide says nothing when it is killed, so there is no sentence of
    its own to record, and a row would be this script inventing one. It is a
    `HarnessFault` because what ran out is ours -- the budget this sweep sets above the
    guide's -- so the sweep stops, publishes nothing, and says which step and how long.
    """

    def __init__(self, argv: list[str], seconds: int, output: str = "") -> None:
        # The script the step runs, which is what a reader recognises: `build.py`,
        # `calibrate_evaluator.py`, or the `readiness.py` the contract probe reads.
        step = next(
            (Path(piece).name for piece in argv[1:] if piece.endswith(".py")), argv[0]
        )
        super().__init__(
            f"{step} ran past the "
            f"sweep's {seconds}-second budget for one step and was killed with every "
            "process it started. The guide's own calibration budget is below that "
            "bound, so a step that reaches it has stopped answering rather than run "
            "slowly; nothing was recorded for the run and cards/ was not touched"
        )
        self.argv = argv
        self.seconds = seconds
        self.output = output


# Every transcript under cards/ is committed, so no line in one may carry a path from the
# machine that produced it. The substitution lives at the writer, not at each call site:
# argv.json was rewritten and the .txt transcripts beside it were not, and a rule applied at
# one of two writers is the kind of gap that only surfaces in a diff somebody happens to read.
PATH_NAMES: list[tuple[str, str]] = []


def name_path(found: object, name: str) -> None:
    """Register a root whose absolute form must never reach a committed file."""
    text = str(found)
    if text and (text, name) not in PATH_NAMES:
        PATH_NAMES.append((text, name))
        # Longest first: $PROJECT lives inside $BANK, and replacing the shorter one first
        # would leave the tail of the longer path behind with a name glued to the front.
        PATH_NAMES.sort(key=lambda pair: len(pair[0]), reverse=True)


def neutralise(text: str) -> str:
    """The same text with every registered root replaced by its name."""
    for found, name in PATH_NAMES:
        text = text.replace(found, name)
    return text


# How long one step may run before the sweep kills it. The guide's calibrator never gives
# itself more than CALIBRATION_TIMEOUT_CEILING_SECONDS = 900 by default
# (skills/traigent-first-run/scripts/calibrate_evaluator.py:103 at the pin), and a
# calibration that spends all of it still has to stop its worker and write the result
# that says so: `slow-scorer` measured at the default budget exited at 900 seconds with
# `timed_out: true`, and that record is the finding. So this bound sits ABOVE the guide's,
# by the headroom the guide's own harness allows the same command for exactly that
# teardown (CALIBRATION_TIMEOUT_HEADROOM_SECONDS = 60, tests/behavioral/harness.py:130 at
# the pin). The guide's budget decides every run that finishes; this one only ends a step
# that has stopped answering, which the sweep otherwise waited on for ever.
GUIDE_CALIBRATION_CEILING_SECONDS = 900
STEP_HEADROOM_SECONDS = 60
STEP_TIMEOUT_SECONDS = GUIDE_CALIBRATION_CEILING_SECONDS + STEP_HEADROOM_SECONDS

# The only variables a step inherits. Every step runs code that is not this script's --
# `build.py`, the guide's scripts, and through `calibrate_evaluator.py --allow-execution`
# the project's own evaluator -- and each used to inherit the whole shell it was started
# from: every provider key, database URL and token the operator had exported. Preflight
# also WRITES what it finds there into the card ("no LLM provider credential names are
# present", "traigent-key: not configured yet"), so the committed evidence depended on
# whose shell measured it.
#
# Four are passed through from the operator's shell when it has them: PATH to find the
# interpreter, LANG and LC_ALL for the text encoding, TMPDIR for where the calibrator's
# temporary files may go. They are the variables in the guide's own behavioural-harness
# environment (tests/behavioral/harness.py `command_environment` at the pin) that describe
# the machine; that harness sets fixed values for them, and this sweep passes the
# operator's own instead, so the locale a card was taken under is the operator's.
#
# HOME is NOT the operator's. Each step gets an empty directory of its own, made when it
# starts and removed when it ends, so nothing a library looks for under HOME by its default
# name -- a `~/.netrc`, `~/.aws/credentials`, the SDK's own config -- is found, and nothing
# one step writes there (the calibrator imports the project's evaluator) is found by the
# next. That is a default
# closed, not a sandbox: a path spelled out in full is still readable. What the sweep's own
# interpreter imports from the user site (`pip install --user`, which is where the SDK is
# on some machines) is still importable, because that site is named for the step through
# PYTHONUSERBASE rather than found through HOME.
#
# The guide sets what it needs beyond these itself -- the calibrator's worker gets
# `TRAIGENT_OFFLINE_MODE` and the local price map from `subprocess_environment`, and
# preflight sets the price map too.
STEP_ENVIRONMENT = ("PATH", "LANG", "LC_ALL", "TMPDIR")


def calibration_step_seconds(budget: int | None) -> int:
    """The bound on a calibration step: the budget the guide gives it, plus the headroom.

    The same derivation the guide's harness makes for the same command -- an explicit
    `--timeout` where one is passed, the ceiling where none is -- so `slow-scorer`, which
    states a five-second budget, is killed by its own calibrator and never by this sweep.
    """
    return (
        GUIDE_CALIBRATION_CEILING_SECONDS if budget is None else budget
    ) + STEP_HEADROOM_SECONDS


def step_environment(home: Path) -> dict[str, str]:
    """What a step is given: `STEP_ENVIRONMENT`, `home` as HOME, and the user site."""
    given = {name: os.environ[name] for name in STEP_ENVIRONMENT if name in os.environ}
    given["HOME"] = str(home)
    if site.ENABLE_USER_SITE:
        given["PYTHONUSERBASE"] = site.getuserbase()
    return given


# How much of a killed step's output its log keeps: the first 4,000 characters, and a count
# of the rest, which is what the guide's harness keeps of a command it kills
# (TIMEOUT_CAPTURE_LIMIT = 4_000, tests/behavioral/harness.py at the pin) -- the start, where
# the invocation's own errors and the phases it opened with are, and short enough that a
# runaway printer cannot bury the line that says it was killed.
KILLED_OUTPUT_LIMIT = 4_000


def killed_output(text: str) -> str:
    """The start of a killed step's output, and how much was dropped after it."""
    if len(text) <= KILLED_OUTPUT_LIMIT:
        return text
    dropped = len(text) - KILLED_OUTPUT_LIMIT
    return f"{text[:KILLED_OUTPUT_LIMIT]}\n[+{dropped} characters dropped]\n"


def end_group(group: int) -> None:
    """Kill every process left in a step's group; a group already empty is fine.

    After a normal finish this runs once the step itself has been reaped. On Linux, while any
    member of its group is alive the group's id cannot be handed out again; once none is, a
    new process could in principle take that id as its own group before this call, and would
    be killed with it. That window is left open deliberately: closing it would mean replacing
    `communicate()`'s reap -- waiting with `os.waitid(..., WEXITED | WNOWAIT)` and killing the
    group before the leader is reaped -- for a race no sweep has met.
    """
    with contextlib.suppress(ProcessLookupError, PermissionError):
        os.killpg(group, signal.SIGKILL)


def run_step(
    argv: list[str], cwd: Path, *, merge_stderr: bool, seconds: int
) -> subprocess.CompletedProcess[str]:
    """Run one step in a session of its own, under a budget, with the minimal environment.

    A session of its own because the step is rarely one process: the calibrator runs the
    evaluator in a worker, and killing only the calibrator leaves that worker holding the
    pipe this call is reading, so the wait never ends. The whole group is killed instead.

    The session is also why the group is killed on every other way out. A terminal's
    Ctrl-C goes to its foreground group, which a step in its own session is not in, so an
    interrupt of this script used to leave the step -- the evaluator, with execution
    allowed -- running on after it. And a step that exits leaving a child of its own
    behind leaves that child in the group, so the group is ended once the step's output is
    read, however it finished.
    """
    home = Path(tempfile.mkdtemp(prefix="score-bank-home-"))
    try:
        with subprocess.Popen(
            argv,
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT if merge_stderr else subprocess.PIPE,
            text=True,
            env=step_environment(home),
            start_new_session=True,
        ) as child:
            try:
                stdout, stderr = child.communicate(timeout=seconds)
            except subprocess.TimeoutExpired:
                end_group(child.pid)
                said, complained = child.communicate()
                raise StepTimedOut(
                    argv,
                    seconds,
                    killed_output(homeless((said or "") + (complained or ""), home)),
                ) from None
            except BaseException:
                end_group(child.pid)
                child.communicate()
                raise
            end_group(child.pid)
    finally:
        shutil.rmtree(home, ignore_errors=True)
    return subprocess.CompletedProcess(
        argv, child.returncode, homeless(stdout, home), homeless(stderr or "", home)
    )


def homeless(text: str, home: Path) -> str:
    """A step's output with its throwaway HOME written as `$HOME`, as the operator's is.

    Replaced here rather than registered with `name_path`, because the directory lives only
    as long as the step: registered, every step of a sweep left a dead name behind in the
    list every committed file is rewritten through.

    Both spellings are replaced, the path as made and the path as resolved: behind a
    symlinked temporary directory a step that resolves its HOME prints the second, which
    need not contain the first. The longer goes first, so a spelling that ends with the
    other is not left half-replaced -- on macOS, where /var links to /private/var, the
    resolved path is the made one with /private in front.
    """
    for spelling in sorted({str(home), str(home.resolve())}, key=len, reverse=True):
        text = text.replace(spelling, "$HOME")
    return text


def killed_log(argv: list[str], log: Path, killed: StepTimedOut) -> None:
    """What a killed step said before it was killed, where its transcript would be."""
    log.write_text(
        neutralise(
            "$ "
            + " ".join(argv)
            + "\n"
            + killed.output
            + f"killed after {killed.seconds} seconds by the sweep's step budget\n"
        ),
        encoding="utf-8",
    )


def capture(
    argv: list[str], cwd: Path, log: Path, seconds: int = STEP_TIMEOUT_SECONDS
) -> subprocess.CompletedProcess[str]:
    """Run one command, writing the invocation, the whole output and the exit status."""
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        done = run_step(argv, cwd, merge_stderr=True, seconds=seconds)
    except StepTimedOut as killed:
        killed_log(argv, log, killed)
        raise
    log.write_text(
        neutralise(
            "$ " + " ".join(argv) + "\n" + done.stdout + f"exit={done.returncode}\n"
        ),
        encoding="utf-8",
    )
    return done


def capture_json(
    argv: list[str],
    cwd: Path,
    log: Path,
    out: Path,
    seconds: int = STEP_TIMEOUT_SECONDS,
) -> subprocess.CompletedProcess[str]:
    """The same, for a command whose stdout is the JSON another step reads."""
    log.parent.mkdir(parents=True, exist_ok=True)
    try:
        done = run_step(argv, cwd, merge_stderr=False, seconds=seconds)
    except StepTimedOut as killed:
        killed_log(argv, log, killed)
        raise
    out.write_text(neutralise(done.stdout), encoding="utf-8")
    log.write_text(
        neutralise(
            "$ " + " ".join(argv) + "\n" + done.stderr + f"exit={done.returncode}\n"
        ),
        encoding="utf-8",
    )
    return done


# Read out of the guide being measured rather than assumed here: which fields each half of
# an --agent-knobs document may carry are readiness.py's own constants, so the check below
# asks the revision in front of it instead of keeping a second copy of a contract that has
# already moved twice. The three constants are the three independently editable contracts
# the guide enforces on these two documents: the top level, the knobs half, the build half.
#
# The same import answers one more question, which is what the guide can say at all: every
# cap condition it can raise, with the remedy and the ranked ceiling it gives each. Read
# from `CAP_CEILING` and `ACTION_FOR_CONDITION`, the two tables `readiness.py` holds equal
# by its own test, so the vocabulary the cards are checked against is the pinned guide's
# and never a list kept here. `results.json` records it beside the runs.
CONTRACT_PROBE = """
import importlib.util
import json
import sys

located = importlib.util.spec_from_file_location("_pinned_readiness", sys.argv[1])
module = importlib.util.module_from_spec(located)
# Registered before it runs: readiness.py builds dataclasses at import, and
# @dataclass resolves annotations through sys.modules[cls.__module__].
sys.modules[located.name] = module
located.loader.exec_module(module)


def listed(name):
    found = getattr(module, name, None)
    if isinstance(found, dict):
        return {key: sorted(names) for key, names in found.items()}
    if isinstance(found, (set, frozenset)):
        return sorted(found)
    return None


def conditions():
    ceilings = getattr(module, "CAP_CEILING", None)
    remedies = getattr(module, "ACTION_FOR_CONDITION", None)
    if not isinstance(ceilings, dict) or not isinstance(remedies, dict):
        return None
    return {
        condition: {"action": remedies.get(condition), "ceiling": ceilings[condition]}
        for condition in sorted(ceilings)
    }


print(
    json.dumps(
        {
            "document": listed("AGENT_KNOBS_DOCUMENT_FIELDS"),
            "knob": listed("DISCOVERED_KNOB_FIELDS"),
            "build": listed("BUILD_CHECK_FIELDS"),
            "conditions": conditions(),
        }
    )
)
"""

# The one thing the guide does not publish as data: which fields it *requires*. Its
# requiredness lives in `readiness.py`'s control flow, not in a constant, so this name is
# read by a human and written here -- the single hardcoded coordinate in this check, and the
# reason `unchecked` below says out loud what the probe could not derive.
REQUIRED_BUILD_FIELD = "source_lines"


def read_guide(scripts: Path) -> dict[str, Any]:
    """What `CONTRACT_PROBE` reads out of the guide's `readiness.py`, as an object."""
    probe = run_step(
        [sys.executable, "-c", CONTRACT_PROBE, str(scripts / "readiness.py")],
        HERE,
        merge_stderr=False,
        seconds=STEP_TIMEOUT_SECONDS,
    )
    if probe.returncode != 0:
        raise HarnessFault(
            "the guide's readiness.py could not be read for its document contracts: "
            f"{probe.stderr.strip() or probe.stdout.strip()}"
        )
    try:
        contracts = json.loads(probe.stdout)
    except ValueError as error:
        # The same defect this script exists to remove, in the gate that removes it: a
        # bare decoder traceback where a sentence belongs. Any print at import time in a
        # future readiness.py lands here.
        said = [line.strip() for line in probe.stdout.splitlines() if line.strip()]
        raise HarnessFault(
            "the guide's readiness.py printed something other than its document "
            "contracts when this script asked for them: "
            + (said[0] if said else "nothing at all")
        ) from error
    if not isinstance(contracts, dict):
        raise HarnessFault(
            f"the contract probe answered with a {type(contracts).__name__}, not an object"
        )
    return contracts


def contract_mismatch(contracts: dict[str, Any]) -> tuple[list[str], list[str]]:
    """Where the guide in front of us and the documents beside us disagree, in its terms.

    The pin and the documents' schema are two independently editable facts. This check
    detects disagreement before anything is built, against `readiness.py`'s own field
    constants rather than against a copy of them kept in this file.

    Returns the disagreements and, beside them, what could not be checked at all -- a
    revision that renames or reshapes one of those constants makes this gate a no-op for
    that half, and a gate that has quietly stopped gating has to say so on the way past.

    What it does *not* claim to derive: requiredness. Requiredness is not expressible from
    field constants alone, so the settled/undetermined distinction is read from the document
    exactly as the guide reads it, and the field name is written down above.
    """
    complaints: list[str] = []
    unchecked: list[str] = []
    for half, label in (
        ("document", "the document's top level"),
        ("knob", "a knob"),
        ("build", "a build check"),
    ):
        if contracts.get(half) is None:
            unchecked.append(
                f"this revision publishes no field list for {label}, so that half of "
                "every document went unchecked"
            )

    for document in sorted(KNOBS.glob("*.json")):
        read = ours(document, "an --agent-knobs document this sweep hands to the guide")
        top = contracts.get("document")
        if isinstance(top, list):
            unknown = sorted(set(read) - set(top))
            if unknown:
                complaints.append(
                    f"{document.name}: carries {', '.join(unknown)} at the top level, "
                    "which this revision does not read"
                )
        knob_fields = contracts.get("knob")
        if isinstance(knob_fields, list):
            for knob, spec in sorted(read.get("knobs", {}).items()):
                if not isinstance(spec, dict):
                    continue
                unknown = sorted(set(spec) - set(knob_fields))
                if unknown:
                    complaints.append(
                        f"{document.name}: knob {knob!r} carries {', '.join(unknown)}, "
                        "which this revision does not read"
                    )
        build_fields = contracts.get("build")
        if not isinstance(build_fields, dict):
            continue
        for check, spec in sorted(read.get("build", {}).items()):
            allowed = build_fields.get(check)
            if allowed is None or not isinstance(spec, dict):
                continue
            unknown = sorted(set(spec) - set(allowed))
            if unknown:
                complaints.append(
                    f"{document.name}: build check {check!r} carries "
                    f"{', '.join(unknown)}, which this revision does not read"
                )
            # Two `if`s, not an `elif`: a check wrong in both ways said so once, was
            # repaired, and refused again on the second complaint.
            settled = spec.get("determined") is not False
            cited = REQUIRED_BUILD_FIELD in spec
            if settled and not cited and REQUIRED_BUILD_FIELD in allowed:
                complaints.append(
                    f"{document.name}: build check {check!r} is settled and carries no "
                    f"{REQUIRED_BUILD_FIELD!r}, which this revision reads"
                )
            # The mirror image, and the reason the arm above tests `settled` at all: an
            # undetermined check has no line establishing it by construction, so the guide
            # refuses a citation on one. Requiring it there would push an honest "I could
            # not settle this" into an invented coordinate, which is the opposite of what
            # the guide asks a read to do.
            if not settled and cited:
                complaints.append(
                    f"{document.name}: build check {check!r} is undetermined and still "
                    f"cites {REQUIRED_BUILD_FIELD!r}, which this revision refuses"
                )
    return complaints, unchecked


def ours(path: Path, what: str) -> Any:
    """One of our own JSON files, read as ours.

    The same conflation the exception split removed, thirty lines from where it was
    removed: an unreadable file of *ours* used to leave through the bare decoder, which
    exits on the status this script documents as "the guide refused one or more runs".
    Whose fault it was is known here too, so it is said here too.
    """
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise HarnessFault(
            f"{what} could not be read ({path.name}): {error}"
        ) from error


def decoded(
    done: subprocess.CompletedProcess[str], step: str
) -> dict[str, Any] | list[Any]:
    """The JSON one step printed, or a refusal naming the step and its own words.

    The reason is the tool's stderr rather than the decoder's complaint: "Refusing to
    calibrate: ..." is the answer, and "Expecting value: line 1 column 1" is only the
    shape of the answer's absence. The transcript beside the empty JSON file already
    holds the whole output; this keeps the first line of it in `results.json`, where
    the row for the refused run is.
    """
    try:
        found = json.loads(done.stdout)
    except ValueError as error:
        said = [
            line.strip()
            for line in (done.stderr or done.stdout or "").splitlines()
            if line.strip()
        ]
        raise GuideRefused(
            step,
            done.returncode,
            said[0] if said else "it printed nothing at all",
        ) from error
    if not isinstance(found, (dict, list)):
        raise GuideRefused(
            step, done.returncode, f"printed a bare {type(found).__name__}"
        )
    return found


def declared_origin(component: dict[str, Any], tag: str) -> str:
    """Who wrote a component, as its record declares; a record that does not is a fault.

    A shipped component with no valid origin in its record is a record this sweep cannot
    declare from, and guessing `brought` for it is the default this replaced.
    """
    origin = component.get("origin")
    if origin not in ("brought", "generated"):
        raise HarnessFault(
            f"the record build.py wrote for {tag!r} declares no valid origin for "
            f"{component.get('path')} ({origin!r})"
        )
    return str(origin)


def present(component: dict[str, Any] | None) -> dict[str, Any] | None:
    """A component that shipped a file, or None. A record with no path shipped nothing."""
    return component if component and component.get("path") else None


def readiness_command(
    *,
    scripts: pathlib.Path,
    room: pathlib.Path,
    project: pathlib.Path,
    agent: dict[str, Any] | None,
    evaluator: dict[str, Any] | None,
    calibrated: bool,
    declared: str | None,
    task_kind: str,
    tag: str,
) -> list[str]:
    """The readiness call for one built project, from what its record declares.

    `agent` is None when the sweep passes no agent read. Each origin comes from the
    record through `declared_origin`, so what the card says of who wrote a component is
    what the builder declared and never a default of this script's.
    """
    readiness = [
        sys.executable,
        str(scripts / "readiness.py"),
        "--preflight",
        str(room / "02-preflight.json"),
    ]
    if agent:
        document = KNOBS / (
            "no-knobs.json" if agent["state"] == "no-knobs" else "ready.json"
        )
        readiness += [
            "--agent-knobs",
            str(document),
            "--agent-source-root",
            str(project),
            "--selected-agent",
            str(project / agent["path"]),
            "--selected-agent-callable",
            "run",
            "--agent-origin",
            declared_origin(agent, tag),
        ]
    if calibrated:
        readiness += ["--calibration", str(room / "03-calibration.json")]
    if evaluator:
        readiness += ["--evaluator-origin", declared_origin(evaluator, tag)]
    if declared:
        readiness += ["--evaluator-method", declared]
    return readiness + ["--task-kind", task_kind, "--color", "never", "--ascii"]


def score_one(
    tag: str,
    build_flags: tuple[str, ...],
    scripts: Path,
    workspace: Path,
    staging: Path,
    *,
    agent_knobs: bool = True,
    force_execution_calibration: bool = False,
    method: str | None = None,
    task_kind: str = "code-sql",
    input_field: str | None = None,
    expected_field: str | None = None,
    calibration_timeout: int | None = None,
) -> dict[str, Any]:
    """Build one demo and score it the way the guide's opening gate scores it."""
    out = workspace / tag
    if out.exists():
        shutil.rmtree(out)
    # Written outside the repository and promoted over `cards/` only by a sweep that got
    # far enough to be worth publishing. `cards/` is the committed evidence a reader runs
    # this script to check, and a run that refuses everything used to overwrite all of it
    # on its way to saying so.
    room = staging / tag
    if room.exists():
        shutil.rmtree(room)
    room.mkdir(parents=True)

    # Registered before the first command runs, so every transcript this call writes is
    # neutral. Order does not matter here -- name_path keeps the roots longest-first.
    name_path(scripts, "$GUIDE")
    name_path(out / "project", "$PROJECT")
    name_path(out, "$DEMO")
    name_path(workspace, "$BANK")
    name_path(room, "$EVIDENCE")
    name_path(KNOBS, "$KNOBS")
    name_path(REPO_ROOT, "$REPO")
    name_path(pathlib.Path.home(), "$HOME")
    name_path(sys.executable, "python3")

    # One command, run and recorded: `argv.json` once rebuilt this list by hand and left
    # out the `demo` subcommand, so the command it recorded was not the one that ran.
    build_command = [
        sys.executable,
        "build.py",
        "demo",
        *build_flags,
        "--out",
        str(out),
    ]
    built = capture(
        build_command,
        REPO_ROOT,
        room / "01-build.txt",
    )
    if built.returncode != 0:
        said = [line.strip() for line in built.stdout.splitlines() if line.strip()]
        # Ours, so it is not a row and it does not reach the promotion decision at all:
        # this repository's builder failing says nothing about the guide, and a sweep
        # that cannot build cannot publish. The transcript is already on disk.
        raise HarnessFault(
            f"build.py exited {built.returncode} building {tag!r}: "
            + (said[-1] if said else "it printed nothing at all")
        )

    project = out / "project"
    components = ours(out / "demo.json", f"the record build.py wrote for {tag!r}")[
        "components"
    ]
    agent = present(components.get("agent"))
    dataset = present(components.get("dataset"))
    evaluator = present(components.get("evaluator"))

    preflight = [
        sys.executable,
        str(scripts / "preflight.py"),
        "--defer-missing-sdk",
        "--json",
    ]
    if agent:
        preflight += ["--models", ",".join(agent["models"])]
    if dataset:
        preflight += ["--dataset", dataset["path"]]
        # Only where a variant declares them. The preset itself is scored the way the
        # tools read a file unaided, which for `raw-export` is under names it does not
        # use; the declaration is what a run that opened the file would add.
        if input_field:
            preflight += ["--input-field", input_field]
        if expected_field:
            preflight += ["--expected-field", expected_field]
    declared = None
    if evaluator:
        preflight += ["--evaluator", evaluator["path"]]
        declared = method or evaluator.get("method")
        if declared:
            preflight += ["--evaluator-method", declared]
    decoded(
        capture_json(
            preflight,
            project,
            room / "02-preflight-stderr.txt",
            room / "02-preflight.json",
        ),
        "preflight.py",
    )

    calibrated = False
    calibration_passed = None
    probes = evaluator.get("calibration") if evaluator else None
    if evaluator and probes:
        executes = bool(evaluator.get("executes_candidate_output"))
        if not executes or force_execution_calibration:
            done = capture_json(
                [
                    sys.executable,
                    str(scripts / "calibrate_evaluator.py"),
                    "--scorer",
                    f"{evaluator['path']}:score",
                    "--import-root",
                    str(project),
                    "--cases",
                    "@" + probes["path"],
                    "--kind",
                    "deterministic",
                    "--allow-execution",
                    "--json",
                ]
                + (
                    # With no `--timeout` the guide budgets this calibration at 900
                    # seconds, and `slow-scorer` reaches the timeout there: each authored
                    # probe takes two minutes, so even the guide's two-case minimum runs
                    # out. That was measured at the pin, with four cases and with two,
                    # and each run took the whole fifteen minutes; making every
                    # reproduction of this sweep wait that long to watch a clock run
                    # out would be a poor trade for a cap that is about cost. So the
                    # budget is stated instead of endured: 5 seconds, which the first
                    # call already outlasts. The timeout is reached in the same phase
                    # and read the same way -- the default-budget run scored the same
                    # 45 `evaluator-timeout` -- and the card records the budget it was
                    # reached under.
                    ["--timeout", str(calibration_timeout)]
                    if calibration_timeout is not None
                    else []
                ),
                project,
                room / "03-calibration-stderr.txt",
                room / "03-calibration.json",
                seconds=calibration_step_seconds(calibration_timeout),
            )
            calibrated = True
            # A refusal is named here rather than left to the readiness step, which
            # would report the empty calibration file it was handed ("cannot read
            # scoring input") instead of the guide's own reason for declining.
            report = decoded(done, "calibrate_evaluator.py")
            calibration_passed = (
                report.get("passed") if isinstance(report, dict) else None
            )

    readiness = readiness_command(
        scripts=scripts,
        room=room,
        project=project,
        agent=agent if agent_knobs else None,
        evaluator=evaluator,
        calibrated=calibrated,
        declared=declared,
        task_kind=task_kind,
        tag=tag,
    )

    capture(readiness, project, room / "04-readiness-card.txt")
    done = capture_json(
        readiness + ["--json"],
        project,
        room / "05-readiness-stderr.txt",
        room / "05-readiness.json",
    )
    card = decoded(done, "readiness.py")
    if not isinstance(card, dict):
        raise GuideRefused("readiness.py", done.returncode, "printed no card object")

    def portable(argv: list[str]) -> list[str]:
        """The same command with this machine's paths replaced by names."""
        return [neutralise(piece) for piece in argv]

    (room / "argv.json").write_text(
        json.dumps(
            {
                "build": portable(build_command),
                "preflight": portable(preflight),
                "calibration_ran": calibrated,
                "readiness": portable(readiness),
            },
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    shutil.rmtree(out)

    pillars = {pillar["name"]: pillar["score"] for pillar in card["pillars"]}
    return {
        "tag": tag,
        "overall": card["overall"],
        "band": card["band"],
        "recommended_action": card["recommended_action"],
        "status": card["status"],
        "confidence": card["confidence"],
        "pillars": pillars,
        "caps": [
            {
                "condition": cap["condition"],
                "ceiling": cap["ceiling"],
                "blocks": cap["blocks"],
                "action_kind": cap["action_kind"],
                "reason": cap["reason"],
            }
            for cap in card["caps"]
        ],
        "declared_evaluator_method": declared,
        "declared_task_kind": task_kind,
        "calibration_ran": calibrated,
        "calibration_passed": calibration_passed,
    }


def agent_requirement_version() -> str:
    """The litellm version `build.py` pins, read from its source without importing it."""
    tree = ast.parse((REPO_ROOT / "build.py").read_text(encoding="utf-8"))
    for node in tree.body:
        if (
            isinstance(node, ast.Assign)
            and any(
                isinstance(target, ast.Name) and target.id == "AGENT_REQUIREMENT"
                for target in node.targets
            )
            and isinstance(node.value, ast.Constant)
            and isinstance(node.value.value, str)
            and node.value.value.startswith("litellm==")
        ):
            return node.value.value.removeprefix("litellm==")
    raise HarnessFault("build.py pins no `litellm==` version in AGENT_REQUIREMENT")


def recorded_environment() -> dict[str, str]:
    """The environment the committed cards were measured in, read from the cards.

    `python` and `traigent` are what preflight printed on every card that scored, and they
    have to agree across all of them. `litellm` is not on a card: preflight imports it for
    its price checks without printing which version it found, so the version given is the
    one this repository and the guide install (`build.py`'s `AGENT_REQUIREMENT`), which is
    the version the committed cards reproduce under.
    """
    record = ours(CARDS / "results.json", "the committed cards/results.json")
    if record.get("guide_revision") != PINNED_REVISION:
        raise HarnessFault(
            f"cards/results.json records guide {record.get('guide_revision')} and the pin "
            f"is {PINNED_REVISION}; the record and the pin disagree"
        )
    seen: dict[str, set[str]] = {"python": set(), "traigent": set()}
    for run in record.get("runs", []):
        if run.get("refused"):
            continue
        preflight = ours(
            CARDS / run["tag"] / "02-preflight.json",
            f"the committed preflight record of {run['tag']!r}",
        )
        checks = {check.get("check"): check for check in preflight}
        try:
            seen["python"].add(str(checks["python-version"]["detail"]))
            metrics = checks["sdk-version"].get("metrics") or {}
        except KeyError as missing:
            raise HarnessFault(
                f"the committed preflight record of {run['tag']!r} has no {missing} check"
            ) from missing
        seen["traigent"].add(str(metrics.get("installed", "absent")))
    for name, values in seen.items():
        if len(values) != 1:
            raise HarnessFault(
                f"the committed cards do not agree on one {name}: {sorted(values)}"
            )
    return {
        "guide": PINNED_REVISION,
        "python": seen["python"].pop(),
        "traigent": seen["traigent"].pop(),
        "litellm": agent_requirement_version(),
    }


def installed(distribution: str) -> str:
    """The installed version of a distribution in this interpreter, or `absent`."""
    try:
        return importlib.metadata.version(distribution)
    except importlib.metadata.PackageNotFoundError:
        return "absent"


def environment_mismatch(recorded: dict[str, str]) -> list[str]:
    """Where this interpreter differs from the one the committed cards were measured in.

    The guide's scripts run under this interpreter, and preflight writes its version and the
    SDK's into every card, so a comparison made anywhere else differs on every card for a
    reason that has nothing to do with the guide.
    """
    here = {
        "python": sys.version.split()[0],
        "traigent": installed("traigent"),
        "litellm": installed("litellm"),
    }
    return [
        f"{name} is {here[name]} here and {recorded[name]} on the committed cards"
        for name in ("python", "traigent", "litellm")
        if here[name] != recorded[name]
    ]


def compare_with_record(
    staging: Path, only: Sequence[str] | None = None
) -> tuple[list[str], int, list[str]]:
    """What a fresh measurement under `staging` says that the committed record does not.

    Returns the differences, how many cards were compared byte for byte, and the runs the
    record says were refused. A refused run's committed directory is the older card
    `--publish` deliberately leaves in place, so there is nothing fresh to compare it with;
    its refusal is compared instead, as a row of `results.json`, which is compared whole.

    With `only`, the comparison is of those runs and nothing else: their cards, their rows
    of `results.json`, and the guide's recorded vocabulary, which every sweep reads. A run
    named there that the record does not hold is a difference -- a subset that compares a
    card nobody has published agrees with nothing, it does not agree with everything.
    """
    record = ours(CARDS / "results.json", "the committed cards/results.json")
    differences: list[str] = []
    if only is None:
        fresh_table = (staging / "results.json").read_bytes()
        if fresh_table != (CARDS / "results.json").read_bytes():
            differences.append(
                "results.json: "
                + first_difference(
                    (CARDS / "results.json").read_bytes().decode("utf-8"),
                    fresh_table.decode("utf-8"),
                )
            )
        rows = record.get("runs", [])
    else:
        fresh = ours(staging / "results.json", "this run's own results.json")
        for field in ("guide_revision", "conditions"):
            if fresh.get(field) != record.get(field):
                differences.append(
                    f"results.json: {field} differs from the committed record"
                )
        committed_rows = {row["tag"]: row for row in record.get("runs", [])}
        fresh_rows = {row["tag"]: row for row in fresh.get("runs", [])}
        rows = []
        for tag in only:
            if tag not in committed_rows:
                differences.append(f"results.json: no committed row for {tag}")
                continue
            rows.append(committed_rows[tag])
            if fresh_rows.get(tag) != committed_rows[tag]:
                differences.append(
                    f"results.json row {tag}: "
                    + first_difference(
                        json.dumps(committed_rows[tag], indent=2),
                        json.dumps(fresh_rows.get(tag), indent=2),
                    )
                )
    runs = [run["tag"] for run in rows]
    refused = [run["tag"] for run in rows if run.get("refused")]
    compared = 0
    for tag in runs:
        if tag in refused:
            continue
        committed, produced = files_under(CARDS / tag), files_under(staging / tag)
        for name in sorted(set(committed) | set(produced)):
            if name not in produced:
                differences.append(f"{tag}/{name}: committed, and not produced now")
            elif name not in committed:
                differences.append(f"{tag}/{name}: produced now, and not committed")
            elif committed[name] != produced[name]:
                differences.append(
                    f"{tag}/{name}: "
                    + first_difference(
                        committed[name].decode("utf-8", "replace"),
                        produced[name].decode("utf-8", "replace"),
                    )
                )
        compared += 1
    if only is None:
        unmeasured = sorted(
            entry.name
            for entry in CARDS.iterdir()
            if entry.is_dir() and entry.name not in runs
        )
        for name in unmeasured:
            differences.append(
                f"{name}/: a committed card no run in the record produces"
            )
    if (only is None and compared == 0) or compared != len(runs) - len(refused):
        differences.append(
            f"compared {compared} cards where the record has {len(runs) - len(refused)} "
            "that scored; a comparison of nothing agrees with everything"
        )
    return differences, compared, refused


def merged_record(fresh: dict[str, Any]) -> dict[str, Any]:
    """The committed `results.json` with the rows a partial sweep measured put in.

    Every other row stays exactly as committed, and the rows keep the order a whole sweep
    writes them in, so the table a partial `--publish` leaves is the one a whole one would
    write wherever the runs it did not repeat still reproduce -- which is what the CI
    comparison of the whole bank then checks. Refused, rather than guessed at: a record
    taken at another revision, and a record holding a run this sweep no longer names.
    """
    committed = ours(CARDS / "results.json", "the committed cards/results.json")
    if committed.get("guide_revision") != fresh["guide_revision"]:
        raise HarnessFault(
            f"cards/results.json records guide {committed.get('guide_revision')} and "
            f"this run measured {fresh['guide_revision']}; a partial --publish cannot "
            "leave one table measured at two revisions"
        )
    order = [tag for tag, _, _ in sweep()]
    kept = {row["tag"]: row for row in committed.get("runs", [])}
    stray = sorted(set(kept) - set(order))
    if stray:
        raise HarnessFault(
            f"cards/results.json holds {', '.join(stray)}, which this sweep no longer "
            "names; a whole --publish rewrites the table"
        )
    measured = {row["tag"]: row for row in fresh["runs"]}
    return {
        "guide_revision": fresh["guide_revision"],
        "conditions": fresh["conditions"],
        "runs": [
            measured.get(tag, kept.get(tag))
            for tag in order
            if tag in measured or tag in kept
        ],
    }


def files_under(directory: Path) -> dict[str, bytes]:
    """Every file in one card directory, by name. A missing directory holds nothing."""
    if not directory.is_dir():
        return {}
    return {
        str(found.relative_to(directory)): found.read_bytes()
        for found in sorted(directory.rglob("*"))
        if found.is_file()
    }


def first_difference(committed: str, fresh: str) -> str:
    """The first line on which two texts differ, both sides of it, and where."""
    old, new = committed.splitlines(), fresh.splitlines()
    for number, (was, now) in enumerate(zip(old, new), start=1):
        if was != now:
            return f"line {number} was {was.strip()[:160]!r}, now {now.strip()[:160]!r}"
    return f"{len(old)} lines committed, {len(new)} produced now"


def harness_fault(broken: HarnessFault, staging: Path | None) -> int:
    """Say it in a sentence, publish nothing, and exit on a status of its own.

    Loud, because it is ours: a sweep that cannot measure has nothing to say about the
    guide and no business rewriting the evidence that says what the guide answered when it
    could. It is not a traceback, because a traceback is what this script's first repair
    existed to remove, and re-introducing one in the handler that removes it would be the
    same defect wearing the fix's clothes.
    """
    print(f"\nHARNESS FAULT: {broken}", file=sys.stderr)
    print(
        "This is a fault in this repository, not a refusal by the guide, so no row was "
        "recorded for it and cards/ was not touched.",
        file=sys.stderr,
    )
    if staging is not None:
        print(
            f"What the sweep produced before it stopped is under {staging}.",
            file=sys.stderr,
        )
    return 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--guide",
        type=Path,
        help="a traigent-first-run checkout; its skills/traigent-first-run/scripts are run",
    )
    parser.add_argument(
        "--revision",
        default=PINNED_REVISION,
        help=f"the guide commit to measure at (default: {PINNED_REVISION[:8]}); "
        "the checkout must be sitting on it",
    )
    parser.add_argument(
        "--workspace",
        type=Path,
        default=Path("/tmp/readiness-bank"),
        help="where demos are built and then deleted (default: /tmp/readiness-bank)",
    )
    outcome = parser.add_mutually_exclusive_group()
    outcome.add_argument(
        "--publish",
        action="store_true",
        help="replace the committed evidence under cards/ with what this run produced; "
        "without it the run writes to the workspace and cards/ is left alone",
    )
    outcome.add_argument(
        "--compare",
        action="store_true",
        help="compare what this run produced with the committed cards, byte for byte, "
        "and exit 4 if they differ; publishes nothing",
    )
    outcome.add_argument(
        "--recorded-environment",
        action="store_true",
        help="print the guide revision, Python, traigent and litellm the committed "
        "cards were measured with, as name=value lines, and exit",
    )
    parser.add_argument(
        "--only",
        nargs="+",
        metavar="RUN",
        help="measure these runs and no others: with --compare, compare their cards "
        "and their rows of results.json; with --publish, replace their cards and put "
        "their rows into the committed results.json, leaving every other row as it is",
    )
    arguments = parser.parse_args()

    if arguments.recorded_environment:
        if arguments.only:
            parser.error(
                "--recorded-environment reads the committed record whole and measures "
                "nothing, so --only has no runs to name for it"
            )
        try:
            recorded = recorded_environment()
        except HarnessFault as broken:
            return harness_fault(broken, None)
        for name, value in recorded.items():
            print(f"{name}={value}")
        return 0
    if arguments.guide is None:
        parser.error("--guide is required to measure")
    runs = sweep()
    only: list[str] | None = None
    if arguments.only:
        only = list(dict.fromkeys(arguments.only))
        unknown = sorted(set(only) - {tag for tag, _, _ in runs})
        if unknown:
            parser.error(
                f"--only names runs the sweep does not make: {', '.join(unknown)}"
            )
        runs = [run for run in runs if run[0] in only]

    scripts = (
        arguments.guide.expanduser().resolve()
        / "skills"
        / "traigent-first-run"
        / "scripts"
    )
    if not (scripts / "readiness.py").is_file():
        parser.error(f"no readiness.py under {scripts}")
    workspace = arguments.workspace.expanduser().resolve()
    workspace.mkdir(parents=True, exist_ok=True)

    checkout = arguments.guide.expanduser().resolve()
    found = subprocess.run(
        ["git", "-C", str(checkout), "rev-parse", "HEAD"],
        stdout=subprocess.PIPE,
        stderr=subprocess.DEVNULL,
        text=True,
    ).stdout.strip()
    if not found:
        parser.error(
            f"{checkout} is not a git checkout, so its revision cannot be pinned"
        )
    if found != arguments.revision:
        parser.error(
            f"{checkout} is on {found[:8]}, not the pinned {arguments.revision[:8]}.\n"
            f"    git -C {checkout} checkout {arguments.revision}\n"
            "  measures what the committed cards say they measured. Pass --revision to "
            "re-measure somewhere else on purpose; the guide's input contracts change, and "
            "a table scored against a moved target is not the table it claims to be."
        )
    revision = found

    if arguments.compare:
        # The record was taken at the pin, so a comparison anywhere else compares two
        # different guides; and in another environment it compares two machines.
        if revision != PINNED_REVISION:
            parser.error(
                f"--compare needs the pinned revision {PINNED_REVISION[:8]}, the one the "
                "committed cards record"
            )
    # A partial publish writes some cards beside others it leaves as they were, so it has
    # to be taken where they were: a card from another interpreter is a record that
    # disagrees with itself about what it was measured on, which `--recorded-environment`
    # and the CI comparison of the whole bank both stop on. A whole publish rewrites every
    # card in one environment and needs no such check.
    if arguments.compare or (arguments.publish and only is not None):
        try:
            mismatch = environment_mismatch(recorded_environment())
        except HarnessFault as broken:
            return harness_fault(broken, None)
        if mismatch:
            parser.error(
                "this interpreter is not the environment the committed cards were "
                "measured in, so every card it made would differ for that reason "
                "alone:\n    "
                + "\n    ".join(mismatch)
                + "\n  `--recorded-environment` prints what to install."
            )

    # Before anything is built: the documents this sweep hands to `readiness.py`, against
    # the contract the checkout in front of us actually reads. A mismatch here is a
    # property of the pair, not of any one run, so it stops the sweep in one sentence
    # instead of 26 refusals over a rewritten cards/.
    try:
        contracts = read_guide(scripts)
        disagreements, unchecked = contract_mismatch(contracts)
    except HarnessFault as broken:
        return harness_fault(broken, None)
    vocabulary = contracts.get("conditions")
    if not isinstance(vocabulary, dict):
        vocabulary = None
        unchecked.append(
            "this revision publishes no condition table (CAP_CEILING and "
            "ACTION_FOR_CONDITION), so results.json records none and nothing checks "
            "the cards against what the guide can raise"
        )
    for gap in unchecked:
        # A gate that has become a no-op says so rather than passing silently.
        print(f"note: {gap}", file=sys.stderr)
    if disagreements:
        print(
            f"the documents under {KNOBS.name}/ and the guide at {revision[:8]} disagree "
            "about what they may carry:",
            file=sys.stderr,
        )
        for complaint in disagreements:
            print(f"  {complaint}", file=sys.stderr)
        remedy = (
            "Repair the documents for the revision in front of you"
            if revision == WORKING_REVISION
            else "Either measure at the revision these documents were written for -- as "
            f"committed here that is\n    --revision {WORKING_REVISION}\n-- or repair "
            "the documents for the revision in front of you"
        )
        print(
            f"\nNothing was built and cards/ was not touched. {remedy}. The pin and the "
            "documents are re-joined by the pending regeneration, which re-measures the "
            "whole table.",
            file=sys.stderr,
        )
        return 2

    staging = workspace / "cards-staging"
    if staging.exists():
        shutil.rmtree(staging)
    staging.mkdir(parents=True)

    results: list[dict[str, Any]] = []

    def measure(tag: str, flags: tuple[str, ...], **options: Any) -> None:
        """One run's row, whether it scored or was refused, and never both lost.

        A run that cannot be scored is a row that says so. The alternative -- the
        exception leaving this loop -- ended the sweep at the first refusal and threw
        away every run behind it, so a single unscorable configuration cost the whole
        bank and the table it feeds.

        Only `GuideRefused` is caught, and only the guide raises it. A `HarnessFault` --
        our builder, our probe, our own inputs -- leaves this loop and ends the sweep:
        recorded as a "refused" row it would read as the tool declining something, which
        is the one thing this vocabulary must not be able to say about our own bugs.
        """
        try:
            row = score_one(tag, flags, scripts, workspace, staging, **options)
        except GuideRefused as refusal:
            step = refusal.step
            reason = refusal.reason
            results.append(
                {
                    "tag": tag,
                    "refused": {
                        "step": step,
                        "exit": refusal.exit_code,
                        "reason": reason,
                    },
                    "overall": None,
                    "band": None,
                    "recommended_action": None,
                    "status": None,
                    "confidence": None,
                    "pillars": {},
                    "caps": [],
                    "declared_evaluator_method": options.get("method"),
                    "declared_task_kind": options.get("task_kind", "code-sql"),
                    "calibration_ran": None,
                    "calibration_passed": None,
                }
            )
            print(f"{tag:20s} REFUSED at {step}: {reason}", flush=True)
            return
        results.append(row)
        print(
            f"{tag:20s} {row['overall']:>3} {row['band']:10s} {row['recommended_action']}",
            flush=True,
        )

    try:
        for tag, flags, options in runs:
            measure(tag, flags, **options)
    except HarnessFault as broken:
        return harness_fault(broken, staging)

    record = {"guide_revision": revision, "conditions": vocabulary, "runs": results}
    (staging / "results.json").write_text(
        json.dumps(record, indent=2) + "\n", encoding="utf-8"
    )
    refused = [row for row in results if row.get("refused")]
    print(f"\nguide revision {revision}")

    if arguments.compare:
        try:
            differences, compared, recorded_refusals = compare_with_record(
                staging, only
            )
        except HarnessFault as broken:
            return harness_fault(broken, staging)
        print(
            f"compared {compared} cards byte for byte with cards/, and "
            + ("results.json whole" if only is None else "their rows of results.json")
            + (
                f"; refusals compared as recorded: {', '.join(recorded_refusals)}"
                if recorded_refusals
                else ""
            )
        )
        if differences:
            print(
                f"\nThe measurement differs from the committed record "
                f"({len(differences)}):"
            )
            for difference in differences:
                print(f"  {difference}")
            print(f"What this run produced is under {staging}")
            return 4
        print("The committed record reproduces.")
        return 0

    # Publishing is asked for, never assumed. `cards/` is committed evidence, and the
    # commonest reason to run this script is to CHECK that evidence rather than to
    # replace it -- so a plain run leaves it exactly as it is and says where its own
    # output went. The guard this replaces asked which step had refused, and a step it
    # did not know about published 26 empty rows over the whole directory.
    if not arguments.publish:
        print(f"cards/ not rewritten. What this run produced is under {staging}")
        print("Pass --publish to replace the committed evidence with it.")
    else:
        # Entry by entry, never the whole directory, and never for a run that did not
        # finish: a refused run's staged directory holds the two or three files it got
        # to before the refusal, and moving that over the committed card deletes the
        # rendered card and the argv record with it -- four files, at this revision, that
        # cannot be produced again. Promotion is a loop of moves rather than one atomic
        # rename, so an interruption leaves cards/ part old and part new; re-run it.
        incomplete = {row["tag"] for row in refused}
        # A partial sweep's own table holds only the runs it made, so the committed one
        # with those rows put in replaces it before promotion -- and before anything
        # moves, so a table that cannot be merged leaves every card where it was.
        if only is not None:
            try:
                table = merged_record(record)
            except HarnessFault as broken:
                return harness_fault(broken, staging)
            (staging / "results.json").write_text(
                json.dumps(table, indent=2) + "\n", encoding="utf-8"
            )
        CARDS.mkdir(parents=True, exist_ok=True)
        for produced in sorted(staging.iterdir()):
            if produced.name in incomplete:
                continue
            landing = CARDS / produced.name
            if landing.is_dir():
                shutil.rmtree(landing)
            elif landing.exists():
                landing.unlink()
            shutil.move(str(produced), str(landing))
        print(f"evidence under {CARDS}")
        for tag in sorted(incomplete):
            print(
                f"  cards/{tag}/ left as it was: this run was refused and produced no "
                f"card. Its partial output is under {staging / tag}"
            )

    if refused:
        # Non-zero, because a sweep with holes in it is not the table this script
        # claims to produce -- and every row it did measure is on disk regardless.
        print(f"\n{len(refused)} of {len(results)} runs were refused:")
        for row in refused:
            print(
                f"  {row['tag']}: {row['refused']['step']} -- {row['refused']['reason']}"
            )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
