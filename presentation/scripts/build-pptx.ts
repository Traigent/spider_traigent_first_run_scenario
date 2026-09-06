import { execFileSync } from "node:child_process";
import { mkdir, writeFile } from "node:fs/promises";
import path from "node:path";

import JSZip from "jszip";
import PptxGenJS from "pptxgenjs";

import { brandBlue, brandName } from "../src/brand";
import { presentation } from "../src/content";
import {
  displayEyebrow,
  sourceFooter,
  type Column,
  type JourneyStep,
  type MatrixRow,
  type Metric,
  type PresentationSpec,
  type Scale,
  type SlideSpec,
  type Tile,
} from "../src/model";
import { theme, toneColor } from "../src/theme";
import { distRoot, isMainModule, repositoryRoot } from "./runtime";
import { validatePresentationContent } from "./validate-content";

export const pptxFileName = "traigent-first-run.pptx";
export const defaultPptxPath = path.join(distRoot, pptxFileName);

const SLIDE_WIDTH = 13.333;
const SLIDE_HEIGHT = 7.5;
const CONTENT_X = 0.82;
const CONTENT_WIDTH = SLIDE_WIDTH - CONTENT_X * 2;
const CONTENT_TOP = 0.62;
const BODY_TOP = 2.38;
const DETAIL_TOP = 3.3;
const FOOTER_TOP = 6.94;
// The content block lives between the heading and the footer.
const CONTENT_BOTTOM = 6.9;
const CONTENT_HEIGHT = CONTENT_BOTTOM - DETAIL_TOP;
const MASTER_NAME = "TRAIGENT_ACCESSIBLE";
const TITLE_PLACEHOLDER_NAME = "slide-title";
const EARLIEST_ZIP_EPOCH_SECONDS = 315_532_800;

export class PptxBuildError extends Error {
  constructor(message: string, options?: ErrorOptions) {
    super(message, options);
    this.name = "PptxBuildError";
  }
}

function addBackground(pptx: PptxGenJS, slide: PptxGenJS.Slide): void {
  slide.background = { color: theme.colors.canvas };
  slide.addShape(pptx.ShapeType.rect, {
    x: 0,
    y: 0,
    w: SLIDE_WIDTH,
    h: SLIDE_HEIGHT,
    line: { color: theme.colors.canvas, transparency: 100 },
    fill: { color: theme.colors.surface, transparency: 2 },
  });
  slide.addShape(pptx.ShapeType.ellipse, {
    x: 9.15,
    y: -2.8,
    w: 6.2,
    h: 6.2,
    line: { color: theme.colors.blue, transparency: 100 },
    fill: { color: theme.colors.blue, transparency: 82 },
  });
  slide.addShape(pptx.ShapeType.line, {
    x: CONTENT_X,
    y: 0.42,
    w: CONTENT_WIDTH,
    h: 0,
    line: { color: theme.colors.border, transparency: 25, width: 0.8 },
  });
}

// The traigent.ai mark, re-drawn from native vector shapes because this build
// intentionally ships no raster media. Geometry is measured from the 155x125
// header icon and expressed in icon pixels, scaled uniformly to the placed
// height.
const BRAND_MARK = {
  sourceWidth: 155,
  sourceHeight: 125,
  bars: [
    { x: 20, y: 14, w: 90, h: 24 },
    { x: 12, y: 54, w: 95, h: 24 },
    { x: 28, y: 94, w: 88, h: 24 },
  ],
  chevronArms: [
    { cx: 116, cy: 37, length: 75, thickness: 24, rotate: 42 },
    { cx: 116, cy: 88, length: 75, thickness: 24, rotate: -42 },
  ],
} as const;

function addBrand(pptx: PptxGenJS, slide: PptxGenJS.Slide): void {
  const markHeight = 0.26;
  const markTop = 0.09;
  const scale = markHeight / BRAND_MARK.sourceHeight;

  for (const bar of BRAND_MARK.bars) {
    slide.addShape(pptx.ShapeType.roundRect, {
      x: CONTENT_X + bar.x * scale,
      y: markTop + bar.y * scale,
      w: bar.w * scale,
      h: bar.h * scale,
      rectRadius: (bar.h * scale) / 2,
      line: { color: brandBlue, transparency: 100 },
      fill: { color: brandBlue },
    });
  }
  for (const arm of BRAND_MARK.chevronArms) {
    slide.addShape(pptx.ShapeType.roundRect, {
      x: CONTENT_X + (arm.cx - arm.length / 2) * scale,
      y: markTop + (arm.cy - arm.thickness / 2) * scale,
      w: arm.length * scale,
      h: arm.thickness * scale,
      rectRadius: (arm.thickness * scale) / 2,
      rotate: arm.rotate,
      line: { color: brandBlue, transparency: 100 },
      fill: { color: brandBlue },
    });
  }
  slide.addText(brandName, {
    x: CONTENT_X + BRAND_MARK.sourceWidth * scale + 0.12,
    y: markTop - 0.02,
    w: 2.2,
    h: markHeight + 0.04,
    margin: 0,
    color: theme.colors.text,
    fontFace: theme.fonts.sans,
    fontSize: 11,
    bold: true,
    charSpacing: 0.2,
    valign: "middle",
    breakLine: false,
  });
}

