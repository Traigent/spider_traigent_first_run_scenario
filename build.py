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
import re
import shutil
import sqlite3
import subprocess
import sys
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Sequence

REPO_ROOT = Path(__file__).resolve().parent
COMPONENTS = REPO_ROOT / "components"
SPIDER_DIR = REPO_ROOT / "spider"
DATASET_PATH = SPIDER_DIR / "spider_300.jsonl"
DATABASES_PATH = SPIDER_DIR / "databases"
# The rows and the databases are third-party data under terms of their own, and those terms
# have to travel with them. One file, the same text in every project: it credits the source
# of the data, gives the licence it is under and says the data was modified. It names no
# repository and describes no directory, because a project that carries a file explaining
# where it was produced is not a project anyone is reading blind.
ATTRIBUTION_SOURCE = COMPONENTS / "legal" / "ATTRIBUTION.txt"
ATTRIBUTION_NAME = "ATTRIBUTION.txt"

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
AGENT_STATES = ("ready", "no-knobs", "two-agents", "missing")
# `two-agents` ships the tunable agent at `agent.py` and, beside it, a second agent that
# has nothing to do with it -- the shape of a project that has grown a side tool. The
# second one lives in a directory of its own with its own rows and its own scorer, and
# which of the two a run should work on is written down by the customer in PROJECT.md,
# a file none of the guide's tools read.
SECOND_AGENT_DIRECTORY = "sql_explainer"
SECOND_AGENT_ROWS = 20
EXPLAINER = COMPONENTS / "explainer"
PROJECT_NOTE = "PROJECT.md"


def agent_file(state: str, provider: str) -> Path | None:
    if state == "missing":
        return None
    if state == "two-agents":
        # `agent.py` is the tunable agent, byte for byte. What the state adds is beside
        # it, not in it.
        state = "ready"
    return COMPONENTS / "agent" / provider / f"agent_{state.replace('-', '_')}.py"


def second_agent_file(provider: str) -> Path:
    """The second agent's own source, per vendor for the same reason the first is."""
    return EXPLAINER / provider / "agent.py"


def agent_models(agent_source: Path | None) -> list[str]:
    """The model ids the shipped agent chooses between, read from the file itself.

    Recorded rather than restated: the roster lives in the agent's source because that is
    the only place the guide's opening read can see it, so the manifest reads it from there
    too instead of keeping a second copy that can disagree.
    """
    if agent_source is None:
        return []
    try:
        source = agent_source.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as error:
        raise BuildError(f"{agent_source} cannot be read: {error}") from error
    try:
        tree = ast.parse(source)
    except SyntaxError as error:
        raise BuildError(f"{agent_source} does not parse: {error}") from error
    for node in tree.body:
        targets: list[str] = []
        value: ast.expr | None = None
        if isinstance(node, ast.Assign):
            targets = [t.id for t in node.targets if isinstance(t, ast.Name)]
            value = node.value
        elif isinstance(node, ast.AnnAssign):
            # `MODELS: tuple[str, ...] = (...)` is the same declaration with a type on it,
            # and reading only the bare form reported no roster for a file that has one.
            targets = [node.target.id] if isinstance(node.target, ast.Name) else []
            value = node.value
        if "MODELS" not in targets or not isinstance(value, (ast.Tuple, ast.List)):
            continue
        models: list[str] = []
        for element in value.elts:
            if not isinstance(element, ast.Constant) or not isinstance(
                element.value, str
            ):
                # Skipping it would write a shorter roster into the manifest than the one
                # the agent actually ships, and nothing downstream could tell.
                raise BuildError(
                    f"{agent_source}: MODELS holds {ast.unparse(element)}, which is not a "
                    "model id"
                )
            models.append(element.value)
        if not models:
            raise BuildError(
                f"{agent_source}: MODELS is empty, so the manifest would record no models "
                "for an agent that ships one -- the same record a missing agent gets"
            )
        return models
    raise BuildError(f"{agent_source} declares no MODELS roster")


def env_file(provider: str) -> Path:
    return COMPONENTS / "env" / f"{provider}.env.example"


# `.env.example` asks for `.env` to stay out of version control once it holds a value, and
# nothing made that hold: a project initialised as a repository committed its keys on the
# first `git add .`. The environments and run artifacts are excluded for the plainer reason
# that neither is source.
GITIGNORE_TEXT = """# Keys live here once filled in. Never commit them.
.env

# Environments -- the project's own and the one a first run creates beside it.
.venv/
.venv-traigent/

# Run artifacts: results, logs and the SDK's own output folder.
traigent-runs/
__pycache__/
"""


EVALUATOR_FILES = {
    "exact-match": COMPONENTS / "evaluator" / "exact_match.py",
    "exec-match": COMPONENTS / "evaluator" / "exec_match.py",
    "broken": COMPONENTS / "evaluator" / "broken.py",
    "swapped": COMPONENTS / "evaluator" / "swapped.py",
    # A scorer that hands both queries to a grading library the project does not carry.
    # It parses, it names a method nothing here can read, and it has never been run.
    "opaque": COMPONENTS / "evaluator" / "opaque.py",
    # A scorer that compares the lengths of the two queries and nothing else: a number
    # that moves, and never for the right reason.
    "length-blind": COMPONENTS / "evaluator" / "length_blind.py",
    # A scorer that compares text the ordinary way and asks a service to do it, one row
    # per call. Nothing is wrong with the comparison; what is wrong is what it costs.
    "slow": COMPONENTS / "evaluator" / "slow.py",
    "missing": None,
}
DATASET_STATES = (
    "ready",
    "mini",
    "tiny",
    "unlabeled",
    "duplicated",
    "wrong-answers",
    "leaky",
    "holdout-labelled",
    "split-by-database",
    "raw-export",
    "torn",
    "undeclared",
    "mostly-undeclared",
    "mostly-synthetic",
    "fully-synthetic",
    "generated-answers",
    "mostly-generated-answers",
    "missing",
)
CALIBRATION_STATES = ("none", "present")
GUIDE_MODES = ("clone", "local")
VENV_STATES = ("none", "ready")
# The name a project gives its own environment. Never `.venv-traigent`: that one is the
# guide's fallback; on that route it stops if one is already there, so a demo must never ship one.
PROJECT_VENV = ".venv"
# The interpreter a project environment is built with, newest first. The guide supports
# 3.11 to 3.13 and this repository targets the top of that range.
SUPPORTED_PYTHONS = ("python3.13", "python3.12", "python3.11")
# What the agent needs to import and run. The same pin the guide installs, so a project that
# already has it is not carrying a different version of the same thing.
AGENT_REQUIREMENT = "litellm==1.93.0"

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
# Every state whose rows leave here other than as the slice holds them. The questions and
# answers are Spider's throughout; what each state does to them on the way out is this
# repository's, and the manifest names it (`damage`) and describes it (`damage_detail`).
DAMAGED_STATES = (
    "duplicated",
    "wrong-answers",
    "leaky",
    "holdout-labelled",
    "split-by-database",
    "raw-export",
    "torn",
    "undeclared",
    "mostly-undeclared",
    "mostly-synthetic",
    "fully-synthetic",
    "generated-answers",
    "mostly-generated-answers",
)
# The states that ship the whole slice. Every other labelled state is a seeded draw.
FULL_SLICE_STATES = (
    "ready",
    "leaky",
    "split-by-database",
    "raw-export",
    "undeclared",
    "mostly-undeclared",
    "mostly-synthetic",
    "fully-synthetic",
    "generated-answers",
    "mostly-generated-answers",
)
UNLABELED_ROWS = 40
SAMPLE_SEED = 42
DRAW_SIZES = {
    "mini": MINI_ROWS,
    "tiny": TINY_ROWS,
    "unlabeled": UNLABELED_ROWS,
    "duplicated": DAMAGED_ROWS,
    "holdout-labelled": MINI_ROWS,
    "torn": MINI_ROWS,
}
# How many tuning rows `leaky` emits a second time under the held-out label, and how a
# copy's id differs from its original's. The copy repeats the row's text and nothing else:
# a copy that kept the id would be two rows with one name, which is a different defect
# and one the guide catches first, hiding the leak behind it.
LEAKED_ROWS = 6
LEAK_ID_SUFFIX = "-holdout"
# The share of rows `split-by-database` holds out as whole databases, and how far from it
# a cut made of whole databases is allowed to land.
DATABASE_HOLDOUT_SHARE = 0.2
DATABASE_HOLDOUT_TOLERANCE = 0.1
# How many lines `torn` cuts short, and where along the line each cut falls.
TORN_LINES = 2
TORN_AT = 0.6
# The key names a row is written under. `raw-export` uses Spider's own, the way a
# benchmark export carries them; everything else uses the two the first-run tooling reads.
DATASET_KEYS = {"input": "input", "output": "output"}
RAW_EXPORT_KEYS = {"input": "question", "output": "query"}
# What `undeclared` writes where the slice says `real`: the name of the benchmark split
# the rows were exported from, which is what somebody who exported them would write, and
# a word outside the guide's provenance vocabulary.
UNDECLARED_PROVENANCE = "spider-dev"
# The share of rows the three "mostly" states touch. The guide's provenance ladder and its
# answer-key ladder each have a rung at "more than half", so damaging every row and
# damaging most of them are different readings, not the same one twice: 65 against 70 on
# the provenance ladder, and a different condition and remedy on the card. 0.6 clears the
# guide's 0.5 boundary by a margin no rounding can cross.
MOSTLY_SHARE = 0.6
# What a row says when the customer declares the row itself written rather than collected,
# and what it says when they declare the ANSWER model-written while the question stays
# real. Both are the fictional customer's own declaration about their own rows -- the same
# in-world channel `undeclared` writes on -- and neither says anything about where this
# repository's bytes came from. `docs/dataset.md` states that separation once, for all of
# them.
SYNTHETIC_PROVENANCE = "synthetic"
GENERATED_ANSWER_PROVENANCE = "model-generated"
# Where a row carries the second declaration. The guide reads an answer's provenance from
# `output_provenance` at the row's top level or inside `metadata`; this repository writes
# everything but `input` and `output` in `metadata`, so it uses that one.
GENERATED_ANSWER_KEY = "output_provenance"
# The two halves of a row's metadata. `STRUCTURAL_ROW_FIELDS` say where the row sits and
# what it is about; `DECLARATION_ROW_FIELDS` are the customer speaking about their own
# rows, which is what the guide's provenance and answer-key checks read.
#
# The split is named rather than derived, and the suite fails when a shipped row carries a
# key in neither set (`test_every_metadata_key_is_classified_as_structure_or_declaration`).
# Deriving it -- "a declaration is anything that is not structural" -- was tried and is
# wrong in the expensive direction: it swept `schema`, the row's whole CREATE TABLE block,
# into a file that has no use for it. Naming both sides means a new field cannot be quietly
# assumed into either one.
STRUCTURAL_ROW_FIELDS = frozenset({"id", "db_id", "difficulty", "split", "schema"})
DECLARATION_ROW_FIELDS = frozenset({"provenance", GENERATED_ANSWER_KEY})

