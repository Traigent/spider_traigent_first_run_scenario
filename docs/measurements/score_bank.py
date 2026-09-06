#!/usr/bin/env python3
"""Re-measure the opening readiness card for every preset, and keep the evidence.

The score table in ../../README.md is produced by this script and by nothing else. It
builds each preset, runs the first-run guide's own `preflight.py`, `calibrate_evaluator.py`
and `readiness.py` over it in the order `SKILL.md`'s opening gate prescribes, and writes
every invocation and every output as a card. Nothing under `cards/` is named `.log`: the
repository's `.gitignore` excludes that suffix, and evidence that is not committed is not
evidence.

    python3 docs/measurements/score_bank.py --guide ~/code/traigent-first-run \
        --revision 6e18086e1499baa3c66a7c0ebeedebdc887d4f0c

**It does not touch `cards/` unless asked.** The cards are committed evidence, and the
commonest reason to run this script is to check them rather than to replace them, so a plain
run writes into the workspace and says where. `--publish` is the regeneration: it replaces the
committed directory of every run that produced a card, and leaves alone the directory of any
run that did not -- a refused run's staged output is the two or three files it reached before
the refusal, and moving that over a committed card deletes the card itself.

Standard library only, like `build.py`. It needs a checkout of the guide, because the
scripts it runs are the guide's, and it never reaches the network.

**It pins the revision, and the pin and the documents currently disagree.**
`PINNED_REVISION` below is the commit every figure under `cards/` was measured at, and the run
refuses a checkout sitting on anything else rather than quietly scoring against a moved target.
The guide is under active development and its input contracts change, and a `build` check's
`source_lines` is the field that keeps moving: `6ec2b9c1`, the pin, does not read it and
refuses a document that carries it; `6e18086e` reads it and requires it of a settled check.
The documents under `agent-knobs/` were repaired to the second contract -- they cite executable
lines and every settled `build` check names them -- so **the sweep runs at `6e18086e` and is
refused at the pin**, which is why the invocation above passes `--revision` and why
`contract_mismatch` below stops the run with one sentence rather than 26 refused rows.

That is a known, deliberate state and not a loose end: the pin says what `cards/` was measured
at, and re-pinning it is part of the pending regeneration, which re-measures the whole table in
the same commit. Until then, `--revision` is how a reader reproduces the sweep, and
`../README.md` and `README.md` say so where they hand out the command. A table that silently
re-measures against whatever HEAD happens to be is not reproducible, which is the whole point
of this directory; the revision used is recorded in `cards/results.json`.

**Exit status.** 0 when every run scored; 1 when the guide refused one or more of them;
2 when the documents and the guide disagree before anything is built; 3 when something of
*ours* broke -- our builder, our probe -- which is never a row and never publishes.
At `6e18086e` one run cannot score: the guide refuses to calibrate an executing scorer, which
is exactly what `best-case--off-method-calibration` asks it to do, so a complete and correct
sweep there ends 1 with that one run refused. Nothing should key on exit 0 alone; read the
refused list the run prints and `results.json` beside it.

What it decides, and why each decision is here rather than in the reader's head:

`--evaluator-method` is taken from `demo.json`, which is the record of what the evaluator
component actually is. A real run declares that from its own reading of the file; this
script cannot read, so it uses the builder's record and says so. The same goes for
`--task-kind code-sql`: every project in this bank produces SQL.

`--agent-knobs` is the coding assistant's own read of the agent's source, and the guide is
explicit that the opening score requires it wherever an agent was found. No assistant is
running here, so the two documents under `agent-knobs/` stand in for one. They were written
by hand against the two agent components and they cite real lines on the real call path --
which is why the figures are faithful, and also why another honest read could move them.

`--calibration` runs only where the demo ships probe answers AND the guide's opening gate
allows it: "if the verdict is sufficient and the complete path does not execute
candidate-generated code or SQL". A scorer that runs model-written SQL fails that gate, so
`best-case` is scored without calibration. The `best-case--off-method-calibration` run in
VARIANTS scores it the other way instead, which is the off-method number and is labelled as one
everywhere it appears.

`--row-review` is not passed. The guide asks for one at the opening gate and it is the
assistant's own read of every row; a hand-written stand-in for it would be this script
deciding, row by row, whether each answer answers its question -- which is exactly the
judgement the `wrong-answers` preset exists to test. Leaving it off keeps the table
mechanical, and the omission is a property of this table rather than of the guide.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

# The guide commit every figure under cards/ was measured at. Changing this is a deliberate
# re-measurement, never a side effect of somebody's checkout having moved -- which is why it
# still names 6ec2b9c1 while the documents under agent-knobs/ only validate at 6e18086e. The
# two are re-joined by the pending regeneration, in the commit that re-measures the table.
# Until then the sweep runs with
#     --revision 6e18086e1499baa3c66a7c0ebeedebdc887d4f0c
# and refuses at the pin, before building anything, with the contract it could not satisfy.
PINNED_REVISION = "6ec2b9c161400cd91faea9c8cdb1c4e00d21c8d9"
WORKING_REVISION = "6e18086e1499baa3c66a7c0ebeedebdc887d4f0c"

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
)

# The four combinations of declared method and declared task kind, all on the same
# unchanged text comparator, from `--preset checked`.
GRID: tuple[tuple[str, str, str], ...] = (
    ("grid-exact--code-sql", "exact", "code-sql"),
    ("grid-normalized-exact--structured", "normalized-exact", "structured"),
    ("grid-normalized-exact--code-sql", "normalized-exact", "code-sql"),
    ("grid-exact--structured", "exact", "structured"),
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


def capture(argv: list[str], cwd: Path, log: Path) -> subprocess.CompletedProcess[str]:
    """Run one command, writing the invocation, the whole output and the exit status."""
    log.parent.mkdir(parents=True, exist_ok=True)
    done = subprocess.run(
        argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True
    )
    log.write_text(
        neutralise(
            "$ " + " ".join(argv) + "\n" + done.stdout + f"exit={done.returncode}\n"
        ),
        encoding="utf-8",
    )
    return done


def capture_json(
    argv: list[str], cwd: Path, log: Path, out: Path
) -> subprocess.CompletedProcess[str]:
    """The same, for a command whose stdout is the JSON another step reads."""
    log.parent.mkdir(parents=True, exist_ok=True)
    done = subprocess.run(
        argv, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
    )
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


print(
    json.dumps(
        {
            "document": listed("AGENT_KNOBS_DOCUMENT_FIELDS"),
            "knob": listed("DISCOVERED_KNOB_FIELDS"),
            "build": listed("BUILD_CHECK_FIELDS"),
        }
    )
)
"""

