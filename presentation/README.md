# Guided First Run presentation

This directory builds one presales story about the public
[Traigent Guided First Run](https://github.com/Traigent/traigent-first-run) guide, from one
validated content source, into two formats:

- a self-contained HTML presentation for a browser; and
- an editable PowerPoint presentation with native text, shapes, and speaker
  notes.

The deck explains what the guide does for a customer: the one prompt, the five
stages, the readiness score and its caps, the two paid approvals, what leaves
the customer's machine, what the result contains, and how presales runs it.
It describes the guide and records no run of its own, so it carries no measured
outcome, no uplift figure, and no example project.

The first 10 slides form the presales/CTO core story. The remaining 10 slides
are a clearly marked technical appendix with stage detail, scoring mechanics,
requirements, licensing, and the repository layout.

## Source of truth

`src/content.ts` is the canonical slide content. Every fact in it is a reviewed
snapshot of the guide at one exact revision, recorded in the deck's `source`
block (repository, 40-character revision, and the guide files the deck draws
on). Each slide lists its `sources` as `FILE · section`, and the footer of every
rendered slide prints them beside the pinned revision, so a reader can open
the guide and check the slide against it. `src/model.ts` validates the
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

## Updating the story

1. Update `src/content.ts` and, only when the contract itself changes,
   `src/model.ts`.
2. Re-check every number and quoted phrase against the guide at the revision
   recorded in the `source` block; when the guide moves, move the revision and
   re-verify rather than carrying old numbers forward.
3. Give each new slide its sources and a useful speaker note.
4. Run `npm run check`.
5. Inspect both `dist/index.html` and the generated PowerPoint before customer
   use.