# Where a project keeps the probe answers it uses to check its own scorer. The guide reads
# this path, and a project that has one can have its evaluator validated at the opening gate
# instead of being held at the unvalidated ceiling.
RUNS_DIRECTORY = "traigent-runs"
CALIBRATION_FILE = "calibration-cases.json"
_TEXT_PROBES = COMPONENTS / "calibration" / "exact_match.json"
CALIBRATION_SOURCES = {
    "exact-match": _TEXT_PROBES,
    # Its own file, not the shared text probes. The slow scorer's comparison is weaker
    # than the text comparator's -- whitespace, keyword case and a trailing semicolon,
    # and nothing about quoting -- so it fails four of the shared `equivalent_good`
    # probes. Shipping those would be exactly the answers-nobody-checked this module
    # refuses elsewhere. These cases pin what it really accepts, and each was run
    # against the shipped scorer before it was written down.
    "slow": COMPONENTS / "calibration" / "slow.json",
    "exec-match": COMPONENTS / "calibration" / "exec_match.json",
    # The always-correct scorer is deliberately given the text comparator's probes: the
    # point is that it fails the same questions the honest one passes. One file rather than
    # a byte-identical copy, because a copy can only drift away from what it is comparing to.
    "broken": _TEXT_PROBES,
    # The mis-wired scorer never looks at the answer, so it fails the same probes for the
    # opposite reason: it marks the right answer wrong instead of the wrong answer right.
    "swapped": _TEXT_PROBES,
    # The length comparison gets the same probes and fails them differently again: the
    # recorded answer scores 1.0, a re-spelling of it scores less, and a wrong answer of
    # about the same length scores nearly full marks. Not constant, and not a ruler.
    "length-blind": _TEXT_PROBES,
    # `opaque` has no entry on purpose. Its grader is a library the project does not
    # carry, so nothing here has ever run it, and probe answers for it would be answers
    # nobody has checked -- `--calibration present` is refused for it.
}
# The guide reserves this as its fallback; on that route it stops if one is already there,
# so a demo must never pre-empt it.
FORBIDDEN_VENV_NAME = ".venv-traigent"

# Which evaluator method and task kind each evaluator honestly is. Recorded in the manifest
# so a run can be described without re-deriving it, and reported by `list`.
EVALUATOR_FACTS: dict[str, dict[str, Any]] = {
    "exact-match": {"method": "normalized-exact", "executes_candidate_output": False},
    "exec-match": {"method": "execution", "executes_candidate_output": True},
    "broken": {"method": "normalized-exact", "executes_candidate_output": False},
    "swapped": {"method": "normalized-exact", "executes_candidate_output": False},
    # No method, because none can be declared honestly. The grader the file calls is not
    # here to read, so whether it executes anything is unknown too: `None` on both, which
    # is the same answer as "not declared" and never more than the file supports.
    "opaque": {"method": None, "executes_candidate_output": None},
    # No method either. A comparison of lengths is not one of the methods the guide
    # names, and declaring the nearest one would credit the file with a comparison it
    # does not make. It imports nothing and runs nothing, so that half is known.
    "length-blind": {"method": None, "executes_candidate_output": False},
    # A method can be declared here: the comparison really is a normalised text match,
    # and the sleep is in how it reaches that comparison rather than in what it compares.
    "slow": {"method": "normalized-exact", "executes_candidate_output": False},
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
    "leaky-split": {"agent": "ready", "dataset": "leaky", "eval": "exact-match"},
    "holdout-only": {
        "agent": "ready",
        "dataset": "holdout-labelled",
        "eval": "exact-match",
    },
    "split-by-database": {
        "agent": "ready",
        "dataset": "split-by-database",
        "eval": "exact-match",
    },
    "raw-export": {"agent": "ready", "dataset": "raw-export", "eval": "exact-match"},
    "torn-lines": {"agent": "ready", "dataset": "torn", "eval": "exact-match"},
    "undeclared-source": {
        "agent": "ready",
        "dataset": "undeclared",
        "eval": "exact-match",
    },
    "mostly-undeclared-source": {
        "agent": "ready",
        "dataset": "mostly-undeclared",
        "eval": "exact-match",
    },
    "mostly-synthetic-source": {
        "agent": "ready",
        "dataset": "mostly-synthetic",
        "eval": "exact-match",
    },
    "synthetic-source": {
        "agent": "ready",
        "dataset": "fully-synthetic",
        "eval": "exact-match",
    },
    "generated-answer-key": {
        "agent": "ready",
        "dataset": "generated-answers",
        "eval": "exact-match",
    },
    "mostly-generated-answer-key": {
        "agent": "ready",
        "dataset": "mostly-generated-answers",
        "eval": "exact-match",
    },
    "opaque-scorer": {"agent": "ready", "dataset": "ready", "eval": "opaque"},
    "slow-scorer": {
        "agent": "ready",
        "dataset": "ready",
        "eval": "slow",
        "calibration": "present",
    },
    "length-blind": {
        "agent": "ready",
        "dataset": "ready",
        "eval": "length-blind",
        "calibration": "present",
    },
    "two-agents": {"agent": "two-agents", "dataset": "ready", "eval": "exact-match"},
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
    "empty": "nothing to work with yet -- no agent, no data, no scorer",
    "wrong-wiring": "a scorer comparing the question with the answer, never the output",
    "duplicated-data": "half the rows appear twice, question and answer both",
    "wrong-answers": "every answer runs, and answers a different question",
    "hand-written": "ten examples, and probes kept for the scorer",
    "best-case": "tunable, complete, probes kept, and scored by running the SQL",
    "leaky-split": "six tuning rows appear a second time as held-out rows",
    "holdout-only": "answers on the held-out rows only; nothing to tune on",
    "split-by-database": "the held-out rows are whole databases the tuning side never sees",
    "raw-export": "the rows under Spider's own key names, as the benchmark exports them",
    "torn-lines": "two lines of the data cut short, the way a stopped export leaves them",
    "slow-scorer": "the scorer is right and asks a service per row, so checking it runs long",
    "undeclared-source": "every row says where it came from in a word the guide does not know",
    "mostly-undeclared-source": "most rows do, and the rest still say they were collected",
    "mostly-synthetic-source": "most rows declare themselves written rather than collected",
    "synthetic-source": "every row declares itself written rather than collected",
    "generated-answer-key": "every answer is declared model-written; the questions are real",
    "mostly-generated-answer-key": "most answers are, and the rest were written by a person",
    "opaque-scorer": "a scorer that calls a grading library the project does not carry",
    "length-blind": "a scorer that compares the lengths of the two queries, and probes",
    "two-agents": "a second agent beside the first, and a note saying which one to work on",
}

