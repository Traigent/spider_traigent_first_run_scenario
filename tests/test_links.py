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

Two kinds of mistake are possible here and they are not equally bad. A **false green** --
a dead link the walk never looked at -- is the failure this file exists to prevent, so
nothing is skipped without a reason written down. A **false red** -- an ordinary sentence
the walk misreads as a broken link -- is how a checker gets deleted by the first person it
inconveniences, so prose that merely *shows* link syntax is not treated as a link: code
spans, code blocks, HTML comments and `{{template}}` placeholders are all passed over.

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
import tempfile
import unittest
from pathlib import Path
from urllib.parse import unquote

REPO_ROOT = Path(__file__).resolve().parents[1]

# `[text](target)` and `![alt](target)`. The target stops at the first whitespace so that
# a Markdown title -- `(path "Title")` -- is not read as part of the path, and nested
# parentheses are not supported for the same reason CommonMark makes them awkward: no link
# in this repository uses them, and pretending otherwise would mean writing a parser.
INLINE_LINK = re.compile(r"!?\[(?:[^\]\\]|\\.)*\]\([ \t]*<?([^)\s>]*)>?[^)]*\)")
# `[label]: target` at the start of a line -- a reference definition.
REFERENCE_LINK = re.compile(
    r"^[ \t]{0,3}\[(?:[^\]\\]|\\.)+\]:[ \t]*<?([^\s>]+)>?", re.MULTILINE
)
# The HTML a Markdown file is allowed to carry. Badges, centred images and hand-written
# anchors are ordinarily written this way, so leaving them out would leave the shape most
# likely to rot next unread. Quoted attribute values only; an unquoted one is not read.
HTML_LINK = re.compile(
    r"<(?:a|area|link)\b[^>]*?\bhref\s*=\s*[\"']([^\"']+)[\"']", re.I | re.S
)
HTML_SOURCE = re.compile(
    r"<(?:img|source|video|audio|embed|iframe)\b[^>]*?\bsrc\s*=\s*[\"']([^\"']+)[\"']",
    re.I | re.S,
)
PATTERNS = (INLINE_LINK, REFERENCE_LINK, HTML_LINK, HTML_SOURCE)

