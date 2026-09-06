import {
  type CSSProperties,
  useCallback,
  useEffect,
  useLayoutEffect,
  useMemo,
  useRef,
  useState,
} from "react";

import { brandName, traigentLogoPngDataUri } from "./brand";
import { coreSlideCount, presentation } from "./content";
import {
  displayEyebrow,
  type JourneyStep,
  type ScaleMarker,
  sourceFooter,
  type SlideSpec,
} from "./model";

/** Column count for a grid that keeps rows balanced: 1-4 in one row, 5-6 in two rows of three, 7-8 in two rows of four. */
function balancedColumns(count: number): number {
  if (count <= 4) {
    return Math.max(1, count);
  }
  return count <= 6 ? 3 : 4;
}

/** Column count for the journey flow: one row up to five steps, then two rows of three. */
function journeyColumns(count: number): number {
  return count <= 5 ? Math.max(1, count) : 3;
}

function gridColumns(columns: number): CSSProperties {
  return { "--columns": columns } as CSSProperties;
}

function executorClass(executor: JourneyStep["executor"]): string {
  return executor === "Coding assistant"
    ? "agent"
    : executor === "Customer"
      ? "human"
      : "service";
}

function initialSlideIndex(): number {
  const slideId = window.location.hash.replace(/^#\/?/, "");
  const index = presentation.slides.findIndex((slide) => slide.id === slideId);
  return index >= 0 ? index : 0;
}

function HighlightedTitle({ slide }: { slide: SlideSpec }) {
  if (slide.accent === undefined) {
    return <>{slide.title}</>;
  }
  const titleLower = slide.title.toLocaleLowerCase("en");
  const accentLower = slide.accent.toLocaleLowerCase("en");
  const start = titleLower.indexOf(accentLower);
  if (start < 0) {
    return <>{slide.title}</>;
  }
  const end = start + slide.accent.length;
  return (
    <>
      {slide.title.slice(0, start)}
      <span className="title-accent">{slide.title.slice(start, end)}</span>
      {slide.title.slice(end)}
    </>
  );
}

function Metrics({ slide }: { slide: SlideSpec }) {
  if (slide.metrics.length === 0) {
    return null;
  }
  return (
    <dl className="metric-grid" aria-label="Guide facts">
      {slide.metrics.map((metric) => (
        <div className={`metric-card tone-${metric.tone}`} key={metric.label}>
          <dt>{metric.label}</dt>
          <dd>{metric.value}</dd>
          <p>{metric.detail}</p>
        </div>
      ))}
    </dl>
  );
}

function Journey({ slide }: { slide: SlideSpec }) {
  if (slide.steps.length === 0) {
    return null;
  }
  const columns = journeyColumns(slide.steps.length);
  return (
    <ol
      className="journey"
      style={gridColumns(columns)}
      aria-label="First-run journey"
    >
      {slide.steps.map((step, index) => {
        const column = index % columns;
        const position = [
          column === 0 ? "journey-row-start" : "",
          column === columns - 1 || index === slide.steps.length - 1
            ? "journey-row-end"
            : "",
        ]
          .filter(Boolean)
          .join(" ");
        return (
          <li
            className={`journey-step${position === "" ? "" : ` ${position}`}`}
            key={`${step.executor}-${step.label}`}
          >
            <div className="step-node">
              <span className="step-number">
                <span className="visually-hidden">Step </span>
                {index + 1}
              </span>
            </div>
            <div className="step-badges">
              <span className={`owner owner-${executorClass(step.executor)}`}>
                {step.executor} executes
              </span>
              {step.humanGate === undefined ? null : (
                <span className="human-gate">{step.humanGate}</span>
              )}
            </div>
            <h2>{step.label}</h2>
            <p>{step.detail}</p>
          </li>
        );
      })}
    </ol>
  );
}

function Tiles({ slide }: { slide: SlideSpec }) {
  if (slide.tiles.length === 0) {
    return null;
  }
  // Seven or eight tiles sit two-by-four, denser than the deck's common cases.
  const dense = slide.tiles.length > 6;
  return (
    <ul
      className={dense ? "tile-grid tile-grid-dense" : "tile-grid"}
      style={gridColumns(balancedColumns(slide.tiles.length))}
    >
      {slide.tiles.map((tile) => (
        <li className="tile" key={tile.label}>
          <span className="tile-icon" aria-hidden="true">
            {tile.icon}
          </span>
          <div>
            <h2>{tile.label}</h2>
            <p>{tile.detail}</p>
          </div>
        </li>
      ))}
    </ul>
  );
}

function Columns({ slide }: { slide: SlideSpec }) {
  if (slide.columns === undefined) {
    return null;
  }
  return (
    <div
      className={
        slide.columns.length > 3
          ? "column-grid column-grid-dense"
          : "column-grid"
      }
      style={gridColumns(slide.columns.length)}
    >
      {slide.columns.map((column) => (
        <section
          className={`column-card tone-${column.tone}`}
          aria-labelledby={`${slide.id}-column-${slugify(column.heading)}`}
          key={column.heading}
        >
          <h2 id={`${slide.id}-column-${slugify(column.heading)}`}>
            {column.heading}
          </h2>
          <ul>
            {column.items.map((item) => (
              <li key={item}>
                <span aria-hidden="true" />
                {item}
              </li>
            ))}
          </ul>
        </section>
      ))}
    </div>
  );
}

function slugify(text: string): string {
  return text
    .toLocaleLowerCase("en")
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-|-$/g, "");
}