function addHeading(slide: PptxGenJS.Slide, slideSpec: SlideSpec): void {
  const titleFontSize = slideSpec.kind === "hero" ? 34 : 28;
  const eyebrow = displayEyebrow(slideSpec);

  slide.addText(eyebrow, {
    x: CONTENT_X,
    y: CONTENT_TOP,
    w: CONTENT_WIDTH,
    h: 0.3,
    margin: 0,
    color: theme.colors.blueBright,
    fontFace: theme.fonts.sans,
    fontSize: 10,
    bold: true,
    charSpacing: 2.1,
    breakLine: false,
  });
  slide.addText(slideSpec.title, {
    placeholder: TITLE_PLACEHOLDER_NAME,
    x: CONTENT_X,
    y: 1.02,
    w: 11.15,
    h: 1.18,
    margin: 0,
    color: theme.colors.text,
    fontFace: theme.fonts.sans,
    fontSize: titleFontSize,
    bold: true,
    align: "left",
    breakLine: false,
    valign: "middle",
  });
  slide.addText(slideSpec.body, {
    x: CONTENT_X,
    y: BODY_TOP,
    w: 11.15,
    h: 0.7,
    margin: 0,
    color: theme.colors.textSoft,
    fontFace: theme.fonts.sans,
    fontSize: 14.5,
    breakLine: false,
    valign: "top",
  });
}

interface HighlightCard {
  y: number;
  h: number;
}

// The raised, blue-edged card that carries the one thing a slide asks the
// audience to take away: the paste-ready prompt on a handoff slide, or the
// sentence on a callout slide.
function addHighlightCard(
  pptx: PptxGenJS,
  slide: PptxGenJS.Slide,
  card: HighlightCard,
): void {
  slide.addShape(pptx.ShapeType.roundRect, {
    x: CONTENT_X,
    y: card.y,
    w: CONTENT_WIDTH,
    h: card.h,
    rectRadius: 0.08,
    line: { color: theme.colors.blueBright, transparency: 50, width: 1.2 },
    fill: { color: theme.colors.surfaceRaised, transparency: 4 },
  });
}

const QUOTE_CARD_HEIGHT = 1.7;

function addQuote(
  pptx: PptxGenJS,
  slide: PptxGenJS.Slide,
  quote: string,
): void {
  addHighlightCard(pptx, slide, { y: DETAIL_TOP, h: QUOTE_CARD_HEIGHT });
  slide.addText("PASTE INTO YOUR CODING ASSISTANT", {
    x: CONTENT_X + 0.28,
    y: DETAIL_TOP + 0.2,
    w: CONTENT_WIDTH - 0.56,
    h: 0.22,
    margin: 0,
    color: theme.colors.blueBright,
    fontFace: theme.fonts.sans,
    fontSize: 7.5,
    bold: true,
    charSpacing: 1.4,
  });
  slide.addText(quote, {
    x: CONTENT_X + 0.28,
    y: DETAIL_TOP + 0.5,
    w: CONTENT_WIDTH - 0.56,
    h: QUOTE_CARD_HEIGHT - 0.7,
    margin: 0,
    color: theme.colors.text,
    fontFace: theme.fonts.mono,
    fontSize: 11.5,
    breakLine: false,
    valign: "middle",
  });
}

interface BulletRowLayout {
  top: number;
  columns: 1 | 2;
  rowHeight: number;
  rowGap: number;
  fontSize: number;
}

// Short rows, each a bordered card with a blue dash marker: the shared bullet
// style of statement, callout and handoff slides.
function addBulletRows(
  pptx: PptxGenJS,
  slide: PptxGenJS.Slide,
  bullets: readonly string[],
  layout: BulletRowLayout,
): void {
  const columnGap = 0.3;
  const cardWidth =
    layout.columns === 1 ? CONTENT_WIDTH : (CONTENT_WIDTH - columnGap) / 2;

  bullets.forEach((bullet, index) => {
    const column = index % layout.columns;
    const row = Math.floor(index / layout.columns);
    const x = CONTENT_X + column * (cardWidth + columnGap);
    const y = layout.top + row * (layout.rowHeight + layout.rowGap);

    slide.addShape(pptx.ShapeType.roundRect, {
      x,
      y,
      w: cardWidth,
      h: layout.rowHeight,
      rectRadius: 0.04,
      line: { color: theme.colors.border, width: 0.8 },
      fill: { color: theme.colors.surfaceRaised, transparency: 8 },
    });
    slide.addShape(pptx.ShapeType.line, {
      x: x + 0.22,
      y: y + layout.rowHeight / 2,
      w: 0.24,
      h: 0,
      line: { color: theme.colors.blueBright, width: 2.2 },
    });
    slide.addText(bullet, {
      x: x + 0.58,
      y: y + 0.05,
      w: cardWidth - 0.78,
      h: layout.rowHeight - 0.1,
      margin: 0,
      color: theme.colors.textSoft,
      fontFace: theme.fonts.sans,
      fontSize: layout.fontSize,
      valign: "middle",
    });
  });
}