FENCE = re.compile(r"^[ \t]{0,3}(`{3,}|~{3,})", re.MULTILINE)
INDENTED = re.compile(r"^(?: {4}|\t)")
# A bullet or an ordered item, at any indent: inside a list, indented text is list content
# rather than a code block, which is the difference between reading a citation and skipping
# one. Any leading whitespace is allowed so that a nested bullet is still a bullet.
LIST_ITEM = re.compile(r"^\s*(?:[-*+]|\d{1,9}[.)])(?:\s|$)")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
CODE_SPAN = re.compile(r"(`+)(?:(?!\1)[\s\S])*?\1")
HEADING = re.compile(r"^[ \t]{0,3}(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$", re.MULTILINE)
HTML_TAG = re.compile(r"</?[A-Za-z][^>]*>")
# Schemes this test deliberately does not follow.
EXTERNAL = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")
# A target that is a template hole rather than a path. `{{badge}}` and `${VERSION}` are
# written to be substituted, so checking them would red an ordinary README.
PLACEHOLDER = re.compile(r"[{}$]")


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

    A link may legitimately name a directory -- `docs/measurements/cards/` -- or the
    repository root, and git tracks files rather than directories, so the containing
    directories are added back.
    """
    paths: set[Path] = {REPO_ROOT}
    for name in git_files():
        current = (REPO_ROOT / name).resolve()
        while current != REPO_ROOT:
            paths.add(current)
            current = current.parent
    return paths


def blank(match: re.Match[str]) -> str:
    """The matched text with everything but its newlines replaced by spaces.

    Blanking rather than deleting is what keeps a reported line number the line number a
    reader will look at.
    """
    return "".join("\n" if character == "\n" else " " for character in match.group(0))


def strip_blocks(text: str) -> str:
    """Blank out block-level code, keeping line numbers intact.

    Code is illustration, not citation: a path inside a block may name a file in a project
    the reader is about to generate rather than a file in this repository. Both spellings
    are removed -- a ``` or ~~~ fence, and a block indented by four spaces or a tab.

    The indented form is the one that has to be careful. CommonMark's four-space rule does
    not apply inside a list, where indented text is the item's own content, so an indented
    run is treated as code only when no list is open and a blank line opened it. Getting
    that wrong in the other direction would skip a genuinely dead link sitting under a
    bullet, which is a false green -- the one outcome this file cannot afford.
    """
    out = text.splitlines(keepends=True)
    fence: str | None = None
    indented = False
    blank_before = True
    in_list = False
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
            indented = False
            continue
        if not line.strip():
            # A blank line can open an indented block, and does not close a list: a list
            # item's continuation paragraph is separated from it by exactly this.
            indented = False
            blank_before = True
            continue
        if LIST_ITEM.match(line):
            in_list = True
            indented = False
        elif INDENTED.match(line):
            if not in_list and (indented or blank_before):
                indented = True
                out[index] = "\n"
        else:
            # An unindented line of prose ends both the list and any indented run.
            in_list = False
            indented = False
        blank_before = False
    return "".join(out)


def strip_code(text: str) -> str:
    """`strip_blocks`, and also the two spellings that quote a link rather than make one.

    A code span is how a README *shows* link syntax -- "write it as `<img src="badge.png">`"
    -- and an HTML comment is what a parked or retired link looks like. Reading either as a
    live link fails a file that is perfectly correct.
    """
    text = strip_blocks(text)
    text = HTML_COMMENT.sub(blank, text)
    return CODE_SPAN.sub(blank, text)


def slug(heading: str) -> str:
    """GitHub's anchor for a heading, as far as this repository's headings need.

    Inline markup and HTML tags are removed, then everything but word characters, spaces
    and hyphens, then spaces become hyphens. `_` is *kept*: it is a word character,
    GitHub's slugger keeps it, and deleting it would fail a link that works while passing
    the spelling that 404s -- the one direction a link test must never get wrong, in a
    repository whose prose is full of `max_trials` and `exact_match`. Only a pair of
    underscores wrapping a whole heading is removed, since that is emphasis rather than a
    name; mid-heading `_emphasis_` is left alone, which is the deliberate cost of that
    choice. Duplicate headings would get a `-1` suffix on GitHub; none of the files here
    have one, and `TestMarkdownLinks.test_headings_are_unique_per_file` asserts that.
    """
    text = re.sub(r"`([^`]*)`", r"\1", heading)
    text = re.sub(r"!?\[((?:[^\]\\]|\\.)*)\]\([^)]*\)", r"\1", text)
    text = HTML_TAG.sub("", text)
    text = re.sub(r"\*", "", text)
    text = re.sub(r"^_+(.+?)_+$", r"\1", text.strip())
    text = re.sub(r"[^\w\s-]", "", text, flags=re.UNICODE)
    return text.strip().lower().replace(" ", "-")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def anchors(path: Path) -> set[str]:
    """The anchors a reader can jump to in this file.

    `strip_blocks` rather than `strip_code`, because a heading may legitimately contain a
    code span -- "What `best-case` really opens at" -- and blanking it here would compute
    the wrong anchor for a heading that works.
    """
    return {
        slug(match.group(2)) for match in HEADING.finditer(strip_blocks(read(path)))
    }


def find_links(text: str) -> list[tuple[int, str]]:
    """Every link target in a Markdown document, with the line it sits on."""
    text = strip_code(text)
    found: list[tuple[int, str]] = []
    for pattern in PATTERNS:
        for match in pattern.finditer(text):
            target = match.group(1).strip()
            if target:
                found.append((text.count("\n", 0, match.start()) + 1, target))
    return sorted(found)


def links(path: Path) -> list[tuple[int, str]]:
    return find_links(read(path))


def followed(target: str) -> bool:
    """Whether a target is one this file makes a claim about."""
    if EXTERNAL.match(target) or target.startswith("//"):
        return False
    return not PLACEHOLDER.search(target)


def unpublished(source: Path, target: str, tracked: set[Path]) -> str | None:
    """The reason a link is broken for a reader, or `None` if it is not.

    Resolution is against `tracked` -- the set git knows about -- and not against the
    working tree: a file that exists only in one contributor's checkout is a 404 for
    everybody else, and a checker that goes green on it is worse than no checker.
    """
    path = unquote(target.split("#", 1)[0].split("?", 1)[0])
    if target.startswith("/"):
        return (
            f"{target} is an absolute path, read from the filesystem root by a checkout "
            "and from the site root by the web, so it is broken in at least one of the two"
        )
    resolved = (source.parent / path).resolve()
    if resolved in tracked:
        return None
    return f"{target} is not tracked by git (present in this working tree: {resolved.exists()})"


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
        self.assertEqual("__init__-and-friends", slug("`__init__` and friends"))

    def test_emphasis_markers_are_removed(self) -> None:
        self.assertEqual("a-bold-heading", slug("A **bold** heading"))
        self.assertEqual("wholly-emphasised", slug("_Wholly emphasised_"))

    def test_code_spans_links_and_html_keep_their_text(self) -> None:
        self.assertEqual(
            "what-best-case-really-opens-at", slug("What `best-case` really opens at")
        )
        self.assertEqual("see-the-card", slug("See [the card](docs/x.md)"))
        self.assertEqual("press-ctrl-c", slug("Press <kbd>Ctrl</kbd> C"))

    def test_punctuation_goes_and_spaces_become_hyphens(self) -> None:
        self.assertEqual(
            "these-figures-have-drifted-and-a-regeneration-is-pending",
            slug("These figures have drifted, and a regeneration is pending"),
        )
        self.assertEqual("100-of-the-rows", slug("100% of the rows"))


class TestStripCode(unittest.TestCase):
    """Only quoted or illustrative text is blanked, and it is blanked in every spelling.

    Every case here is one of the two mistakes named in the module docstring, pinned in
    the direction it must not drift: a false green (a real link the walk stops seeing) or
    a false red (ordinary prose the walk starts reading as a link).
    """

    def test_a_fenced_block_is_not_read(self) -> None:
        self.assertNotIn("nope.md", strip_code("a\n\n```\n[x](nope.md)\n```\n"))

    def test_an_indented_block_is_not_read(self) -> None:
        self.assertNotIn("nope.md", strip_code("before\n\n    [x](nope.md)\n"))

    def test_a_link_under_a_bullet_is_still_read(self) -> None:
        """A false green, and the worst kind: indented text in a list is not code.

        CommonMark's four-space rule does not apply inside a list, so a citation in a
        nested bullet or a continuation paragraph must stay visible to the walk.
        """
        nested = "- one\n    - [x](yes.md)\n"
        self.assertIn("yes.md", strip_code(nested))
        continuation = "- one\n\n    [x](yes.md)\n"
        self.assertIn("yes.md", strip_code(continuation))
        ordered = "1. one\n\n    [x](yes.md)\n"
        self.assertIn("yes.md", strip_code(ordered))

    def test_a_list_ends_at_unindented_prose(self) -> None:
        text = "- one\n\nplain prose\n\n    [x](nope.md)\n"
        self.assertNotIn("nope.md", strip_code(text))

    def test_an_indented_continuation_of_a_paragraph_is_still_read(self) -> None:
        """No blank line opens it, so it is prose that happens to be indented."""
        self.assertIn("yes.md", strip_code("a sentence that wraps\n    [x](yes.md)\n"))

    def test_a_code_span_shows_link_syntax_rather_than_linking(self) -> None:
        text = 'Write it as `<img src="nonexistent.png">` in your README.\n'
        self.assertEqual([], find_links(text))

    def test_a_commented_out_link_is_not_live(self) -> None:
        text = '<!-- <a href="retired.md">old link</a> -->\n\n[y](yes.md)\n'
        self.assertEqual([(3, "yes.md")], find_links(text))

    def test_line_numbers_survive(self) -> None:
        text = "a\n\n```\nb\n```\n\n<!--\nc\n-->\n\n[y](yes.md)\n"
        self.assertEqual(len(text.splitlines()), len(strip_code(text).splitlines()))
        self.assertEqual([(11, "yes.md")], find_links(text))


class TestLinkExtraction(unittest.TestCase):
    """What counts as a link, pinned to fixtures instead of to the corpus.

    The repository happens to contain only inline Markdown links today, so the corpus
    cannot tell anyone whether the HTML half of the walk works, or whether it has been
    removed. These fixtures can.
    """

    def test_html_href_and_src_are_links(self) -> None:
        text = '<a href="docs/a.md">a</a>\n<img src="docs/b.png">\n'
        self.assertEqual([(1, "docs/a.md"), (2, "docs/b.png")], find_links(text))

    def test_html_attributes_may_be_single_quoted_or_span_lines(self) -> None:
        text = "<a\n  class='x'\n  href='docs/c.md'>c</a>\n"
        self.assertEqual([(1, "docs/c.md")], find_links(text))

    def test_markdown_inline_reference_and_image_are_links(self) -> None:
        text = '[a](docs/a.md)\n![b](docs/b.png "title")\n\n[c]: docs/c.md\n'
        self.assertEqual(
            [(1, "docs/a.md"), (2, "docs/b.png"), (4, "docs/c.md")], find_links(text)
        )

    def test_a_template_hole_is_not_a_path(self) -> None:
        self.assertFalse(followed("{{path_to_badge}}"))
        self.assertFalse(followed("${VERSION}/docs.md"))
        self.assertTrue(followed("docs/a.md"))

    def test_external_and_protocol_relative_targets_are_left_alone(self) -> None:
        self.assertFalse(followed("https://example.invalid/x"))
        self.assertFalse(followed("mailto:someone@example.invalid"))
        self.assertFalse(followed("//example.invalid/x"))


class TestUnpublished(unittest.TestCase):
    """Resolution is against what git tracks, not against this working tree.

    Without this class the difference is invisible: every link in the repository points at
    a tracked file, so swapping the tracked-set check back for `Path.exists()` passes the
    whole suite while quietly restoring a local green for a link that 404s on the web.
    """

    tracked: set[Path]

    @classmethod
    def setUpClass(cls) -> None:
        cls.tracked = tracked_paths()

    def test_a_tracked_file_and_a_tracked_directory_resolve(self) -> None:
        readme = REPO_ROOT / "README.md"
        self.assertIsNone(unpublished(readme, "docs/dataset.md", self.tracked))
        self.assertIsNone(unpublished(readme, "docs/measurements/cards/", self.tracked))
        self.assertIsNone(
            unpublished(readme, "./docs/dataset.md#a-heading", self.tracked)
        )
        self.assertIsNone(unpublished(readme, "docs/dataset.md?plain=1", self.tracked))

    def test_a_file_present_but_untracked_does_not_resolve(self) -> None:
        with tempfile.TemporaryDirectory(dir=REPO_ROOT) as directory:
            here = Path(directory)
            (here / "untracked.md").write_text("x", encoding="utf-8")
            target = f"{here.name}/untracked.md"
            reason = unpublished(REPO_ROOT / "README.md", target, self.tracked)
            self.assertIsNotNone(reason)
            assert reason is not None
            self.assertIn("not tracked by git", reason)
            self.assertIn("present in this working tree: True", reason)

    def test_a_missing_file_does_not_resolve(self) -> None:
        reason = unpublished(REPO_ROOT / "README.md", "docs/gone.md", self.tracked)
        self.assertIsNotNone(reason)
        assert reason is not None
        self.assertIn("present in this working tree: False", reason)

    def test_an_absolute_path_is_refused(self) -> None:
        reason = unpublished(REPO_ROOT / "README.md", "/docs/dataset.md", self.tracked)
        self.assertIsNotNone(reason)
        assert reason is not None
        self.assertIn("absolute path", reason)


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
                if not followed(target) or target.startswith("#"):
                    continue
                with self.subTest(file=name, line=line, target=target):
                    reason = unpublished(path, target, self.tracked)
                    self.assertIsNone(reason, f"{name}:{line}: {reason}")

    def test_anchors_name_a_heading(self) -> None:
        for path in self.files:
            name = path.relative_to(REPO_ROOT).as_posix()
            for line, target in links(path):
                if not followed(target):
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
        against the heading it did not mean. GitHub would disambiguate with a `-1` suffix;
        this repository has no such pair, and requiring that keeps every anchor readable.
        """
        for path in self.files:
            name = path.relative_to(REPO_ROOT).as_posix()
            slugs = [
                slug(m.group(2)) for m in HEADING.finditer(strip_blocks(read(path)))
            ]
            with self.subTest(file=name):
                duplicates = sorted({s for s in slugs if slugs.count(s) > 1})
                self.assertEqual([], duplicates, f"{name} repeats {duplicates}")


if __name__ == "__main__":
    unittest.main()
