# Guided First Run presentation

This directory builds one customer-facing story about the public
[Traigent Guided First Run](https://github.com/Traigent/traigent-first-run) guide, from one
validated content source, into two formats:

- a self-contained HTML presentation for a browser; and
- an editable PowerPoint presentation with native text, shapes, and speaker
  notes.

The deck is delivered live to customers, so it is built to be spoken over,
not read off the screen. Every slide carries one visual (icon tiles, a
side-by-side column comparison, a left-to-right flow, a 0-100 scale, a
two-column table, a callout card, or a short bullet list) and a few short
lines; the talk track and every detail cut from the slide live in the speaker
notes, which are the presenter's half of the deck. The story: the words the
guide uses, the one prompt, the four asks, the five stages, when money enters,
what happens from each starting point, the readiness score and its caps, the
secrets and safety boundaries, what leaves the customer's machine, what the
result contains, and how to start. The deck describes the guide and
records no run of its own, so it carries no measured outcome, no uplift figure,
and no example project.

The first 22 slides form the overview a reader with no prior Traigent
knowledge can follow. The remaining 18 slides are a clearly marked technical
appendix with stage detail, scoring mechanics, requirements, licensing, and the
repository layout.

## Source of truth

`src/content.ts` is the canonical slide content. Every fact in it is a reviewed
snapshot of the guide at one exact revision, recorded in the deck's `source`
block (repository, 40-character revision, and the guide files the deck draws
on). Each slide lists its `sources` as `FILE · section`. They are not printed on
the slide the customer sees; the speaker notes end with them beside the pinned
revision, in the browser deck's notes pane and on the PowerPoint notes page, so
the presenter can open the guide and check the slide against it. `src/model.ts` validates the
complete presentation before either renderer uses it, and rejects a source
that names a file the deck does not declare.

Both HTML and PowerPoint consume the same parsed `presentation` object. Do not
maintain separate claims for the two formats, and do not hand-edit generated
files under `dist/`.

When the guide changes, re-check the source constants (check names, pillar
weights, band thresholds, cap ceilings and blocking rules in
`skills/traigent-first-run/scripts/readiness.py`, the pinned SDK version in
`assets/requirements-first-run.txt`, and the wording of the opening message and
approval gates in `SKILL.md`), update the revision in the `source` block, and
never adjust a number merely to improve slide layout.

## Requirements

- Node.js 20.19 or newer
- npm with the committed lockfile
- Google Chrome or Chromium on `PATH`, or `CHROME_BIN` pointing to it, for
  the two-pass, isolated 1366x768 and 1600x900 browser-fit gate

Install locked dependencies and run the complete validation and build:

```bash
cd presentation
npm ci
npm run check
```

`npm run check` runs TypeScript checks, formatting validation, tests, semantic
content validation, and both presentation builds. Each gate identifies itself
by canonical path, so a gate invoked through a symbolic link runs instead of
exiting silently, and a gate that cannot place its own entry point fails rather
than reporting success. The browser-fit gate reads its verdict from the
attribute the in-page measurement wrote on the document element, so deck copy
that quotes that attribute cannot answer for a slide.

For focused work:

```bash
npm run dev          # local browser preview
npm run validate     # validate semantic content and claims
npm run build:web    # build the self-contained HTML
npm run build:pptx   # build the editable PowerPoint
npm run build:bundle # assemble the customer handoff bundle
npm run fit:browser  # render every slide at both required browser sizes
```

Run `npm run build` when the validated final outputs are needed together.

## Generated outputs

```text
dist/
  index.html
  traigent-first-run.pptx
  customer-bundle/
    LICENSE
    NOTICE
    presentation.html
    presentation.pptx
    build-manifest.json
    checksums.txt
    THIRD_PARTY_NOTICES.txt
```

`dist/index.html` is a single self-contained file and can be opened directly in
an approved modern browser without a web server. The PowerPoint keeps slide text
and shapes editable and includes the presenter notes from the semantic source.

The customer bundle gives the two formats stable names and includes the
repository's Apache-2.0 `LICENSE` and `NOTICE`, a build manifest, transfer
checksums, and notices for third-party runtime software.

The manifest and checksums cover both repository legal files. The manifest's
`deck` block records the guide repository, revision, and files the deck
describes, and every slide's sources, so the artifact says what it was checked
against.

The manifest's `offline` block is recorded from the checks that produced it and
carries a `verified_by` object stating what those checks establish. The scanned
set is the files the deck can actually reach: the walk of `src/` closed over the
imports those files declare, so a module imported from outside the presentation
tree is scanned as well instead of being compiled into the artifact without ever
being opened. An extension the scanner does not know is a build failure, not a
file it skips. The built HTML is then read as markup, so its external
references, style declarations, and the scripts the browser will run are each
inspected, and deck copy that quotes a tag or names a network API stays text. A
`/` or a quote the lexer cannot classify - a regular expression that would
enclose a network call, or a string literal that runs across a line break -
fails the build instead of hiding the code after it. Neither check runs the
deck: `browser_execution_observed` is `false`, and the block records what the
artifact contains rather than what a browser was seen to do. In the built
artifact a request is reported when its address is visible, because bundled
third-party code may call `fetch` for local reasons; the first-party scan is
the stricter of the two and reports the capability itself.

Bundle creation fails without replacing an existing bundle when either
repository legal file is missing, empty, outside the repository, or a symbolic
link. Verify the checksums after copying the bundle to another machine using the
customer's approved tooling.

## What the content validator refuses

Every slide must name at least one guide source and carry at least one speaker
note. Content validation rejects any sentence that reports a run result -
"we measured", "cost fell by", "verified result" and their kin - wherever it
renders: slide body, footer, speaker notes, or deck subtitle. The scan reads
every string the content model carries, so a field added to the schema is
covered without editing a list. A sentence that denies its own claim is not a
claim, and a denial in one clause does not cover a claim in the next. Metric
tiles have no green tone, because the deck has no success to colour.

The validator also holds the deck to its live-delivery shape. Each slide kind
carries exactly its own block (tiles on a tiles slide, columns on a columns
slide, and so on), a visual kind never stacks a bullet list on top, and a
callout or handoff slide pairs its card with at most four bullets. Every
visible line has a word budget, counted as tokens that carry a letter or a
digit: 14 words for a title, 32 for the body sentence, 9 for a bullet or a
column item, 12 for a tile detail, 14 for a callout or a flow-step detail, 10
and 18 for the two cells of a table row, and 3 and 6 for a scale band and a
scale marker. The budgets live in `WORD_BUDGETS` in
`scripts/validate-content.ts`; speaker notes have no budget, because that is
where the full explanation belongs.

## Updating the story

1. Update `src/content.ts` and, only when the contract itself changes,
   `src/model.ts`. Keep each slide to one visual and to its word budgets;
   put the detail in the speaker notes.
2. Re-check every number and quoted phrase against the guide at the revision
   recorded in the `source` block; when the guide moves, move the revision and
   re-verify rather than carrying old numbers forward.
3. Give each new slide its sources and a useful speaker note.
4. Run `npm run check`.
5. Inspect both `dist/index.html` and the generated PowerPoint before customer
   use.
