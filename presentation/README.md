# Customer Presentation

This directory builds one customer-facing story from one validated semantic source:

- a self-contained HTML presentation for a browser; and
- an editable PowerPoint presentation with native text, shapes, and speaker
  notes.

The presentation explains the guided first run, the Spider text-to-SQL demo
projects this repository builds, and the boundary between a catalog check
(`build.py check`), a Phase A opening, and a separately approved Phase B live
optimization. The current content does not claim that a fresh worker run has
been recorded or verified.

The first 10 slides form the presales/CTO core story. The remaining 11 slides
are a clearly marked technical appendix with stage detail, scoring mechanics,
held-out evaluation, and the Spider scenario reference cards.

## Source of truth

`src/content.ts` is the canonical slide content. It imports nothing from outside
`src/`; its Spider facts are a reviewed snapshot of this repository's `README.md`
and of `python3 build.py list` and `python3 build.py check`. `src/model.ts`
validates the complete presentation before either renderer uses it.

Both HTML and PowerPoint consume the same parsed `presentation` object. Do not
maintain separate claims for the two formats, and do not hand-edit generated
files under `dist/`.

The Stage 2 scoring and cap slides are a reviewed snapshot of the public
Guided First Run scorer at revision
[`75d338c3`](https://github.com/Traigent/traigent-first-run/blob/75d338c31c97643c6a6d28a6aeef582d7b938db8/skills/traigent-first-run/scripts/readiness.py).
Their evidence footer records that revision. Re-check the source constants,
check display names, confidence behavior, and cap semantics whenever the guide
changes; do not adjust a number merely to improve slide layout.

## Reproduction contract behind the deck

The presentation's evidence wording follows this repository's `build.py`
contract. `build.py` is standard library only, has no install step, and builds
from committed data, so a fresh clone can build offline:

- `python3 build.py list` shows the 17 presets and every component state the
  presets-matrix slide summarises.
- `python3 build.py check` validates this repository's own components and data.
  It builds nothing and runs no agent; it is the deck's "catalog check" layer.
- `python3 build.py demo --preset NAME --out DIR` builds one demo project, and
  `python3 build.py suite --out DIR` builds every preset, each in its own
  blinded directory. Only the optional `--venv ready` flag installs anything,
  and only into the demo's own environment.
- `python3 build.py verify --demo DIR` checks that a built demo is
  self-contained, blind, and able to run. It reports problems rather than
  raising, and it executes no agent or guide code.

The current deck has the published presets and their expected routing but no
referenced captured worker result. A passing `check` or `verify`, or a built
demo directory, must not be presented as verified run evidence.

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
  traigent-first-run-scenarios.pptx
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

The manifest and checksums cover both repository legal files. The manifest
records every slide's evidence state and the exact source revision for each
guide-contract slide; the current manifest therefore makes the absence of
verified-run slides explicit.

The manifest's `offline` block is recorded from the checks that produced it and
carries a `verified_by` object stating what those checks establish. The scanned
set is the files the deck can actually reach: the walk of `src/` closed over the
imports those files declare, so a module imported from outside the presentation
tree is scanned as well instead of being compiled into the artifact without ever
being opened. An extension
the scanner does not know is a build failure, not a file it skips. The built HTML
is then read as markup, so its external references, style declarations, and the
scripts the browser will run are each inspected, and deck copy that quotes a tag
or names a network API stays text. A `/` or a quote the lexer cannot classify -
a regular expression that would enclose a network call, or a string literal
that runs across a line break - fails the build instead of hiding the code
after it. Neither check runs the deck:
`browser_execution_observed` is `false`, and the block records what the artifact
contains rather than what a browser was seen to do. In the built artifact a
request is reported when its address is visible, because bundled third-party code
may call `fetch` for local reasons; the first-party scan is the stricter of the
two and reports the capability itself.

Bundle creation fails without replacing an existing bundle when either
repository legal file is missing, empty, outside the repository, or a symbolic
link. Verify the checksums after copying the bundle to another machine using the
customer's approved tooling.

## Evidence labels

Every slide must contain at least one evidence reference, at least one speaker
note, and exactly one evidence state:

| Label                                   | Use                                                                           |
| --------------------------------------- | ----------------------------------------------------------------------------- |
| **Guide contract · no recorded run**    | Guide behavior pinned to an exact 40-character public guide revision          |
| **Scenario contract · no recorded run** | Published scenario facts or expected values without a referenced recorded run |
| **Verified run evidence**               | Complete retained Phase A report plus successful semantic verification        |
| **Not demonstrated in this deck**       | A live path, improvement, or other outcome that was not exercised             |

The current deck uses guide-contract, scenario-contract, and not-demonstrated
states. Do not change a slide to verified-run merely because its expected
values look correct. A run record, result JSON, and `PASS` alone are
insufficient. A verified claim requires both the matching semantic verification
and a retained report identifying the revisions, worker and session,
environment and isolation boundary, exact handoff and response, captured JSON,
complete commands, output and final statuses, verifier output, and stop point.

The validator currently rejects every verified-run slide until that evidence
has a strict retained schema and validator. This is an intentional fail-closed
boundary, not a missing checkbox that prose can satisfy.

Content validation rejects unsupported live-value and improvement claims. It
also prevents an absent result from becoming an implied green outcome. An
Excellent expected band is the published grade for this scenario's opening
contract; it is not a universal grade for the coding agent or proof of a live
optimization. The claim scan reads every string the content model carries, so a
claim is caught wherever it renders - slide body, footer evidence, speaker
notes, catalog card, or deck subtitle - and a field added to the schema is
covered without editing a list. Two things are not claims: a sentence that
denies its own claim, and the `Not proven` and `Does not prove` fields, whose
heading already states that the deck asserts nothing there. A denial in one
sentence does not cover a claim in the next.

## Updating the story

1. Update `src/content.ts` and, only when the contract itself changes,
   `src/model.ts`.
2. Re-check every Spider fact against `README.md`, `python3 build.py list`, and
   `python3 build.py check` whenever the presets or data change; the deck's
   numbers are a reviewed snapshot, not a live read.
3. Give each new slide an evidence state, evidence reference, and useful speaker
   note.
4. Run `npm run check`.
5. Inspect both `dist/index.html` and the generated PowerPoint before customer
   use.

See the [repository README](../README.md), [the data](../docs/dataset.md),
[the two SQL scorers](../docs/eval-methods.md), and
[keeping a demo separate](../docs/isolation.md) for the operating and evidence
boundaries.
