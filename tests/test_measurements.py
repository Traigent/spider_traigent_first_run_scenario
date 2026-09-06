# SPDX-License-Identifier: Apache-2.0
"""The hand-written agent reads still point at the agents they were written against.

`docs/measurements/agent-knobs/*.json` is the coding assistant's read that the guide's
opening score requires, standing in for one because no assistant runs here. Every entry in
it cites physical lines of `agent.py` -- and `agent.py` is a file in *this* repository, so
an edit to `components/agent/*/agent_ready.py` moves the lines out from under a document
nobody re-reads. That is not hypothetical: both documents were once left citing a blank
line and a `build` half with no citations at all, and the way it surfaced was the guide
refusing the whole sweep months later.

So the guide's own rule is replicated here, from `readiness.py`'s `checked_source_lines`
and the static-source reader beside it: a cited line must be inside the file and must be
executable, where executable means a line a Python token starts on, minus the lines a
docstring occupies. Comments and blank lines are not evidence of anything. This needs no
guide checkout and runs in well under a second, which is why it can sit in the suite that
gates every change to the agents.
"""

from __future__ import annotations

import ast
import difflib
import io
import json
import tokenize
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
KNOBS_DIR = REPO_ROOT / "docs" / "measurements" / "agent-knobs"
AGENT_DIR = REPO_ROOT / "components" / "agent"

# Which agent each document was written against. `score_bank.py` picks between them by the
# built demo's agent state, and `build.py` ships one of the two providers' copies as
# `agent.py`; the providers differ only in the model roster, line for line, so a citation
# that holds for one holds for both and both are checked.
DOCUMENTS = {
    "ready.json": "agent_ready.py",
    "no-knobs.json": "agent_no_knobs.py",
}
PROVIDERS = ("direct", "openrouter")


def executable_lines(text: str) -> set[int]:
    """The lines the guide will accept a citation to, by the guide's own definition.

    Token starts rather than AST node spans: an AST range covers the comment lines inside
    a multi-line call, and a citation to one of those is a citation to a comment.
    Docstrings are removed explicitly because they are `Expr(Constant(str))` nodes that
    tokenize like any other string.
    """
    tree = ast.parse(text)
    docstrings: set[int] = set()
    owners = [tree] + [
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))
    ]
    for owner in owners:
        body = owner.body
        if (
            body
            and isinstance(body[0], ast.Expr)
            and isinstance(getattr(body[0], "value", None), ast.Constant)
            and isinstance(body[0].value.value, str)
        ):
            first = body[0]
            docstrings.update(
                range(first.lineno, getattr(first, "end_lineno", first.lineno) + 1)
            )
    ignored = {
        tokenize.COMMENT,
        tokenize.NL,
        tokenize.NEWLINE,
        tokenize.INDENT,
        tokenize.DEDENT,
        tokenize.ENDMARKER,
        tokenize.ENCODING,
    }
    found = {
        token.start[0]
        for token in tokenize.generate_tokens(io.StringIO(text).readline)
        if token.type not in ignored
    }
    return found - docstrings


def citations(document: dict) -> list[tuple[str, list]]:
    """Every `source_lines` in one document, each with the entry that carries it."""
    entries = []
    for name, spec in sorted(document.get("knobs", {}).items()):
        entries.append((f"knob {name!r}", spec.get("source_lines")))
    for check, spec in sorted(document.get("build", {}).items()):
        if spec.get("determined") is False:
            # A read that could not settle a check has no line establishing it, and the
            # guide refuses a citation on one. Nothing to check, and nothing to require.
            continue
        entries.append((f"build check {check!r}", spec.get("source_lines")))
    return entries


class TheAgentReadsCiteTheAgents(unittest.TestCase):
    """Each document, against each provider's copy of the agent it describes."""

    def test_every_cited_line_is_inside_the_file_and_executable(self) -> None:
        for name, agent in DOCUMENTS.items():
            document = json.loads((KNOBS_DIR / name).read_text(encoding="utf-8"))
            for provider in PROVIDERS:
                source = (AGENT_DIR / provider / agent).read_text(encoding="utf-8")
                allowed = executable_lines(source)
                total = len(source.splitlines())
                for owner, lines in citations(document):
                    with self.subTest(document=name, provider=provider, entry=owner):
                        self.assertIsInstance(
                            lines,
                            list,
                            f"{owner} carries no 'source_lines'; the guide requires one "
                            "on every settled entry",
                        )
                        self.assertTrue(
                            lines, f"{owner} carries an empty 'source_lines'"
                        )
                        for line in lines:
                            # `bool` is an `int` in Python and not one to the guide,
                            # which rejects `True` as a line number outright.
                            self.assertNotIsInstance(
                                line, bool, f"{owner} cites {line!r}"
                            )
                            self.assertIsInstance(line, int, f"{owner} cites {line!r}")
                            self.assertGreaterEqual(line, 1, f"{owner} cites {line}")
                            self.assertLessEqual(
                                line,
                                total,
                                f"{owner} cites line {line} of a {total}-line "
                                f"{provider}/{agent}",
                            )
                            self.assertIn(
                                line,
                                allowed,
                                f"{owner} cites {provider}/{agent}:{line}, which is "
                                "blank, a comment or a docstring; cite the executable "
                                "statement that establishes the value",
                            )

    def test_every_entry_carries_evidence_and_a_citation(self) -> None:
        """The two halves the guide reads: prose for a human, lines for the checker."""
        for name in DOCUMENTS:
            document = json.loads((KNOBS_DIR / name).read_text(encoding="utf-8"))
            for section in ("knobs", "build"):
                for entry, spec in sorted(document.get(section, {}).items()):
                    with self.subTest(document=name, entry=f"{section}.{entry}"):
                        self.assertTrue(
                            str(spec.get("evidence", "")).strip(),
                            "every entry names the file and line it was read from",
                        )

    def test_the_agents_line_up_between_providers(self) -> None:
        """One set of citations for two files, so no line may move between them.

        Counting lines was not enough: the likely edit here is a swapped model id, which
        changes what a line says without changing how many there are, and a citation's
        prose can then be true of one provider and false of the other. So the two files
        are aligned line by line, and the only difference allowed is a line replaced by
        another line -- never one inserted or deleted, which is what shifts a citation.
        """
        for agent in DOCUMENTS.values():
            left, right = (
                (AGENT_DIR / provider / agent).read_text(encoding="utf-8").splitlines()
                for provider in PROVIDERS
            )
            moved = []
            for (
                kind,
                left_from,
                left_to,
                right_from,
                right_to,
            ) in difflib.SequenceMatcher(
                None, left, right, autojunk=False
            ).get_opcodes():
                shifts = kind in ("insert", "delete") or (left_to - left_from) != (
                    right_to - right_from
                )
                if shifts:
                    moved.append((kind, left_from + 1, left_to))
            with self.subTest(agent=agent):
                self.assertEqual(
                    moved,
                    [],
                    f"{agent} does not line up between {PROVIDERS[0]} and "
                    f"{PROVIDERS[1]}: {moved}. The agent-knobs documents cite one set of "
                    "line numbers for both, so a line added or removed in one of them "
                    "moves every citation below it",
                )


if __name__ == "__main__":
    unittest.main()
