import { readFileSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

import { describe, expect, it } from "vitest";

import {
  ContentValidationError,
  countWords,
  validatePresentationContent,
  WORD_BUDGETS,
} from "../scripts/validate-content";
import { presentation } from "../src/content";
import { SOURCE_SEPARATOR, type PresentationSpec } from "../src/model";

const presentationRoot = fileURLToPath(new URL("..", import.meta.url));

const GUIDE_REPOSITORY = "Traigent/traigent-first-run";
const GUIDE_REVISION = "75d338c31c97643c6a6d28a6aeef582d7b938db8";

const CORE_SLIDE_IDS = [
  "ready-to-optimize",
  "what-the-guide-does",
  "the-words-your-project",
  "the-words-of-the-run",
  "one-customer-prompt",
  "four-asks",
  "shared-control",
  "free-first-paid-later",
  "your-starting-point",
  "when-material-is-weak",
  "special-cases",
  "readiness-at-a-glance",
  "readiness-bands",
  "caps-blockers-and-asks",
  "the-opening-score",
  "secrets-and-safety",
  "the-preview-before-paying",
  "what-leaves-your-machine",
  "what-you-get",
  "two-honest-outcomes",
  "how-to-start",
  "no-project-yet",
];

const APPENDIX_SLIDE_IDS = [
  "stage-inspect",
  "status-marks",
  "stage-readiness",
  "readiness-confidence",
  "readiness-scoring",
  "readiness-ceilings",
  "ceiling-rules",
  "stage-baseline",
  "baseline-grid",
  "stage-optimize",
  "what-the-search-may-change",
  "your-data-first",
  "selection-and-heldout",
  "stage-results",
  "what-you-keep",
  "requirements",
  "licensing",
  "repository-layout",
];

const CUSTOMER_PROMPT =
  "Help me run my first Traigent optimization.\nClone https://github.com/Traigent/traigent-first-run and follow GUIDE.md.";

// Phrases from the internal tooling that tests the guide. The deck is about
// the guide alone, so none of them may appear on any rendered surface.
const FOREIGN_TOPICS =
  /\b(?:fixture bank|fixture skills?|captain|spider|companion repo(?:sitory)?|worked case|verification layers?|evidence states?|coverage targets?|recorded run|run record|build\.py|text-to-sql|measurement cards?|preset bank|scenario (?:bank|contract|catalog)|phase [ab]|pre-?sales?)\b/i;

function copyPresentation(): PresentationSpec {
  return structuredClone(presentation);
}

function renderedStrings(value: unknown, collected: string[] = []): string[] {
  if (typeof value === "string") {
    collected.push(value);
  } else if (Array.isArray(value)) {
    for (const item of value) {
      renderedStrings(item, collected);
    }
  } else if (typeof value === "object" && value !== null) {
    for (const item of Object.values(value)) {
      renderedStrings(item, collected);
    }
  }
  return collected;
}

function slideById(spec: PresentationSpec, id: string) {
  const slide = spec.slides.find((candidate) => candidate.id === id);
  if (slide === undefined) {
    throw new Error(`no slide ${id}`);
  }
  return slide;
}

function expectValidationIssue(candidate: unknown, fragment: string): void {
  try {
    validatePresentationContent(candidate);
  } catch (error: unknown) {
    expect(error).toBeInstanceOf(ContentValidationError);
    expect((error as ContentValidationError).issues.join("\n")).toContain(
      fragment,
    );
    return;
  }
  throw new Error(`expected validation to fail with: ${fragment}`);
}

describe("presentation content validation", () => {
  it("accepts the canonical deck and pins the guide it describes", () => {
    const validated = validatePresentationContent(presentation);

    expect(validated.source.repository).toBe(GUIDE_REPOSITORY);
    expect(validated.source.revision).toBe(GUIDE_REVISION);
    expect(validated.source.files).toEqual(
      expect.arrayContaining([
        "README.md",
        "GUIDE.md",
        "skills/traigent-first-run/SKILL.md",
        "skills/traigent-first-run/scripts/readiness.py",
      ]),
    );

    expect(validated.slides.map((slide) => slide.id)).toEqual([
      ...CORE_SLIDE_IDS,
      ...APPENDIX_SLIDE_IDS,
    ]);
    expect(
      validated.slides
        .filter((slide) => slide.section === "core")
        .map((slide) => slide.id),
    ).toEqual(CORE_SLIDE_IDS);
    expect(
      validated.slides
        .filter((slide) => slide.section === "appendix")
        .map((slide) => slide.id),
    ).toEqual(APPENDIX_SLIDE_IDS);

    const declared = new Set(validated.source.files);
    for (const slide of validated.slides) {
      expect(slide.notes.length).toBeGreaterThan(0);
      expect(slide.sources.length).toBeGreaterThan(0);
      for (const source of slide.sources) {
        const [file, section] = source.split(SOURCE_SEPARATOR);
        expect(declared.has(file!)).toBe(true);
        expect(section?.trim().length ?? 0).toBeGreaterThan(0);
      }
    }
  });

  it("describes the guide alone, with no internal tooling vocabulary anywhere", () => {
    const text = renderedStrings(presentation).join("\n");
    const hit = FOREIGN_TOPICS.exec(text);
    expect(hit === null ? null : hit[0]).toBeNull();

    const readme = readFileSync(
      path.join(presentationRoot, "README.md"),
      "utf8",
    );
    const readmeHit = FOREIGN_TOPICS.exec(readme);
    expect(readmeHit === null ? null : readmeHit[0]).toBeNull();
    expect(readme).toContain("records no run");
  });

  it("keeps the customer prompt verbatim", () => {
    const text = renderedStrings(presentation).join("\n");
    expect(text).toContain(CUSTOMER_PROMPT);
  });

  it("keeps the guide's scoring facts on the scoring slides", () => {
    const glance = renderedStrings(
      slideById(presentation, "readiness-at-a-glance"),
    ).join("\n");
    expect(glance).toMatch(/dataset[^\n]*40/i);
    expect(glance).toMatch(/evaluation[^\n]*35/i);
    expect(glance).toMatch(/agent[^\n]*25/i);

    const ceilings = renderedStrings(
      slideById(presentation, "readiness-ceilings"),
    ).join("\n");
    for (const ceiling of ["25", "45", "65", "74"]) {
      expect(ceilings).toContain(ceiling);
    }
  });

  it("keeps every slide to one visual and every visible line inside its word budget", () => {
    const validated = validatePresentationContent(presentation);
    expect(validated.schemaVersion).toBe(4);

    for (const slide of validated.slides) {
      const blocks = [
        slide.bullets.length > 0,
        slide.tiles.length > 0,
        slide.columns !== undefined,
        slide.scale !== undefined,
        slide.matrix !== undefined,
        slide.steps.length > 0,
        slide.metrics.length > 0,
      ].filter(Boolean).length;
      // Bullets count as the block on statement, callout and handoff slides,
      // so no slide ever stacks two.
      expect(blocks).toBeLessThanOrEqual(1);
      expect(slide.bullets.length).toBeLessThanOrEqual(8);
      expect(countWords(slide.title)).toBeLessThanOrEqual(WORD_BUDGETS.title);
      expect(countWords(slide.body)).toBeLessThanOrEqual(WORD_BUDGETS.body);
      for (const bullet of slide.bullets) {
        expect(countWords(bullet)).toBeLessThanOrEqual(WORD_BUDGETS.bullet);
      }
    }
  });

  it("counts words as tokens that carry a letter or a digit", () => {
    expect(countWords("40 · 35 · 25")).toBe(3);
    expect(countWords("$5.00 default stop target")).toBe(4);
    expect(countWords("✅ real, ❗ thin")).toBe(2);
    expect(countWords("  spaced   out  ")).toBe(2);
  });

  it("rejects a bullet, a body and a callout that run past their budgets", () => {
    const longBullet = copyPresentation();
    slideById(longBullet, "stage-inspect").bullets[0] =
      "one two three four five six seven eight nine ten";
    expectValidationIssue(longBullet, "bullet 1 runs to 10 words");

    const longBody = copyPresentation();
    slideById(longBody, "stage-inspect").body = Array.from(
      { length: WORD_BUDGETS.body + 1 },
      (_, index) => `word${index}`,
    ).join(" ");
    expectValidationIssue(longBody, "body runs to");

    const longCallout = copyPresentation();
    slideById(longCallout, "the-opening-score").callout = Array.from(
      { length: WORD_BUDGETS.callout + 1 },
      (_, index) => `word${index}`,
    ).join(" ");
    expectValidationIssue(longCallout, "callout runs to");
  });

  it("rejects a callout slide without a callout, and a callout elsewhere", () => {
    const missing = copyPresentation();
    delete slideById(missing, "the-opening-score").callout;
    expectValidationIssue(missing, "callout slides require a callout");

    const stray = copyPresentation();
    slideById(stray, "stage-inspect").callout = "stray";
    expectValidationIssue(stray, "only callout slides may define a callout");
  });

  it("rejects tiles, columns and a scale outside their own kinds, and their kinds without them", () => {
    const strayTiles = copyPresentation();
    slideById(strayTiles, "stage-inspect").tiles = [
      { icon: "x", label: "a", detail: "b" },
    ];
    expectValidationIssue(strayTiles, "only tiles slides may define tiles");

    const emptyTiles = copyPresentation();
    slideById(emptyTiles, "four-asks").tiles = [];
    expectValidationIssue(emptyTiles, "tiles slides require at least one tile");

    const strayColumns = copyPresentation();
    slideById(strayColumns, "stage-inspect").columns = [
      { heading: "a", tone: "blue", items: ["b"] },
      { heading: "c", tone: "blue", items: ["d"] },
    ];
    expectValidationIssue(
      strayColumns,
      "only columns slides may define columns",
    );

    const emptyColumns = copyPresentation();
    delete slideById(emptyColumns, "licensing").columns;
    expectValidationIssue(emptyColumns, "columns slides require columns");

    const strayScale = copyPresentation();
    slideById(strayScale, "stage-inspect").scale = slideById(
      copyPresentation(),
      "readiness-bands",
    ).scale;
    expectValidationIssue(strayScale, "only scale slides may define a scale");

    const emptyScale = copyPresentation();
    delete slideById(emptyScale, "readiness-bands").scale;
    expectValidationIssue(emptyScale, "scale slides require a scale");
  });

  it("rejects bullets stacked on a visual kind", () => {
    const candidate = copyPresentation();
    slideById(candidate, "four-asks").bullets = ["a stray bullet"];
    expectValidationIssue(
      candidate,
      "tiles slides carry their visual instead of bullets",
    );

    const crowded = copyPresentation();
    slideById(crowded, "the-opening-score").bullets = [
      "one",
      "two",
      "three",
      "four",
      "five",
    ];
    expectValidationIssue(crowded, "callout slides carry at most 4 bullets");
  });

  it("rejects a scale whose bands leave a gap or stop short of 100", () => {
    const gapped = copyPresentation();
    const scale = slideById(gapped, "readiness-bands").scale!;
    scale.bands[1]!.from = 31;
    expectValidationIssue(gapped, "scale bands must be contiguous from 0");

    const short = copyPresentation();
    const shortScale = slideById(short, "readiness-bands").scale!;
    shortScale.bands[shortScale.bands.length - 1]!.to = 99;
    expectValidationIssue(short, "scale bands must end at 100");
  });

  it("rejects a duplicate slide id", () => {
    const candidate = copyPresentation();
    candidate.slides[1]!.id = candidate.slides[0]!.id;
    expectValidationIssue(candidate, "duplicate slide id");
  });

  it("rejects a source that names a file the deck does not declare", () => {
    const candidate = copyPresentation();
    candidate.slides[0]!.sources = [
      `docs/elsewhere.md${SOURCE_SEPARATOR}Intro`,
    ];
    expectValidationIssue(
      candidate,
      "source names a file the deck does not declare",
    );
  });

  it("rejects a source without a section", () => {
    const candidate = copyPresentation();
    candidate.slides[0]!.sources = ["README.md"];
    expectValidationIssue(candidate, "source must read");
  });

  it("rejects a handoff slide without a quote and a quote elsewhere", () => {
    const withoutQuote = copyPresentation();
    const handoff = slideById(withoutQuote, "one-customer-prompt");
    delete handoff.quote;
    expectValidationIssue(withoutQuote, "handoff slides require a quote");

    const strayQuote = copyPresentation();
    slideById(strayQuote, "ready-to-optimize").quote = "stray";
    expectValidationIssue(strayQuote, "only handoff slides may define a quote");
  });

  it("rejects matrix rows outside matrix slides and matrix slides without rows", () => {
    const stray = copyPresentation();
    slideById(stray, "ready-to-optimize").matrix = [
      { startingPoint: "a", safestNextStep: "b" },
    ];
    expectValidationIssue(stray, "only matrix slides may define matrix rows");

    const empty = copyPresentation();
    delete slideById(empty, "caps-blockers-and-asks").matrix;
    expectValidationIssue(empty, "matrix slides require matrix rows");
  });

  it("rejects an accent that is not in the title", () => {
    const candidate = copyPresentation();
    slideById(candidate, "ready-to-optimize").accent = "not in the title";
    expectValidationIssue(
      candidate,
      "accent is not present in the slide title",
    );
  });

  it("rejects a run result reported anywhere it renders", () => {
    const cases: Array<[string, (candidate: PresentationSpec) => void]> = [
      [
        "a slide body",
        (candidate) => {
          candidate.slides[0]!.body = "Cost fell 30% in the latest run.";
        },
      ],
      [
        "a speaker note",
        (candidate) => {
          candidate.slides[0]!.notes.push("We measured a 41% improvement.");
        },
      ],
      [
        "a source line",
        (candidate) => {
          candidate.slides[0]!.sources.push(
            `README.md${SOURCE_SEPARATOR}verified result section`,
          );
        },
      ],
      [
        "the deck subtitle",
        (candidate) => {
          candidate.subtitle = "Quality improved by 20% on our first run.";
        },
      ],
    ];
    for (const [, mutate] of cases) {
      const candidate = copyPresentation();
      mutate(candidate);
      expectValidationIssue(candidate, "reports a run result");
    }
  });

  it("accepts a sentence that denies a run result, but not a claim after the comma", () => {
    const denied = copyPresentation();
    denied.slides[0]!.notes.push(
      "The deck has not measured any improvement and claims none.",
    );
    expect(() => validatePresentationContent(denied)).not.toThrow();

    const smuggled = copyPresentation();
    smuggled.slides[0]!.notes.push(
      "No customer data leaves the laptop, and we measured a 41% quality improvement.",
    );
    expectValidationIssue(smuggled, "reports a run result");
  });

  it("rejects internal tooling vocabulary wherever it renders", () => {
    const candidate = copyPresentation();
    candidate.slides[0]!.notes.push(
      "This case comes from the fixture bank the captain runs.",
    );
    expectValidationIssue(
      candidate,
      "names internal tooling the deck does not describe",
    );

    const deckLevel = copyPresentation();
    deckLevel.subtitle = "A worked case from the fixture bank";
    expectValidationIssue(deckLevel, "deck: names internal tooling");
  });

  it("rejects a green metric tone and an unknown executor at the schema", () => {
    const green = copyPresentation() as unknown as {
      slides: Array<{ metrics: Array<{ tone: string }> }>;
    };
    const metricSlide = green.slides.find((slide) => slide.metrics.length > 0)!;
    metricSlide.metrics[0]!.tone = "green";
    expectValidationIssue(green, "tone");

    const executor = copyPresentation() as unknown as {
      slides: Array<{ steps: Array<{ executor: string }> }>;
    };
    const journey = executor.slides.find((slide) => slide.steps.length > 0)!;
    journey.steps[0]!.executor = "Coding agent";
    expectValidationIssue(executor, "executor");
  });

  it("rejects a slide without speaker notes", () => {
    const candidate = copyPresentation();
    candidate.slides[0]!.notes = [];
    expectValidationIssue(candidate, "notes");
  });
});
