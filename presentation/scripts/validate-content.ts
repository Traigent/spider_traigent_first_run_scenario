import { ZodError } from "zod";

import { presentation } from "../src/content";
import {
  parsePresentation,
  sourceCitation,
  type PresentationSpec,
  type SlideSpec,
} from "../src/model";
import { isMainModule } from "./runtime";

// The deck describes the guide and records no run of its own, so there is no
// measured result anywhere in it to report. A sentence that reports one is
// wrong wherever it renders.
const POSITIVE_RUN_CLAIMS = [
  /\bwe (?:achieved|measured|observed|reduced|improved|increased)\b/i,
  /\b(?:achieved|measured|observed) (?:an? )?(?:live |optimization )?(?:result|improvement|gain|reduction)\b/i,
  /\b(?:quality|latency|cost) (?:improved|decreased|increased|reduced) by\b/i,
  /\b(?:quality|latency|cost) (?:fell|rose|dropped|improved|decreased|increased|reduced)\b/i,
  /\bverified (?:live )?(?:run|result|optimization|improvement)\b/i,
] as const;

// A claim phrase inside a sentence that denies it is not a claim. Speaker
// notes are where the deck says what it is not asserting, so refusing those
// sentences would push authors away from the plain wording the deck exists
// to use.
const CLAIM_NEGATORS =
  /\b(?:no|not|never|without|cannot|can't|don't|doesn't|didn't|isn't|aren't|wasn't|weren't|none|nothing|neither|nor|un(?:proven|verified)|absent)\b/i;

// Clause boundaries count, not only sentence boundaries. A negator only
// disclaims what it governs, and it stops governing at the comma: "No customer
// data leaves the laptop, and we measured a 41% quality improvement" is a real
// claim wearing a denial's opening.
const CLAUSE_BOUNDARY = /[.!?;,:\n]/;

export class ContentValidationError extends Error {
  readonly issues: readonly string[];

  constructor(issues: readonly string[], options?: ErrorOptions) {
    super(
      `Presentation content validation failed:\n- ${issues.join("\n- ")}`,
      options,
    );
    this.name = "ContentValidationError";
    this.issues = issues;
  }
}

function uniqueIssues(values: readonly string[], label: string): string[] {
  const normalized = new Set<string>();
  const issues: string[] = [];

  for (const value of values) {
    const key = value.trim().toLocaleLowerCase("en");
    if (normalized.has(key)) {
      issues.push(`${label} contains a duplicate value: ${value}`);
    }
    normalized.add(key);
  }

  return issues;
}

/**
 * Collect every string the content model carries, at any depth.
 *
 * The honesty rule has to hold on every surface a reader sees, and the deck
 * renders more than a slide's body: the footer prints `sources`, the
 * speaker-note pane and the PowerPoint notes page print `notes`, and the deck
 * subtitle becomes the PowerPoint subject. The scan walks the parsed model, so
 * a field added to the schema is covered the day it is added.
 */
function collectRenderedStrings(value: unknown, collected: string[]): void {
  if (typeof value === "string") {
    collected.push(value);
    return;
  }
  if (Array.isArray(value)) {
    for (const item of value) {
      collectRenderedStrings(item, collected);
    }
    return;
  }
  if (typeof value === "object" && value !== null) {
    for (const item of Object.values(value)) {
      collectRenderedStrings(item, collected);
    }
  }
}

function visibleClaimText(...values: readonly unknown[]): string {
  const collected: string[] = [];
  for (const value of values) {
    collectRenderedStrings(value, collected);
  }
  return collected.join("\n");
}

/** The text preceding a match, back to the start of its own clause. */
function clauseLeadIn(claimText: string, matchStart: number): string {
  const window = claimText.slice(Math.max(0, matchStart - 160), matchStart);
  let boundary = -1;
  for (let index = window.length - 1; index >= 0; index -= 1) {
    if (CLAUSE_BOUNDARY.test(window[index]!)) {
      boundary = index;
      break;
    }
  }
  return window.slice(boundary + 1);
}

function hasPositiveRunClaim(claimText: string): boolean {
  for (const pattern of POSITIVE_RUN_CLAIMS) {
    const scan = new RegExp(pattern.source, `${pattern.flags}g`);
    for (
      let match = scan.exec(claimText);
      match !== null;
      match = scan.exec(claimText)
    ) {
      if (!CLAIM_NEGATORS.test(clauseLeadIn(claimText, match.index))) {
        return true;
      }
    }
  }
  return false;
}

const RUN_CLAIM_ISSUE =
  "reports a run result, and the deck describes the guide without recording any run";

// The deck describes the public guide and nothing else. These phrases belong
// to the internal tooling that tests the guide, and a slide that uses one is
// talking about that tooling, which the customer never sees.
const FOREIGN_TOPICS =
  /\b(?:fixture bank|fixture skills?|captain|spider|companion repo(?:sitory)?|worked case|verification layers?|evidence states?|coverage targets?|recorded run|run record|build\.py|text-to-sql|measurement cards?|preset bank|scenario (?:bank|contract|catalog)|pre-?sales?)\b/i;