// Statement: up to eight bullets in two columns, so four rows share the box.
function addBullets(
  pptx: PptxGenJS,
  slide: PptxGenJS.Slide,
  bullets: readonly string[],
): void {
  const columns = bullets.length === 1 ? 1 : 2;
  const rows = Math.ceil(bullets.length / columns);
  const rowGap = 0.16;
  const rowHeight = Math.min(
    0.78,
    (CONTENT_HEIGHT - 0.12 - rowGap * (rows - 1)) / rows,
  );
  addBulletRows(pptx, slide, bullets, {
    top: DETAIL_TOP,
    columns,
    rowHeight,
    rowGap,
    fontSize: 12.5,
  });
}

const CALLOUT_CARD_HEIGHT = 1.2;

function addCallout(
  pptx: PptxGenJS,
  slide: PptxGenJS.Slide,
  slideSpec: SlideSpec,
): void {
  if (slideSpec.callout === undefined) {
    throw new PptxBuildError(
      `Slide ${slideSpec.id} is a callout slide without a callout`,
    );
  }
  addHighlightCard(pptx, slide, { y: DETAIL_TOP, h: CALLOUT_CARD_HEIGHT });
  slide.addText(slideSpec.callout, {
    x: CONTENT_X + 0.32,
    y: DETAIL_TOP + 0.12,
    w: CONTENT_WIDTH - 0.64,
    h: CALLOUT_CARD_HEIGHT - 0.24,
    margin: 0,
    color: theme.colors.text,
    fontFace: theme.fonts.sans,
    fontSize: 20,
    bold: true,
    breakLine: false,
    valign: "middle",
  });
  if (slideSpec.bullets.length > 0) {
    addBulletRows(pptx, slide, slideSpec.bullets, {
      top: DETAIL_TOP + CALLOUT_CARD_HEIGHT + 0.22,
      columns: slideSpec.bullets.length === 1 ? 1 : 2,
      rowHeight: 0.72,
      rowGap: 0.14,
      fontSize: 12.5,
    });
  }
}

function addHandoff(
  pptx: PptxGenJS,
  slide: PptxGenJS.Slide,
  slideSpec: SlideSpec,
): void {
  if (slideSpec.quote === undefined) {
    throw new PptxBuildError(
      `Slide ${slideSpec.id} is a handoff slide without a quote`,
    );
  }
  addQuote(pptx, slide, slideSpec.quote);
  if (slideSpec.bullets.length > 0) {
    addBulletRows(pptx, slide, slideSpec.bullets, {
      top: DETAIL_TOP + QUOTE_CARD_HEIGHT + 0.16,
      columns: 1,
      rowHeight: 0.36,
      rowGap: 0.07,
      fontSize: 11,
    });
  }
}

function addMetrics(
  pptx: PptxGenJS,
  slide: PptxGenJS.Slide,
  metrics: readonly Metric[],
): void {
  const gap = 0.22;
  const count = metrics.length;
  const cardWidth = (CONTENT_WIDTH - gap * (count - 1)) / count;
  const cardHeight = 2.0;

  metrics.forEach((metric, index) => {
    const x = CONTENT_X + index * (cardWidth + gap);
    const color = toneColor(metric.tone);
    slide.addShape(pptx.ShapeType.roundRect, {
      x,
      y: DETAIL_TOP,
      w: cardWidth,
      h: cardHeight,
      rectRadius: 0.05,
      line: { color: theme.colors.border, width: 0.8 },
      fill: { color: theme.colors.surfaceRaised, transparency: 4 },
    });
    slide.addShape(pptx.ShapeType.line, {
      x: x + 0.03,
      y: DETAIL_TOP + 0.03,
      w: cardWidth - 0.06,
      h: 0,
      line: { color, width: 2.4 },
    });
    slide.addText(metric.label.toLocaleUpperCase("en"), {
      x: x + 0.2,
      y: DETAIL_TOP + 0.25,
      w: cardWidth - 0.4,
      h: 0.25,
      margin: 0,
      color: theme.colors.muted,
      fontFace: theme.fonts.sans,
      fontSize: 9,
      bold: true,
      charSpacing: 1,
    });
    slide.addText(metric.value, {
      x: x + 0.2,
      y: DETAIL_TOP + 0.59,
      w: cardWidth - 0.4,
      h: 0.55,
      margin: 0,
      color: theme.colors.text,
      fontFace: theme.fonts.mono,
      fontSize: 24,
      bold: true,
      valign: "middle",
    });
    slide.addText(metric.detail, {
      x: x + 0.2,
      y: DETAIL_TOP + 1.22,
      w: cardWidth - 0.4,
      h: cardHeight - 1.34,
      margin: 0,
      color: theme.colors.textSoft,
      fontFace: theme.fonts.sans,
      fontSize: 10,
      valign: "top",
    });
  });
}

function executorColor(executor: JourneyStep["executor"]): string {
  switch (executor) {
    case "Customer":
      return theme.colors.amber;
    case "Traigent service":
      return theme.colors.green;
    case "Coding assistant":
      return theme.colors.blueBright;
  }
}

// Vertical offsets inside one journey node, measured from the row top.
interface JourneyNodeLayout {
  circle: number;
  badgeTop: number;
  gateHeight: number;
  labelTop: number;
  labelHeight: number;
  labelSize: number;
  detailSize: number;
  badgeSize: number;
}

