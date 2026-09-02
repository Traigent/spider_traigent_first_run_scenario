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
import ast
import hashlib
import json
import random
import shutil
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parent
COMPONENTS = REPO_ROOT / "components"
SPIDER_DIR = REPO_ROOT / "spider"
DATASET_PATH = SPIDER_DIR / "spider_300.jsonl"
DATABASES_PATH = SPIDER_DIR / "databases"
DATA_LICENCE_PATH = SPIDER_DIR / "LICENSE-DATA"
# The demo is a copy of Traigent-authored code and third-party data, handed to someone
# outside this repository. Both sets of terms have to travel with it.
CODE_LICENCE_PATHS = (REPO_ROOT / "LICENSE", REPO_ROOT / "NOTICE")

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

# Which vendor serves the models the agent chooses between. LiteLLM carries all three, so
# the only thing that changes between them is the roster of model ids -- but that roster has
# to be a literal in the agent's own source, because the guide's opening read credits a
# setting only from values it can see there. Hence one agent per vendor rather than one
# agent reading a roster from somewhere else.
PROVIDERS = ("openrouter", "direct")
AGENT_STATES = ("ready", "no-knobs", "missing")


def agent_file(state: str, provider: str) -> Path | None:
    if state == "missing":
        return None
    return COMPONENTS / "agent" / provider / f"agent_{state.replace('-', '_')}.py"


def agent_models(agent_source: Path | None) -> list[str]:
    """The model ids the shipped agent chooses between, read from the file itself.

    Recorded rather than restated: the roster lives in the agent's source because that is
    the only place the guide's opening read can see it, so the manifest reads it from there
    too instead of keeping a second copy that can disagree.
    """
    if agent_source is None:
        return []
    tree = ast.parse(agent_source.read_text(encoding="utf-8"))
    for node in tree.body:
        if not isinstance(node, ast.Assign):
            continue
        targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
        if "MODELS" in targets and isinstance(node.value, (ast.Tuple, ast.List)):
            return [
                element.value
                for element in node.value.elts
                if isinstance(element, ast.Constant) and isinstance(element.value, str)
            ]
    raise BuildError(f"{agent_source} declares no MODELS roster")


def env_file(provider: str) -> Path:
    return COMPONENTS / "env" / f"{provider}.env.example"


EVALUATOR_FILES = {
    "exact-match": COMPONENTS / "evaluator" / "exact_match.py",
    "exec-match": COMPONENTS / "evaluator" / "exec_match.py",
    "broken": COMPONENTS / "evaluator" / "broken.py",
    "swapped": COMPONENTS / "evaluator" / "swapped.py",
    "missing": None,
}
DATASET_STATES = (
    "ready",
    "mini",
    "tiny",
    "unlabeled",
    "duplicated",
    "wrong-answers",
    "missing",
)
CALIBRATION_STATES = ("none", "present")
GUIDE_MODES = ("clone", "local")

# The share of each difficulty band the full slice holds back, kept by every smaller draw.
HOLDOUT_SHARE = 0.2
DEFAULT_PROVIDER = "openrouter"
MINI_ROWS = 30
# Small enough that the guide's own floor for a measurable comparison bites: it caps a
# project whose tuning side holds fewer than ten rows. Ten total leaves eight to tune on,
# which is the state of someone who has written a handful of examples by hand.
TINY_ROWS = 10
# How many of the rows a damaged dataset ships are damaged, and how. Recorded in the manifest
# so a run can be described honestly: the questions and answers are Spider's, the damage is
# this repository's.
DAMAGED_ROWS = 60
DUPLICATED_SHARE = 0.5
DAMAGED_STATES = ("duplicated", "wrong-answers")
UNLABELED_ROWS = 40
SAMPLE_SEED = 42