function foreignTopicIssues(claimText: string): string[] {
  const match = FOREIGN_TOPICS.exec(claimText);
  return match === null
    ? []
    : [`names internal tooling the deck does not describe: "${match[0]}"`];
}

// The deck is read aloud in front of a customer, so every visible line is a
// phrase, not a paragraph. A word is a whitespace-separated token that carries
// a letter or a digit, so "40 · 35 · 25" is three words and "$5.00" is one.
export const WORD_BUDGETS = {
  title: 14,
  body: 32,
  bullet: 9,
  callout: 14,
  tileLabel: 4,
  tileDetail: 12,
  columnHeading: 5,
  columnItem: 9,
  stepLabel: 4,
  stepDetail: 14,
  metricDetail: 12,
  matrixStartingPoint: 10,
  matrixNextStep: 18,
  scaleBandLabel: 3,
  scaleMarkerLabel: 6,
} as const;

// Text-bearing blocks a slide may carry beside its heading. Each visual kind
// carries exactly its own block, so a slide never stacks two visuals.
const VISUAL_KINDS = new Set<SlideSpec["kind"]>([
  "journey",
  "evidence",
  "matrix",
  "tiles",
  "columns",
  "scale",
]);

const BULLET_LIMITS: Partial<Record<SlideSpec["kind"], number>> = {
  hero: 0,
  callout: 4,
  handoff: 4,
};

export function countWords(text: string): number {
  return text.split(/\s+/).filter((token) => /[\p{L}\p{N}]/u.test(token))
    .length;
}

function wordBudgetIssue(
  label: string,
  text: string,
  budget: number,
): string[] {
  const words = countWords(text);
  return words > budget
    ? [`${label} runs to ${words} words; the budget is ${budget}: "${text}"`]
    : [];
}

function validateWordBudgets(slide: SlideSpec): string[] {
  const issues = [
    ...wordBudgetIssue("title", slide.title, WORD_BUDGETS.title),
    ...wordBudgetIssue("body", slide.body, WORD_BUDGETS.body),
    ...slide.bullets.flatMap((bullet, index) =>
      wordBudgetIssue(`bullet ${index + 1}`, bullet, WORD_BUDGETS.bullet),
    ),
    ...slide.tiles.flatMap((tile, index) => [
      ...wordBudgetIssue(
        `tile ${index + 1} label`,
        tile.label,
        WORD_BUDGETS.tileLabel,
      ),
      ...wordBudgetIssue(
        `tile ${index + 1} detail`,
        tile.detail,
        WORD_BUDGETS.tileDetail,
      ),
    ]),
    ...(slide.columns ?? []).flatMap((column, index) => [
      ...wordBudgetIssue(
        `column ${index + 1} heading`,
        column.heading,
        WORD_BUDGETS.columnHeading,
      ),
      ...column.items.flatMap((item, itemIndex) =>
        wordBudgetIssue(
          `column ${index + 1} item ${itemIndex + 1}`,
          item,
          WORD_BUDGETS.columnItem,
        ),
      ),
    ]),
    ...slide.steps.flatMap((step, index) => [
      ...wordBudgetIssue(
        `step ${index + 1} label`,
        step.label,
        WORD_BUDGETS.stepLabel,
      ),
      ...wordBudgetIssue(
        `step ${index + 1} detail`,
        step.detail,
        WORD_BUDGETS.stepDetail,
      ),
    ]),
    ...slide.metrics.flatMap((metric, index) =>
      wordBudgetIssue(
        `metric ${index + 1} detail`,
        metric.detail,
        WORD_BUDGETS.metricDetail,
      ),
    ),
    ...(slide.matrix ?? []).flatMap((row, index) => [
      ...wordBudgetIssue(
        `matrix row ${index + 1} starting point`,
        row.startingPoint,
        WORD_BUDGETS.matrixStartingPoint,
      ),
      ...wordBudgetIssue(
        `matrix row ${index + 1} next step`,
        row.safestNextStep,
        WORD_BUDGETS.matrixNextStep,
      ),
    ]),
    ...(slide.scale?.bands ?? []).flatMap((band, index) =>
      wordBudgetIssue(
        `scale band ${index + 1} label`,
        band.label,
        WORD_BUDGETS.scaleBandLabel,
      ),
    ),
    ...(slide.scale?.markers ?? []).flatMap((marker, index) =>
      wordBudgetIssue(
        `scale marker ${index + 1} label`,
        marker.label,
        WORD_BUDGETS.scaleMarkerLabel,
      ),
    ),
  ];
  if (slide.callout !== undefined) {
    issues.push(
      ...wordBudgetIssue("callout", slide.callout, WORD_BUDGETS.callout),
    );
  }
  return issues;
}