# The readiness conditions each preset was built to put on the guide's opening card -- the
# state it stands for, in the guide's own vocabulary. Declared once, here beside the presets,
# so that the committed measurement of each one can be held to it: a re-measurement at a
# later guide revision that moves a preset off the state it was built for fails the suite
# instead of being published as an ordinary change of score.
#
# Two presets are built for no condition. `checked` is the complete project with nothing
# wrong in it, and `two-agents` asks which agent a run selects, which the opening card does
# not record; `tests/test_score_bank.py` declares exactly what each one's card carries.
# Three are built for a condition their own card does not carry -- one needs probes the
# preset does not ship, one a row review the measurement never passes, and one is a
# finding about the guide -- and `tests/test_score_bank.py` names each with its reason.
PRESET_CAPS: dict[str, tuple[str, ...]] = {
    "ready": ("evaluator-unvalidated",),
    "checked": (),
    "no-eval": ("evaluator-absent",),
    "no-labels": ("dataset-no-expected-outputs",),
    "no-knobs": ("agent-no-varying-knobs",),
    "sql-exec-stop": ("evaluator-calibration-refused",),
    "fake-ruler": ("evaluator-invalid",),
    "agent-and-logs": ("dataset-no-expected-outputs", "evaluator-absent"),
    "logs-only": ("agent-absent", "dataset-no-expected-outputs", "evaluator-absent"),
    "no-agent": ("agent-absent",),
    "no-data": ("dataset-absent",),
    "empty": ("agent-absent", "dataset-absent", "evaluator-absent"),
    "wrong-wiring": ("evaluator-invalid",),
    "duplicated-data": ("dataset-integrity-fail", "dataset-repeated-rows"),
    "wrong-answers": ("dataset-unsound-expected-outputs",),
    "hand-written": ("dataset-below-measurable-size",),
    "best-case": ("evaluator-calibration-refused",),
    "leaky-split": ("dataset-tune-holdout-overlap",),
    "holdout-only": ("dataset-tuning-split-empty",),
    "split-by-database": ("dataset-split-by-task-family",),
    "raw-export": ("dataset-shape-unrecognised",),
    "torn-lines": ("dataset-integrity-fail",),
    "undeclared-source": ("dataset-undeclared-provenance",),
    "mostly-undeclared-source": ("dataset-mostly-undeclared",),
    "mostly-synthetic-source": ("dataset-mostly-synthetic",),
    "synthetic-source": ("dataset-fully-synthetic",),
    "generated-answer-key": ("dataset-generated-answer-key",),
    "mostly-generated-answer-key": ("dataset-mostly-generated-answer-key",),
    "opaque-scorer": ("evaluator-unresolved",),
    "slow-scorer": ("evaluator-timeout",),
    "length-blind": ("evaluator-invalid",),
    "two-agents": (),
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
    # Checked directly, and not only through Git. A ZIP download, a vendored copy or a
    # `tar --exclude=.git` of this repository has no `.git` to find, and building into one
    # of those put the demo inside the very checkout it is supposed to be independent of.
    target = parent.resolve() / out.name
    if target == REPO_ROOT or target.is_relative_to(REPO_ROOT):
        raise BuildError(
            f"output would land inside this repository at {target}. Build demos outside it "
            "-- a demo built inside the thing that made it is not self-contained, and the "
            "agent is supposed to see only the demo."
        )
    enclosing = enclosing_git_repository(parent.resolve())
    if enclosing is not None:
        raise BuildError(
            f"output would land inside the Git working tree at {enclosing}. Build demos "
            "outside every checkout -- a demo inside one gets picked up as part of that "
            "project, and the guide is supposed to see only the demo."
        )


def band_balanced_sample(
    rows: Sequence[dict[str, Any]], wanted: int
) -> list[dict[str, Any]]:
    """A deterministic draw of `wanted` rows, spread evenly across the difficulty bands.

    Taking a slice off the front of a list sorted by `(difficulty, input)` is not a sample of
    it: alphabetically `easy < hard < medium < very-hard`, so half of a 60-row set came out
    as every easy row and every hard row and nothing else.
    """
    by_band: dict[str, list[dict[str, Any]]] = {}
    for row in rows:
        by_band.setdefault(row["metadata"]["difficulty"], []).append(row)
    if not by_band:
        return []
    rng = random.Random(SAMPLE_SEED)
    per_band, remainder = divmod(wanted, len(by_band))
    picked: list[dict[str, Any]] = []
    for position, band_name in enumerate(sorted(by_band)):
        take = per_band + (1 if position < remainder else 0)
        pool = sorted(by_band[band_name], key=lambda r: r["input"])
        rng.shuffle(pool)
        picked.extend(pool[:take])
    return picked


def deranged_draw(rows: list[dict[str, Any]], wanted: int) -> list[dict[str, Any]]:
    """The rows `wrong-answers` draws, chosen so that rotating answers moves every one.

    Rotating inside a database only re-pairs a row if that database contributes at least two
    rows and no two of them carry the same gold query. Drawn without that constraint, four
    databases contributed a single row each -- a rotation of one is the identity -- and a
    fifth rotated a row onto a byte-identical answer, so five of sixty rows kept the answer
    they came with while the project claimed every answer had moved.

    So the draw is made out of whole database groups: a database contributes two rows, or
    three where a band needs an odd count, and never one. Within a band the groups are taken
    in a seeded order, so the draw is the same everywhere; the bands are filled to the same
    size the even draw would have used.
    """
    # One row per distinct gold query per database, so a group can never rotate a row onto
    # its own answer. Ordered before anything is dropped, so which row survives is fixed.
    candidates: dict[tuple[str, str], list[dict[str, Any]]] = {}
    seen: dict[str, set[str]] = {}
    for row in sorted(
        rows,
        key=lambda r: (
            r["metadata"]["db_id"],
            r["metadata"]["difficulty"],
            r["input"],
        ),
    ):
        db_id = row["metadata"]["db_id"]
        if row["output"] in seen.setdefault(db_id, set()):
            continue
        seen[db_id].add(row["output"])
        candidates.setdefault((row["metadata"]["difficulty"], db_id), []).append(row)

    groups = {key: group for key, group in candidates.items() if len(group) >= 2}
    bands = sorted({band for band, _ in groups})
    if not bands:
        raise BuildError(
            "no database in the slice has two rows with different answers in one difficulty "
            "band, so no draw can be rotated"
        )
    rng = random.Random(SAMPLE_SEED)
    per_band, remainder = divmod(wanted, len(bands))
    picked: list[dict[str, Any]] = []
    for position, band_name in enumerate(bands):
        take = per_band + (1 if position < remainder else 0)
        pool = sorted(key for key in groups if key[0] == band_name)
        rng.shuffle(pool)
        chosen: list[dict[str, Any]] = []
        for key in pool:
            room = take - len(chosen)
            if room == 0:
                break
            group = groups[key]
            if room <= 3:
                # The last group closes the band exactly. Two leaves an odd band one short
                # and a group of one cannot be rotated, so the remainder is taken whole.
                if len(group) >= room:
                    chosen.extend(group[:room])
                continue
            chosen.extend(group[:2])
        if len(chosen) != take:
            raise BuildError(
                f"the {band_name} band cannot supply {take} rows in groups of two or more "
                "per database with distinct answers"
            )
        picked.extend(chosen)
    picked.sort(key=lambda r: (r["metadata"]["difficulty"], r["input"]))
    return picked


def select_rows(rows: list[dict[str, Any]], state: str) -> list[dict[str, Any]]:
    """The rows a given dataset state ships.

    Drawn evenly across difficulty, and within each band across the tuning/holdout split in
    the same proportion the full slice uses. Sampling on difficulty alone would keep the
    bands balanced and quietly flatten the split -- a 30-row draw came out with a single
    held-out question in three of the four bands, which cannot check a winner against
    anything.

    `wrong-answers` draws differently, because the damage it ships constrains which rows can
    be drawn at all -- see `deranged_draw`.
    """
    if state in FULL_SLICE_STATES:
        return list(rows)
    if state == "wrong-answers":
        return deranged_draw(rows, DAMAGED_ROWS)
    wanted = DRAW_SIZES[state]
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

    Both claims are checked here rather than asserted in prose: no row keeps the answer it
    came with, and every answer that ships still runs against its own database and still
    returns rows.

    `leaky` appends a few tuning rows a second time under the held-out label, `split-by-
    database` moves the split line so that it falls between databases, and `undeclared`
    rewrites what every row says about where it came from. The remaining damaged states --
    `holdout-labelled`, `raw-export` and `torn` -- change nothing about which rows ship or
    what they hold; what they change is how the rows are written, which is `project_row`'s
    and `write_dataset`'s business, so they pass through here untouched.
    """
    if state == "leaky":
        return leak_rows(rows)
    if state == "split-by-database":
        return resplit_by_database(rows)
    if state == "undeclared":
        return [
            {
                **row,
                "metadata": {**row["metadata"], "provenance": UNDECLARED_PROVENANCE},
            }
            for row in rows
        ]
    if state == "mostly-undeclared":
        return declare_on_most(rows, "provenance", UNDECLARED_PROVENANCE)
    if state == "mostly-synthetic":
        return declare_on_most(rows, "provenance", SYNTHETIC_PROVENANCE)
    if state == "fully-synthetic":
        return [
            {
                **row,
                "metadata": {**row["metadata"], "provenance": SYNTHETIC_PROVENANCE},
            }
            for row in rows
        ]
    if state == "generated-answers":
        return [
            {
                **row,
                "metadata": {
                    **row["metadata"],
                    GENERATED_ANSWER_KEY: GENERATED_ANSWER_PROVENANCE,
                },
            }
            for row in rows
        ]
    if state == "mostly-generated-answers":
        return declare_on_most(rows, GENERATED_ANSWER_KEY, GENERATED_ANSWER_PROVENANCE)
    if state not in ("duplicated", "wrong-answers"):
        return list(rows)
    if state == "duplicated":
        # A band-balanced draw, not the front of the list. Sorted by `(difficulty, input)`,
        # the front of a 60-row set is every easy row and every hard row, which ships a
        # difficulty spread nothing in the project accounts for.
        repeated = band_balanced_sample(
            rows, max(1, round(len(rows) * DUPLICATED_SHARE))
        )
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
    for db_id, positions in by_database.items():
        if len(positions) < 2:
            raise BuildError(
                f"database {db_id} contributes one row, and a rotation of one row is the "
                "identity -- that row would keep its own answer"
            )
        borrowed = [answers[p] for p in positions[1:]] + [answers[positions[0]]]
        for position, answer in zip(positions, borrowed):
            answers[position] = answer
    damaged = [{**row, "output": answer} for row, answer in zip(rows, answers)]
    check_every_answer_moved(rows, damaged)
    check_answers_run(damaged)
    return damaged


def leak_rows(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """The slice, with a few tuning rows emitted a second time as held-out rows.

    The shape of a holdout somebody drew from the file they were already tuning on: the
    same question and the same answer on both sides of the line, so the check that is
    supposed to catch a winner tuned to its own test has nothing to catch it with. The rows
    are drawn across the difficulty bands, seeded, and appended the way an export appends
    rather than sorted in beside their originals.

    Each copy carries its own id, and that is a decision rather than an oversight. A copy
    that kept the original's id is two rows with one name -- the `duplicated` defect -- and
    the guide reports that one first and holds the score below where this one would bind,
    so the leak would never be measured on its own. The copy repeats the row's text; the
    text is the leak.
    """
    tuning = [row for row in rows if row["metadata"].get("split") == "tuning"]
    leaked = band_balanced_sample(tuning, LEAKED_ROWS)
    if len(leaked) != LEAKED_ROWS:
        raise BuildError(
            f"the tuning side supplies {len(leaked)} rows for the leak and {LEAKED_ROWS} "
            "are needed"
        )
    copies = [
        {
            **row,
            "metadata": {
                **row["metadata"],
                "split": "holdout",
                "id": f"{row['metadata']['id']}{LEAK_ID_SUFFIX}",
            },
        }
        for row in leaked
    ]
    return list(rows) + copies


def leaked_ids(rows: Sequence[dict[str, Any]]) -> list[str]:
    """The ids of the rows a `leaky` dataset emits twice, read off the rows that ship."""
    return [
        row["metadata"]["id"][: -len(LEAK_ID_SUFFIX)]
        for row in rows
        if row["metadata"]["id"].endswith(LEAK_ID_SUFFIX)
    ]


def resplit_by_database(rows: Sequence[dict[str, Any]]) -> list[dict[str, Any]]:
    """The slice, re-split so that the held-out rows are whole databases.

    A split a customer actually makes: hold a few databases back and tune on the rest, so
    the winner is checked on schemas it never saw. The databases are taken in a seeded
    order and kept while the held-out side stays under the share the slice holds out plus
    the tolerance, so the cut lands as near one row in five as whole databases allow; it is
    refused if whole databases cannot get within the tolerance at all.
    """
    sizes: Counter[str] = Counter(row["metadata"]["db_id"] for row in rows)
    order = sorted(sizes)
    random.Random(SAMPLE_SEED).shuffle(order)
    target = len(rows) * DATABASE_HOLDOUT_SHARE
    ceiling = target * (1 + DATABASE_HOLDOUT_TOLERANCE)
    held: list[str] = []
    count = 0
    for db_id in order:
        if count + sizes[db_id] <= ceiling:
            held.append(db_id)
            count += sizes[db_id]
    if count < target * (1 - DATABASE_HOLDOUT_TOLERANCE):
        raise BuildError(
            f"whole databases cannot hold out about {DATABASE_HOLDOUT_SHARE:.0%} of "
            f"{len(rows)} rows: the nearest cut holds {count}"
        )
    held_out = set(held)
    return [
        {
            **row,
            "metadata": {
                **row["metadata"],
                "split": (
                    "holdout" if row["metadata"]["db_id"] in held_out else "tuning"
                ),
            },
        }
        for row in rows
    ]


def held_out_databases(rows: Sequence[dict[str, Any]]) -> list[str]:
    """The databases every one of whose rows is held out, read off the rows that ship."""
    sides: dict[str, set[str]] = {}
    for row in rows:
        sides.setdefault(row["metadata"]["db_id"], set()).add(row["metadata"]["split"])
    return sorted(db_id for db_id, splits in sides.items() if splits == {"holdout"})


def torn_line_numbers(count: int) -> list[int]:
    """Which lines `torn` cuts short, one-based, for a file of `count` lines.

    A third and two thirds of the way in: never the first line, which is the one a
    reader opens the file on, and never the last, which is where a stopped export is
    expected to be ragged. A file too short to hold two cuts away from both ends is
    refused rather than cut somewhere else.
    """
    if count < 6:
        raise BuildError(f"{count} rows is too few to tear {TORN_LINES} lines out of")
    return [count // 3, 2 * count // 3]


def check_every_answer_moved(
    before: Sequence[dict[str, Any]], after: Sequence[dict[str, Any]]
) -> None:
    """No row keeps the answer it came with.

    The project claims every answer moved. A row that rotated onto a byte-identical query
    has not moved, and it is indistinguishable from a correct row -- which makes the claim
    false and the damage unmeasurable at the same time.
    """
    kept = [
        original["metadata"].get("id", original["input"])
        for original, rotated in zip(before, after)
        if original["output"] == rotated["output"]
    ]
    if kept:
        raise BuildError(
            f"{len(kept)} of {len(after)} rows kept their own answer "
            f"({', '.join(str(name) for name in kept[:5])}), so 'every answer answers a "
            "different question' is not true of what would ship"
        )


def check_answers_run(rows: Sequence[dict[str, Any]]) -> None:
    """Every answer still runs against its own database and still returns rows.

    An answer that does not run makes the damage obvious for the wrong reason, and one that
    returns nothing scores the same as one that is right about an empty table.
    """
    for row in rows:
        db_id = row["metadata"]["db_id"]
        database = DATABASES_PATH / db_id / f"{db_id}.sqlite"
        if not database.is_file():
            raise BuildError(f"database missing from the repository: {database}")
        connection = sqlite3.connect(f"file:{database}?mode=ro", uri=True)
        try:
            returned = connection.execute(row["output"]).fetchone()
        except sqlite3.Error as error:
            raise BuildError(
                f"the answer paired with {row['input']!r} does not run against {db_id}: "
                f"{error}"
            ) from error
        finally:
            connection.close()
        if returned is None:
            raise BuildError(
                f"the answer paired with {row['input']!r} returns no rows from {db_id}"
            )


def project_row(row: dict[str, Any], state: str) -> dict[str, Any]:
    """One dataset line as the demo ships it.

    Flat: `input` is the question and `output` is the gold SQL, both plain text. The
    first-run tooling reads those two fields as text -- handing it nested objects puts the
    whole CREATE TABLE block inside the row's identity and corrupts its duplicate and split
    analysis. Everything else rides in `metadata`, where the evaluator can still reach it.
    """
    if state == "raw-export":
        # Spider's own key names, the way the benchmark's export carries them: the
        # question under `question`, the gold query under `query`, the database at the
        # top level as well as in `metadata`. Nothing about the row is changed except
        # what it is called.
        return {
            RAW_EXPORT_KEYS["input"]: row["input"],
            RAW_EXPORT_KEYS["output"]: row["output"],
            "db_id": row["metadata"]["db_id"],
            "metadata": dict(row["metadata"]),
        }
    projected: dict[str, Any] = {"input": row["input"]}
    if row_is_labelled(row, state):
        projected["output"] = row["output"]
    projected["metadata"] = dict(row["metadata"])
    if state == "unlabeled":
        # No expected answer means no split to hold out and nothing to grade against.
        projected["metadata"].pop("split", None)
    return projected


def declare_on_most(
    rows: Sequence[dict[str, Any]], declaration: str, value: str
) -> list[dict[str, Any]]:
    """Write one declaration onto most of the rows, and leave the rest alone.

    The rows that carry it are a band-balanced draw rather than the front of the
    list, for the reason `duplicated` takes one: sorted by difficulty, the front
    of the set is whole bands, so damaging it would ship a difficulty spread
    nothing in the project accounts for and the guide would be reading two
    things at once.

    The row order is unchanged -- only the fields move -- so the split counts,
    the ids and the question texts are the same as the undamaged slice's, which
    is what makes the reading a reading of this declaration and nothing else.
    """

    touched = {
        row["metadata"]["id"]
        for row in band_balanced_sample(rows, round(len(rows) * MOSTLY_SHARE))
    }
    return [
        (
            {**row, "metadata": {**row["metadata"], declaration: value}}
            if row["metadata"]["id"] in touched
            else {**row, "metadata": dict(row["metadata"])}
        )
        for row in rows
    ]


def row_is_labelled(row: dict[str, Any], state: str) -> bool:
    """Whether this row ships with its answer.

    `holdout-labelled` keeps the answer on the held-out rows only -- the state of a team
    that wrote out the answers it meant to grade on and never the ones it meant to tune
    on -- so what is labelled is a property of the row and not only of the state.
    """
    if state == "unlabeled":
        return False
    if state == "holdout-labelled":
        return bool(row["metadata"].get("split") == "holdout")
    return True


def dataset_keys(state: str) -> dict[str, str]:
    """Under which names a row's question and answer are written in this state."""
    return RAW_EXPORT_KEYS if state == "raw-export" else DATASET_KEYS


def write_jsonl(path: Path, rows: Sequence[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for row in rows:
            handle.write(json.dumps(row, ensure_ascii=False, sort_keys=True) + "\n")


def write_dataset(path: Path, rows: Sequence[dict[str, Any]], state: str) -> list[int]:
    """The rows as the state writes them, and which lines, if any, were cut short.

    `torn` writes every row and then cuts two of the lines part-way through, which is
    what an export that stopped mid-write leaves behind: most of the file is fine, two
    lines are not JSON, and nothing announces which. The cut lines are chosen by position,
    so the same build tears the same lines everywhere, and each cut is checked to have
    made the line unreadable -- a cut that happened to leave valid JSON would ship a file
    with nothing wrong with it under a record saying two lines are torn.
    """
    write_jsonl(path, rows)
    if state != "torn":
        return []
    torn = torn_line_numbers(len(rows))
    lines = path.read_text(encoding="utf-8").split("\n")
    for number in torn:
        line = lines[number - 1]
        cut = line[: int(len(line) * TORN_AT)]
        try:
            json.loads(cut)
        except ValueError:
            lines[number - 1] = cut
            continue
        raise BuildError(f"cutting line {number} at {TORN_AT:.0%} left it readable")
    path.write_text("\n".join(lines), encoding="utf-8")
    return torn


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

    Called while a Plan is being made. `check_calibration_source` has to have passed first;
    it is what makes the lookup and the read below safe.
    """
    if calibration_state != "present":
        return set()
    check_calibration_source(evaluator_state)
    source = CALIBRATION_SOURCES[evaluator_state]
    try:
        cases = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        raise BuildError(f"{source} cannot be read: {error}") from error
    return {
        case["metadata"]["db_id"]
        for case in cases
        if isinstance(case.get("metadata"), dict) and case["metadata"].get("db_id")
    }


def check_databases_present(databases: Sequence[str]) -> None:
    """Refuse a build whose rows or probes name a database this repository does not hold."""
    for db_id in databases:
        source = DATABASES_PATH / db_id / f"{db_id}.sqlite"
        if not source.exists():
            raise BuildError(f"database missing from the repository: {source}")


def copy_databases(databases: Sequence[str], destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for db_id in databases:
        source = DATABASES_PATH / db_id / f"{db_id}.sqlite"
        target = destination / db_id
        target.mkdir(exist_ok=True)
        shutil.copy2(source, target / f"{db_id}.sqlite")


def resolve_python() -> str:
    """The newest supported interpreter on this machine."""
    for name in SUPPORTED_PYTHONS:
        found = shutil.which(name)
        if found is not None:
            return found
    raise BuildError(
        f"--venv ready needs one of {', '.join(SUPPORTED_PYTHONS)} on PATH, and none is "
        "there. Install one, or build without --venv."
    )


def make_project_venv(project: Path, interpreter: str) -> dict[str, Any]:
    """A working environment for the project, the way a project that runs has one.

    Not scenery. The agent's dependency is installed, so the agent imports and the project
    can actually be run before the guide builds an environment of its own. The guide discovers
    this environment and proposes installing into it (existing-project route); `--venv ready`
    changes which route the run takes and what the approval card shows.
    """
    venv_dir = project / PROJECT_VENV
    run_or_refuse(
        [interpreter, "-m", "venv", str(venv_dir)],
        f"could not create {PROJECT_VENV}",
    )
    strip_venv_origin(venv_dir)
    run_or_refuse(
        [str(venv_dir / "bin" / "pip"), "install", "--quiet", AGENT_REQUIREMENT],
        f"could not install {AGENT_REQUIREMENT} into {PROJECT_VENV}",
    )
    version = run_or_refuse(
        [
            str(venv_dir / "bin" / "python"),
            "-c",
            "import sys; print('.'.join(map(str, sys.version_info[:3])))",
        ],
        f"{PROJECT_VENV} was built and does not run",
    ).strip()
    # The environment is rewritten above, so this is the proof that it still works: the
    # agent's own dependency, imported by the project's own interpreter.
    run_or_refuse(
        [str(venv_dir / "bin" / "python"), "-c", "import litellm"],
        f"{PROJECT_VENV} cannot import what the agent needs",
    )
    return {
        "path": PROJECT_VENV,
        "python_version": version,
        "installed": [AGENT_REQUIREMENT],
    }


def run_or_refuse(command: Sequence[str], what: str) -> str:
    """Run a command, or refuse the build saying what failed. Never a `CalledProcessError`.

    A build is refused with `BuildError`, which `main` turns into one line and exit 2. A
    subprocess failure that escapes as `CalledProcessError` is the same failure printed as a
    traceback with a different exit code, from the same function, for no reason a reader can
    see.
    """
    try:
        result = subprocess.run(
            list(command), capture_output=True, text=True, check=False
        )
    except OSError as error:
        raise BuildError(f"{what}: {error}") from error
    if result.returncode != 0:
        raise BuildError(
            f"{what}: {result.stderr.strip() or result.stdout.strip() or 'no output'}"
        )
    return result.stdout


# What a virtual environment needs in its `pyvenv.cfg` to work. `executable` and `command`
# are records of how it was made, and `command` holds the absolute path it was created at --
# which, in a bank built one directory per starting state, is the name of the starting state.
VENV_CONFIG_KEYS = frozenset(
    {
        "home",
        "include-system-site-packages",
        "version",
        "version_info",
        "implementation",
    }
)


def strip_venv_origin(venv_dir: Path) -> None:
    """Drop the keys that record where the environment was built, keep the ones it runs on."""
    config = venv_dir / "pyvenv.cfg"
    try:
        lines = config.read_text(encoding="utf-8").splitlines()
    except (OSError, UnicodeDecodeError) as error:
        raise BuildError(f"could not read {config.name}: {error}") from error
    kept = [
        line
        for line in lines
        if line.split("=", 1)[0].strip().casefold() in VENV_CONFIG_KEYS
    ]
    if not kept:
        raise BuildError(
            f"{config.name} holds none of {sorted(VENV_CONFIG_KEYS)}, so rewriting it would "
            "leave an environment that cannot run"
        )
    config.write_text("\n".join(kept) + "\n", encoding="utf-8")


def check_guide_source(guide_src: Path | None) -> None:
    """Refuse a guide checkout that is not one, before the demo directory is created.

    A copied checkout is the only thing that brings an arbitrary tree into a project, so the
    two things that tree could be wrong about are settled here: it has to be a checkout, and
    it must not already hold the environment the guide creates for itself.
    """
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
    for name in GUIDE_PATHS:
        source = resolved / name
        if not source.exists():
            continue
        found = (
            [source]
            if source.name == FORBIDDEN_VENV_NAME
            else (list(source.rglob(FORBIDDEN_VENV_NAME)) if source.is_dir() else [])
        )
        for path in found:
            raise BuildError(
                f"{resolved} holds a {FORBIDDEN_VENV_NAME} at "
                f"{path.relative_to(resolved)}, and copying it in would hand over a demo "
                "whose fallback route the guide would refuse."
            )


def guide_revision(guide_src: Path) -> str:
    """The commit the copied guide checkout is at.

    Recorded so a run can be tied to the guide it was run against. Refused rather than
    written as null: `"git_sha": null` is what a checkout with no commits, a machine with no
    git and a `rev-parse` that failed all look like, and a record that cannot tell those
    apart is not evidence of anything.
    """
    return run_or_refuse(
        ["git", "-C", str(guide_src), "rev-parse", "HEAD"],
        f"could not read the commit of the guide checkout at {guide_src}",
    ).strip()


def check_calibration_source(evaluator_state: str) -> None:
    """Refuse a calibration request that has no cases to ship, before anything is written."""
    source = CALIBRATION_SOURCES.get(evaluator_state)
    if source is None and EVALUATOR_FILES.get(evaluator_state) is not None:
        # A scorer that exists and has no probes is not the same refusal as no scorer.
        # `opaque` hands the answer to a library the project does not carry, so nothing
        # here has ever run it, and probe answers for it would be answers nobody checked.
        # The message stays general: the next scorer without probes may lack them for a
        # reason of its own, and its docstring is where that reason lives.
        raise BuildError(
            f"no probe answers ship for --eval {evaluator_state}: nothing in this "
            "repository has run that scorer, so nothing could vouch for the probes; its "
            "docstring says why"
        )
    if source is None:
        raise BuildError(
            f"--calibration present needs an evaluator to calibrate, and "
            f"--eval {evaluator_state} ships none"
        )
    if not source.exists():
        raise BuildError(f"calibration cases missing from the repository: {source}")


def copy_calibration(evaluator_state: str, project: Path) -> dict[str, Any]:
    """The probe answers this project keeps for its own scorer.

    Each evaluator gets its own cases, because what counts as an equivalent answer is not the
    same question for a scorer that compares text as for one that compares rows.

    Whether there are cases to copy at all is `check_calibration_source`'s question, asked
    while the Plan is made. This used to re-ask it in the same two `raise`s, word for word,
    from a point where the project directory already existed.
    """
    source = CALIBRATION_SOURCES[evaluator_state]
    runs = project / RUNS_DIRECTORY
    runs.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, runs / CALIBRATION_FILE)
    cases = json.loads(source.read_text(encoding="utf-8"))
    return {
        "path": f"{RUNS_DIRECTORY}/{CALIBRATION_FILE}",
        "case_count": len(cases),
    }


def copy_guide(guide_src: Path, project: Path, git_sha: str | None) -> dict[str, Any]:
    """Copy a guide checkout into the project the agent is pointed at.

    The copy lands in the project, not beside it: the handoff for `--guide local` tells the
    agent to read `./traigent-first-run/GUIDE.md`, relative to the directory it is started in.
    """
    guide_src = guide_src.expanduser().resolve()
    destination = project / GUIDE_DIRECTORY
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
    return {
        "directory": GUIDE_DIRECTORY,
        "source": str(guide_src),
        "paths": copied,
        "git_sha": git_sha,
    }


def inventory(project: Path) -> list[dict[str, Any]]:
    """Every file in the project, with its hash, so drift is visible later."""
    files = []
    for path in sorted(project.rglob("*")):
        if path.is_dir() or path.is_symlink():
            continue
        if PROJECT_VENV in path.relative_to(project).parts:
            continue
        files.append(
            {
                "path": path.relative_to(project).as_posix(),
                "sha256": sha256_of(path),
                "size": path.stat().st_size,
            }
        )
    return files


FILE_DESCRIPTIONS = {
    PROJECT_NOTE: "which of the two agents here this project is about.",
    "agent.py": "writes the SQL. `run(question, config)` returns a query as text.",
    f"{SECOND_AGENT_DIRECTORY}/": None,  # filled in from what the directory holds
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
    ".gitignore": "keeps `.env`, the environments and the run artifacts out of a repository.",
    ATTRIBUTION_NAME: (
        "where the questions come from, the licence they are under, and that they were "
        "modified. It travels with them."
    ),
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
    keys: dict[str, str] | None = None,
    second_agent_rows: int = 0,
) -> str:
    """The project's own README, describing only what this project actually contains.

    Every line of it is derived from the files that were written. A fixed description would
    tell a reader about files that are not here and fields the rows do not carry -- which, in
    a project deliberately built with something missing, hands over the very thing the run is
    supposed to discover.
    """
    # `DATASET_KEYS` is a module constant, and a constant used as a default
    # argument is one shared object every caller could mutate through.
    keys = DATASET_KEYS if keys is None else keys
    table = ["| File | |", "|---|---|"]
    for name in shipped:
        if name not in FILE_DESCRIPTIONS:
            raise BuildError(
                f"{name} is shipped with no description, so the project's README would not "
                "mention it. Add one to FILE_DESCRIPTIONS."
            )
        description = FILE_DESCRIPTIONS[name]
        if name == "dataset.jsonl":
            labelled = sum(1 for row in rows if keys["output"] in row)
            # Counts what the file holds. `rows` is lines, and a set that repeats a question
            # has more lines than questions -- calling every line a question said "90
            # questions" of a file holding 60 of them. And a file whose answers sit on some
            # rows and not others says how many, because "each a question with the query
            # that answers it" is false of a file where most rows have no answer.
            if labelled == len(rows):
                description = (
                    f"{len(rows)} rows, each a question with the query that answers it."
                )
            elif labelled:
                description = (
                    f"{len(rows)} rows, each a question; {labelled} of them carry the "
                    "query that answers it."
                )
            else:
                description = f"{len(rows)} rows, each a question."
        elif name == "databases/":
            description = f"{len(databases)} SQLite databases, one directory each."
        elif name == f"{SECOND_AGENT_DIRECTORY}/":
            description = (
                "a second agent, unrelated to the first: turns a query into a plain-English "
                f"description of what it returns, with {second_agent_rows} queries to run "
                "it on and a rough check of its own."
            )
        if not description:
            # Dropping the row would leave a file in the project that the README does not
            # mention, which is the one thing this table exists to prevent.
            raise BuildError(
                f"{name} has no description to print, so the project's README would not "
                "mention a file that is in it. Give it one in FILE_DESCRIPTIONS."
            )
        table.append(f"| `{name}` | {description} |")

    # Every section is written only when the thing it describes is here. A fixed paragraph
    # about the data reads as a claim that there is data, in a project built to have none --
    # and the opening claimed the project answers questions in projects holding no agent.
    if agent_state != "missing":
        opening = "\nAnswers questions about a database by writing the SQL that gets the answer.\n"
    elif rows and any(keys["output"] in row for row in rows):
        opening = "\nQuestions about a database, and the SQL that answers them.\n"
    elif rows:
        opening = "\nQuestions about a database.\n"
    else:
        opening = (
            "\nA place for something that turns a question about a database into the SQL\n"
            "that answers it.\n"
        )
    if rows:
        # The question only. Printing the row's answer beside it put whatever that row holds
        # on the first screen -- which, in a project whose answers have been re-paired, is
        # the damage itself, announced in the opening paragraph.
        opening += (
            f"\nOne of the questions it is given: *\"{rows[0][keys['input']]}\"*\n"
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
            "\nThe data is licensed CC BY-SA 4.0 and `" + ATTRIBUTION_NAME + "` in this"
            " directory carries the attribution and the terms. It has to stay with the data"
            " wherever the data goes.\n"
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
    # A sixth placeholder in the template used to render into the project verbatim, at exit
    # 0: a fixed list of five replacements has no way to notice a key it does not know.
    leftover = sorted(set(TEMPLATE_PLACEHOLDER.findall(text)))
    if leftover:
        raise BuildError(
            f"the project README still holds {', '.join(leftover)} after rendering. Every "
            "placeholder in the template needs a value in render_readme."
        )
    return text


TEMPLATE_PLACEHOLDER = re.compile(r"\{\{([A-Za-z0-9_]+)\}\}")
README_PLACEHOLDERS = frozenset(
    {"OPENING", "FILE_TABLE", "DATA_SECTION", "AGENT_SECTION", "HANDOFF"}
)


def check_readme_template(template: Path) -> None:
    """Refuse a template asking for something the renderer does not know how to fill."""
    if not template.is_file():
        raise BuildError(f"component missing: {template}")
    unknown = sorted(
        set(TEMPLATE_PLACEHOLDER.findall(template.read_text(encoding="utf-8")))
        - README_PLACEHOLDERS
    )
    if unknown:
        raise BuildError(
            f"{template} asks for {', '.join(unknown)}, which render_readme does not fill"
        )


# --------------------------------------------------------------------------- commands


@dataclass(frozen=True)
class Plan:
    """One demo, fully decided and checked, and not yet written.

    Everything a build needs is resolved here and nowhere else. The point of the type is the
    boundary it draws: `plan_demo` is the only place that reads the command line or refuses
    anything, and `write_demo` takes a Plan and writes it. "Already validated" is then a
    property of what the writer was handed rather than a promise in its docstring, and the
    writer can be driven from a test without a command line at all.

    `rows` are the rows as they will ship, damage included: which rows a damaged state can
    draw at all is one of the things being decided, and checking the damage means checking
    the rows that go on disk.

    The three fields with defaults are what `plan_demo` resolves out of this repository --
    the model roster, the databases the probes need, the guide's commit. They default to
    "nothing" so a Plan can still be built by hand in a test; a build made through
    `plan_demo` always has them filled in.
    """

    out: Path
    agent: str
    dataset: str
    evaluator: str
    calibration: str
    provider: str
    rows: list[dict[str, Any]]
    guide_source: Path | None
    interpreter: str | None
    models: tuple[str, ...] = ()
    probe_databases: frozenset[str] = frozenset()
    guide_sha: str | None = None
    # The rows as drawn, before any damage. Empty when nothing was damaged: `rows` is then
    # the same list, and a second copy of three hundred rows would only invite drift.
    undamaged_rows: list[dict[str, Any]] = field(default_factory=list)

    @property
    def project(self) -> Path:
        return self.out / PROJECT_SUBDIR

    @property
    def databases(self) -> list[str]:
        """Every database the project has to carry: the rows' own, plus the probes'."""
        return sorted(
            {row["metadata"]["db_id"] for row in self.rows} | set(self.probe_databases)
        )

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
    def ships_second_agent(self) -> bool:
        return self.agent == "two-agents"

    @property
    def second_agent_rows(self) -> list[dict[str, Any]]:
        """The queries the second agent is given: gold queries of the slice, unlabelled.

        Drawn across the difficulty bands from the rows as the project drew them, before
        any damage, seeded, so the same project carries the same twenty. The damage is the
        first agent's dataset's, and it is recorded against that dataset; a draw from the
        damaged rows handed the second agent a repeated id or a `-holdout` copy that no
        record mentioned. Each carries the query as its input, no expected answer --
        nobody wrote the descriptions down -- and enough of the row's other fields to say
        where the query came from.
        """
        if not self.ships_second_agent:
            return []
        source = self.undamaged_rows or self.rows
        # Every declaration is read from the rows AS SHIPPED, not from the undamaged
        # draw. A state that rewrites what a row says about itself and a second file
        # still saying the old thing for twenty of those ids contradict each other
        # inside one project, which is the opposite of what the state is for.
        #
        # Mirrored by the whole CLASS rather than one field at a time. The first
        # version of this named `provenance`, which was the only declaration there
        # was; `generated-answers` then declared on `output_provenance` and the
        # contradiction came straight back, in a second file the reader can hold
        # beside the first. The class is `DECLARATION_ROW_FIELDS`, by name: a state
        # that declares on a third field is carried here once that field is added
        # there, and a field added to neither set fails the suite rather than being
        # guessed into one side -- see the comment on the two sets.
        declared = {
            row["metadata"]["id"]: {
                key: value
                for key, value in row["metadata"].items()
                if key in DECLARATION_ROW_FIELDS
            }
            for row in self.rows
        }
        return [
            {
                "input": row["output"],
                "metadata": {
                    "db_id": row["metadata"]["db_id"],
                    "difficulty": row["metadata"]["difficulty"],
                    "id": row["metadata"]["id"],
                    **declared.get(
                        row["metadata"]["id"],
                        {
                            key: value
                            for key, value in row["metadata"].items()
                            if key in DECLARATION_ROW_FIELDS
                        },
                    ),
                },
            }
            for row in band_balanced_sample(source, SECOND_AGENT_ROWS)
        ]

    @property
    def keys(self) -> dict[str, str]:
        return dataset_keys(self.dataset)

    @property
    def ships_calibration(self) -> bool:
        return self.calibration == "present"

    @property
    def shipped_files(self) -> list[str]:
        """The names the project will hold, in the order its README lists them.

        One list, read by the check that every one of them has a description and by the
        writer that puts them there, so the two cannot disagree about what ships.
        """
        names: list[str] = []
        if self.ships_second_agent:
            names.append(PROJECT_NOTE)
        if self.agent_source is not None:
            names.append("agent.py")
        if self.ships_second_agent:
            names.append(f"{SECOND_AGENT_DIRECTORY}/")
        if self.evaluator_source is not None:
            names.append("evaluator.py")
        if self.rows:
            # The attribution travels with the rows and the databases, and only with them:
            # a project holding no data has nothing to attribute.
            names += ["dataset.jsonl", "catalog.json", "databases/", ATTRIBUTION_NAME]
        names.append(".env.example")
        names.append(".gitignore")
        if self.ships_calibration:
            names.append(f"{RUNS_DIRECTORY}/{CALIBRATION_FILE}")
        names.append("README.md")
        return names


def check_plan(plan: Plan) -> None:
    """Everything about a Plan that can be settled before a directory exists.

    Called at the end of `plan_demo`, on the Plan it is about to return. What is checked here
    used to be discovered by `write_demo` with the project already half written: a database
    the repository does not hold, a shipped file with no README entry, a template placeholder
    nothing fills.
    """
    check_databases_present(plan.databases)
    for name in plan.shipped_files:
        if name not in FILE_DESCRIPTIONS:
            raise BuildError(
                f"{name} is shipped with no description, so the project's README would not "
                "mention it. Add one to FILE_DESCRIPTIONS."
            )
    template = COMPONENTS / "readme" / "DEMO_README.md.tmpl"
    check_readme_template(template)
    if plan.rows and not ATTRIBUTION_SOURCE.is_file():
        raise BuildError(f"component missing: {ATTRIBUTION_SOURCE}")
    if plan.ships_second_agent:
        for source in second_agent_components(plan.provider):
            if not source.is_file():
                raise BuildError(f"component missing: {source}")
        if not plan.rows:
            raise BuildError(
                "--agent two-agents gives the second agent queries drawn from the rows, "
                "and --dataset missing ships none"
            )
        # The second agent's input IS the row's gold query. A dataset state that
        # withholds answers therefore cannot ship one: the answers to the withheld
        # rows would sit in a file beside them, under the same ids, and the project
        # would be blind to nothing at all. Keyed on `row_is_labelled` rather than
        # on a list of state names, so a labelling state added later is refused
        # without anyone remembering to come back here.
        withheld = sum(
            1
            for row in (plan.undamaged_rows or plan.rows)
            if not row_is_labelled(row, plan.dataset)
        )
        if withheld:
            raise BuildError(
                "--agent two-agents gives the second agent the rows' gold queries as "
                f"its input, and --dataset {plan.dataset} withholds the answer on "
                f"{withheld} of them: the project would ship the answers it is meant "
                "to be missing, in a file beside them, under the same ids"
            )
        if len(plan.second_agent_rows) != SECOND_AGENT_ROWS:
            raise BuildError(
                f"the rows supply {len(plan.second_agent_rows)} queries for the second "
                f"agent and {SECOND_AGENT_ROWS} are needed"
            )
    if plan.dataset == "torn":
        # Refused here, before the directory exists, rather than by the writer.
        torn_line_numbers(len(plan.rows))
    # Rendered, and the result thrown away. It is a function of the Plan and nothing else, so
    # rendering it here is how its refusals happen before anything is on disk; the writer
    # renders the same text from the same Plan.
    render_readme(
        template,
        handoff=plan.handoff,
        shipped=plan.shipped_files,
        rows=[project_row(row, plan.dataset) for row in plan.rows],
        databases=plan.databases,
        agent_state=plan.agent,
        keys=plan.keys,
        second_agent_rows=len(plan.second_agent_rows),
    )


def second_agent_components(provider: str) -> tuple[Path, Path, Path]:
    """The three files the second agent brings: its source, its scorer, the note."""
    return (
        second_agent_file(provider),
        EXPLAINER / "evaluator.py",
        EXPLAINER / PROJECT_NOTE,
    )


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
    interpreter = resolve_python() if args.venv == "ready" else None
    guide_source: Path | None = None
    guide_sha: str | None = None
    if args.guide == "local":
        check_guide_source(args.guide_src)
        guide_source = args.guide_src
        assert guide_source is not None  # check_guide_source refuses None
        guide_sha = guide_revision(guide_source.expanduser().resolve())
    if calibration == "present":
        check_calibration_source(evaluator)

    rows = select_rows(read_dataset(), dataset) if dataset != "missing" else []
    undamaged_rows: list[dict[str, Any]] = []
    if dataset in DAMAGED_STATES:
        undamaged_rows = list(rows)
        # Damaged here rather than in the writer: what the damage does to the rows is one of
        # the things a Plan has decided, and the checks on it -- that no row kept its own
        # answer, that every answer still runs -- are checks on the rows that go on disk.
        rows = damage_rows(rows, dataset)
    if calibration == "present" and not rows:
        raise BuildError(
            "--calibration present needs the databases its probes run against, and "
            "--dataset missing ships none"
        )

    plan = Plan(
        out=out,
        agent=agent,
        dataset=dataset,
        evaluator=evaluator,
        calibration=calibration,
        provider=provider,
        rows=rows,
        guide_source=guide_source,
        interpreter=interpreter,
        models=tuple(agent_models(agent_file(agent, provider))),
        probe_databases=frozenset(calibration_databases(evaluator, calibration)),
        guide_sha=guide_sha,
        undamaged_rows=undamaged_rows,
    )
    check_plan(plan)
    return plan


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
    """Write the demo a Plan describes.

    Nothing here decides anything. Every refusal a Plan could settle has already happened in
    `plan_demo`, before this directory existed -- the rows, the databases, the roster, the
    README. The one failure left is building the project's environment, which is a `pip`
    install and cannot be known before it is attempted.
    """
    project = plan.project
    project.mkdir()
    created = plan.shipped_files
    projected = [project_row(row, plan.dataset) for row in plan.rows]
    databases = plan.databases

    if plan.agent_source is not None:
        shutil.copy2(plan.agent_source, project / "agent.py")

    second_agent_record = None
    if plan.ships_second_agent:
        agent_source, evaluator_source, note = second_agent_components(plan.provider)
        sibling = project / SECOND_AGENT_DIRECTORY
        sibling.mkdir()
        shutil.copy2(agent_source, sibling / "agent.py")
        shutil.copy2(evaluator_source, sibling / "evaluator.py")
        write_jsonl(sibling / "dataset.jsonl", plan.second_agent_rows)
        shutil.copy2(note, project / PROJECT_NOTE)
        second_agent_record = {
            "directory": SECOND_AGENT_DIRECTORY,
            "path": f"{SECOND_AGENT_DIRECTORY}/agent.py",
            "evaluator": f"{SECOND_AGENT_DIRECTORY}/evaluator.py",
            "dataset": f"{SECOND_AGENT_DIRECTORY}/dataset.jsonl",
            "rows": len(plan.second_agent_rows),
            "labelled": False,
            "models": agent_models(agent_source),
            "note": PROJECT_NOTE,
        }

    if plan.evaluator_source is not None:
        shutil.copy2(plan.evaluator_source, project / "evaluator.py")

    torn: list[int] = []
    if plan.rows:
        torn = write_dataset(project / "dataset.jsonl", projected, plan.dataset)
        write_catalog(project / "catalog.json", plan.rows)
        copy_databases(databases, project / "databases")
        # The rows are CC BY-SA, and what they are and what may be done with them travels
        # with them, always.
        shutil.copy2(ATTRIBUTION_SOURCE, project / ATTRIBUTION_NAME)

    shutil.copy2(env_file(plan.provider), project / ".env.example")
    (project / ".gitignore").write_text(GITIGNORE_TEXT, encoding="utf-8")

    calibration_record = (
        copy_calibration(plan.evaluator, project) if plan.ships_calibration else None
    )

    guide_record = (
        copy_guide(plan.guide_source, project, plan.guide_sha)
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
    labelled = sum(1 for row in projected if plan.keys["output"] in row)

    readme = render_readme(
        COMPONENTS / "readme" / "DEMO_README.md.tmpl",
        handoff=plan.handoff,
        shipped=created,
        rows=projected,
        databases=databases,
        agent_state=plan.agent,
        keys=plan.keys,
        second_agent_rows=len(plan.second_agent_rows),
    )
    (project / "README.md").write_text(readme, encoding="utf-8")

    venv_record = (
        make_project_venv(project, plan.interpreter)
        if plan.interpreter is not None
        else None
    )

    manifest: dict[str, Any] = {
        "manifest_version": MANIFEST_VERSION,
        "built_by": "build.py",
        "project_directory": PROJECT_SUBDIR,
        "components": {
            "agent": {
                "state": plan.agent,
                "path": "agent.py" if plan.agent_source else None,
                "provider": plan.provider,
                "models": list(plan.models),
                # The other agent in the project, where the state ships one. Recorded
                # beside the first rather than as a second component, because the first
                # is the one every tool is pointed at and this one is what sits next to it.
                "second_agent": second_agent_record,
            },
            "dataset": {
                "state": plan.dataset,
                "path": "dataset.jsonl" if plan.rows else None,
                "rows": len(projected),
                # Under which names a row's question and answer are written. The tooling
                # reads `input` and `output`; `raw-export` writes Spider's own names.
                "fields": plan.keys,
                "labelled": bool(plan.rows) and labelled == len(projected),
                "labelled_rows": labelled,
                # The questions and answers are Spider's. Damage is this repository's, and
                # saying which is which is the difference between a fixture and a false
                # claim about the benchmark. `damage` names the state; `damage_detail`
                # says what it did to these rows, in terms a reader can check on disk.
                "damage": plan.dataset if plan.dataset in DAMAGED_STATES else None,
                "damage_detail": damage_detail(plan, torn),
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
            "project_venv": venv_record,
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


def damage_detail(plan: Plan, torn: Sequence[int]) -> dict[str, Any] | None:
    """What a damaged state did to the rows, said in terms checkable against the file.

    Read off the rows that ship wherever that is possible, rather than restated from the
    constants that produced them: the leaked ids are the ids that carry the suffix, the
    held-out databases are the ones with no tuning row, the torn lines are the ones the
    writer reports having cut.
    """
    if plan.dataset not in DAMAGED_STATES:
        return None
    if plan.dataset == "duplicated":
        repeated = Counter(row["metadata"]["id"] for row in plan.rows)
        return {"repeated_ids": sorted(i for i, n in repeated.items() if n > 1)}
    if plan.dataset == "wrong-answers":
        return {"rotated_within": "db_id", "rows_keeping_their_answer": 0}
    if plan.dataset == "leaky":
        return {
            "leaked_ids": leaked_ids(plan.rows),
            "copy_split": "holdout",
            "copy_id_suffix": LEAK_ID_SUFFIX,
        }
    if plan.dataset == "holdout-labelled":
        return {"labelled_split": "holdout"}
    if plan.dataset == "split-by-database":
        return {"held_out_databases": held_out_databases(plan.rows)}
    if plan.dataset == "raw-export":
        return {"keys": dict(RAW_EXPORT_KEYS), "top_level": ["db_id"]}
    if plan.dataset == "torn":
        return {"torn_lines": list(torn), "cut_at": TORN_AT}
    if plan.dataset == "undeclared":
        return {"provenance": UNDECLARED_PROVENANCE, "slice_says": "real"}
    if plan.dataset == "fully-synthetic":
        return {
            "provenance": SYNTHETIC_PROVENANCE,
            "slice_says": "real",
            "declared_rows": sum(
                1
                for row in plan.rows
                if row["metadata"].get("provenance") == SYNTHETIC_PROVENANCE
            ),
            "of_rows": len(plan.rows),
        }
    if plan.dataset in ("mostly-undeclared", "mostly-synthetic"):
        declared = (
            UNDECLARED_PROVENANCE
            if plan.dataset == "mostly-undeclared"
            else SYNTHETIC_PROVENANCE
        )
        return {
            "provenance": declared,
            "slice_says": "real",
            "declared_rows": sum(
                1 for row in plan.rows if row["metadata"].get("provenance") == declared
            ),
            "of_rows": len(plan.rows),
        }
    if plan.dataset in ("generated-answers", "mostly-generated-answers"):
        return {
            "output_provenance": GENERATED_ANSWER_PROVENANCE,
            "slice_says": "nothing -- the slice declares no answer provenance",
            "declared_rows": sum(
                1
                for row in plan.rows
                if row["metadata"].get(GENERATED_ANSWER_KEY)
                == GENERATED_ANSWER_PROVENANCE
            ),
            "of_rows": len(plan.rows),
        }
    raise BuildError(
        f"{plan.dataset} is a damaged state with no description of its damage"
    )


# The name of the record a bank keeps of itself, and the prefix of the directories inside it.
# The record sits at the root, outside every project, for the same reason `demo.json` sits
# outside `project/`: it names the state each demo was built in.
BANK_RECORD = "bank.json"
BANK_DIRECTORY_PREFIX = "project-"


def bank_directory(preset: str) -> str:
    """The directory one preset's demo is built in, inside a bank. Not the preset's name.

    A demo's own absolute path is not private to the demo: `venv` writes it into
    `pyvenv.cfg`, into `VIRTUAL_ENV` in every `activate` script, and into the shebang of
    every console script the environment installs. So a bank that named each directory after
    the state its demo was built in wrote that state into the project, where the agent reads
    it -- `#!/.../bank/wrong-answers/project/.venv/bin/python` in a file the project ships.

    Scrubbing those files afterwards would mean changing what a working environment
    contains. Choosing a directory name that says nothing costs nothing, and closes the
    whole class at once -- `pyvenv.cfg`, shebangs, `activate`, and anything else that
    records where it is.

    Derived from the name rather than counted, so that adding a preset does not renumber the
    others and notes naming a directory keep meaning what they meant.
    """
    digest = hashlib.sha256(preset.encode("utf-8")).hexdigest()[:8]
    return f"{BANK_DIRECTORY_PREFIX}{digest}"


def cmd_suite(args: argparse.Namespace) -> dict[str, Any]:
    """Build every preset at once, each in its own directory under one root.

    A bank of starting states is only useful if making the whole bank is one command. Each
    demo is built exactly as `demo` builds it, and one failing preset does not take the
    others with it -- the failure is reported against the preset that caused it.

    Any failure, not only a refusal. Isolating `BuildError` alone kept that promise for the
    failures this file raises deliberately and broke it for every other kind: a component
    with a syntax error in it ended the whole bank on the first preset, as a traceback.

    Which directory holds which starting state is recorded in the bank's own record, at the
    root and outside every project -- readable by whoever runs the bank, and not by an agent
    pointed at one project inside it.
    """
    root = args.out.expanduser()
    check_output_path(root)

    directories = {name: bank_directory(name) for name in sorted(PRESETS)}
    if len(set(directories.values())) != len(directories):
        raise BuildError(
            "two presets want the same directory in the bank, so one would refuse to build "
            "over the other"
        )
    root.mkdir(parents=True)

    built: list[dict[str, Any]] = []
    failed: list[dict[str, str]] = []
    for name in sorted(PRESETS):
        one = argparse.Namespace(
            out=root / directories[name],
            preset=name,
            agent=None,
            dataset=None,
            eval=None,
            calibration=None,
            provider=args.provider,
            guide=args.guide,
            guide_src=args.guide_src,
            venv=args.venv,
        )
        try:
            result = cmd_demo(one)
        except BuildError as error:
            failed.append({"preset": name, "error": str(error)})
            continue
        except Exception as error:
            # Not BaseException: a KeyboardInterrupt is meant to stop the bank, not to be
            # recorded as one preset's problem and followed by sixteen more builds.
            failed.append({"preset": name, "error": f"{type(error).__name__}: {error}"})
            continue
        built.append(
            {
                "preset": name,
                "directory": directories[name],
                "project": result["project"],
                "rows": result["rows"],
                "components": result["components"],
            }
        )

    (root / BANK_RECORD).write_text(
        json.dumps(
            {
                "manifest_version": MANIFEST_VERSION,
                "built_by": "build.py",
                "demos": [
                    {
                        "directory": entry["directory"],
                        "preset": entry["preset"],
                        "note": PRESET_NOTES[entry["preset"]],
                        "components": entry["components"],
                        "rows": entry["rows"],
                    }
                    for entry in built
                ],
                "failed": failed,
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    return {
        "ok": not failed,
        "root": str(root),
        "record": BANK_RECORD,
        "built": built,
        "failed": failed,
        "handoff": HANDOFF_LOCAL if args.guide == "local" else HANDOFF_CLONE,
    }


# Words that could only mean "this was assembled for a test". Ordinary English is not a tell:
# a preset called `empty` shares a word with an env file that says to leave a key empty, and a
# checker that cannot tell those apart teaches people to ignore it. So the list is the
# vocabulary of this repository's own machinery, and nothing that describes the data. Notably
# absent: `holdout`, `tuning` and `difficulty`, which are real properties of the rows and
# appear in any honest description of them, and `calibration-cases.json`, which is the name a
# real project gives that file.
#
# Matched after normalising, because the same words are written several ways. The leak this
# roster was widened for read "Spider Traigent First Run Scenario" -- spaces and capitals --
# against a list holding `spider_traigent` and `first_run_scenario`, and passed.
FIXTURE_TELLS = (
    "preset",
    "fixture",
    "plant",
    "scenario",
    "deliberate",
    "is observed",
    "generated demo",
    "spider_traigent",
    "first_run_scenario",
    "build.py",
    "demo.json",
)

_SEPARATORS = re.compile(r"[\s_-]+")

# How much of a file the blinding scan reads. Everything a project ships is far below this --
# the largest is a few hundred kilobytes -- and the bound is what stops a file that is not
# from stalling the scan.
MAX_SCAN_BYTES = 4 << 20


def normalized(text: str) -> str:
    """Case, underscores, hyphens and runs of whitespace all folded to one form."""
    return _SEPARATORS.sub(" ", text.casefold())


def revealing_names() -> tuple[str, ...]:
    """The hyphenated state and preset names, which read as labels rather than as prose.

    Matched as written, hyphens and all, and not normalised. The hyphen is what makes
    `no-agent` a label; normalised it becomes "no agent", which an agent file writes by
    accident in "no database recorded for this question" -- exactly the false alarm that
    teaches a reader to ignore this check.
    """
    named = (
        set(PRESETS) | set(DATASET_STATES) | set(EVALUATOR_FILES) | set(AGENT_STATES)
    )
    return tuple(sorted(n for n in named if "-" in n and len(n) > 6))


def readable_text(path: Path) -> str | None:
    """The file's text, or None if it is not text this scan can read.

    Read by what it holds rather than by what it is called. `NOTICE` has no suffix, and a
    scan that read only known suffixes skipped the one file in the project that named the
    repository which produced it.
    """
    try:
        with path.open("rb") as handle:
            data = handle.read(MAX_SCAN_BYTES)
    except OSError:
        return None
    if b"\x00" in data:
        return None
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError:
        return None


def path_problems(project: Path) -> list[str]:
    """Whether the demo's own location says what the demo is.

    The path is not private to the demo. `venv` writes it into `pyvenv.cfg`, into
    `VIRTUAL_ENV` in each `activate`, and into the shebang of every console script -- so a
    demo sitting in a directory named after the state it was built in has that name inside
    it, in files the project ships. `suite` chooses names that say nothing; a single
    `demo --out ~/demos/wrong-answers` is the operator's own choice, and nothing said so.
    """
    hits = tells_in(str(project.resolve()), "the path this demo sits at")
    if not hits:
        return []
    if (project / PROJECT_VENV).is_dir():
        remedy = (
            "Build it somewhere else. The project's environment has this path written into "
            "every script in it, so renaming the directory would break the environment "
            "rather than clean it."
        )
    else:
        remedy = (
            "Rename the directory. Nothing inside the demo records where it is, so moving "
            "it is enough and it does not have to be built again."
        )
    return [f"{hit}. {remedy}" for hit in hits]


def tells_in(text: str, where: str) -> list[str]:
    """Every tell the given text holds, reported against `where`."""
    found = []
    folded = normalized(text)
    for tell in FIXTURE_TELLS:
        if normalized(tell) in folded:
            found.append(f"{where} contains {tell!r}, which says this is a test")
    # Hyphenated labels are matched literally rather than fully normalised (see
    # `revealing_names`): a hyphen is what makes `no-agent` a label rather than the
    # ordinary phrase "no agent" an agent file writes by accident. An underscore joins
    # words the same way a hyphen does -- nothing writes `no_agent` by accident describing
    # a piece of hardware that is absent -- so it is folded to the same hyphen spelling
    # before matching. A space is left alone; that is the distinction the check depends on.
    joined = text.casefold().replace("_", "-")
    for name in revealing_names():
        if name in joined:
            found.append(f"{where} contains {name!r}, which says this is a test")
    return found


def verify_demo(root: Path) -> list[str]:
    """Everything that has to be true of a built demo before an agent is pointed at it.

    Three properties, and they are what make a run mean anything. It has to be
    self-contained, so the agent reads a project and not the repository that made it. It has
    to be blind, so the agent is not handed the answer. And it has to work -- the agent and
    the evaluator compile, the data is readable, the databases are present -- because a
    project that cannot run tests the guide's patience rather than its judgement.
    """
    problems: list[str] = []
    record = root / "demo.json"
    project = root / PROJECT_SUBDIR
    if not record.is_file():
        return [f"no build record at {record}"]
    if not project.is_dir():
        return [f"no project at {project}"]
    manifest = json.loads(record.read_text(encoding="utf-8"))

    if (project / record.name).exists():
        problems.append("the build record is inside the project the agent reads")
    # Anywhere inside, not just at the top: `--guide local` copies a whole checkout into
    # `project/traigent-first-run/`, and one that brought this directory with it left a demo
    # whose fallback route the guide would refuse while this check said the project was clean.
    for path in project.rglob(FORBIDDEN_VENV_NAME):
        problems.append(
            f"the project contains {FORBIDDEN_VENV_NAME} at {path.relative_to(project)}"
        )

    problems += path_problems(project)

    on_disk: set[str] = set()
    for path in sorted(project.rglob("*")):
        relative = path.relative_to(project)
        in_venv = PROJECT_VENV in relative.parts
        if in_venv:
            # The project's own environment, read where it is written rather than skipped
            # wholesale. Two places record where the environment was built: `pyvenv.cfg` at
            # the root, and the scripts in `bin/` -- shebangs and `activate`'s `VIRTUAL_ENV`
            # both hold the absolute path. Below those is `site-packages`, which is large,
            # third-party and written by pip, and `lib64`, which is a symbolic link `venv`
            # makes for itself.
            readable_here = relative.parts[1:-1] in ((), ("bin",))
            if (
                relative.parts[0] != PROJECT_VENV
                or not readable_here
                or not path.is_file()
                or path.is_symlink()
            ):
                continue
        if path.is_symlink():
            problems.append(f"{relative} is a symbolic link")
            continue
        # Names, not only contents. A file called FIXTURE_NOTES.md says what it says whether
        # or not anything was ever written in it.
        for part in relative.parts:
            problems += tells_in(part, f"the name {relative}")
        if not path.is_file():
            continue
        if not in_venv:
            on_disk.add(relative.as_posix())
        text = readable_text(path)
        if text is None:
            continue
        if str(REPO_ROOT) in text:
            problems.append(
                f"{relative} names the path of the repository that built it"
            )
        problems += tells_in(text, str(relative))

    recorded = {entry["path"] for entry in manifest["files"]}
    for entry in manifest["files"]:
        path = project / entry["path"]
        if not path.is_file():
            problems.append(f"{entry['path']} is in the record and not on disk")
        elif sha256_of(path) != entry["sha256"]:
            problems.append(f"{entry['path']} does not match the record")
    # And the other direction. Walking the record alone can only find what went missing; a
    # file added to the project afterwards was invisible to it, and the demo still passed.
    for extra in sorted(on_disk - recorded):
        problems.append(f"{extra} is on disk and not in the record")

    # Parsed, never run. Every Python file the project ships is handed to an agent that has
    # not been told what it is; running one would call a model. Compiling proves the
    # project can start. The two the guide is pointed at are `agent.py` and `evaluator.py`;
    # a second agent's files sit in a directory of their own and are read the same way.
    for source in sorted(project.rglob("*.py")):
        relative = source.relative_to(project)
        if PROJECT_VENV in relative.parts or GUIDE_DIRECTORY in relative.parts:
            continue
        try:
            compile(source.read_text(encoding="utf-8"), relative.as_posix(), "exec")
        except (OSError, UnicodeDecodeError, SyntaxError, ValueError) as error:
            problems.append(f"{relative.as_posix()} does not compile: {error}")

    # Everything below reads files that may be malformed -- which is one of the things worth
    # reporting. A checker that raises on bad input fails exactly when it is needed, and a
    # traceback is the one result a reader cannot act on.
    #
    # Two states write the file other than the way the tooling reads it, and the record
    # says so: `raw-export` names its fields differently, and `torn` ships lines that are
    # not JSON. A torn line is checked against the record exactly -- every line the record
    # says is torn must fail to parse, and every other line must parse -- so a torn demo
    # verifies clean while a demo torn somewhere the record does not say still does not.
    dataset = project / "dataset.jsonl"
    if dataset.is_file():
        recorded_dataset = manifest["components"].get("dataset") or {}
        keys = recorded_dataset.get("fields") or DATASET_KEYS
        detail = recorded_dataset.get("damage_detail") or {}
        torn = set(detail.get("torn_lines") or [])
        try:
            rows = []
            for number, line in enumerate(
                dataset.read_text(encoding="utf-8").split("\n"), 1
            ):
                if not line:
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    if number not in torn:
                        raise
                    continue
                if number in torn:
                    problems.append(
                        f"line {number} is recorded as torn and reads as a whole row"
                    )
                rows.append(row)
            catalog = json.loads((project / "catalog.json").read_text(encoding="utf-8"))
            questions = [row[keys["input"]] for row in rows]
            databases = sorted({row["metadata"]["db_id"] for row in rows})
        except (ValueError, KeyError, TypeError, OSError) as error:
            problems.append(f"the rows or the catalog cannot be read: {error}")
        else:
            if any(question not in catalog for question in questions):
                problems.append("a question is not in the catalog the agent reads")
            for db_id in databases:
                if not (project / "databases" / db_id / f"{db_id}.sqlite").is_file():
                    problems.append(
                        f"the rows name database {db_id}, which is not here"
                    )
    return problems


def cmd_verify(args: argparse.Namespace) -> dict[str, Any]:
    """Check one built demo, or every demo under one root."""
    root = args.demo.expanduser()
    if not root.is_dir():
        raise BuildError(f"no directory at {root}")
    # Every directory under the root, not only the ones holding a record. A build interrupted
    # before it wrote `demo.json` leaves exactly a directory without one, and filtering those
    # out dropped the broken demo from the report while the run still read as a passing gate.
    roots = (
        [root]
        if (root / "demo.json").is_file()
        else sorted(p for p in root.iterdir() if p.is_dir())
    )
    if not roots:
        raise BuildError(f"{root} holds no built demo")
    checked = [{"demo": r.name, "problems": verify_demo(r)} for r in roots]
    return {
        "ok": all(not entry["problems"] for entry in checked),
        "root": str(root),
        "checked": checked,
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
            "venv": list(VENV_STATES),
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
        component_paths[f"explainer/{provider}"] = second_agent_file(provider)
    component_paths["explainer/evaluator"] = EXPLAINER / "evaluator.py"
    component_paths["explainer/note"] = EXPLAINER / PROJECT_NOTE
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

    template = COMPONENTS / "readme" / "DEMO_README.md.tmpl"
    try:
        check_readme_template(template)
    except BuildError as error:
        problems.append(str(error))

    if not ATTRIBUTION_SOURCE.exists():
        problems.append(f"component missing: {ATTRIBUTION_SOURCE}")

    rows = read_dataset()
    if len(rows) != 300:
        problems.append(f"expected 300 dataset rows, found {len(rows)}")
    # A row missing a field is exactly what this command exists to report, so the fields are
    # read only after they are known to be there. Everything below runs on `sound`: reaching
    # into `row["metadata"]` on the whole set turned a bad row into a KeyError traceback
    # from the one command whose job is to describe a bad row. Collecting a row's text into
    # a set is the same mistake wearing different clothes -- a dict in `input` or `output`
    # is unhashable, so the set comprehension raised TypeError from the command whose job is
    # to say "row N is not flat". Both sets are therefore built from `sound` as well.
    sound: list[dict[str, Any]] = []
    for index, row in enumerate(rows):
        if not isinstance(row.get("input"), str) or not isinstance(
            row.get("output"), str
        ):
            problems.append(
                f"row {index} is not flat: input and output must both be text"
            )
            continue
        metadata = row.get("metadata")
        if not isinstance(metadata, dict):
            problems.append(f"row {index} carries no metadata")
            continue
        absent = [f for f in ("db_id", "difficulty", "split") if f not in metadata]
        if absent:
            problems.append(f"row {index} has no metadata {', '.join(absent)}")
            continue
        sound.append(row)

    questions = {row["input"] for row in sound}
    if len(questions) != len(sound):
        problems.append(
            f"dataset has {len(sound) - len(questions)} duplicate questions"
        )

    needed = sorted({row["metadata"]["db_id"] for row in sound})
    for db_id in needed:
        if not (DATABASES_PATH / db_id / f"{db_id}.sqlite").exists():
            problems.append(f"database missing: {db_id}")

    gold_queries = {row["output"] for row in sound}
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

    bands = Counter(row["metadata"]["difficulty"] for row in sound)
    splits = Counter(row["metadata"]["split"] for row in sound)

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
        "PRESET             AGENT      DATASET            EVAL           CALIB    "
        "WHAT IT IS"
    ]
    for preset in result["presets"]:
        lines.append(
            f"{preset['name']:<18} {preset['agent']:<10} {preset['dataset']:<18} "
            f"{preset['eval']:<14} {preset['calibration']:<8} {preset['note']}"
        )
    lines.append("")
    for name, values in result["states"].items():
        lines.append(f"--{name}: {', '.join(values)}")
    return "\n".join(lines)


def render_suite(result: dict[str, Any]) -> str:
    lines = [
        f"Built {len(result['built'])} projects under {result['root']}",
        "",
        "  DIRECTORY          PRESET             AGENT      DATASET            EVAL",
    ]
    for entry in result["built"]:
        parts = entry["components"]
        lines.append(
            f"  {entry['directory']:<18} {entry['preset']:<18} {parts['agent']:<10} "
            f"{parts['dataset']:<18} {parts['eval']:<13} {entry['rows']:>4} rows"
        )
    for entry in result["failed"]:
        lines.append(f"  {'--':<18} {entry['preset']:<18} FAILED: {entry['error']}")
    if not result["built"]:
        # Every preset failed, so there is no project to point an agent at. The
        # handoff below tells a reader to hand one over, and printing it under a
        # bank of nothing reads as success with a missing directory rather than
        # as the refusal it is.
        lines += [
            "",
            "No project was built, so there is nothing to hand to an agent. Each",
            "preset's refusal is above and in the record; fix those and run again.",
        ]
        return "\n".join(lines)
    lines += [
        "",
        f"  {result['record']}  which directory is which; it names the state each demo was",
        "             built in, so keep it out of the agent's view as well.",
        "",
        "The directories say nothing on purpose: a demo's path is written into its own",
        "environment, so a directory named after a starting state hands that state over.",
        "",
        "Point one fresh agent at one project's directory, and give it exactly this:",
        "",
    ]
    lines += ["    " + line for line in result["handoff"].splitlines()]
    return "\n".join(lines)


def render_verify(result: dict[str, Any]) -> str:
    lines = []
    for entry in result["checked"]:
        if entry["problems"]:
            lines.append(f"  {entry['demo']}")
            lines += [f"      {problem}" for problem in entry["problems"]]
        else:
            lines.append(f"  ok  {entry['demo']}")
    lines += ["", "OK" if result["ok"] else "PROBLEMS ABOVE"]
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
    "verify": render_verify,
}


# --------------------------------------------------------------------------- cli


def enumerated(choices: Sequence[str], glosses: dict[str, str]) -> str:
    """Help text naming every choice, from the same sequence the parser accepts.

    Written out by hand, the `--eval` help listed every scorer but the newest one; a list
    built from the choices cannot fall behind them. A gloss for a name that is not a choice
    is the same drift in the other direction, and is refused rather than printed.
    """
    unknown = sorted(set(glosses) - set(choices))
    if unknown:
        raise BuildError(f"help describes {', '.join(unknown)}, which are not choices")
    return " | ".join(
        f"{choice} ({glosses[choice]})" if choice in glosses else choice
        for choice in choices
    )


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
    suite.add_argument("--venv", choices=VENV_STATES, default="none")
    suite.set_defaults(func=cmd_suite, name="suite")

    verify = commands.add_parser(
        "verify", help="check a built demo is self-contained, blind, and able to run"
    )
    verify.add_argument("--demo", type=Path, required=True, metavar="DIR")
    verify.set_defaults(func=cmd_verify, name="verify")

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
        help=enumerated(
            AGENT_STATES,
            {
                "ready": "tunable",
                "no-knobs": "nothing to search",
                "two-agents": "a second agent beside it",
            },
        ),
    )
    demo.add_argument(
        "--dataset",
        choices=DATASET_STATES,
        help=enumerated(
            DATASET_STATES,
            {
                "ready": "the whole slice",
                "mini": f"{MINI_ROWS} rows",
                "tiny": f"{TINY_ROWS} rows",
                "unlabeled": "no expected answers",
            },
        )
        + "; `list` describes the damaged ones",
    )
    demo.add_argument(
        "--eval",
        dest="eval",
        choices=sorted(EVALUATOR_FILES),
        help=enumerated(
            sorted(EVALUATOR_FILES),
            {"exact-match": "does not execute", "exec-match": "runs the SQL"},
        ),
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
        "--venv",
        choices=VENV_STATES,
        default="none",
        help="give the project a working environment of its own, on the newest supported Python",
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
