# SPDX-License-Identifier: Apache-2.0
"""Every relative link in a tracked Markdown file points at something that exists.

The README is the front door of a public repository, and it argues by citation: a claim
is made and a path is given for the reader who wants the evidence. A path that resolves
to nothing turns that into a dead end, and it does so silently -- nothing in the build,
the linter or the suite reads a link. Two links to a measurement card that was never
published survived a README rewrite and were found by a person reading the file, which is
the slowest way to find them.

So this file reads them instead. It covers both halves of a link that can rot: the path
part, checked against the set of files git tracks, and the `#anchor` part, checked against
the headings of the file it names. Both Markdown syntax (`[text](target)`, `![alt](src)`,
`[label]: target`) and the HTML a Markdown file may carry (`<a href>`, `<img src>`) are
read.

Two deliberate limits, so the docstring does not promise more than the code does. External
links (`http`, `https`, `mailto`) are not followed: that needs the network, and a suite
that needs the network goes red for reasons that have nothing to do with the change in
front of it. And the check is against what git tracks rather than against the working tree,
because an untracked file that happens to sit in one contributor's checkout does not exist
for the reader the links are written for.
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
# The HTML a Markdown file is allowed to carry. Badges, centred images and hand-written
# anchors are ordinarily written this way, so leaving them out would leave the shape most
# likely to rot next unread.
HTML_LINK = re.compile(
    r"<(?:a|area|link)\b[^>]*?\bhref\s*=\s*[\"']([^\"']+)[\"']", re.I
)
HTML_SOURCE = re.compile(
    r"<(?:img|source|video|audio|embed|iframe)\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']",
    re.I,
)
FENCE = re.compile(r"^\s{0,3}(`{3,}|~{3,})", re.MULTILINE)
INDENTED_CODE = re.compile(r"^(?: {4}|\t)")
HEADING = re.compile(r"^\s{0,3}(#{1,6})\s+(.*?)\s*#*\s*$", re.MULTILINE)
# Schemes this test deliberately does not follow.
EXTERNAL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
PATTERNS = (INLINE_LINK, REFERENCE_LINK, HTML_LINK, HTML_SOURCE)


def git_files() -> list[str]:
    """Every path git tracks, which is what a reader on the web gets."""
    listing = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    return [name for name in listing.split("\0") if name]


def tracked_markdown() -> list[Path]:
    return [REPO_ROOT / name for name in git_files() if name.endswith(".md")]


def tracked_paths() -> set[Path]:
    """The tracked files, plus every directory that contains one.

    A link may legitimately name a directory -- `docs/measurements/cards/` -- and git
    tracks files rather than directories, so the containing directories are added back.
    """
    paths: set[Path] = set()
    for name in git_files():
        current = (REPO_ROOT / name).resolve()
        while current != REPO_ROOT:
            paths.add(current)
            current = current.parent
    return paths


def strip_code(text: str) -> str:
    """Blank out code blocks, keeping line numbers intact.

    Code is illustration, not citation: a path inside a block may name a file in a project
    the reader is about to generate rather than a file in this repository. Both spellings
    are removed -- a ``` or ~~~ fence, and a block indented by four spaces or a tab after
    a blank line. The indented form is deliberately conservative: it opens only after a
    blank line, so an indented continuation line inside a fence or a paragraph is not
    mistaken for code and its links stay visible.
    """
    out = text.splitlines(keepends=True)
    fence: str | None = None
    indented = False
    blank_before = True
    for index, line in enumerate(out):
        match = FENCE.match(line)
        if fence is not None:
            out[index] = "\n"
            if match and match.group(1).startswith(fence):
                fence = None
            blank_before = False
            continue
        if match:
            fence = match.group(1)[0] * 3
            out[index] = "\n"
            blank_before = False
            continue
        if not line.strip():
            indented = False
            blank_before = True
            continue
        if INDENTED_CODE.match(line) and (indented or blank_before):
            indented = True
            out[index] = "\n"
        else:
            indented = False
        blank_before = False
    return "".join(out)


def slug(heading: str) -> str:
    """GitHub's anchor for a heading, as far as this repository's headings need.

    Inline markup is removed, then everything but word characters, spaces and hyphens,
    then spaces become hyphens. `_` is *kept*: it is a word character, GitHub's slugger
    keeps it, and deleting it would fail a link that works while passing the spelling
    that 404s -- the one direction a link test must never get wrong, in a repository
    whose prose is full of `max_trials` and `exact_match`. Only a pair of underscores
    wrapping a whole heading is removed, since that is emphasis rather than a name.
    Duplicate headings would get a `-1` suffix on GitHub; none of the files here have
    one, and `TestMarkdownLinks.test_headings_are_unique_per_file` asserts that.
    """
    text = re.sub(r"`([^`]*)`", r"\1", heading)
    text = re.sub(r"!?\[((?:[^\]\\]|\\.)*)\]\([^)]*\)", r"\1", text)
    text = re.sub(r"\*", "", text)
    text = re.sub(r"^_+(.+?)_+$", r"\1", text.strip())
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return text.strip().lower().replace(" ", "-")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def anchors(path: Path) -> set[str]:
    return {slug(match.group(2)) for match in HEADING.finditer(strip_code(read(path)))}


def links(path: Path) -> list[tuple[int, str]]:
    """Every link target in the file, with the line it sits on."""
    text = strip_code(read(path))
    found: list[tuple[int, str]] = []
    for pattern in PATTERNS:
        for match in pattern.finditer(text):
            target = match.group(1).strip()
            if target:
                found.append((text.count("\n", 0, match.start()) + 1, target))
    return sorted(found)


class TestSlug(unittest.TestCase):
    """The anchor rule, held to fixtures rather than to whatever the code happens to do.

    The underscore case is the reason this class exists. An earlier revision of `slug`
    stripped `_` along with `*`, which turned the working anchor for a heading such as
    `The max_trials refusal` into `the-maxtrials-refusal`: the correct link went red and
    the broken one went green. A check that fails on correct input is worse than no check,
    because the cheapest way to make it pass is to write the broken spelling.
    """

    def test_an_underscore_in_a_name_survives(self) -> None:
        self.assertEqual("the-max_trials-refusal", slug("The max_trials refusal"))
        self.assertEqual(
            "exact_match-and-exec_match", slug("exact_match and exec_match")
        )

    def test_emphasis_markers_are_removed(self) -> None:
        self.assertEqual("a-bold-heading", slug("A **bold** heading"))
        self.assertEqual("wholly-emphasised", slug("_Wholly emphasised_"))

    def test_code_spans_and_links_keep_their_text(self) -> None:
        self.assertEqual(
            "what-best-case-really-opens-at", slug("What `best-case` really opens at")
        )
        self.assertEqual("see-the-card", slug("See [the card](docs/x.md)"))

    def test_punctuation_goes_and_spaces_become_hyphens(self) -> None:
        self.assertEqual(
            "these-figures-have-drifted-and-a-regeneration-is-pending",
            slug("These figures have drifted, and a regeneration is pending"),
        )
        self.assertEqual(
            "the-bank-and-why-its-names-are-unreadable",
            slug("The bank, and why its names are unreadable"),
        )


class TestStripCode(unittest.TestCase):
    """Only code is blanked, and code is blanked in both of its spellings."""

    def test_a_fenced_block_is_not_read(self) -> None:
        text = "before\n\n```\n[x](nope.md)\n```\n\n[y](yes.md)\n"
        self.assertNotIn("nope.md", strip_code(text))
        self.assertIn("yes.md", strip_code(text))

    def test_an_indented_block_is_not_read(self) -> None:
        text = "before\n\n    [x](nope.md)\n\n[y](yes.md)\n"
        self.assertNotIn("nope.md", strip_code(text))
        self.assertIn("yes.md", strip_code(text))

    def test_an_indented_continuation_of_a_paragraph_is_still_read(self) -> None:
        """No blank line opens it, so it is prose that happens to be indented."""
        text = "a sentence that wraps\n    [x](yes.md)\n"
        self.assertIn("yes.md", strip_code(text))

    def test_line_numbers_survive(self) -> None:
        text = "a\n\n```\nb\n```\n\n[y](yes.md)\n"
        self.assertEqual(len(text.splitlines()), len(strip_code(text).splitlines()))


class TestMarkdownLinks(unittest.TestCase):
    """The suite reads what the README promises, so a promise cannot rot unseen."""

    files: list[Path]
    tracked: set[Path]

    @classmethod
    def setUpClass(cls) -> None:
        cls.files = tracked_markdown()
        cls.tracked = tracked_paths()

    def test_the_repository_has_markdown_to_check(self) -> None:
        """A silent zero here would make every assertion below vacuously true."""
        names = {path.relative_to(REPO_ROOT).as_posix() for path in self.files}
        self.assertIn("README.md", names)
        self.assertGreaterEqual(len(names), 5, names)
        self.assertGreater(sum(len(links(path)) for path in self.files), 20)

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
                    # assertIn would print the whole tracked set -- thousands of
                    # paths -- for one dead link, which buries the one line that says
                    # which link died.
                    self.assertTrue(
                        resolved in self.tracked,
                        f"{name}:{line} links to {target}, which git does not track "
                        f"(present in this working tree: {resolved.exists()})",
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
                destination = (
                    path if not head else (path.parent / unquote(head)).resolve()
                )
                if destination.suffix != ".md" or destination not in self.tracked:
                    continue
                with self.subTest(file=name, line=line, target=target):
                    self.assertIn(
                        unquote(fragment).lower(),
                        anchors(destination),
                        f"{name}:{line} links to {target}, and no heading in that "
                        "file has that anchor",
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