# The one thing the guide does not publish as data: which fields it *requires*. Its
# requiredness lives in `readiness.py`'s control flow, not in a constant, so this name is
# read by a human and written here -- the single hardcoded coordinate in this check, and the
# reason `unchecked` below says out loud what the probe could not derive.
REQUIRED_BUILD_FIELD = "source_lines"


def contract_mismatch(scripts: Path) -> tuple[list[str], list[str]]:
    """Where the guide in front of us and the documents beside us disagree, in its terms.

    The pin and the documents' schema are two independently editable facts, and letting
    them drift apart is how this directory has now broken twice in opposite directions:
    once with documents too old for the guide, once with documents too new for the pin.
    Both times the reader found out by running 26 builds and reading 26 refusals. So the
    disagreement is settled here, before anything is built, against `readiness.py`'s own
    field constants rather than against a copy of them kept in this file.

    Returns the disagreements and, beside them, what could not be checked at all -- a
    revision that renames or reshapes one of those constants makes this gate a no-op for
    that half, and a gate that has quietly stopped gating has to say so on the way past.

    What it does *not* claim to derive: requiredness. `source_lines` is required of a
    settled `build` check at `6e18086e` and refused on an undetermined one, and neither
    fact is expressible from the constants -- so the settled/undetermined distinction is
    read from the document exactly as the guide reads it, and the field name is written
    down above.
    """
    probe = subprocess.run(
        [sys.executable, "-c", CONTRACT_PROBE, str(scripts / "readiness.py")],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
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


def present(component: dict[str, Any] | None) -> dict[str, Any] | None:
    """A component that shipped a file, or None. A record with no path shipped nothing."""
    return component if component and component.get("path") else None


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

    built = capture(
        [sys.executable, "build.py", "demo", *build_flags, "--out", str(out)],
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
                ],
                project,
                room / "03-calibration-stderr.txt",
                room / "03-calibration.json",
            )
            calibrated = True
            # A refusal is named here rather than left to the readiness step, which
            # would report the empty calibration file it was handed ("cannot read
            # scoring input") instead of the guide's own reason for declining.
            report = decoded(done, "calibrate_evaluator.py")
            calibration_passed = (
                report.get("passed") if isinstance(report, dict) else None
            )

    readiness = [
        sys.executable,
        str(scripts / "readiness.py"),
        "--preflight",
        str(room / "02-preflight.json"),
    ]
    if agent and agent_knobs:
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
            "brought",
        ]
    if calibrated:
        readiness += ["--calibration", str(room / "03-calibration.json")]
    if evaluator:
        readiness += ["--evaluator-origin", "brought"]
    if declared:
        readiness += ["--evaluator-method", declared]
    readiness += ["--task-kind", task_kind, "--color", "never", "--ascii"]

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
                "build": portable(
                    [sys.executable, "build.py", *build_flags, "--out", "$DEMO"]
                ),
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
        required=True,
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
    parser.add_argument(
        "--publish",
        action="store_true",
        help="replace the committed evidence under cards/ with what this run produced; "
        "without it the run writes to the workspace and cards/ is left alone",
    )
    arguments = parser.parse_args()

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

    # Before anything is built: the documents this sweep hands to `readiness.py`, against
    # the contract the checkout in front of us actually reads. A mismatch here is a
    # property of the pair, not of any one run, so it stops the sweep in one sentence
    # instead of 26 refusals over a rewritten cards/.
    try:
        disagreements, unchecked = contract_mismatch(scripts)
    except HarnessFault as broken:
        return harness_fault(broken, None)
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
        for preset in PRESETS:
            measure(preset, ("--preset", preset))
        for tag, flags, options in VARIANTS:
            measure(tag, flags, **options)
        for tag, declared, kind in GRID:
            measure(tag, ("--preset", "checked"), method=declared, task_kind=kind)
    except HarnessFault as broken:
        return harness_fault(broken, staging)

    (staging / "results.json").write_text(
        json.dumps({"guide_revision": revision, "runs": results}, indent=2) + "\n",
        encoding="utf-8",
    )
    refused = [row for row in results if row.get("refused")]
    print(f"\nguide revision {revision}")

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
