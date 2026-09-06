# SPDX-License-Identifier: Apache-2.0
"""Every relative link in a tracked Markdown file points at something that exists.

The README is the front door of a public repository, and it argues by citation: a claim
is made and a path is given for the reader who wants the evidence. A path that resolves
to nothing turns that into a dead end, and it does so silently -- nothing in the build,
the linter or the suite reads a link. Two links to a measurement card that was never
published survived a README rewrite and were found by a person reading the file, which is
the slowest way to find them.

So this file reads them instead. It covers both halves of a link that can rot: the path
part, checked against the working tree, and the `#anchor` part, checked against the
headings of the file it names. External links (`http`, `https`, `mailto`) are out of scope
-- they need the network, and a suite that needs the network is a suite that goes red for
reasons that have nothing to do with the change in front of it.
"""

from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parents[1]

# `[text](target)` and `![alt](target)`. The target stops at the first whitespace so that
# a Markdown title -- `(path "Title")` -- is not read as part of the path, and nested
# parentheses are not supported for the same reason CommonMark makes them awkward: no link
# in this repository uses them, and pretending otherwise would mean writing a parser.
INLINE_LINK = re.compile(r"!?\[(?:[^\]\\]|\\.)*\]\(\s*<?([^)\s>]*)>?[^)]*\)")
# `[label]: target` at the start of a line -- a reference definition.
REFERENCE_LINK = re.compile(
    r"^\s{0,3}\[(?:[^\]\\]|\\.)+\]:\s*<?([^\s>]+)>?", re.MULTILINE
)
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})", re.MULTILINE)
HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$", re.MULTILINE)
# Schemes this test deliberately does not follow.
EXTERNAL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def tracked_markdown() -> list[Path]:
    """The Markdown files git knows about, which is what a reader on the web gets."""
    listing = subprocess.run(
        ["git", "ls-files", "-z", "*.md"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    return [REPO_ROOT / name for name in listing.split("\0") if name]


def strip_code(text: str) -> str:
    """Blank out fenced code blocks, keeping line numbers intact.

    A fenced block is illustration, not citation: a path inside one may name a file in a
    project the reader is about to generate rather than a file in this repository.
    """
    out = text.splitlines(keepends=True)
    fence: str | None = None
    for index, line in enumerate(out):
        match = FENCE.match(line)
        if fence is None:
            if match:
                fence = match.group(1)[0] * 3
                out[index] = "\n"
            continue
        out[index] = "\n"
        if match and match.group(1).startswith(fence):
            fence = None
    return "".join(out)


def slug(heading: str) -> str:
    """GitHub's anchor for a heading, as far as this repository's headings need.

    Inline markup is removed, then everything but word characters, spaces and hyphens,
    then spaces become hyphens. Duplicate headings would get a `-1` suffix on GitHub;
    none of the files here have one, and the caller asserts that.
    """
    text = re.sub(r"`([^`]*)`", r"\1", heading)
    text = re.sub(r"!?\[((?:[^\]\\]|\\.)*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"[*_]", "", text)
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return text.strip().lower().replace(" ", "-")


def anchors(path: Path) -> set[str]:
    return {slug(match.group(2)) for match in HEADING.finditer(strip_code(read(path)))}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def links(path: Path) -> list[tuple[int, str]]:
    """Every link target in the file, with the line it sits on."""
    text = strip_code(read(path))
    found: list[tuple[int, str]] = []
    for pattern in (INLINE_LINK, REFERENCE_LINK):
        for match in pattern.finditer(text):
            target = match.group(1).strip()
            if target:
                found.append((text.count("\n", 0, match.start()) + 1, target))
    return sorted(found)


class TestMarkdownLinks(unittest.TestCase):
    """The suite reads what the README promises, so a promise cannot rot unseen."""

    files: list[Path]

    @classmethod
    def setUpClass(cls) -> None:
        cls.files = tracked_markdown()

    def test_the_repository_has_markdown_to_check(self) -> None:
        """A silent zero here would make every assertion below vacuously true."""
        names = {path.relative_to(REPO_ROOT).as_posix() for path in self.files}
        self.assertIn("README.md", names)
        self.assertGreaterEqual(len(names), 5, names)

    def test_relative_paths_resolve(self) -> None:
        for path in self.files:
            name = path.relative_to(REPO_ROOT).as_posix()
            for line, target in links(path):
                if EXTERNAL.match(target) or target.startswith(("#", "//")):
                    continue
                with self.subTest(file=name, line=line, target=target):
                    self.assertFalse(
                        target.startswith("/"),
                        "an absolute path is read from the filesystem root by a "
                        "checkout and from the site root by the web, so it is broken "
                        "in at least one of the two",
                    )
                    resolved = (
                        path.parent / unquote(target.split("#", 1)[0])
                    ).resolve()
                    self.assertTrue(
                        resolved.exists(),
                        f"{name}:{line} links to {target}, which does not exist",
                    )
                    self.assertTrue(
                        resolved.is_relative_to(REPO_ROOT),
                        f"{name}:{line} links to {target}, outside the repository",
                    )

    def test_anchors_name_a_heading(self) -> None:
        for path in self.files:
            name = path.relative_to(REPO_ROOT).as_posix()
            for line, target in links(path):
                if EXTERNAL.match(target) or target.startswith("//"):
                    continue
                head, _, fragment = target.partition("#")
                if not fragment:
                    continue
                destination = path if not head else (path.parent / unquote(head))
                if destination.suffix != ".md" or not destination.exists():
                    continue
                with self.subTest(file=name, line=line, target=target):
                    self.assertIn(
                        unquote(fragment).lower(),
                        anchors(destination),
                        f"{name}:{line} links to {target}, and no heading in "
                        f"{destination.relative_to(REPO_ROOT).as_posix()} has that anchor",
                    )

    def test_headings_are_unique_per_file(self) -> None:
        """Two headings with one slug make an anchor mean whichever came first.

        It also makes the check above weaker than it reads, since a link could resolve
        against the heading it did not mean.
        """
        for path in self.files:
            name = path.relative_to(REPO_ROOT).as_posix()
            slugs = [slug(m.group(2)) for m in HEADING.finditer(strip_code(read(path)))]
            with self.subTest(file=name):
                duplicates = sorted({s for s in slugs if slugs.count(s) > 1})
                self.assertEqual([], duplicates, f"{name} repeats {duplicates}")


if __name__ == "__main__":
    unittest.main()