// Journey: a left-to-right flow. Numbered circles sit on one connecting line;
// under each circle come the executor badge, the optional human gate, the
// step label and its detail. Up to five steps share one row; six steps
// become two rows of three.
function addJourney(
  pptx: PptxGenJS,
  slide: PptxGenJS.Slide,
  steps: readonly JourneyStep[],
): void {
  const count = steps.length;
  const columns = count > 5 ? 3 : count;
  const rows = Math.ceil(count / columns);
  const gap = 0.16;
  const rowGap = 0.14;
  const nodeWidth = (CONTENT_WIDTH - gap * (columns - 1)) / columns;
  const rowHeight =
    rows === 1
      ? CONTENT_HEIGHT - 0.1
      : (CONTENT_HEIGHT - 0.1 - rowGap * (rows - 1)) / rows;
  const hasGates = steps.some((step) => step.humanGate !== undefined);
  const layout: JourneyNodeLayout =
    rows === 1
      ? {
          circle: 0.54,
          badgeTop: 0.72,
          gateHeight: hasGates ? 0.32 : 0,
          labelTop: 1.04,
          labelHeight: 0.46,
          labelSize: 13,
          detailSize: 10.5,
          badgeSize: 8,
        }
      : {
          circle: 0.44,
          badgeTop: 0.54,
          gateHeight: hasGates ? 0.28 : 0,
          labelTop: 0.8,
          labelHeight: 0.28,
          labelSize: 12,
          detailSize: 10,
          badgeSize: 7.5,
        };
  const circleTop = 0.06;
  const centreY = (rowTop: number): number =>
    rowTop + circleTop + layout.circle / 2;
  const centreX = (column: number): number =>
    CONTENT_X + column * (nodeWidth + gap) + nodeWidth / 2;

  // The connecting line first, so the circles drawn after it sit on top.
  for (let row = 0; row < rows; row += 1) {
    const first = row * columns;
    const last = Math.min(count, first + columns) - 1;
    if (last <= first) continue;
    const rowTop = DETAIL_TOP + row * (rowHeight + rowGap);
    slide.addShape(pptx.ShapeType.line, {
      x: centreX(0),
      y: centreY(rowTop),
      w: centreX(last - first) - centreX(0),
      h: 0,
      line: { color: theme.colors.blueBright, transparency: 45, width: 1.5 },
    });
  }

  steps.forEach((step, index) => {
    const column = index % columns;
    const row = Math.floor(index / columns);
    const x = CONTENT_X + column * (nodeWidth + gap);
    const rowTop = DETAIL_TOP + row * (rowHeight + rowGap);
    const color = executorColor(step.executor);
    const circleX = centreX(column) - layout.circle / 2;

    slide.addShape(pptx.ShapeType.ellipse, {
      x: circleX,
      y: rowTop + circleTop,
      w: layout.circle,
      h: layout.circle,
      line: { color, width: 2 },
      fill: { color: theme.colors.surface },
    });
    slide.addText(String(index + 1).padStart(2, "0"), {
      x: circleX,
      y: rowTop + circleTop,
      w: layout.circle,
      h: layout.circle,
      margin: 0,
      color: theme.colors.text,
      fontFace: theme.fonts.mono,
      fontSize: rows === 1 ? 12 : 10.5,
      bold: true,
      align: "center",
      valign: "middle",
    });
    slide.addText(step.executor.toLocaleUpperCase("en"), {
      x,
      y: rowTop + layout.badgeTop,
      w: nodeWidth,
      h: 0.22,
      margin: 0,
      color,
      fontFace: theme.fonts.sans,
      fontSize: layout.badgeSize,
      bold: true,
      charSpacing: 0.8,
      align: "center",
      valign: "middle",
    });
    if (step.humanGate !== undefined) {
      const gateTop = rowTop + layout.badgeTop + 0.26;
      const gateWidth = Math.min(nodeWidth - 0.4, 2.3);
      const gateX = x + (nodeWidth - gateWidth) / 2;
      slide.addShape(pptx.ShapeType.roundRect, {
        x: gateX,
        y: gateTop,
        w: gateWidth,
        h: 0.24,
        rectRadius: 0.12,
        line: { color: theme.colors.amber, transparency: 35, width: 0.8 },
        fill: { color: theme.colors.amber, transparency: 86 },
      });
      slide.addText(step.humanGate.toLocaleUpperCase("en"), {
        x: gateX,
        y: gateTop,
        w: gateWidth,
        h: 0.24,
        margin: 0,
        color: theme.colors.amber,
        fontFace: theme.fonts.sans,
        fontSize: 7.5,
        bold: true,
        charSpacing: 0.6,
        align: "center",
        valign: "middle",
      });
    }
    const labelTop = rowTop + layout.labelTop + layout.gateHeight;
    slide.addText(step.label, {
      x: x + 0.08,
      y: labelTop,
      w: nodeWidth - 0.16,
      h: layout.labelHeight,
      margin: 0,
      color: theme.colors.text,
      fontFace: theme.fonts.sans,
      fontSize: layout.labelSize,
      bold: true,
      align: "center",
      valign: "top",
    });
    const detailTop = labelTop + layout.labelHeight + 0.04;
    slide.addText(step.detail, {
      x: x + 0.08,
      y: detailTop,
      w: nodeWidth - 0.16,
      h: rowTop + rowHeight - detailTop,
      margin: 0,
      color: theme.colors.textSoft,
      fontFace: theme.fonts.sans,
      fontSize: layout.detailSize,
      align: "center",
      valign: "top",
    });
  });
}