// A marker label is centred on its tick unless the tick sits near an end of
// the bar, where centring would push the label past the figure.
function markerAnchor(marker: ScaleMarker): string {
  return marker.value <= 8
    ? "scale-marker-start"
    : marker.value >= 92
      ? "scale-marker-end"
      : "";
}

function ReadinessScale({ slide }: { slide: SlideSpec }) {
  if (slide.scale === undefined) {
    return null;
  }
  const { bands, markers } = slide.scale;
  const summary = [
    `Scale from 0 to 100 in ${bands.length} bands: ${bands
      .map((band) => `${band.label} ${band.from} to ${band.to}`)
      .join(", ")}.`,
    markers.length === 0
      ? ""
      : `Markers: ${markers
          .map((marker) => `${marker.label} at ${marker.value}`)
          .join(", ")}.`,
  ]
    .filter(Boolean)
    .join(" ");
  return (
    <figure className="scale-figure">
      <figcaption className="visually-hidden">{summary}</figcaption>
      {markers.length === 0 ? null : (
        <ul className="scale-markers" aria-hidden="true">
          {markers.map((marker, index) => (
            <li
              className={[
                "scale-marker",
                index % 2 === 0 ? "scale-marker-low" : "scale-marker-high",
                markerAnchor(marker),
              ]
                .filter(Boolean)
                .join(" ")}
              style={{ left: `${marker.value}%` }}
              key={`${marker.value}-${marker.label}`}
            >
              <span className="scale-marker-label">
                {marker.label}
                <small>{marker.value}</small>
              </span>
              <span className="scale-tick" />
            </li>
          ))}
        </ul>
      )}
      <ol className="scale-bar" aria-hidden="true">
        {bands.map((band) => (
          <li
            className={`scale-band tone-${band.tone}`}
            style={{ width: `${((band.to - band.from + 1) / 101) * 100}%` }}
            key={`${band.from}-${band.to}`}
          >
            <strong>{band.label}</strong>
            <span>
              {band.from}–{band.to}
            </span>
          </li>
        ))}
      </ol>
      <div className="scale-ends" aria-hidden="true">
        <span>0</span>
        <span>100</span>
      </div>
    </figure>
  );
}

