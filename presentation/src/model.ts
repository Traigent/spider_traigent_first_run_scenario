import { z } from "zod";

// The deck describes the public Traigent Guided First Run guide at one exact
// revision. Every slide names the guide files it is drawn from, and the deck
// records no run of its own: there is no measured result in it to claim.

const GIT_REVISION = /^[0-9a-f]{40}$/;
const REPOSITORY = /^[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+$/;

// A source reads "FILE · section": the file must be one the deck declares it
// was drawn from, and the section names where in that file the fact lives.
export const SOURCE_SEPARATOR = " · ";

const metricSchema = z
  .object({
    label: z.string().min(1),
    value: z.string().min(1),
    detail: z.string().min(1),
    // No green: the deck carries no measured outcome to colour as a success.
    tone: z.enum(["blue", "amber", "violet"]).default("blue"),
  })
  .strict();

const stepSchema = z
  .object({
    label: z.string().min(1),
    detail: z.string().min(1),
    executor: z.enum(["Coding assistant", "Customer", "Traigent service"]),
    humanGate: z.string().min(1).optional(),
  })
  .strict();

const matrixRowSchema = z
  .object({
    startingPoint: z.string().min(1),
    safestNextStep: z.string().min(1),
  })
  .strict();

export const slideSchema = z
  .object({
    id: z.string().regex(/^[a-z0-9]+(?:-[a-z0-9]+)*$/),
    kind: z.enum([
      "hero",
      "statement",
      "journey",
      "evidence",
      "handoff",
      "matrix",
    ]),
    section: z.enum(["core", "appendix"]).optional(),
    eyebrow: z.string().min(1),
    title: z.string().min(1),
    body: z.string().min(1),
    accent: z.string().min(1).optional(),
    quote: z.string().min(1).optional(),
    bullets: z.array(z.string().min(1)).max(6).default([]),
    metrics: z.array(metricSchema).max(4).default([]),
    steps: z.array(stepSchema).max(6).default([]),
    matrix: z.array(matrixRowSchema).min(1).max(5).optional(),
    sources: z.array(z.string().min(1)).min(1).max(4),
    notes: z.array(z.string().min(1)).min(1),
  })
  .strict();

export const presentationSchema = z
  .object({
    schemaVersion: z.literal(3),
    title: z.string().min(1),
    subtitle: z.string().min(1),
    source: z
      .object({
        repository: z.string().regex(REPOSITORY),
        revision: z.string().regex(GIT_REVISION),
        // Repository-relative paths of every guide file the deck draws on.
        files: z.array(z.string().min(1)).min(1),
      })
      .strict(),
    slides: z.array(slideSchema).min(1),
  })
  .strict()
  .superRefine((value, context) => {
    const ids = new Set<string>();
    const titles = new Set<string>();
    const files = new Set(value.source.files);

    for (const [index, slide] of value.slides.entries()) {
      if (ids.has(slide.id)) {
        context.addIssue({
          code: "custom",
          message: `duplicate slide id ${slide.id}`,
          path: ["slides", index, "id"],
        });
      }
      ids.add(slide.id);

      const normalizedTitle = slide.title.trim().toLocaleLowerCase("en");
      if (titles.has(normalizedTitle)) {
        context.addIssue({
          code: "custom",
          message: `duplicate slide title ${slide.title}`,
          path: ["slides", index, "title"],
        });
      }
      titles.add(normalizedTitle);

      for (const [sourceIndex, source] of slide.sources.entries()) {
        const separator = source.indexOf(SOURCE_SEPARATOR);
        const file = separator < 0 ? source : source.slice(0, separator);
        const section =
          separator < 0
            ? ""
            : source.slice(separator + SOURCE_SEPARATOR.length);
        if (separator < 0 || section.trim().length === 0) {
          context.addIssue({
            code: "custom",
            message: `source must read "FILE${SOURCE_SEPARATOR}section": ${source}`,
            path: ["slides", index, "sources", sourceIndex],
          });
        } else if (!files.has(file)) {
          context.addIssue({
            code: "custom",
            message: `source names a file the deck does not declare: ${file}`,
            path: ["slides", index, "sources", sourceIndex],
          });
        }
      }
    }
  });

export type Metric = z.infer<typeof metricSchema>;
export type JourneyStep = z.infer<typeof stepSchema>;
export type MatrixRow = z.infer<typeof matrixRowSchema>;
export type SlideSpec = z.infer<typeof slideSchema>;
export type PresentationSpec = z.infer<typeof presentationSchema>;

export function parsePresentation(value: unknown): PresentationSpec {
  return presentationSchema.parse(value);
}

export function displayEyebrow(slide: SlideSpec): string {
  return slide.section === "appendix" &&
    !slide.eyebrow.toLocaleUpperCase("en").startsWith("APPENDIX")
    ? `APPENDIX · ${slide.eyebrow}`
    : slide.eyebrow;
}

/** `Traigent/traigent-first-run@75d338c3`: the pinned guide the deck describes. */
export function sourceCitation(spec: PresentationSpec): string {
  return `${spec.source.repository}@${spec.source.revision.slice(0, 8)}`;
}

/** The slide footer: where in the guide each statement on the slide comes from. */
export function sourceFooter(spec: PresentationSpec, slide: SlideSpec): string {
  return `Source: ${slide.sources.join(" | ")} (${sourceCitation(spec)})`;
}