// Tiles: a grid of at most four per row (5-6 tiles become 2x3, 7-8 become
// 2x4). Each card carries its glyph in a faint blue square, a bold label and
// one soft line of detail.
function addTiles(
  pptx: PptxGenJS,
  slide: PptxGenJS.Slide,
  tiles: readonly Tile[],
): void {
  const count = tiles.length;
  const columns = count <= 4 ? count : count <= 6 ? 3 : 4;
  const rows = Math.ceil(count / columns);
  const gap = 0.2;
  const rowGap = 0.18;
  const cardWidth = (CONTENT_WIDTH - gap * (columns - 1)) / columns;
  const cardHeight =
    rows === 1 ? 2.0 : (CONTENT_HEIGHT - 0.1 - rowGap * (rows - 1)) / rows;
  const iconSize = 0.5;

  tiles.forEach((tile, index) => {
    const column = index % columns;
    const row = Math.floor(index / columns);
    const x = CONTENT_X + column * (cardWidth + gap);
    const y = DETAIL_TOP + row * (cardHeight + rowGap);

    slide.addShape(pptx.ShapeType.roundRect, {
      x,
      y,
      w: cardWidth,
      h: cardHeight,
      rectRadius: 0.05,
      line: { color: theme.colors.border, width: 0.8 },
      fill: { color: theme.colors.surfaceRaised, transparency: 4 },
    });
    slide.addShape(pptx.ShapeType.roundRect, {
      x: x + 0.2,
      y: y + 0.18,
      w: iconSize,
      h: iconSize,
      rectRadius: 0.09,
      line: { color: theme.colors.blueBright, transparency: 60, width: 0.8 },
      fill: { color: theme.colors.blueBright, transparency: 82 },
    });
    slide.addText(tile.icon, {
      x: x + 0.2,
      y: y + 0.18,
      w: iconSize,
      h: iconSize,
      margin: 0,
      color: theme.colors.text,
      fontFace: theme.fonts.sans,
      fontSize: 15,
      align: "center",
      valign: "middle",
    });
    slide.addText(tile.label, {
      x: x + 0.2,
      y: y + 0.78,
      w: cardWidth - 0.4,
      h: 0.3,
      margin: 0,
      color: theme.colors.text,
      fontFace: theme.fonts.sans,
      fontSize: 12.5,
      bold: true,
      valign: "middle",
    });
    slide.addText(tile.detail, {
      x: x + 0.2,
      y: y + 1.1,
      w: cardWidth - 0.4,
      h: cardHeight - 1.2,
      margin: 0,
      color: theme.colors.textSoft,
      fontFace: theme.fonts.sans,
      fontSize: 9.5,
      valign: "top",
    });
  });
}

// Columns: two to four equal cards, each with a tone-coloured top rule, an
// uppercase heading in that tone and up to five short items with a tone dash.
function addColumns(
  pptx: PptxGenJS,
  slide: PptxGenJS.Slide,
  columns: readonly Column[],
): void {
  const count = columns.length;
  const gap = 0.2;
  const cardWidth = (CONTENT_WIDTH - gap * (count - 1)) / count;
  const cardHeight = CONTENT_HEIGHT - 0.1;
  const itemTop = 0.66;
  const itemRowHeight = 0.55;
  const itemFontSize = count >= 4 ? 10 : 11;

  columns.forEach((column, index) => {
    const x = CONTENT_X + index * (cardWidth + gap);
    const color = toneColor(column.tone);
    slide.addShape(pptx.ShapeType.roundRect, {
      x,
      y: DETAIL_TOP,
      w: cardWidth,
      h: cardHeight,
      rectRadius: 0.05,
      line: { color: theme.colors.border, width: 0.8 },
      fill: { color: theme.colors.surfaceRaised, transparency: 4 },
    });
    slide.addShape(pptx.ShapeType.line, {
      x: x + 0.03,
      y: DETAIL_TOP + 0.03,
      w: cardWidth - 0.06,
      h: 0,
      line: { color, width: 2.4 },
    });
    slide.addText(column.heading.toLocaleUpperCase("en"), {
      x: x + 0.2,
      y: DETAIL_TOP + 0.22,
      w: cardWidth - 0.4,
      h: 0.38,
      margin: 0,
      color,
      fontFace: theme.fonts.sans,
      fontSize: 9,
      bold: true,
      charSpacing: 1,
      valign: "top",
    });
    column.items.forEach((item, itemIndex) => {
      const rowY = DETAIL_TOP + itemTop + itemIndex * itemRowHeight;
      slide.addShape(pptx.ShapeType.line, {
        x: x + 0.2,
        y: rowY + itemRowHeight / 2,
        w: 0.18,
        h: 0,
        line: { color, width: 2 },
      });
      slide.addText(item, {
        x: x + 0.46,
        y: rowY + 0.03,
        w: cardWidth - 0.66,
        h: itemRowHeight - 0.06,
        margin: 0,
        color: theme.colors.textSoft,
        fontFace: theme.fonts.sans,
        fontSize: itemFontSize,
        valign: "middle",
      });
    });
  });
}