# Where a project keeps the probe answers it uses to check its own scorer. The guide reads
# this path, and a project that has one can have its evaluator validated at the opening gate
# instead of being held at the unvalidated ceiling.
RUNS_DIRECTORY = "traigent-runs"
CALIBRATION_FILE = "calibration-cases.json"
_TEXT_PROBES = COMPONENTS / "calibration" / "exact_match.json"
CALIBRATION_SOURCES = {
    "exact-match": _TEXT_PROBES,
    "exec-match": COMPONENTS / "calibration" / "exec_match.json",
    # The always-correct scorer is deliberately given the text comparator's probes: the
    # point is that it fails the same questions the honest one passes. One file rather than
    # a byte-identical copy, because a copy can only drift away from what it is comparing to.
    "broken": _TEXT_PROBES,
    # The mis-wired scorer never looks at the answer, so it fails the same probes for the
    # opposite reason: it marks the right answer wrong instead of the wrong answer right.
    "swapped": _TEXT_PROBES,
}
# The guide creates this itself and stops if it already exists, so a demo must never have one.
FORBIDDEN_VENV_NAME = ".venv-traigent"

# Which evaluator method and task kind each evaluator honestly is. Recorded in the manifest
# so a run can be described without re-deriving it, and reported by `list`.
EVALUATOR_FACTS = {
    "exact-match": {"method": "normalized-exact", "executes_candidate_output": False},
    "exec-match": {"method": "execution", "executes_candidate_output": True},
    "broken": {"method": "normalized-exact", "executes_candidate_output": False},
    "swapped": {"method": "normalized-exact", "executes_candidate_output": False},
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
    "fake-ruler": {
        "agent": "ready",
        "dataset": "ready",
        "eval": "broken",
        "calibration": "present",
    },
    "agent-and-logs": {"agent": "ready", "dataset": "unlabeled", "eval": "missing"},
    "logs-only": {"agent": "missing", "dataset": "unlabeled", "eval": "missing"},
    "no-agent": {"agent": "missing", "dataset": "ready", "eval": "exact-match"},
    "no-data": {"agent": "ready", "dataset": "missing", "eval": "exact-match"},
    "empty": {"agent": "missing", "dataset": "missing", "eval": "missing"},
    "wrong-wiring": {"agent": "ready", "dataset": "ready", "eval": "swapped"},
    "duplicated-data": {
        "agent": "ready",
        "dataset": "duplicated",
        "eval": "exact-match",
    },
    "wrong-answers": {
        "agent": "ready",
        "dataset": "wrong-answers",
        "eval": "exact-match",
    },
    "hand-written": {
        "agent": "ready",
        "dataset": "tiny",
        "eval": "exact-match",
        "calibration": "present",
    },
    "best-case": {
        "agent": "ready",
        "dataset": "ready",
        "eval": "exec-match",
        "calibration": "present",
    },
}

