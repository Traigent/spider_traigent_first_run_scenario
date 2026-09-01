#!/usr/bin/env python3
# SPDX-License-Identifier: Apache-2.0
"""Build a text-to-SQL demo project for the Traigent Guided First Run.

Each demo is a small, self-contained project on real Spider data, assembled from the
components in this repository. The flags choose which pieces the project starts with -- a
tunable agent or one with nothing to search, labelled data or none, a sound evaluator or a
broken one -- so a run can be started from a known state and what the guide does with it can
be observed.

Standard library only. No install step; a bare clone can build immediately.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import shutil
import subprocess
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parent
COMPONENTS = REPO_ROOT / "components"
SPIDER_DIR = REPO_ROOT / "spider"
DATASET_PATH = SPIDER_DIR / "spider_300.jsonl"
DATABASES_PATH = SPIDER_DIR / "databases"
DATA_LICENCE_PATH = SPIDER_DIR / "LICENSE-DATA"

MANIFEST_VERSION = 1
# The demo directory holds two things: the project an agent is pointed at, and the record of
# how it was built. The record stays outside the project -- it names the state each component
# was put in, and a run where the agent can read that is not a test of anything.
PROJECT_SUBDIR = "project"
GUIDE_URL = "https://github.com/Traigent/traigent-first-run"
GUIDE_DIRECTORY = "traigent-first-run"

# Byte-identical to the prompt the product hands customers. Pinned by tests/test_build.py.
HANDOFF_CLONE = (
    "Help me run my first Traigent optimization.\n"
    f"Clone {GUIDE_URL} and follow GUIDE.md."
)
HANDOFF_LOCAL = (
    "Help me run my first Traigent optimization.\n"
    f"Use the Traigent first-run checkout at ./{GUIDE_DIRECTORY} and follow "
    f"./{GUIDE_DIRECTORY}/GUIDE.md."
)

# Paths copied out of a local guide checkout when --guide local is used.
GUIDE_PATHS = (
    "GUIDE.md",
    "README.md",
    "AGENTS.md",
    "CLAUDE.md",
    ".env.example",
    "skills",
)
GUIDE_REQUIRED = ("GUIDE.md", "skills")

AGENT_FILES = {
    "ready": COMPONENTS / "agent" / "agent_ready.py",
    "no-knobs": COMPONENTS / "agent" / "agent_no_knobs.py",
    "missing": None,
}
EVALUATOR_FILES = {
    "exact-match": COMPONENTS / "evaluator" / "exact_match.py",
    "exec-match": COMPONENTS / "evaluator" / "exec_match.py",
    "broken": COMPONENTS / "evaluator" / "broken.py",
    "missing": None,
}
DATASET_STATES = ("ready", "mini", "unlabeled", "missing")
CALIBRATION_STATES = ("none", "present")
VENV_STATES = ("none", "one-compatible", "old-python")
GUIDE_MODES = ("clone", "local")

MINI_ROWS = 30
UNLABELED_ROWS = 40
SAMPLE_SEED = 42

# The interpreter a "one-compatible" venv is built with must sit inside the guide's
# supported 3.11-3.13 range; "old-python" must sit below it.
COMPATIBLE_PYTHONS = ("python3.13", "python3.12", "python3.11")
OLD_PYTHON = "python3.10"
PROJECT_VENV_NAME = ".venv-project"
# Where a project keeps the probe answers it uses to check its own scorer. The guide reads
# this path, and a project that has one can have its evaluator validated at the opening gate
# instead of being held at the unvalidated ceiling.
RUNS_DIRECTORY = "traigent-runs"
CALIBRATION_FILE = "calibration-cases.json"
CALIBRATION_SOURCES = {
    "exact-match": COMPONENTS / "calibration" / "exact_match.json",
    "exec-match": COMPONENTS / "calibration" / "exec_match.json",
    "broken": COMPONENTS / "calibration" / "broken.json",
}
# The guide creates this itself and stops if it already exists, so a demo must never have one.
FORBIDDEN_VENV_NAME = ".venv-traigent"

# Which evaluator method and task kind each evaluator honestly is. Recorded in the manifest
# so a run can be described without re-deriving it, and reported by `list`.
EVALUATOR_FACTS = {
    "exact-match": {"method": "normalized-exact", "executes_candidate_output": False},
    "exec-match": {"method": "execution", "executes_candidate_output": True},
    "broken": {"method": "normalized-exact", "executes_candidate_output": False},
}

PRESETS = {
    "ready": {"agent": "ready", "dataset": "ready", "eval": "exact-match"},
    "checked": {
        "agent": "ready",
        "dataset": "ready",
        "eval": "exact-match",
        "calibration": "present",
    },
    "no-eval": {"agent": "ready", "dataset": "ready", "eval": "missing"},
    "no-labels": {"agent": "ready", "dataset": "unlabeled", "eval": "exact-match"},
    "no-knobs": {"agent": "no-knobs", "dataset": "ready", "eval": "exact-match"},
    "sql-exec-stop": {"agent": "ready", "dataset": "ready", "eval": "exec-match"},
    "best-case": {
        "agent": "ready",
        "dataset": "ready",
        "eval": "exec-match",
        "calibration": "present",
    },
}

PRESET_NOTES = {
    "ready": "everything present and tunable, scorer not yet checked",
    "checked": "the same, and the team keeps probe answers for its scorer",
    "no-eval": "no way to score an answer",
    "no-labels": "questions with no expected answers",
    "no-knobs": "an agent with nothing to search",
    "sql-exec-stop": "an evaluator that executes the candidate SQL",
    "best-case": "the highest-scoring project this data allows -- and it runs the SQL",
}


class BuildError(RuntimeError):
    """Raised when a demo cannot be built as asked."""


# --------------------------------------------------------------------------- helpers


def read_dataset() -> list[dict[str, Any]]:
    if not DATASET_PATH.exists():
        raise BuildError(f"the Spider slice is missing: {DATASET_PATH}")
    with DATASET_PATH.open(encoding="utf-8") as handle:
        return [json.loads(line) for line in handle if line.strip()]


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 16), b""):
            digest.update(chunk)
    return digest.hexdigest()


def enclosing_git_repository(path: Path) -> Path | None:
    """The nearest ancestor that is a Git working tree, if there is one."""
    for candidate in [path, *path.parents]:
        if (candidate / ".git").exists():
            return candidate
    return None


def check_output_path(out: Path) -> None:
    """A demo is built outside every checkout, and never on top of anything."""
    if out.exists() or out.is_symlink():
        raise BuildError(f"output already exists; refusing to write over it: {out}")
    parent = out.parent
    if not parent.is_dir():
        raise BuildError(f"the parent directory does not exist: {parent}")
    if parent.is_symlink():
        raise BuildError(f"the parent directory is a symbolic link: {parent}")
    enclosing = enclosing_git_repository(parent.resolve())
    if enclosing is not None:
        raise BuildError(
            f"output would land inside the Git working tree at {enclosing}. Build demos "
            "outside every checkout -- a demo inside one gets picked up as part of that "
            "project, and the guide is supposed to see only the demo."
        )


def select_rows(rows: list[dict[str, Any]], state: str) -> list[dict[str, Any]]:
    """The rows a given dataset state ships, drawn evenly across difficulty."""
    if state == "ready":
        return list(rows)
    wanted = MINI_ROWS if state == "mini" else UNLABELED_ROWS
    by_band: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_band.setdefault(row["metadata"]["difficulty"], []).append(row)
    rng = random.Random(SAMPLE_SEED)
    per_band, remainder = divmod(wanted, len(by_band))
    picked: list[dict[str, Any]] = []
    for position, band in enumerate(sorted(by_band)):
        take = per_band + (1 if position < remainder else 0)
        pool = sorted(by_band[band], key=lambda r: r["input"])
        rng.shuffle(pool)
        picked.extend(pool[:take])
    picked.sort(key=lambda r: (r["metadata"]["difficulty"], r["input"]))
    return picked


def project_row(row: dict[str, Any], state: str) -> dict[str, Any]:
    """One dataset line as the demo ships it.

    Flat: `input` is the question and `output` is the gold SQL, both plain text. The
    first-run tooling reads those two fields as text -- handing it nested objects puts the
    whole CREATE TABLE block inside the row's identity and corrupts its duplicate and split
    analysis. Everything else rides in `metadata`, where the evaluator can still reach it.
    """
    projected: dict[str, Any] = {"input": row["input"]}
    if state != "unlabeled":
        projected["output"] = row["output"]
    projected["metadata"] = dict(row["metadata"])
    if state == "unlabeled":
        # No expected answer means no split to hold out and nothing to grade against.
        projected["metadata"].pop("split", None)
    return projected


def write_jsonl(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_catalog(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    """Question -> its database and schema, which the agent needs and `input` does not carry."""
    catalog = {
        row["input"]: {
            "db_id": row["metadata"]["db_id"],
            "schema": row["metadata"]["schema"],
        }
        for row in rows
    }
    path.write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def calibration_databases(evaluator_state: str, calibration_state: str) -> set[str]:
    """Databases the shipped probe answers refer to.

    The probes name their own rows, which need not be among the rows the dataset ships -- so
    a smaller dataset must not leave a probe pointing at a database that is not here.
    """
    if calibration_state != "present":
        return set()
    source = CALIBRATION_SOURCES.get(evaluator_state)
    if source is None or not source.exists():
        return set()
    cases = json.loads(source.read_text(encoding="utf-8"))
    return {
        case["metadata"]["db_id"]
        for case in cases
        if isinstance(case.get("metadata"), dict) and case["metadata"].get("db_id")
    }


def copy_databases(
    rows: Sequence[dict[str, Any]], destination: Path, also: set[str] | None = None
) -> list[str]:
    needed = sorted({row["metadata"]["db_id"] for row in rows} | (also or set()))
    destination.mkdir(parents=True, exist_ok=True)
    for db_id in needed:
        source = DATABASES_PATH / db_id / f"{db_id}.sqlite"
        if not source.exists():
            raise BuildError(f"database missing from the repository: {source}")
        target = destination / db_id
        target.mkdir(exist_ok=True)
        shutil.copy2(source, target / f"{db_id}.sqlite")
    return needed


def resolve_interpreter(state: str) -> str:
    if state == "old-python":
        found = shutil.which(OLD_PYTHON)
        if found is None:
            raise BuildError(
                f"--existing-venv old-python needs {OLD_PYTHON} on PATH, and it is not there. "
                "Install it or choose another --existing-venv value; this build will not "
                "quietly substitute a different interpreter, because the version is the "
                "entire point of that option."
            )
        return found
    for name in COMPATIBLE_PYTHONS:
        found = shutil.which(name)
        if found is not None:
            return found
    raise BuildError(
        "--existing-venv one-compatible needs one of "
        f"{', '.join(COMPATIBLE_PYTHONS)} on PATH, and none is there."
    )


def make_project_venv(out: Path, state: str) -> dict[str, Any] | None:
    """A pre-existing environment for the demo project, when one is asked for.

    This is scenery, not plumbing: nothing in the demo runs from it. It exists so a run can
    start from a project that already has an environment, and so the version of that
    environment can be chosen.
    """
    if state == "none":
        return None
    interpreter = resolve_interpreter(state)
    venv_dir = out / PROJECT_VENV_NAME
    result = subprocess.run(
        [interpreter, "-m", "venv", str(venv_dir)],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        raise BuildError(
            f"could not create {venv_dir} with {interpreter}: "
            f"{result.stderr.strip() or result.stdout.strip()}"
        )
    version = subprocess.run(
        [
            str(venv_dir / "bin" / "python"),
            "-c",
            "import sys; print('.'.join(map(str, sys.version_info[:3])))",
        ],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    return {
        "path": PROJECT_VENV_NAME,
        "interpreter": interpreter,
        "python_version": version,
    }


def copy_calibration(evaluator_state: str, project: Path) -> dict[str, Any] | None:
    """The probe answers this project keeps for its own scorer.

    Each evaluator gets its own cases, because what counts as an equivalent answer is not the
    same question for a scorer that compares text as for one that compares rows.
    """
    source = CALIBRATION_SOURCES.get(evaluator_state)
    if source is None:
        raise BuildError(
            f"--calibration present needs an evaluator to calibrate, and --eval {evaluator_state} "
            "ships none"
        )
    if not source.exists():
        raise BuildError(f"calibration cases missing from the repository: {source}")
    runs = project / RUNS_DIRECTORY
    runs.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, runs / CALIBRATION_FILE)
    cases = json.loads(source.read_text(encoding="utf-8"))
    return {
        "path": f"{RUNS_DIRECTORY}/{CALIBRATION_FILE}",
        "case_count": len(cases),
    }


def copy_guide(guide_src: Path, out: Path) -> dict[str, Any]:
    guide_src = guide_src.resolve()
    for required in GUIDE_REQUIRED:
        if not (guide_src / required).exists():
            raise BuildError(
                f"{guide_src} does not look like a traigent-first-run checkout: {required} is missing"
            )
    destination = out / GUIDE_DIRECTORY
    destination.mkdir(parents=True)
    copied = []
    for name in GUIDE_PATHS:
        source = guide_src / name
        if not source.exists():
            continue
        if source.is_dir():
            shutil.copytree(
                source,
                destination / name,
                ignore=shutil.ignore_patterns("__pycache__", "*.pyc"),
            )
        else:
            shutil.copy2(source, destination / name)
        copied.append(name)
    revision = subprocess.run(
        ["git", "-C", str(guide_src), "rev-parse", "HEAD"],
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "directory": GUIDE_DIRECTORY,
        "source": str(guide_src),
        "paths": copied,
        "git_sha": revision.stdout.strip() if revision.returncode == 0 else None,
    }


def inventory(out: Path) -> list[dict[str, Any]]:
    """Every file in the demo, with its hash, so drift is visible later."""
    files = []
    for path in sorted(out.rglob("*")):
        if path.is_dir() or path.is_symlink():
            continue
        if PROJECT_VENV_NAME in path.relative_to(out).parts:
            continue
        files.append(
            {
                "path": path.relative_to(out).as_posix(),
                "sha256": sha256_of(path),
                "size": path.stat().st_size,
            }
        )
    return files


def render_readme(template: Path, values: dict[str, str]) -> str:
    text = template.read_text(encoding="utf-8")
    for key, value in values.items():
        text = text.replace("{{" + key + "}}", value)
    return text


# --------------------------------------------------------------------------- commands


def cmd_demo(args: argparse.Namespace) -> dict[str, Any]:
    settings = dict(PRESETS[args.preset]) if args.preset else {}
    for name in ("agent", "dataset", "eval", "calibration"):
        chosen = getattr(args, name.replace("-", "_"))
        if chosen is not None:
            settings[name] = chosen
    settings.setdefault("agent", "ready")
    settings.setdefault("dataset", "ready")
    settings.setdefault("eval", "exact-match")
    settings.setdefault("calibration", "none")
    calibration_state = settings["calibration"]
    if calibration_state == "present" and settings["eval"] == "missing":
        raise BuildError(
            "--calibration present needs an evaluator; --eval missing ships none"
        )

    if args.guide == "local" and args.guide_src is None:
        raise BuildError(
            "--guide local needs --guide-src pointing at a traigent-first-run checkout"
        )
    if args.guide == "clone" and args.guide_src is not None:
        raise BuildError("--guide-src only applies to --guide local")

    out = args.out.expanduser()
    check_output_path(out)

    rows = read_dataset()
    selected = (
        select_rows(rows, settings["dataset"])
        if settings["dataset"] != "missing"
        else []
    )
    if calibration_state == "present" and not selected:
        raise BuildError(
            "--calibration present needs the databases its probes run against, and "
            "--dataset missing ships none"
        )

    out.mkdir(parents=True)
    project = out / PROJECT_SUBDIR
    project.mkdir()
    created: list[str] = []

    agent_source = AGENT_FILES[settings["agent"]]
    if agent_source is not None:
        shutil.copy2(agent_source, project / "agent.py")
        created.append("agent.py")

    evaluator_source = EVALUATOR_FILES[settings["eval"]]
    if evaluator_source is not None:
        shutil.copy2(evaluator_source, project / "evaluator.py")
        created.append("evaluator.py")

    databases: list[str] = []
    if selected:
        write_jsonl(
            project / "dataset.jsonl",
            [project_row(row, settings["dataset"]) for row in selected],
        )
        created.append("dataset.jsonl")
        write_catalog(project / "catalog.json", selected)
        created.append("catalog.json")
        databases = copy_databases(
            selected,
            project / "databases",
            calibration_databases(settings["eval"], calibration_state),
        )
        created.append("databases/")
        # The rows are CC BY-SA; their licence travels with them, always.
        shutil.copy2(DATA_LICENCE_PATH, project / "LICENSE-DATA")
        created.append("LICENSE-DATA")

    shutil.copy2(COMPONENTS / "env" / "env.example", project / ".env.example")
    created.append(".env.example")

    calibration_record = (
        copy_calibration(settings["eval"], project)
        if calibration_state == "present"
        else None
    )
    if calibration_record is not None:
        created.append(f"{RUNS_DIRECTORY}/{CALIBRATION_FILE}")

    guide_record = (
        copy_guide(args.guide_src, project) if args.guide == "local" else None
    )
    handoff = HANDOFF_LOCAL if args.guide == "local" else HANDOFF_CLONE

    bands = Counter(row["metadata"]["difficulty"] for row in selected)
    splits = Counter(row["metadata"].get("split", "unsplit") for row in selected)
    venv_record = make_project_venv(project, args.existing_venv)

    readme = render_readme(
        COMPONENTS / "readme" / "DEMO_README.md.tmpl",
        {
            "HANDOFF": handoff,
            "ROWS": str(len(selected)),
            "DATABASES": str(len(databases)),
        },
    )
    (project / "README.md").write_text(readme, encoding="utf-8")
    created.append("README.md")

    manifest: dict[str, Any] = {
        "manifest_version": MANIFEST_VERSION,
        "built_by": "build.py",
        "project_directory": PROJECT_SUBDIR,
        "components": {
            "agent": {
                "state": settings["agent"],
                "path": "agent.py" if agent_source else None,
            },
            "dataset": {
                "state": settings["dataset"],
                "path": "dataset.jsonl" if selected else None,
                "rows": len(selected),
                "labelled": settings["dataset"] not in ("unlabeled", "missing"),
                "difficulty_counts": dict(sorted(bands.items())),
                "split_counts": dict(sorted(splits.items())),
                "databases": databases,
            },
            "evaluator": {
                "state": settings["eval"],
                "path": "evaluator.py" if evaluator_source else None,
                **(EVALUATOR_FACTS.get(settings["eval"], {})),
                "calibration": calibration_record,
            },
            "project_venv": venv_record,
            "guide": guide_record,
        },
        "data_licence": "CC-BY-SA-4.0",
        "handoff": handoff,
        "files": inventory(project),
    }
    (out / "demo.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    if (project / FORBIDDEN_VENV_NAME).exists():
        raise BuildError(
            f"a {FORBIDDEN_VENV_NAME} ended up in the demo. The guide creates that itself and "
            "stops if it already exists, so a demo carrying one cannot be run."
        )

    return {
        "ok": True,
        "out": str(out),
        "project": str(project),
        "components": {
            k: settings[k] for k in ("agent", "dataset", "eval", "calibration")
        },
        "rows": len(selected),
        "databases": len(databases),
        "project_venv": venv_record,
        "created": created,
        "handoff": handoff,
    }


def cmd_list(args: argparse.Namespace) -> dict[str, Any]:
    return {
        "ok": True,
        "presets": [
            {
                "name": name,
                "note": PRESET_NOTES[name],
                "calibration": "none",
                **PRESETS[name],
            }
            for name in sorted(PRESETS)
        ],
        "states": {
            "agent": sorted(AGENT_FILES),
            "dataset": list(DATASET_STATES),
            "eval": sorted(EVALUATOR_FILES),
            "calibration": list(CALIBRATION_STATES),
            "existing-venv": list(VENV_STATES),
            "guide": list(GUIDE_MODES),
        },
        "evaluators": EVALUATOR_FACTS,
    }


def cmd_check(args: argparse.Namespace) -> dict[str, Any]:
    problems: list[str] = []

    for state, path in {**AGENT_FILES, **EVALUATOR_FILES}.items():
        if path is None:
            continue
        if not path.exists():
            problems.append(f"component missing: {path}")
            continue
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as error:
            problems.append(f"component does not parse: {path}: {error}")

    for extra in (
        COMPONENTS / "env" / "env.example",
        COMPONENTS / "readme" / "DEMO_README.md.tmpl",
    ):
        if not extra.exists():
            problems.append(f"component missing: {extra}")

    rows = read_dataset()
    if len(rows) != 300:
        problems.append(f"expected 300 dataset rows, found {len(rows)}")
    questions = {row["input"] for row in rows}
    if len(questions) != len(rows):
        problems.append(f"dataset has {len(rows) - len(questions)} duplicate questions")
    for index, row in enumerate(rows):
        if not isinstance(row.get("input"), str) or not isinstance(
            row.get("output"), str
        ):
            problems.append(
                f"row {index} is not flat: input and output must both be text"
            )
            break
    needed = sorted({row["metadata"]["db_id"] for row in rows})
    for db_id in needed:
        if not (DATABASES_PATH / db_id / f"{db_id}.sqlite").exists():
            problems.append(f"database missing: {db_id}")
    if not DATA_LICENCE_PATH.exists():
        problems.append(f"data licence missing: {DATA_LICENCE_PATH}")

    gold_queries = {row["output"] for row in rows}
    for state, source in CALIBRATION_SOURCES.items():
        if not source.exists():
            problems.append(f"calibration cases missing: {source}")
            continue
        cases = json.loads(source.read_text(encoding="utf-8"))
        if len(cases) < 2:
            problems.append(
                f"{source.name}: at least two cases are required, found {len(cases)}"
            )
        for case in cases:
            if case["expected"] not in gold_queries:
                problems.append(
                    f"{source.name}: case {case.get('name', '?')!r} expects a query that is not "
                    "a recorded answer in the slice"
                )
            db_id = (case.get("metadata") or {}).get("db_id")
            if db_id and not (DATABASES_PATH / db_id / f"{db_id}.sqlite").exists():
                problems.append(
                    f"{source.name}: case names database {db_id}, which is not committed"
                )

    bands = Counter(row["metadata"]["difficulty"] for row in rows)
    splits = Counter(row["metadata"]["split"] for row in rows)

    return {
        "ok": not problems,
        "problems": problems,
        "dataset": {
            "rows": len(rows),
            "databases": len(needed),
            "difficulty_counts": dict(sorted(bands.items())),
            "split_counts": dict(sorted(splits.items())),
            "sha256": sha256_of(DATASET_PATH),
        },
    }


# --------------------------------------------------------------------------- rendering


def render_demo(result: dict[str, Any]) -> str:
    lines = [
        f"Built {result['out']}",
        f"  project    {result['project']}   <- point the agent here",
        "  demo.json  the record of how it was built; keep it out of the agent's view",
        "",
        f"  agent      {result['components']['agent']}",
        f"  dataset    {result['components']['dataset']} ({result['rows']} rows, {result['databases']} databases)",
        f"  evaluator  {result['components']['eval']}"
        + (
            "  (+ calibration cases)"
            if result["components"]["calibration"] == "present"
            else ""
        ),
    ]
    if result["project_venv"]:
        venv = result["project_venv"]
        lines.append(f"  venv       {venv['path']} (Python {venv['python_version']})")
    lines += [
        "",
        "Start a fresh agent with that project as its working directory, and give it",
        "exactly this and nothing else:",
        "",
    ]
    lines += ["    " + line for line in result["handoff"].splitlines()]
    return "\n".join(lines)


def render_list(result: dict[str, Any]) -> str:
    lines = [
        "PRESET           AGENT      DATASET    EVAL           CALIB    WHAT IT IS"
    ]
    for preset in result["presets"]:
        lines.append(
            f"{preset['name']:<16} {preset['agent']:<10} {preset['dataset']:<10} "
            f"{preset['eval']:<14} {preset['calibration']:<8} {preset['note']}"
        )
    lines.append("")
    for name, values in result["states"].items():
        lines.append(f"--{name}: {', '.join(values)}")
    return "\n".join(lines)


def render_check(result: dict[str, Any]) -> str:
    dataset = result["dataset"]
    lines = [
        f"dataset   {dataset['rows']} rows, {dataset['databases']} databases",
        f"          difficulty {dataset['difficulty_counts']}",
        f"          splits     {dataset['split_counts']}",
        f"          sha256     {dataset['sha256']}",
    ]
    if result["ok"]:
        lines.append("\nOK")
    else:
        lines.append("")
        lines += [f"PROBLEM   {problem}" for problem in result["problems"]]
    return "\n".join(lines)


RENDERERS: dict[str, Callable[[dict[str, Any]], str]] = {
    "demo": render_demo,
    "list": render_list,
    "check": render_check,
}


# --------------------------------------------------------------------------- cli


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="build.py",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("--format", choices=("text", "json"), default="text")
    commands = parser.add_subparsers(dest="command", required=True)

    listing = commands.add_parser(
        "list", help="show the presets and every component state"
    )
    listing.set_defaults(func=cmd_list, name="list")

    check = commands.add_parser(
        "check", help="validate this repository's own components and data"
    )
    check.set_defaults(func=cmd_check, name="check")

    demo = commands.add_parser("demo", help="build one demo project")
    demo.add_argument(
        "--out",
        type=Path,
        required=True,
        metavar="DIR",
        help="where to build it; must not exist, and must be outside every checkout",
    )
    demo.add_argument(
        "--preset",
        choices=sorted(PRESETS),
        help="a named combination; individual flags below override it",
    )
    demo.add_argument(
        "--agent",
        choices=sorted(AGENT_FILES),
        help="ready (tunable) | no-knobs (nothing to search) | missing",
    )
    demo.add_argument(
        "--dataset",
        choices=DATASET_STATES,
        help="ready (300) | mini (30) | unlabeled (no expected answers) | missing",
    )
    demo.add_argument(
        "--eval",
        dest="eval",
        choices=sorted(EVALUATOR_FILES),
        help="exact-match (does not execute) | exec-match (runs the SQL) | broken | missing",
    )
    demo.add_argument(
        "--calibration",
        choices=CALIBRATION_STATES,
        help="ship the probe answers a project would use to check its own scorer",
    )
    demo.add_argument(
        "--existing-venv",
        choices=VENV_STATES,
        default="none",
        help="ship the project with an environment already in it",
    )
    demo.add_argument(
        "--guide",
        choices=GUIDE_MODES,
        default="clone",
        help="clone: the agent clones the guide itself | local: copy a checkout in",
    )
    demo.add_argument(
        "--guide-src",
        type=Path,
        metavar="DIR",
        help="a traigent-first-run checkout, for --guide local",
    )
    demo.set_defaults(func=cmd_demo, name="demo")
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        result = args.func(args)
    except BuildError as error:
        if args.format == "json":
            print(json.dumps({"ok": False, "error": str(error)}, indent=2))
        else:
            print(f"error: {error}", file=sys.stderr)
        return 2
    if args.format == "json":
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(RENDERERS[args.name](result))
    return 0 if result.get("ok", True) else 1


if __name__ == "__main__":
    sys.exit(main())