// Scale: one 0-100 bar across the content width. Bands are contiguous
// segments sized by (to - from + 1) / 101, each with its bold label and its
// "from-to" range beneath the bar; markers hang a tick and a dot at value%
// with the label above the bar, alternating between a low and a high row so
// near neighbours do not collide.
function addScale(pptx: PptxGenJS, slide: PptxGenJS.Slide, scale: Scale): void {
  const barTop = DETAIL_TOP + 1.18;
  const barHeight = 0.72;
  const barCentre = barTop + barHeight / 2;
  const bandLabelTop = barTop + barHeight + 0.1;
  const bandLabelHeight = 0.36;
  const markerLabelHeight = 0.36;
  const markerLabelWidth = 1.9;
  const markerRowTop = [DETAIL_TOP + 0.44, DETAIL_TOP + 0.02] as const;
  const xAt = (value: number): number =>
    CONTENT_X + (value / 100) * CONTENT_WIDTH;

  scale.bands.forEach((band) => {
    const x = CONTENT_X + (band.from / 101) * CONTENT_WIDTH;
    const width = ((band.to - band.from + 1) / 101) * CONTENT_WIDTH;
    const color = toneColor(band.tone);
    slide.addShape(pptx.ShapeType.rect, {
      x,
      y: barTop,
      w: width,
      h: barHeight,
      line: { color: theme.colors.canvas, width: 1 },
      fill: { color, transparency: 65 },
    });
    slide.addText(band.label, {
      x,
      y: bandLabelTop,
      w: width,
      h: bandLabelHeight,
      margin: 0.02,
      color: theme.colors.text,
      fontFace: theme.fonts.sans,
      fontSize: 11,
      bold: true,
      align: "center",
      valign: "top",
    });
    slide.addText(`${band.from}-${band.to}`, {
      x,
      y: bandLabelTop + bandLabelHeight + 0.02,
      w: width,
      h: 0.22,
      margin: 0,
      color: theme.colors.muted,
      fontFace: theme.fonts.mono,
      fontSize: 9,
      align: "center",
      valign: "middle",
    });
  });

  const endLabelOptions = {
    y: barTop - 0.28,
    w: 0.6,
    h: 0.22,
    margin: 0,
    color: theme.colors.muted,
    fontFace: theme.fonts.mono,
    fontSize: 9,
    valign: "middle",
  } as const;
  slide.addText("0", { ...endLabelOptions, x: CONTENT_X, align: "left" });
  slide.addText("100", {
    ...endLabelOptions,
    x: CONTENT_X + CONTENT_WIDTH - endLabelOptions.w,
    align: "right",
  });

  scale.markers.forEach((marker, index) => {
    const x = xAt(marker.value);
    const labelTop = markerRowTop[index % 2]!;
    const labelX = Math.min(
      Math.max(x - markerLabelWidth / 2, CONTENT_X),
      CONTENT_X + CONTENT_WIDTH - markerLabelWidth,
    );
    const tickTop = labelTop + markerLabelHeight + 0.02;
    slide.addShape(pptx.ShapeType.line, {
      x,
      y: tickTop,
      w: 0,
      h: barCentre - tickTop,
      line: { color: theme.colors.text, transparency: 35, width: 1 },
    });
    slide.addShape(pptx.ShapeType.ellipse, {
      x: x - 0.08,
      y: barCentre - 0.08,
      w: 0.16,
      h: 0.16,
      line: { color: theme.colors.canvas, width: 1 },
      fill: { color: theme.colors.text },
    });
    slide.addText(
      [
        {
          text: String(marker.value),
          options: { color: theme.colors.muted, fontFace: theme.fonts.mono },
        },
        {
          text: `  ${marker.label}`,
          options: { color: theme.colors.text, bold: true },
        },
      ],
      {
        x: labelX,
        y: labelTop,
        w: markerLabelWidth,
        h: markerLabelHeight,
        margin: 0,
        fontFace: theme.fonts.sans,
        fontSize: 9.5,
        align: "center",
        valign: "bottom",
      },
    );
  });
}

function addTableCell(
  pptx: PptxGenJS,
  slide: PptxGenJS.Slide,
  text: string,
  x: number,
  y: number,
  width: number,
  height: number,
  header = false,
  accent = false,
): void {
  slide.addShape(pptx.ShapeType.rect, {
    x,
    y,
    w: width,
    h: height,
    line: { color: theme.colors.border, width: 0.55 },
    fill: {
      color: header ? theme.colors.canvas : theme.colors.surfaceRaised,
      transparency: header ? 2 : 6,
    },
  });
  slide.addText(text, {
    x: x + 0.1,
    y: y + 0.07,
    w: width - 0.2,
    h: height - 0.12,
    margin: 0,
    color: accent
      ? theme.colors.blueBright
      : header
        ? theme.colors.muted
        : theme.colors.textSoft,
    fontFace: theme.fonts.sans,
    fontSize: header ? 8.5 : 10.3,
    bold: header || accent,
    charSpacing: header ? 0.45 : 0,
    valign: "middle",
    breakLine: false,
  });
}

