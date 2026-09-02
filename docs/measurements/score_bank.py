#!/usr/bin/env python3
"""Re-measure the opening readiness card for every preset, and keep the evidence.

The score table in ../../README.md is produced by this script and by nothing else. It
builds each preset, runs the first-run guide's own `preflight.py`, `calibrate_evaluator.py`
and `readiness.py` over it in the order `SKILL.md`'s opening gate prescribes, and writes
every invocation and every output under `cards/`. Nothing there is named `.log`: the
repository's `.gitignore` excludes that suffix, and evidence that is not committed is not
evidence.

    python3 docs/measurements/score_bank.py --guide ~/code/traigent-first-run

Standard library only, like `build.py`. It needs a checkout of the guide, because the
scripts it runs are the guide's, and it never reaches the network.

**It pins the revision.** `PINNED_REVISION` below is the commit every published figure was
measured at, and the run refuses a checkout sitting on anything else rather than quietly
scoring against a moved target. The guide is under active development and its input contracts
change: measured on 2026-09-02, a checkout four commits later rejected the `--agent-knobs`
documents in `agent-knobs/` outright, because `build` checks had grown a required
`source_lines` field. A table that silently re-measures against whatever HEAD happens to be is
not reproducible, which is the whole point of this directory. Pass `--revision` to measure at a
different commit deliberately; the revision used is recorded in `cards/results.json`.

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
import shutil
import subprocess
import sys
import pathlib
from pathlib import Path
from typing import Any

# The guide commit every figure under cards/ was measured at. Changing this is a deliberate
# re-measurement, never a side effect of somebody's checkout having moved.
PINNED_REVISION = "6ec2b9c161400cd91faea9c8cdb1c4e00d21c8d9"

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
    """A step that has to succeed did not."""


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


def present(component: dict[str, Any] | None) -> dict[str, Any] | None:
    """A component that shipped a file, or None. A record with no path shipped nothing."""
    return component if component and component.get("path") else None


def score_one(
    tag: str,
    build_flags: tuple[str, ...],
    scripts: Path,
    workspace: Path,
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
    room = CARDS / tag
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
        raise MeasurementError(f"{tag}: build.py exited {built.returncode}")

    project = out / "project"
    components = json.loads((out / "demo.json").read_text(encoding="utf-8"))[
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
    capture_json(
        preflight, project, room / "02-preflight-stderr.txt", room / "02-preflight.json"
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
            try:
                calibration_passed = json.loads(done.stdout)["passed"]
            except (ValueError, KeyError):
                calibration_passed = None

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
    card = json.loads(done.stdout)

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

    results = []
    for preset in PRESETS:
        results.append(score_one(preset, ("--preset", preset), scripts, workspace))
        last = results[-1]
        print(
            f"{preset:20s} {last['overall']:>3} {last['band']:10s} {last['recommended_action']}",
            flush=True,
        )
    for tag, flags, options in VARIANTS:
        results.append(score_one(tag, flags, scripts, workspace, **options))
        last = results[-1]
        print(
            f"{tag:20s} {last['overall']:>3} {last['band']:10s} {last['recommended_action']}",
            flush=True,
        )
    for tag, declared, kind in GRID:
        results.append(
            score_one(
                tag,
                ("--preset", "checked"),
                scripts,
                workspace,
                method=declared,
                task_kind=kind,
            )
        )
        last = results[-1]
        print(
            f"{tag:20s} {last['overall']:>3} {last['band']:10s} {last['recommended_action']}",
            flush=True,
        )

    (CARDS / "results.json").write_text(
        json.dumps({"guide_revision": revision, "runs": results}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"\nguide revision {revision}")
    print(f"evidence under {CARDS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