PRESET_NOTES = {
    "ready": "tunable and complete, scorer not yet checked",
    "checked": "tunable and complete, with probe answers kept for the scorer",
    "no-eval": "no way to score an answer",
    "no-labels": "questions with no expected answers",
    "no-knobs": "an agent with nothing to search",
    "sql-exec-stop": "an evaluator that executes the candidate SQL",
    "fake-ruler": "a scorer that marks everything correct, and probes that catch it",
    "agent-and-logs": "an agent, and logged questions with no answers and no scorer",
    "logs-only": "nothing but logged questions -- all three pieces have to be built",
    "no-agent": "data and a scorer, and nothing to run them against",
    "no-data": "an agent and a scorer, and nothing to measure them on",
    "empty": "an empty directory",
    "wrong-wiring": "a scorer comparing the question with the answer, never the output",
    "duplicated-data": "half the rows appear twice, question and answer both",
    "wrong-answers": "every answer runs, and answers a different question",
    "hand-written": "ten examples written by hand, and probes kept for the scorer",
    "best-case": "tunable, complete, probes kept, and scored by running the SQL",
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
    """The rows a given dataset state ships.

    Drawn evenly across difficulty, and within each band across the tuning/holdout split in
    the same proportion the full slice uses. Sampling on difficulty alone would keep the
    bands balanced and quietly flatten the split -- a 30-row draw came out with a single
    held-out question in three of the four bands, which cannot check a winner against
    anything.
    """
    if state == "ready":
        return list(rows)
    wanted = {
        "mini": MINI_ROWS,
        "tiny": TINY_ROWS,
        "duplicated": DAMAGED_ROWS,
        "wrong-answers": DAMAGED_ROWS,
    }.get(state, UNLABELED_ROWS)
    by_band: dict[str, dict[str, list[dict[str, Any]]]] = {}
    for row in rows:
        band = by_band.setdefault(
            row["metadata"]["difficulty"], {"tuning": [], "holdout": []}
        )
        split = row["metadata"].get("split")
        if split not in band:
            raise BuildError(
                f"row {row['metadata'].get('id', '?')} has split "
                f"{split!r}; every row in the slice needs tuning or holdout"
            )
        band[split].append(row)

    rng = random.Random(SAMPLE_SEED)
    per_band, remainder = divmod(wanted, len(by_band))
    picked: list[dict[str, Any]] = []
    for position, band_name in enumerate(sorted(by_band)):
        take = per_band + (1 if position < remainder else 0)
        holdout_take = round(take * HOLDOUT_SHARE)
        for split, split_take in (
            ("holdout", holdout_take),
            ("tuning", take - holdout_take),
        ):
            pool = sorted(by_band[band_name][split], key=lambda r: r["input"])
            rng.shuffle(pool)
            if len(pool) < split_take:
                raise BuildError(
                    f"the slice has {len(pool)} {split} rows in the {band_name} band and "
                    f"{split_take} are needed for --dataset {state}"
                )
            picked.extend(pool[:split_take])
    picked.sort(key=lambda r: (r["metadata"]["difficulty"], r["input"]))
    return picked


def damage_rows(rows: list[dict[str, Any]], state: str) -> list[dict[str, Any]]:
    """The rows a deliberately damaged dataset ships.

    `duplicated` repeats half of them, which is the shape of a set assembled by appending an
    export to itself: the same question and the same answer, twice, so a score computed over
    it counts the same evidence more than once.

    `wrong-answers` keeps every question and every answer and pairs them with each other,
    which is what a column read one row out of step looks like. The rotation happens inside
    each database, so every answer still runs and still returns rows -- it simply answers a
    different question. Nothing is invented and nothing is deleted; the pairing is wrong, and
    a pairing that runs is far harder to notice than one that does not.
    """
    if state == "duplicated":
        repeated = rows[: max(1, int(len(rows) * DUPLICATED_SHARE))]
        return sorted(
            rows + repeated, key=lambda r: (r["metadata"]["difficulty"], r["input"])
        )
    # Rotated within each database, not across all of them. An answer borrowed from another
    # database does not even run, which makes the damage obvious for the wrong reason -- the
    # interesting version is an answer that runs perfectly and answers a different question.
    by_database: dict[str, list[int]] = {}
    for position, row in enumerate(rows):
        by_database.setdefault(row["metadata"]["db_id"], []).append(position)
    answers = [row["output"] for row in rows]
    for positions in by_database.values():
        if len(positions) < 2:
            continue
        borrowed = [answers[p] for p in positions[1:]] + [answers[positions[0]]]
        for position, answer in zip(positions, borrowed):
            answers[position] = answer
    return [{**row, "output": answer} for row, answer in zip(rows, answers)]


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
    check_calibration_source(evaluator_state)
    source = CALIBRATION_SOURCES[evaluator_state]
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


def check_guide_source(guide_src: Path | None) -> None:
    """Refuse a guide checkout that is not one, before the demo directory is created."""
    if guide_src is None:
        raise BuildError(
            "--guide local needs --guide-src pointing at a traigent-first-run checkout"
        )
    resolved = guide_src.expanduser().resolve()
    for required in GUIDE_REQUIRED:
        if not (resolved / required).exists():
            raise BuildError(
                f"{resolved} does not look like a traigent-first-run checkout: "
                f"{required} is missing"
            )


def check_calibration_source(evaluator_state: str) -> None:
    """Refuse a calibration request that has no cases to ship, before anything is written."""
    source = CALIBRATION_SOURCES.get(evaluator_state)
    if source is None:
        raise BuildError(
            f"--calibration present needs an evaluator to calibrate, and "
            f"--eval {evaluator_state} ships none"
        )
    if not source.exists():
        raise BuildError(f"calibration cases missing from the repository: {source}")


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
    guide_src = guide_src.expanduser().resolve()
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
    # Recorded when it can be. Git being absent is not a reason to refuse a build that has
    # already copied everything it needs, but it must not surface as a traceback either.
    git_sha: str | None = None
    try:
        revision = subprocess.run(
            ["git", "-C", str(guide_src), "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except (OSError, subprocess.SubprocessError):
        git_sha = None
    else:
        git_sha = revision.stdout.strip() if revision.returncode == 0 else None
    return {
        "directory": GUIDE_DIRECTORY,
        "source": str(guide_src),
        "paths": copied,
        "git_sha": git_sha,
    }


def check_no_dedicated_environment(project: Path) -> None:
    """Refuse to hand over a project that already contains the guide's own environment.

    The guide creates `.venv-traigent` itself and stops if that path exists, so a demo
    carrying one anywhere inside it cannot be run at all. Checked over the whole tree,
    because a copied guide checkout could bring one in.
    """
    for path in project.rglob(FORBIDDEN_VENV_NAME):
        raise BuildError(
            f"a {FORBIDDEN_VENV_NAME} ended up in the demo at "
            f"{path.relative_to(project)}. The guide creates that itself and stops if it "
            "already exists, so a demo carrying one cannot be run."
        )


def inventory(out: Path) -> list[dict[str, Any]]:
    """Every file in the demo, with its hash, so drift is visible later."""
    files = []
    for path in sorted(out.rglob("*")):
        if path.is_dir() or path.is_symlink():
            continue
        files.append(
            {
                "path": path.relative_to(out).as_posix(),
                "sha256": sha256_of(path),
                "size": path.stat().st_size,
            }
        )
    return files


FILE_DESCRIPTIONS = {
    "agent.py": "writes the SQL. `run(question, config)` returns a query as text.",
    "dataset.jsonl": None,  # filled in from what the rows actually carry
    "catalog.json": "which database each question is about, and that database's structure.",
    "databases/": None,
    "evaluator.py": (
        "marks an answer. `score(output, expected, input_data, metadata)` returns 1.0 or 0.0."
    ),
    "traigent-runs/calibration-cases.json": (
        "probe answers kept for checking the scorer: a right one, an equivalent one, a "
        "partly-right one and a wrong one."
    ),
    "README.md": "this file.",
    ".env.example": "the keys this project would need, with no values in it.",
    "LICENSE": "the terms the code here is under.",
    "NOTICE": "who wrote what, and which parts are under which licence.",
    "LICENSE-DATA": "the licence the questions are under. It travels with them.",
}

METADATA_NOTES = {
    "db_id": "which database the question is about.",
    "schema": "that database's `CREATE TABLE` text.",
    "split": (
        "`tuning` or `holdout`. Holdout questions are held back to check a winner against "
        "questions it was not tuned on."
    ),
    "difficulty": "how involved the query the question needs is.",
    "provenance": "where the row came from.",
    "id": "a stable identifier for the row.",
}


def render_readme(
    template: Path,
    *,
    handoff: str,
    shipped: Sequence[str],
    rows: Sequence[dict[str, Any]],
    databases: Sequence[str],
    agent_state: str,
) -> str:
    """The project's own README, describing only what this project actually contains.

    Every line of it is derived from the files that were written. A fixed description would
    tell a reader about files that are not here and fields the rows do not carry -- which, in
    a project deliberately built with something missing, hands over the very thing the run is
    supposed to discover.
    """
    table = ["| File | |", "|---|---|"]
    for name in shipped:
        if name not in FILE_DESCRIPTIONS:
            raise BuildError(
                f"{name} is shipped with no description, so the project's README would not "
                "mention it. Add one to FILE_DESCRIPTIONS."
            )
        description = FILE_DESCRIPTIONS[name]
        if name == "dataset.jsonl":
            labelled = bool(rows) and "output" in rows[0]
            # Describes the file, and no more than that. Announcing "no expected answers"
            # would be accurate and would also hand over the thing a run is meant to notice
            # for itself; the sample row below shows the shape either way.
            description = (
                f"{len(rows)} questions with the query that answers each one."
                if labelled
                else f"{len(rows)} questions."
            )
        elif name == "databases/":
            description = f"{len(databases)} SQLite databases, one directory each."
        if description:
            table.append(f"| `{name}` | {description} |")

    # Every section is written only when the thing it describes is here. A fixed paragraph
    # about the data reads as a claim that there is data, in a project built to have none.
    opening = "\nAnswers questions about a database by writing the SQL that gets the answer.\n"
    if rows:
        example = rows[0]
        answer = example.get("output")
        opening += (
            f"\nAsk it *\"{example['input']}\"* and it returns\n`{answer}`.\n"
            if answer
            else f"\nOne of the questions it is given: *\"{example['input']}\"*\n"
        )

    data_section = ""
    if rows:
        # The schema is the longest value by far and its shape is what matters here, not
        # its content; printed whole it buries the rest of the row.
        shown = dict(rows[0])
        shown["metadata"] = dict(shown.get("metadata", {}))
        schema = shown["metadata"].get("schema")
        if isinstance(schema, str) and "\n" in schema:
            shown["metadata"]["schema"] = schema.splitlines()[0] + " ..."
        sample = json.dumps(shown, ensure_ascii=False, indent=1, sort_keys=True)
        notes = [
            f"- `metadata.{field}` -- {METADATA_NOTES[field]}"
            for field in sorted(rows[0].get("metadata", {}))
            if field in METADATA_NOTES
        ]
        data_section = (
            "\n## The data\n\nRows look like this:\n\n```json\n"
            + sample
            + "\n```\n\n"
            + "\n".join(notes)
            + "\n\nThese questions come from **Spider**, a text-to-SQL benchmark of"
            " human-written questions over databases in many different subject areas"
            " (Yu et al., EMNLP 2018). They are real recorded data, not generated examples.\n"
            "\nSpider is old enough and public enough that current models have very likely"
            " seen it, and what is here is a small sample -- enough to tell configurations"
            " apart, not enough to settle a question about production.\n"
            "\nThe data is licensed CC BY-SA 4.0 and `LICENSE-DATA` in this directory carries"
            " the attribution and the terms. It has to stay with the data wherever the data"
            " goes.\n"
        )

    if agent_state == "missing":
        agent_section = (
            "\nThere is no agent here yet. Something that turns a question into SQL is the\n"
            "thing that needs building.\n"
        )
    else:
        agent_section = (
            "\nWhich way of asking works best is not obvious, and the way to find out is to\n"
            "measure.\n"
        )

    text = template.read_text(encoding="utf-8")
    for key, value in {
        "OPENING": opening,
        "FILE_TABLE": "\n".join(table),
        "DATA_SECTION": data_section,
        "AGENT_SECTION": agent_section,
        "HANDOFF": handoff,
    }.items():
        text = text.replace("{{" + key + "}}", value)
    return text


# --------------------------------------------------------------------------- commands


@dataclass(frozen=True)
class Plan:
    """One demo, fully decided and checked, and not yet written.

    Everything a build needs is resolved here and nowhere else. The point of the type is the
    boundary it draws: `plan_demo` is the only place that reads the command line or refuses
    anything, and `write_demo` takes a Plan and writes it. "Already validated" is then a
    property of what the writer was handed rather than a promise in its docstring, and the
    writer can be driven from a test without a command line at all.
    """

    out: Path
    agent: str
    dataset: str
    evaluator: str
    calibration: str
    provider: str
    rows: list[dict[str, Any]]
    guide_source: Path | None

    @property
    def project(self) -> Path:
        return self.out / PROJECT_SUBDIR

    @property
    def handoff(self) -> str:
        """What a fresh agent is given. A copied guide is pointed at; otherwise it clones."""
        return HANDOFF_LOCAL if self.guide_source is not None else HANDOFF_CLONE

    @property
    def agent_source(self) -> Path | None:
        return agent_file(self.agent, self.provider)

    @property
    def evaluator_source(self) -> Path | None:
        return EVALUATOR_FILES[self.evaluator]

    @property
    def ships_calibration(self) -> bool:
        return self.calibration == "present"


def plan_demo(args: argparse.Namespace) -> Plan:
    """Decide and check everything, without writing anything.

    Every refusal lives here, before the output directory exists. A build that failed half
    way used to leave a directory holding an agent, a dataset and databases with no sign that
    it was incomplete -- and the path it occupied then refused the retry.
    """
    chosen = dict(PRESETS[args.preset]) if args.preset else {}
    for name in ("agent", "dataset", "eval", "calibration", "provider"):
        supplied = getattr(args, name)
        if supplied is not None:
            chosen[name] = supplied

    agent = chosen.get("agent", "ready")
    dataset = chosen.get("dataset", "ready")
    evaluator = chosen.get("eval", "exact-match")
    calibration = chosen.get("calibration", "none")
    provider = chosen.get("provider", DEFAULT_PROVIDER)

    if calibration == "present" and evaluator == "missing":
        raise BuildError(
            "--calibration present needs an evaluator; --eval missing ships none"
        )
    if args.guide == "clone" and args.guide_src is not None:
        raise BuildError("--guide-src only applies to --guide local")

    out = args.out.expanduser()
    check_output_path(out)
    guide_source: Path | None = None
    if args.guide == "local":
        check_guide_source(args.guide_src)
        guide_source = args.guide_src
    if calibration == "present":
        check_calibration_source(evaluator)

    rows = select_rows(read_dataset(), dataset) if dataset != "missing" else []
    if calibration == "present" and not rows:
        raise BuildError(
            "--calibration present needs the databases its probes run against, and "
            "--dataset missing ships none"
        )

    return Plan(
        out=out,
        agent=agent,
        dataset=dataset,
        evaluator=evaluator,
        calibration=calibration,
        provider=provider,
        rows=rows,
        guide_source=guide_source,
    )


def cmd_demo(args: argparse.Namespace) -> dict[str, Any]:
    plan = plan_demo(args)
    plan.out.mkdir(parents=True)
    try:
        return write_demo(plan)
    except BaseException:
        # A half-built demo is worse than none. Said out loud, because this also catches an
        # interrupt, and a directory disappearing without a word is its own surprise.
        print(f"build failed; removing the partial demo at {plan.out}", file=sys.stderr)
        shutil.rmtree(plan.out, ignore_errors=True)
        if plan.out.exists():
            print(
                f"could not remove it: {plan.out} is still there and will refuse the "
                "next build",
                file=sys.stderr,
            )
        raise


def write_demo(plan: Plan) -> dict[str, Any]:
    """Write the demo a Plan describes. Nothing here decides anything or refuses anything."""
    project = plan.project
    project.mkdir()
    created: list[str] = []
    shipped_rows = (
        damage_rows(plan.rows, plan.dataset)
        if plan.dataset in DAMAGED_STATES
        else plan.rows
    )
    projected = [project_row(row, plan.dataset) for row in shipped_rows]

    if plan.agent_source is not None:
        shutil.copy2(plan.agent_source, project / "agent.py")
        created.append("agent.py")

    if plan.evaluator_source is not None:
        shutil.copy2(plan.evaluator_source, project / "evaluator.py")
        created.append("evaluator.py")

    databases: list[str] = []
    if plan.rows:
        write_jsonl(project / "dataset.jsonl", projected)
        created.append("dataset.jsonl")
        write_catalog(project / "catalog.json", shipped_rows)
        created.append("catalog.json")
        databases = copy_databases(
            shipped_rows,
            project / "databases",
            calibration_databases(plan.evaluator, plan.calibration),
        )
        created.append("databases/")
        # The rows are CC BY-SA; their licence travels with them, always.
        shutil.copy2(DATA_LICENCE_PATH, project / "LICENSE-DATA")
        created.append("LICENSE-DATA")

    shutil.copy2(env_file(plan.provider), project / ".env.example")
    created.append(".env.example")

    for licence in CODE_LICENCE_PATHS:
        shutil.copy2(licence, project / licence.name)
        created.append(licence.name)

    calibration_record = (
        copy_calibration(plan.evaluator, project) if plan.ships_calibration else None
    )
    if calibration_record is not None:
        created.append(f"{RUNS_DIRECTORY}/{CALIBRATION_FILE}")

    guide_record = (
        copy_guide(plan.guide_source, project)
        if plan.guide_source is not None
        else None
    )

    # Counted over the rows the project ships, not the rows they were drawn from: an
    # unlabelled dataset carries no split, and reporting one would describe a file that is
    # not there.
    bands = Counter(row["metadata"]["difficulty"] for row in projected)
    splits = Counter(
        row["metadata"]["split"] for row in projected if "split" in row["metadata"]
    )

    created.append("README.md")
    readme = render_readme(
        COMPONENTS / "readme" / "DEMO_README.md.tmpl",
        handoff=plan.handoff,
        shipped=created,
        rows=projected,
        databases=databases,
        agent_state=plan.agent,
    )
    (project / "README.md").write_text(readme, encoding="utf-8")

    check_no_dedicated_environment(project)

    manifest: dict[str, Any] = {
        "manifest_version": MANIFEST_VERSION,
        "built_by": "build.py",
        "project_directory": PROJECT_SUBDIR,
        "components": {
            "agent": {
                "state": plan.agent,
                "path": "agent.py" if plan.agent_source else None,
                "provider": plan.provider,
                "models": agent_models(plan.agent_source),
            },
            "dataset": {
                "state": plan.dataset,
                "path": "dataset.jsonl" if plan.rows else None,
                "rows": len(projected),
                "labelled": plan.dataset not in ("unlabeled", "missing"),
                # The questions and answers are Spider's. Damage is this repository's, and
                # saying which is which is the difference between a fixture and a false
                # claim about the benchmark.
                "damage": plan.dataset if plan.dataset in DAMAGED_STATES else None,
                "difficulty_counts": dict(sorted(bands.items())),
                "split_counts": dict(sorted(splits.items())),
                "databases": databases,
            },
            "evaluator": {
                "state": plan.evaluator,
                "path": "evaluator.py" if plan.evaluator_source else None,
                "method": None,
                "executes_candidate_output": None,
                **(EVALUATOR_FACTS.get(plan.evaluator, {})),
                "calibration": calibration_record,
            },
            "guide": guide_record,
        },
        "data_licence": "CC-BY-SA-4.0",
        "handoff": plan.handoff,
        "files": inventory(project),
    }
    (plan.out / "demo.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )

    return {
        "ok": True,
        "out": str(plan.out),
        "project": str(project),
        "components": {
            "agent": plan.agent,
            "dataset": plan.dataset,
            "eval": plan.evaluator,
            "calibration": plan.calibration,
            "provider": plan.provider,
        },
        "rows": len(projected),
        "databases": len(databases),
        "created": created,
        "handoff": plan.handoff,
    }


def cmd_suite(args: argparse.Namespace) -> dict[str, Any]:
    """Build every preset at once, each in its own directory under one root.

    A bank of starting states is only useful if making the whole bank is one command. Each
    demo is built exactly as `demo` builds it, and one failing preset does not take the
    others with it -- the failure is reported against the preset that caused it.
    """
    root = args.out.expanduser()
    check_output_path(root)
    root.mkdir(parents=True)

    built: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    for name in sorted(PRESETS):
        one = argparse.Namespace(
            out=root / name,
            preset=name,
            agent=None,
            dataset=None,
            eval=None,
            calibration=None,
            provider=args.provider,
            guide=args.guide,
            guide_src=args.guide_src,
        )
        try:
            result = cmd_demo(one)
        except BuildError as error:
            failed.append({"preset": name, "error": str(error)})
            continue
        built.append(
            {
                "preset": name,
                "project": result["project"],
                "rows": result["rows"],
                "components": result["components"],
            }
        )

    return {
        "ok": not failed,
        "root": str(root),
        "built": built,
        "failed": failed,
        "handoff": HANDOFF_LOCAL if args.guide == "local" else HANDOFF_CLONE,
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
            "agent": list(AGENT_STATES),
            "provider": list(PROVIDERS),
            "dataset": list(DATASET_STATES),
            "eval": sorted(EVALUATOR_FILES),
            "calibration": list(CALIBRATION_STATES),
            "guide": list(GUIDE_MODES),
        },
        "evaluators": EVALUATOR_FACTS,
    }


def cmd_check(args: argparse.Namespace) -> dict[str, Any]:
    problems: list[str] = []

    component_paths = {
        f"{state}/{provider}": agent_file(state, provider)
        for state in AGENT_STATES
        for provider in PROVIDERS
    }
    component_paths.update(EVALUATOR_FILES)
    for provider in PROVIDERS:
        component_paths[f"env/{provider}"] = env_file(provider)
    for state, path in component_paths.items():
        if path is None:
            continue
        if not path.exists():
            problems.append(f"component missing: {path}")
            continue
        if path.suffix != ".py":
            continue
        try:
            compile(path.read_text(encoding="utf-8"), str(path), "exec")
        except SyntaxError as error:
            problems.append(f"component does not parse: {path}: {error}")

    if not (COMPONENTS / "readme" / "DEMO_README.md.tmpl").exists():
        problems.append(
            f"component missing: {COMPONENTS / 'readme' / 'DEMO_README.md.tmpl'}"
        )

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
            f"{preset['name']:<17} {preset['agent']:<10} {preset['dataset']:<14} "
            f"{preset['eval']:<13} {preset['calibration']:<8} {preset['note']}"
        )
    lines.append("")
    for name, values in result["states"].items():
        lines.append(f"--{name}: {', '.join(values)}")
    return "\n".join(lines)


def render_suite(result: dict[str, Any]) -> str:
    lines = [f"Built {len(result['built'])} projects under {result['root']}", ""]
    for entry in result["built"]:
        parts = entry["components"]
        lines.append(
            f"  {entry['preset']:<17} {parts['agent']:<8} {parts['dataset']:<14} "
            f"{parts['eval']:<12} {entry['rows']:>4} rows"
        )
    for entry in result["failed"]:
        lines.append(f"  {entry['preset']:<17} FAILED: {entry['error']}")
    lines += [
        "",
        "Point one fresh agent at one project's directory, and give it exactly this:",
        "",
    ]
    lines += ["    " + line for line in result["handoff"].splitlines()]
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
    "suite": render_suite,
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

    suite = commands.add_parser(
        "suite", help="build every preset at once, each in its own directory"
    )
    suite.add_argument("--out", type=Path, required=True, metavar="DIR")
    suite.add_argument("--provider", choices=PROVIDERS)
    suite.add_argument("--guide", choices=GUIDE_MODES, default="clone")
    suite.add_argument("--guide-src", type=Path, metavar="DIR")
    suite.set_defaults(func=cmd_suite, name="suite")

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
        choices=AGENT_STATES,
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
        "--provider",
        choices=PROVIDERS,
        help="which vendor serves the models the agent chooses between",
    )
    demo.add_argument(
        "--calibration",
        choices=CALIBRATION_STATES,
        help="ship the probe answers a project would use to check its own scorer",
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