function addStartingPointMatrix(
  pptx: PptxGenJS,
  slide: PptxGenJS.Slide,
  matrix: readonly MatrixRow[],
): void {
  const widths = [4.4, CONTENT_WIDTH - 4.4];
  const headers = ["STARTING CONDITION", "SAFEST JUSTIFIED NEXT STEP"];
  const headerHeight = 0.43;
  const rowHeight = 0.58;
  let x = CONTENT_X;
  headers.forEach((header, index) => {
    addTableCell(
      pptx,
      slide,
      header,
      x,
      DETAIL_TOP,
      widths[index]!,
      headerHeight,
      true,
    );
    x += widths[index]!;
  });
  matrix.forEach((row, rowIndex) => {
    const y = DETAIL_TOP + headerHeight + rowIndex * rowHeight;
    const values = [row.startingPoint, row.safestNextStep];
    let cellX = CONTENT_X;
    values.forEach((value, columnIndex) => {
      addTableCell(
        pptx,
        slide,
        value,
        cellX,
        y,
        widths[columnIndex]!,
        rowHeight,
      );
      cellX += widths[columnIndex]!;
    });
  });
}

function addFooter(
  slide: PptxGenJS.Slide,
  spec: PresentationSpec,
  slideSpec: SlideSpec,
  slideNumber: number,
  slideCount: number,
): void {
  slide.addText(sourceFooter(spec, slideSpec), {
    x: CONTENT_X,
    y: FOOTER_TOP,
    w: 10.3,
    h: 0.3,
    margin: 0,
    color: theme.colors.muted,
    fontFace: theme.fonts.sans,
    fontSize: 9,
    valign: "middle",
  });
  slide.addText(
    `${slideSpec.section === "appendix" ? "APPENDIX" : "CORE"} · ${slideNumber} / ${slideCount}`,
    {
      x: 11.3,
      y: FOOTER_TOP,
      w: 1.8,
      h: 0.3,
      margin: 0,
      color: theme.colors.muted,
      fontFace: theme.fonts.mono,
      fontSize: 9,
      align: "right",
      valign: "middle",
    },
  );
}

function requireBlock<T>(
  slideSpec: SlideSpec,
  block: T | undefined,
  name: string,
): T {
  if (block === undefined) {
    throw new PptxBuildError(
      `Slide ${slideSpec.id} is a ${slideSpec.kind} slide without ${name}`,
    );
  }
  return block;
}

// Each slide kind owns exactly one content block, so the renderer dispatches
// on the kind rather than on which array happens to be filled.
function addSlideContent(
  pptx: PptxGenJS,
  slide: PptxGenJS.Slide,
  slideSpec: SlideSpec,
): void {
  switch (slideSpec.kind) {
    case "hero":
      return;
    case "statement":
      addBullets(pptx, slide, slideSpec.bullets);
      return;
    case "callout":
      addCallout(pptx, slide, slideSpec);
      return;
    case "handoff":
      addHandoff(pptx, slide, slideSpec);
      return;
    case "journey":
      addJourney(pptx, slide, slideSpec.steps);
      return;
    case "evidence":
      addMetrics(pptx, slide, slideSpec.metrics);
      return;
    case "matrix":
      addStartingPointMatrix(
        pptx,
        slide,
        requireBlock(slideSpec, slideSpec.matrix, "matrix rows"),
      );
      return;
    case "tiles":
      addTiles(pptx, slide, slideSpec.tiles);
      return;
    case "columns":
      addColumns(
        pptx,
        slide,
        requireBlock(slideSpec, slideSpec.columns, "columns"),
      );
      return;
    case "scale":
      addScale(
        pptx,
        slide,
        requireBlock(slideSpec, slideSpec.scale, "a scale"),
      );
      return;
    default: {
      const unhandled: never = slideSpec.kind;
      throw new PptxBuildError(`Unsupported slide kind: ${String(unhandled)}`);
    }
  }
}

export function createPptx(value: PresentationSpec = presentation): PptxGenJS {
  const validated = validatePresentationContent(value);
  const pptx = new PptxGenJS();
  pptx.defineLayout({
    name: "TRAIGENT_WIDE",
    width: SLIDE_WIDTH,
    height: SLIDE_HEIGHT,
  });
  pptx.layout = "TRAIGENT_WIDE";
  pptx.author = "Traigent Ltd";
  pptx.company = "Traigent Ltd";
  pptx.subject = validated.subtitle;
  pptx.title = validated.title;
  pptx.revision = "1";
  pptx.theme = {
    headFontFace: theme.fonts.sans,
    bodyFontFace: theme.fonts.sans,
  };
  pptx.defineSlideMaster({
    title: MASTER_NAME,
    background: { color: theme.colors.canvas },
    objects: [
      {
        placeholder: {
          options: {
            name: TITLE_PLACEHOLDER_NAME,
            type: "title",
            x: CONTENT_X,
            y: 1.02,
            w: 11.15,
            h: 1.18,
            margin: 0,
          },
          text: "",
        },
      },
    ],
  });

  validated.slides.forEach((slideSpec, index) => {
    const slide = pptx.addSlide({ masterName: MASTER_NAME });
    addBackground(pptx, slide);
    addBrand(pptx, slide);
    addHeading(slide, slideSpec);
    addSlideContent(pptx, slide, slideSpec);
    addFooter(slide, validated, slideSpec, index + 1, validated.slides.length);
    slide.addNotes(slideSpec.notes.join("\n\n"));
  });

  return pptx;
}