function StartingPointMatrix({ slide }: { slide: SlideSpec }) {
  if (slide.matrix === undefined) {
    return null;
  }
  return (
    <div className="matrix-wrap">
      <span className="matrix-scroll-hint" aria-hidden="true">
        Scroll sideways to see every column
      </span>
      <table className="starting-matrix">
        <caption>Starting condition and the safest justified next step</caption>
        <thead>
          <tr>
            <th scope="col">Starting condition</th>
            <th scope="col">Safest justified next step</th>
          </tr>
        </thead>
        <tbody>
          {slide.matrix.map((row) => (
            <tr key={row.startingPoint}>
              <th scope="row">{row.startingPoint}</th>
              <td>{row.safestNextStep}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

function Slide({ slide }: { slide: SlideSpec }) {
  const isHero = slide.kind === "hero";
  const slideRef = useRef<HTMLElement>(null);
  const eyebrow = displayEyebrow(slide);

  useLayoutEffect(() => {
    const fitParameters = new URLSearchParams(window.location.search);
    if (!fitParameters.has("fit-check")) {
      return;
    }
    const element = slideRef.current;
    if (element === null) {
      return;
    }
    const slideBounds = element.getBoundingClientRect();
    const selectors = [
      ".slide-heading",
      ".prompt-card",
      ".bullet-grid",
      ".metric-grid",
      ".journey",
      ".matrix-wrap",
      ".tile-grid",
      ".column-grid",
      ".scale-figure",
      ".scale-marker-label",
      ".callout-card",
      ".slide-brand",
    ].join(",");
    const clipped = Array.from(element.querySelectorAll<HTMLElement>(selectors))
      .filter((child) => {
        const bounds = child.getBoundingClientRect();
        return (
          bounds.top < slideBounds.top - 1 ||
          bounds.left < slideBounds.left - 1 ||
          bounds.right > slideBounds.right + 1 ||
          bounds.bottom > slideBounds.bottom + 1
        );
      })
      .map((child) =>
        Array.from(child.classList)
          .map((name) => `.${name}`)
          .join(""),
      );
    const reasons = [
      Number(fitParameters.get("fit-width")) !== window.innerWidth ||
      Number(fitParameters.get("fit-height")) !== window.innerHeight
        ? `viewport mismatch ${window.innerWidth}x${window.innerHeight}`
        : "",
      element.scrollHeight > element.clientHeight + 1
        ? `slide vertical overflow ${element.scrollHeight}/${element.clientHeight}`
        : "",
      document.documentElement.scrollHeight > window.innerHeight + 1
        ? `page vertical overflow ${document.documentElement.scrollHeight}/${window.innerHeight}`
        : "",
      document.documentElement.scrollWidth > window.innerWidth + 1
        ? `page horizontal overflow ${document.documentElement.scrollWidth}/${window.innerWidth}`
        : "",
      ...clipped.map((className) => `clipped .${className}`),
    ].filter(Boolean);
    document.documentElement.dataset.fitStatus =
      reasons.length === 0 ? "pass" : "fail";
    document.documentElement.dataset.fitDetail = reasons.join("; ");
    document.documentElement.dataset.fitSlide = slide.id;
  }, [slide]);

  return (
    <article
      className={`slide slide-${slide.kind}`}
      aria-labelledby={`${slide.id}-title`}
      data-source-revision={presentation.source.revision}
      ref={slideRef}
    >
      <div className="slide-glow" aria-hidden="true" />
      <div className="slide-brand" aria-hidden="true">
        <img src={traigentLogoPngDataUri} alt="" />
        <span>{brandName}</span>
      </div>
      <header className="slide-heading">
        <p className="eyebrow">
          <span aria-hidden="true" />
          {eyebrow}
        </p>
        <h1
          id={`${slide.id}-title`}
          className={isHero ? "hero-title" : undefined}
        >
          <HighlightedTitle slide={slide} />
        </h1>
        <p className="slide-body">{slide.body}</p>
      </header>

      {isHero ? null : (
        <div className="slide-visual">
          {slide.quote !== undefined ? (
            <blockquote className="prompt-card">
              <span className="prompt-label">
                Paste into your coding assistant
              </span>
              <code>{slide.quote}</code>
            </blockquote>
          ) : null}

          {slide.callout !== undefined ? (
            <p className="callout-card">{slide.callout}</p>
          ) : null}

          {slide.bullets.length > 0 ? (
            <ul className="bullet-grid">
              {slide.bullets.map((bullet) => (
                <li key={bullet}>
                  <span aria-hidden="true" />
                  {bullet}
                </li>
              ))}
            </ul>
          ) : null}

          <Metrics slide={slide} />
          <Journey slide={slide} />
          <StartingPointMatrix slide={slide} />
          <Tiles slide={slide} />
          <Columns slide={slide} />
          <ReadinessScale slide={slide} />
        </div>
      )}
    </article>
  );
}

export function App() {
  const [slideIndex, setSlideIndex] = useState(initialSlideIndex);
  const [notesVisible, setNotesVisible] = useState(false);
  const mainRef = useRef<HTMLElement>(null);
  const slide = presentation.slides[slideIndex];

  const goTo = useCallback((nextIndex: number) => {
    const boundedIndex = Math.min(
      presentation.slides.length - 1,
      Math.max(0, nextIndex),
    );
    setSlideIndex(boundedIndex);
  }, []);

  const goPrevious = useCallback(
    () => goTo(slideIndex - 1),
    [goTo, slideIndex],
  );
  const goNext = useCallback(() => goTo(slideIndex + 1), [goTo, slideIndex]);

  useEffect(() => {
    window.history.replaceState(null, "", `#/${slide.id}`);
    document.title = `${slide.title} | ${presentation.title}`;
    mainRef.current?.focus({ preventScroll: true });
  }, [slide]);

  useEffect(() => {
    const handleKeyDown = (event: KeyboardEvent) => {
      const target = event.target;
      if (
        target instanceof HTMLInputElement ||
        target instanceof HTMLTextAreaElement ||
        target instanceof HTMLSelectElement
      ) {
        return;
      }
      if (event.key === "ArrowLeft" || event.key === "PageUp") {
        event.preventDefault();
        goPrevious();
      } else if (
        event.key === "ArrowRight" ||
        event.key === "PageDown" ||
        (event.key === " " && target === mainRef.current)
      ) {
        event.preventDefault();
        goNext();
      } else if (event.key === "Home") {
        event.preventDefault();
        goTo(0);
      } else if (event.key === "End") {
        event.preventDefault();
        goTo(presentation.slides.length - 1);
      } else if (event.key.toLocaleLowerCase("en") === "n") {
        event.preventDefault();
        setNotesVisible((visible) => !visible);
      }
    };
    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, [goNext, goPrevious, goTo]);

  const progressLabel = useMemo(() => {
    if (slideIndex < coreSlideCount) {
      return `Core ${slideIndex + 1} of ${coreSlideCount}`;
    }
    return `Appendix ${slideIndex + 1 - coreSlideCount} of ${
      presentation.slides.length - coreSlideCount
    }`;
  }, [slideIndex]);

  return (
    <div className="presentation-shell">
      <a className="skip-link" href="#presentation-slide">
        Skip to slide content
      </a>
      <header className="topbar">
        <div className="brand" aria-label="Traigent">
          <img src={traigentLogoPngDataUri} alt="" aria-hidden="true" />
          <span>{brandName}</span>
        </div>
        <div className="deck-context">
          <span>Guided First Run</span>
          <span className="context-divider" aria-hidden="true" />
          <span>
            {slide.section === "appendix" ? "Technical appendix" : "Overview"}
          </span>
        </div>
      </header>

      <main
        id="presentation-slide"
        className="stage"
        ref={mainRef}
        tabIndex={-1}
      >
        <Slide slide={slide} />
      </main>

      <nav className="controls" aria-label="Presentation controls">
        <button type="button" onClick={goPrevious} disabled={slideIndex === 0}>
          Previous
        </button>
        <div className="slide-picker" aria-label="Choose a slide">
          {presentation.slides.map((candidate, index) => (
            <button
              type="button"
              className={index === slideIndex ? "active" : undefined}
              aria-current={index === slideIndex ? "step" : undefined}
              aria-label={`Go to slide ${index + 1}: ${candidate.title}`}
              onClick={() => goTo(index)}
              key={candidate.id}
            >
              <span aria-hidden="true" />
            </button>
          ))}
        </div>
        <span className="progress" aria-live="polite">
          {progressLabel}
        </span>
        <button
          type="button"
          onClick={() => setNotesVisible((visible) => !visible)}
        >
          {notesVisible ? "Hide notes" : "Show notes"}
        </button>
        <button
          type="button"
          onClick={goNext}
          disabled={slideIndex === presentation.slides.length - 1}
        >
          Next
        </button>
      </nav>

      {notesVisible ? (
        <aside className="speaker-notes" aria-label="Speaker notes">
          <strong>Speaker notes</strong>
          <ul>
            {slide.notes.map((note) => (
              <li key={note}>{note}</li>
            ))}
          </ul>
          <p className="speaker-sources">{sourceFooter(presentation, slide)}</p>
        </aside>
      ) : null}
    </div>
  );
}