function validateTemplateContract(slide: SlideSpec): string[] {
  const issues: string[] = [];

  if (slide.kind === "handoff" && slide.quote === undefined) {
    issues.push("handoff slides require a quote");
  }
  if (slide.kind !== "handoff" && slide.quote !== undefined) {
    issues.push("only handoff slides may define a quote");
  }
  if (slide.kind === "callout" && slide.callout === undefined) {
    issues.push("callout slides require a callout");
  }
  if (slide.kind !== "callout" && slide.callout !== undefined) {
    issues.push("only callout slides may define a callout");
  }
  if (slide.kind === "journey" && slide.steps.length === 0) {
    issues.push("journey slides require at least one step");
  }
  if (slide.kind !== "journey" && slide.steps.length > 0) {
    issues.push("only journey slides may define steps");
  }
  if (slide.kind === "evidence" && slide.metrics.length === 0) {
    issues.push("evidence slides require at least one metric");
  }
  if (slide.kind !== "evidence" && slide.metrics.length > 0) {
    issues.push("only evidence slides may define metrics");
  }
  if (slide.kind === "matrix" && slide.matrix === undefined) {
    issues.push("matrix slides require matrix rows");
  }
  if (slide.kind !== "matrix" && slide.matrix !== undefined) {
    issues.push("only matrix slides may define matrix rows");
  }
  if (slide.kind === "tiles" && slide.tiles.length === 0) {
    issues.push("tiles slides require at least one tile");
  }
  if (slide.kind !== "tiles" && slide.tiles.length > 0) {
    issues.push("only tiles slides may define tiles");
  }
  if (slide.kind === "columns" && slide.columns === undefined) {
    issues.push("columns slides require columns");
  }
  if (slide.kind !== "columns" && slide.columns !== undefined) {
    issues.push("only columns slides may define columns");
  }
  if (slide.kind === "scale" && slide.scale === undefined) {
    issues.push("scale slides require a scale");
  }
  if (slide.kind !== "scale" && slide.scale !== undefined) {
    issues.push("only scale slides may define a scale");
  }
  if (VISUAL_KINDS.has(slide.kind) && slide.bullets.length > 0) {
    issues.push(`${slide.kind} slides carry their visual instead of bullets`);
  }
  const bulletLimit = BULLET_LIMITS[slide.kind];
  if (bulletLimit !== undefined && slide.bullets.length > bulletLimit) {
    issues.push(
      `${slide.kind} slides carry at most ${bulletLimit} bullets, not ${slide.bullets.length}`,
    );
  }
  if (slide.accent !== undefined) {
    const title = slide.title.toLocaleLowerCase("en");
    const accent = slide.accent.toLocaleLowerCase("en");
    if (!title.includes(accent)) {
      issues.push(`accent is not present in the slide title: ${slide.accent}`);
    }
  }

  return issues;
}

function validateSlide(slide: SlideSpec): string[] {
  const issues = [
    ...validateTemplateContract(slide),
    ...validateWordBudgets(slide),
    ...(hasPositiveRunClaim(visibleClaimText(slide)) ? [RUN_CLAIM_ISSUE] : []),
    ...foreignTopicIssues(visibleClaimText(slide)),
    ...uniqueIssues(slide.bullets, "bullets"),
    ...uniqueIssues(slide.sources, "sources"),
    ...uniqueIssues(slide.notes, "notes"),
    ...uniqueIssues(
      slide.metrics.map((metric) => metric.label),
      "metric labels",
    ),
    ...uniqueIssues(
      slide.steps.map((step) => step.label),
      "step labels",
    ),
    ...uniqueIssues(
      slide.tiles.map((tile) => tile.label),
      "tile labels",
    ),
    ...uniqueIssues(
      (slide.columns ?? []).map((column) => column.heading),
      "column headings",
    ),
  ];

  return issues.map((issue) => `slide ${slide.id}: ${issue}`);
}

function schemaIssues(error: ZodError): string[] {
  return error.issues.map((issue) => {
    const path =
      issue.path.length === 0 ? "presentation" : issue.path.join(".");
    return `${path}: ${issue.message}`;
  });
}

function validateDeckContract(spec: PresentationSpec): string[] {
  // Deck-level text renders on every slide and in the PowerPoint document
  // properties.
  const deckText = visibleClaimText(spec.title, spec.subtitle);
  return [
    ...(hasPositiveRunClaim(deckText) ? [`deck: ${RUN_CLAIM_ISSUE}`] : []),
    ...foreignTopicIssues(deckText).map((issue) => `deck: ${issue}`),
  ];
}

export function validatePresentationContent(value: unknown): PresentationSpec {
  let parsed: PresentationSpec;
  try {
    parsed = parsePresentation(value);
  } catch (error: unknown) {
    if (error instanceof ZodError) {
      throw new ContentValidationError(schemaIssues(error), { cause: error });
    }
    throw error;
  }

  const issues = [
    ...validateDeckContract(parsed),
    ...parsed.slides.flatMap((slide) => validateSlide(slide)),
  ];
  if (issues.length > 0) {
    throw new ContentValidationError(issues);
  }

  return parsed;
}

export function validateCurrentPresentation(): PresentationSpec {
  return validatePresentationContent(presentation);
}

if (isMainModule(import.meta.url)) {
  const validated = validateCurrentPresentation();
  process.stdout.write(
    `Validated ${validated.slides.length} presentation slides describing ${sourceCitation(validated)}.\n`,
  );
}