function parsePptxEpochSeconds(value: string, label: string): number {
  if (!/^\d+$/.test(value)) {
    throw new PptxBuildError(`${label} must be a non-negative integer`);
  }
  const parsed = Number(value);
  if (!Number.isSafeInteger(parsed)) {
    throw new PptxBuildError(`${label} is outside the safe integer range`);
  }
  if (parsed < EARLIEST_ZIP_EPOCH_SECONDS) {
    throw new PptxBuildError(
      `${label} must be on or after 1980-01-01 for ZIP output`,
    );
  }
  const timestamp = new Date(parsed * 1000);
  if (Number.isNaN(timestamp.valueOf())) {
    throw new PptxBuildError(`${label} is outside the supported date range`);
  }
  return parsed;
}

export function resolvePptxEpochSeconds(
  sourceDateEpoch = process.env.SOURCE_DATE_EPOCH,
): number {
  if (sourceDateEpoch !== undefined) {
    return parsePptxEpochSeconds(sourceDateEpoch, "SOURCE_DATE_EPOCH");
  }
  try {
    const commitEpoch = execFileSync(
      "git",
      ["show", "-s", "--format=%ct", "HEAD"],
      {
        cwd: repositoryRoot,
        encoding: "utf8",
        stdio: ["ignore", "pipe", "pipe"],
      },
    ).trim();
    return parsePptxEpochSeconds(commitEpoch, "Git commit timestamp");
  } catch (error: unknown) {
    if (error instanceof PptxBuildError) {
      throw error;
    }
    throw new PptxBuildError(
      "Unable to resolve a reproducible PowerPoint timestamp; use a Git checkout or set SOURCE_DATE_EPOCH",
      { cause: error },
    );
  }
}

function replaceCoreTimestamp(
  coreProperties: string,
  field: "created" | "modified",
  timestamp: string,
): string {
  const pattern = new RegExp(
    `(<dcterms:${field}\\b[^>]*>)[^<]*(</dcterms:${field}>)`,
  );
  if (!pattern.test(coreProperties)) {
    throw new PptxBuildError(`PowerPoint core properties are missing ${field}`);
  }
  return coreProperties.replace(pattern, `$1${timestamp}$2`);
}

async function normalizePptxArchive(
  bytes: Uint8Array,
  epochSeconds: number,
): Promise<Buffer> {
  const timestamp = new Date(epochSeconds * 1000);
  const archive = await JSZip.loadAsync(bytes);
  const coreFile = archive.file("docProps/core.xml");
  if (coreFile === null) {
    throw new PptxBuildError("PowerPoint archive is missing docProps/core.xml");
  }
  const isoTimestamp = timestamp.toISOString().replace(".000Z", "Z");
  const coreProperties = replaceCoreTimestamp(
    replaceCoreTimestamp(
      await coreFile.async("string"),
      "created",
      isoTimestamp,
    ),
    "modified",
    isoTimestamp,
  );

  archive.forEach((_relativePath, entry) => {
    entry.date = timestamp;
  });
  archive.file("docProps/core.xml", coreProperties, { date: timestamp });

  return archive.generateAsync({
    type: "nodebuffer",
    compression: "DEFLATE",
    compressionOptions: { level: 9 },
    platform: "UNIX",
  });
}

export async function renderPptxBuffer(
  value: PresentationSpec = presentation,
  sourceEpochSeconds = resolvePptxEpochSeconds(),
): Promise<Buffer> {
  const validatedEpochSeconds = parsePptxEpochSeconds(
    String(sourceEpochSeconds),
    "PowerPoint source epoch",
  );
  const output = await createPptx(value).write({
    outputType: "nodebuffer",
    compression: true,
  });
  if (!(output instanceof Uint8Array)) {
    throw new PptxBuildError("PptxGenJS returned a non-binary Node output");
  }
  return normalizePptxArchive(output, validatedEpochSeconds);
}

export async function buildPptx(
  outputPath = defaultPptxPath,
  sourceEpochSeconds = resolvePptxEpochSeconds(),
): Promise<string> {
  try {
    const bytes = await renderPptxBuffer(presentation, sourceEpochSeconds);
    await mkdir(path.dirname(outputPath), { recursive: true });
    await writeFile(outputPath, bytes);
    return outputPath;
  } catch (error: unknown) {
    if (error instanceof PptxBuildError) {
      throw error;
    }
    throw new PptxBuildError(`Unable to build PowerPoint at ${outputPath}`, {
      cause: error,
    });
  }
}

if (isMainModule(import.meta.url)) {
  const outputPath = await buildPptx();
  process.stdout.write(`Built editable PowerPoint: ${outputPath}\n`);
}
