import { parsePresentation, type PresentationSpec } from "./model";

const customerPrompt =
  "Help me run my first Traigent optimization.\nClone https://github.com/Traigent/traigent-first-run and follow GUIDE.md.";

const guideRevision = "75d338c31c97643c6a6d28a6aeef582d7b938db8";
const guideRef = `Traigent/traigent-first-run@${guideRevision.slice(0, 8)}`;
const readinessEvidence = `${guideRef} readiness scorer`;

// The committed opening card for the ready preset. It is the guide's own
// preflight and readiness scripts run over the built demo (guide revision
// 6ec2b9c1, 2026-09-02, no network), with a hand-written agent read standing in
// for the assistant's. No coding-agent session is recorded, so every slide that
// cites it stays at scenario-contract.
const measuredCardRevision = "6ec2b9c1";
const readyCardEvidence =
  "Companion repo docs/measurements/cards/ready/05-readiness.json (guide scorer at 6ec2b9c1 over the built demo; no coding-agent session recorded)";
const scoreTableEvidence =
  "Companion repo README score table and docs/measurements/README.md";

const rawPresentation = {
  schemaVersion: 2,
  title: "Traigent First Run: Presales Showcase",
  subtitle:
    "How Traigent Guided First Run leads customer projects from inspection to graded readiness, gap repair, and a justified next step",
  scenario: {
    slug: "spider-text-to-sql-benchmark",
    legacyId: 1,
    title: "Spider Text-to-SQL First-Run Scenario",
    expectedBand: "PARTIAL" as const,
    phase: "phase-a-opening" as const,
  },
  catalog: [
    {
      slug: "spider-text-to-sql-benchmark",
      label: "Spider Text-to-SQL Preset: Ready",
      publication: "published" as const,
      startingState:
        "Ready preset: tunable agent, 300 Spider questions across 18 SQLite databases, and an exact-match text evaluator present. No calibration probes ship with it, so the scorer is not yet checked.",
      components: [
        "Agent (ready): tunable model, schema_context, prompt_style, and temperature; the output is always SQLite SQL",
        "Dataset (ready): 300 Spider questions and gold queries across 18 SQLite schemas; build.py holds back 60 of them",
        "Evaluator (ready): exact-match text comparator that normalises spacing, quotes, and keyword case; it never executes SQL",
        "Calibration: none in this preset; probe answers travel only with checked, hand-written, fake-ruler, and best-case",
      ],
      dataset:
        "Spider 1.0 benchmark data (Yu et al., EMNLP 2018) under CC BY-SA 4.0; 300 questions across 18 SQLite databases, balanced 75 apiece across easy, medium, hard, and very-hard strata. Limitations: text-to-SQL specific domain, and a public benchmark current models have very likely seen.",
      evaluator:
        "Normalised exact match against the recorded gold query as text. It never runs SQL, so a correct query written differently from the gold is marked wrong. The repo's execution-match scorer is a separate evaluator the guide stops before running.",
      expectedRouting:
        "Committed opening card: 45/100, band PARTIAL, recommended action proceed, one cap (evaluator-unvalidated, ceiling 45, not blocking); pillars agent 70, dataset 98, evaluation 33. Calibrating the scorer (preset checked) reads 86 STRONG with no caps.",
      testedLayer:
        "Preflight and static readiness scoring over the built demo, run with the guide's own scripts at guide revision 6ec2b9c1. No coding-agent session and no baseline are recorded.",
      notProven: [
        "Universal model accuracy across unseen schemas",
        "Production deployment performance on non-SQLite engines",
        "Any baseline or optimization outcome on this preset",
      ],
    },
  ],
  slides: [
    {
      id: "ready-to-optimize",
      kind: "hero",
      eyebrow: "TRAIGENT FIRST RUN · PRESALES SHOWCASE",
      title:
        "Start with the project you have. Leave with a justified next step.",
      accent: "justified next step",
      body: "Traigent Guided First Run meets customer repositories where they actually are. It inspects without touching production or spending money, grades readiness honestly, repairs evaluation and data gaps on a working copy, and leads to an approved, bounded first run.",
      bullets: [],
      metrics: [],
      steps: [],
      evidenceState: "guide-contract",
      sourceRevision: guideRevision,
      evidence: [
        `Guided First Run contract at ${guideRef}; no fresh coding-agent run supplied`,
      ],
      notes: [
        "Lead with honest routing: we do not demand a clean, pre-built benchmark or a perfect agent.",
        "The customer own assets determine their score and route; we never sell a guaranteed uplift.",
        "Talk track: the deliverable of the first run is a truthful position and a next step, not a score.",
        "Repair means a working copy with provenance preserved, never silent; generated material is never marked as a real, validated component.",
      ],
    },
    {
      id: "shared-control",
      kind: "journey",
      eyebrow: "AGENT-LED, HUMAN-GOVERNED",
      title: "Five stages. Three actors. Two paid approvals.",
      body: "Every project enters Inspect. Safe discovery needs no approval; the run stops only for a genuine component choice, a task-intent question, secrets, paid or private-data calls, judgment calls on real labels, or production-affecting changes. Paid work sits behind exactly two approvals: the baseline first, the connected optimization separately.",
      bullets: [],
      metrics: [],
      steps: [
        {
          label: "1 Inspect",
          detail:
            "Find the agent, dataset, and evaluator; mark each real component ✅ (found and validated) or ❗ (missing, invalid, or evidence-limited). Reads files locally only: no project code runs, no provider or Traigent calls.",
          executor: "Coding agent",
        },
        {
          label: "2 Readiness",
          detail:
            "Score the evidence, apply caps - score ceilings set by the material - and explain the safest next route. Not an approval gate: the user is never asked to approve safe discovery. Stop before paid work when the evaluator cannot tell good from bad answers.",
          executor: "Coding agent",
        },
        {
          label: "3 Baseline",
          detail:
            "Preserve and measure the existing baseline, or prepare a fixed 12-configuration grid only when none exists. The first model-provider stage.",
          executor: "Coding agent",
          humanGate: "Paid approval 1 of 2",
        },
        {
          label: "4 Optimize",
          detail:
            "Search the approved space and compare it with the preserved baseline.",
          executor: "Traigent service",
          humanGate: "Paid approval 2 of 2",
        },
        {
          label: "5 Results",
          detail:
            "Report the comparison, cost evidence, and limits, closing with one recommended next action; the human decides.",
          executor: "Coding agent",
          humanGate: "Human decides",
        },
      ],
      evidenceState: "guide-contract",
      sourceRevision: guideRevision,
      evidence: [`First-run stages and approval boundaries at ${guideRef}`],
      notes: [
        "The boundary the presenter must draw: stages 1-2 make no calls to the customer project-model provider or the Traigent service and incur no spend with either.",
        "Stage 3 is the first project-model stage, on the customer approved key and cost boundary.",
        "Stage 4 is a separate approval from stage 3 on purpose: the baseline preserves the user existing local space, while enhanced search explores a broader space.",
        "Do not present Readiness as a gate the human approves; the guide says not to make the user approve safe discovery. The human is asked only for the stops listed in the body.",
      ],
    },
    {
      id: "one-customer-prompt",
      kind: "handoff",
      eyebrow: "ZERO-FRICTION CUSTOMER ONBOARDING",
      title: "One prompt to the coding agent already on your project.",
      body: "The guide carries the workflow. The human keeps control of domain decisions, credentials, cost, data movement, and production-affecting actions.",
      quote: customerPrompt,
      bullets: [],
      metrics: [],
      steps: [],
      evidenceState: "guide-contract",
      sourceRevision: guideRevision,
      evidence: [
        `Published real-project handoff at ${guideRef}; outcome not demonstrated here`,
      ],
      notes: [
        "Customers paste this exact prompt into Claude Code, Cursor, Codex, or Gemini CLI.",
        "The assistant builds an isolated .venv-traigent environment and never modifies customer project dependencies.",
      ],
    },
    {
      id: "different-starting-points",
      kind: "statement",
      eyebrow: "MEETING CUSTOMER REALITY",
      title:
        "Every customer project enters here. The route depends on what is present.",
      body: "Customer repositories rarely arrive complete. Traigent first-run diagnoses the exact condition and routes to the safest next action — whether that means proceeding to baseline, synthesizing a missing scorer, or stopping for human review.",
      bullets: [
        "Ready components → explain readiness; proceed directly to baseline approval",
        "Missing evaluator → synthesize a deterministic, task-aligned scoring method",
        "Missing or unlabeled data → prepare structured walkthrough substitutes with clear labels",
        "Missing tunable knobs → detect variable parameters and prove request variation locally",
        "Broken evaluator → cap at 25 and block paid runs until the ruler is repaired",
        "Unsafe execution path → stop immediately before executing candidate code or SQL",
      ],
      metrics: [],
      steps: [],
      evidenceState: "guide-contract",
      sourceRevision: guideRevision,
      evidence: [`Route behavior at ${guideRef}`],
      notes: [
        "Do not promise an Excellent opening. A gap, cap, repair, or stop can be the correct and useful outcome for the material the customer brought.",
        "The six bullets summarize next-action families; they are not an exhaustive taxonomy of every project condition.",
        "On the Spider bank the opening gate does not separate mispaired answers or a mis-wired scorer from the ready project; calibration probes and the row review the guide asks for are what catch them.",
      ],
    },
    {
      id: "spider-repo-overview",
      kind: "statement",
      eyebrow: "COMPANION REPOSITORY · SPIDER SCENARIOS",
      title: "The Spider companion repo: instant, realistic SQL demo projects.",
      body: "A Traigent-maintained companion repository, internal today, generates complete text-to-SQL projects from real Spider data. Presales builds a demo project from it and hands only the project directory to the coding agent, so a live onboarding walkthrough needs no customer code.",
      bullets: [
        "Standard-library build CLI: python3 build.py demo --preset ready --out ~/demos/first-try; also list, check, suite, and verify",
        "Real benchmark data: 300 Spider questions, 18 SQLite schemas, four difficulty strata from easy to very-hard, 75 rows each",
        "Offline build and scoring; each demo is self-contained and blind, so the agent inspects a realistic project, never the generator. The default --guide clone step fetches the guide itself from GitHub during the run",
        "Realistic agent: text-to-SQL agent with tunable model, schema_context, prompt_style, and temperature; the output is always SQLite",
        "Two evaluators: exact-match text comparison (the ready preset) and execution match against live SQLite, which the guide stops before running",
        "No provider or Traigent keys needed to inspect and score readiness; the committed cards were produced with no network",
      ],
      metrics: [],
      steps: [],
      evidenceState: "scenario-contract",
      evidence: [
        "Companion repo README and build.py CLI (internal to the Traigent GitHub organisation today)",
        "Spider 1.0 benchmark dataset under CC BY-SA 4.0",
      ],
      notes: [
        "Presales positioning: the companion repo is a scenario generator for demonstrations and testing, while traigent-first-run is the customer guide.",
        "The repository is internal to the Traigent GitHub organisation today; do not promise a customer clone or quote a URL for it.",
        "Keep bank.json and demo.json out of the agent's working directory: they name the state each demo was built in.",
      ],
    },
    {
      id: "spider-presets-matrix",
      kind: "matrix",
      eyebrow: "TESTING ONBOARDING RESILIENCE",
      title: "Seventeen presets to test every onboarding branch live.",
      body: "The Spider scenario bank provides 17 presets, each a starting state a real project could arrive in. Presales can run the exact customer prompt against any preset. The committed opening cards span four of the five bands: no preset opens EXCELLENT on-method, and the best on-method opening is checked at 86 STRONG.",
      bullets: [],
      metrics: [],
      steps: [],
      scenarioMatrix: [
        {
          family: "Preset: ready",
          setup:
            "Agent, dataset, and exact-match evaluator present; no calibration probes, so the scorer is not yet checked",
          expectedRoute:
            "Opening card 45 PARTIAL, action proceed, ceiling 45 from evaluator-unvalidated; the happy path is calibrate the scorer, then baseline approval",
          coverage: "published",
        },
        {
          family: "Preset: checked",
          setup: "The ready project plus probe answers kept for its scorer",
          expectedRoute:
            "Opening card 86 STRONG with no caps: the best on-method opening in the bank, four points below EXCELLENT",
          coverage: "coverage-target",
        },
        {
          family: "Preset: fake-ruler",
          setup:
            "Evaluator marks everything correct, and probe answers ship that catch it",
          expectedRoute:
            "Opening card 25 NOT READY, action repair-evaluator, blocking cap evaluator-invalid; without the probes the same project reads 45 proceed",
          coverage: "coverage-target",
        },
        {
          family: "Preset: wrong-answers",
          setup:
            "60 rows whose gold answers are rotated inside each database, so every answer still runs but answers a different question",
          expectedRoute:
            "Opening card 45 PARTIAL proceed, the same as ready: the opening gate does not notice the mispairing, and with probes it reads 83 STRONG with no caps. The guide's row review is what would catch it",
          coverage: "coverage-target",
        },
        {
          family: "Presets: best-case and sql-exec-stop",
          setup:
            "The Spider-faithful execution scorer, with and without probe answers",
          expectedRoute:
            "Opening card 45 PARTIAL proceed, byte-identical for both; the guide will not calibrate or execute a scorer that runs candidate SQL, so this is where the guide hands over, not a gap it repairs",
          coverage: "coverage-target",
        },
      ],
      evidenceState: "scenario-contract",
      evidence: [
        scoreTableEvidence,
        "traigent-first-run readiness, caps, and progression gates",
      ],
      notes: [
        "Presales script: choose a preset, run the same customer prompt, and narrate the route as evidence-driven behavior instead of a canned success path.",
        "Other committed openings: no-data 20 NOT READY get-data; no-eval 40 PARTIAL connect-evaluator; no-knobs 45 vary-knobs; wrong-wiring and no-agent 45 proceed, so a mis-wired scorer and an absent agent are invisible to the opening gate without probes.",
        `All cards come from the guide's own preflight and readiness scripts at guide revision ${measuredCardRevision} on 2026-09-02, with a hand-written agent read standing in for the assistant's; no coding-agent session is recorded, and the scorer has moved since, so re-measure before quoting a number that matters.`,
        "This slide is about behavior coverage and trust boundaries, not promised uplift metrics.",
      ],
    },
    {
      id: "worked-case-ready",
      kind: "evidence",
      eyebrow: "WORKED DEMO EVIDENCE",
      title: "Worked case: the ready preset under first-run inspection.",
      body: "The companion repo's own getting-started preset, scored by the guide's preflight and readiness scripts over the built demo. The committed card opens at 45 PARTIAL with the recommended action proceed and one ceiling, evaluator-unvalidated at 45, because no calibration probes ship with this preset. It is a scorer run over files, not a recorded coding-agent session.",
      bullets: [],
      metrics: [
        {
          label: "Rows",
          value: "300",
          detail: "18 SQLite schemas, 4 strata; 240 to tune on, 60 held back",
          tone: "blue",
        },
        {
          label: "Agent knobs",
          value: "4",
          detail:
            "model, schema_context, prompt_style, temperature; the static reader credits 3 (18 configurations)",
          tone: "violet",
        },
        {
          label: "Evaluator",
          value: "Exact match",
          detail:
            "normalised text comparison; never executes SQL; no probes shipped",
          tone: "blue",
        },
        {
          label: "Opening card",
          value: "45 · PARTIAL",
          detail:
            "action proceed; ceiling 45 evaluator-unvalidated, not blocking; confidence 0.68",
          tone: "amber",
        },
      ],
      steps: [],
      evidenceState: "scenario-contract",
      evidence: [
        readyCardEvidence,
        scoreTableEvidence,
        "Spider 1.0 benchmark dataset under CC BY-SA 4.0",
      ],
      notes: [
        "Talk track: this is the ready row in the matrix. 45 is the size of the gap the run has to close, not a verdict: calibrate the scorer and the same project reads 86 STRONG (preset checked).",
        "Pillars on the card: agent 70, dataset 98, evaluation 33. The evaluation pillar is low because calibration and probe spread could not be scored without probes, and normalized-exact is flagged a poor ruler for code-sql output.",
        `Provenance: the card was produced at guide revision ${measuredCardRevision} on 2026-09-02. At the deck's cited revision ${guideRevision.slice(0, 8)} the evaluator-unvalidated ceiling is still 45, so the ceiling holds, but the pillar figures were not re-scored there.`,
        "Evidence state stays scenario-contract: the guide's scripts ran over the built demo with a hand-written agent read; no coding agent ran and no baseline was prepared.",
      ],
    },
    {
      id: "test-layers",
      kind: "matrix",
      eyebrow: "VERIFICATION LAYERS",
      title: "Three checks, three different proofs.",
      body: "Passing one check proves only that check - never the next one. Today this repository ships the scenario files, the committed opening cards, and the expected result to compare against; no recorded agent run is included yet. Nothing here requires a prior run: anyone can run all three from a fresh clone - the paid layer with their own approved keys and spend.",
      bullets: [],
      metrics: [],
      testMatrix: [
        {
          layer: "Catalog check",
          action:
            "Validate the repository's own components and data (build.py check), then gate a built demo as self-contained, blind, and able to run (build.py verify)",
          passSupports:
            "The generator is intact and the demo is fit to hand to an agent",
          doesNotProve: "Agent behavior or live value",
        },
        {
          layer: "Phase A (free opening)",
          action: "Fresh coding-agent session performs Inspect and Readiness",
          passSupports:
            "The agent captured readiness matched the published expected result",
          doesNotProve: "Paid baseline or optimization",
        },
        {
          layer: "Phase B (paid optimization)",
          action: "Approved Baseline, Optimize, and Results",
          passSupports: "Live evidence for that approved run",
          doesNotProve: "Universal outcome or production safety",
        },
      ],
      steps: [],
      evidenceState: "scenario-contract",
      evidence: ["Published verification and phase boundaries"],
      notes: [
        "Catalog check is two commands: build.py check validates this repository, build.py verify gates one built demo. Neither runs a coding agent.",
        "Phase A covers Inspect and Readiness. Phase B covers approved Baseline, Optimize, and Results. Phase A and Phase B are this deck's labels for the guide's free and paid halves, not the guide's own terms.",
        "No prior run is needed for any layer; each one can be run today from a fresh clone.",
      ],
    },
    {
      id: "trust-boundary",
      kind: "statement",
      eyebrow: "SECURITY & PROCUREMENT BOUNDARIES",
      title:
        "Phase A is free and local; optimization requires explicit approval.",
      body: "Credentials, paid calls to your model provider or Traigent, moving data out of your environment, installing software, changing production, and optimization each remain separate approval gates. A Phase A result does not authorize Phase B.",
      bullets: [
        "Phase A stops at the first material human decision",
        "Access codes and API keys belong to Phase B, the separately approved paid optimization",
        "No claim of quality, cost, or latency improvement",
        "No production mutation or data movement beyond the approved coding-agent context",
        "The coding-agent service itself may be remote and billed; the human approves that service and the context it receives",
      ],
      metrics: [],
      steps: [],
      evidenceState: "guide-contract",
      sourceRevision: guideRevision,
      evidence: [`Phase A and Phase B boundary at ${guideRef}`],
      notes: [
        "This is the security and procurement slide. Keep the boundary concrete.",
        "Phase A and Phase B are deck vocabulary; the guide speaks of two paid approvals, the provider-paid baseline first and the connected optimization second.",
      ],
    },
    {
      id: "next-step",
      kind: "statement",
      eyebrow: "PRESALES PLAYBOOK & NEXT STEPS",
      title: "How presales engineers run this with prospects today.",
      accent: "run this with prospects",
      body: "Presales can run a live walkthrough using Spider demo presets, or run the free inspection directly inside a prospect repository to surface their readiness score and gap roadmap. Neither path carries a published duration; building a demo needs nothing installed, and scoring all seventeen presets took about two minutes on the maintainers' machine.",
      bullets: [
        "Option 1 (Demo): build a Spider preset (python3 build.py demo --preset ready) and show the journey live",
        "Option 2 (Prospect Repo): paste the single prompt into their agent for a zero-cost readiness card",
        "Executive Deliverable: a 14-check readiness score and concrete gap-remediation plan",
        "Paid Pilot: approve the provider-paid baseline, then the connected optimization separately; the guide's $5.00 default is an execution stop target and re-approval trigger, not a billing cap",
        "Long-term Handover: install traigent-skills (npx skills add Traigent/traigent-skills) for continuous tuning",
      ],
      metrics: [],
      steps: [],
      evidenceState: "guide-contract",
      sourceRevision: guideRevision,
      evidence: [
        `Published guide and scenario handoff boundaries at ${guideRef}; no live outcome claimed`,
      ],
      notes: [
        "The two available paths are alternatives: demo with the Spider benchmark, or run on the customer own project.",
        "The SDK skills are Apache-2.0 documentation; installing skills authorizes nothing - Phase B still needs its own approval.",
        "The two-minute figure is the seventeen-preset scoring sweep recorded in the companion repo's docs/measurements/README.md, not a walkthrough length; do not quote a demo duration.",
      ],
    },
    {
      id: "stage-inspect",
      kind: "statement",
      eyebrow: "STAGE 1 OF 5 - INSPECT",
      title: "Preserve the customer useful work before proposing anything new.",
      body: "The coding agent performs read-only discovery of the project and identifies the selected agent, comparison data, evaluator, and meaningful tunable settings without importing or executing project code.",
      bullets: [
        "Input: the customer project, stated task, and files already present",
        "Agent action: cite the discovered component paths and distinguish real components from temporary substitutes created for the walkthrough",
        "Human role: resolve ambiguous project intent or choose among multiple plausible components",
        "Stage output: each real component marked ✅ (found and validated) or ❗ (missing, invalid, or evidence-limited); any substitute the run generates is listed unmarked under walkthrough setup",
        "Next route: continue to Readiness; do not replace usable material merely to make a demo easier",
      ],
      metrics: [],
      steps: [],
      evidenceState: "guide-contract",
      sourceRevision: guideRevision,
      evidence: [`Inspect-stage contract at ${guideRef}`],
      notes: [
        "Inspect is not a runtime test and does not prove model quality. It establishes what the project has before the guide changes anything.",
        "There are exactly two marks. Synthetic material is never marked as real and validated, and the run never says 3/3 ready when any component is a substitute.",
      ],
    },
    {
      id: "stage-readiness",
      kind: "statement",
      eyebrow: "STAGE 2 OF 5 - READINESS",
      title: "Turn the starting state into a route, not a sales score.",
      body: "The coding agent evaluates the agent, dataset, and evaluator. It may run the evaluator only after reading its code and confirming that exact path stays local, changes nothing outside the run, and never executes generated code or SQL. It then applies caps - score ceilings set by the material - and names the shortest justified next action.",
      bullets: [
        "Ready: explain the opening - the readiness answer produced before any paid work - and stop at the human baseline approval",
        "Missing: derive what can be derived, ask only for an unresolved human or domain choice, create or repair the required dependency, then re-check",
        "Limited evidence: allow only a clearly bounded demonstration or request stronger material",
        "Evaluator quality: calibrate or defer an unvalidated evaluator; inspect, repair, or replace an invalid evaluator, then revalidate before any paid comparison",
        "Evaluator timeout: present the bounded human choice; do not call the evaluator broken merely because it was slow",
        "Candidate code/SQL execution path: end this guide run before candidate output executes; containment design and any restart are separately reviewed outside the guide",
      ],
      metrics: [],
      steps: [],
      evidenceState: "guide-contract",
      sourceRevision: guideRevision,
      evidence: [`Readiness and routing contract at ${guideRef}`],
      notes: [
        "Readiness weights dataset, evaluation, and agent evidence, then applies caps so strength in one pillar cannot hide a broken foundation.",
        "The opening score describes the customer starting point. A later re-score verifies that a remedy cleared its gate; it is not a new claim about the original project.",
      ],
    },
    {
      id: "readiness-scoring",
      kind: "statement",
      eyebrow: "STAGE 2 OF 5 - HOW THE SCORE IS BUILT",
      title: "Fourteen checks, three pillars, one number out of 100.",
      body: "Readiness runs 14 checks across the three things that decide success: your dataset, your evaluation method, and your agent. Each area carries a different weight - dataset the most, because an optimization cannot outrun the material it is measured on. The scorer itself makes no model-provider or Traigent calls.",
      bullets: [
        "Dataset - 40 points: answers to score against; examples to compare on; range of difficulty; repeated or dominant answers; where the rows came from",
        "Evaluation - 35 points: checked on known-good and known-bad; right kind of check for this output; same answer every time; separates good answers from bad",
        "Agent - 25 points: settings-combinations to try; what the model is told and shown; whether the answer shape is pinned down; whether the agent is guaranteed to stop, and what stops it; tools it declares and can reach",
        "Bands: NOT READY 0-29; PARTIAL 30-54; WORKABLE 55-74; STRONG 75-89; EXCELLENT 90-100",
        "Thin-evidence rule: below 0.75 confidence overall or in any area, a score that would land STRONG or EXCELLENT is held at WORKABLE; lower bands are unchanged",
      ],
      metrics: [],
      steps: [],
      evidenceState: "guide-contract",
      sourceRevision: guideRevision,
      evidence: [readinessEvidence],
      notes: [
        "The weighting is the argument: 40 points on the dataset says plainly that optimization cannot outrun the data it is measured on.",
        "Each applicable check is measured, withheld, or not applicable. A withheld check keeps its weight and earns no points; it is not dropped from the denominator to flatter the score.",
        "Confidence is the share of check weight the scorer could actually measure - measurement coverage, not statistical confidence.",
        "The confidence rule is a ceiling, not a floor. It never promotes NOT READY or PARTIAL to WORKABLE.",
      ],
    },
    {
      id: "readiness-ceilings-foundations",
      kind: "matrix",
      eyebrow: "STAGE 2 OF 5 - FOUNDATION CAPS",
      title: "Broken measurement sets the lowest ceilings.",
      body: "A cap is a ceiling on the total score out of 100 - the maximum the evidence allows, applied after the three weighted areas are summed; it is not a deduction. The 45 row is the ready preset's own committed card; the other rows are shipped scorer rules whose Spider example cards exist in the companion repo but are not published in this deck's catalog.",
      bullets: [],
      metrics: [],
      steps: [],
      matrix: [
        {
          startingPoint:
            "The evaluator is unvalidated - no calibration has run - or nothing in the agent varies",
          safestNextStep:
            "Ceiling 45; calibrate the evaluator or wire a setting worth searching. This is the ready preset's opening: 45 PARTIAL, action proceed",
          coverage: "published",
        },
        {
          startingPoint:
            "The evaluator rates a known-bad answer as highly as a known-good answer",
          safestNextStep:
            "Ceiling 25 and BLOCKED; repair and revalidate the evaluator first (preset fake-ruler reads 25, repair-evaluator)",
          coverage: "coverage-target",
        },
        {
          startingPoint:
            "Agent, data, and evaluator are usable and the evaluator has been calibrated; no cap fires",
          safestNextStep:
            "No ceiling from a cap; explain readiness and stop at baseline approval (preset checked reads 86 STRONG, no caps)",
          coverage: "coverage-target",
        },
      ],
      evidenceState: "guide-contract",
      sourceRevision: guideRevision,
      evidence: [readinessEvidence, readyCardEvidence],
      notes: [
        "A capped project is not a failed project. A truthful 45 with a named ceiling is more useful than an unsupported 90.",
        "Only the ready preset has a catalog entry in this deck. fake-ruler and checked have committed cards in the companion repo; cite them from there rather than saying they appear here.",
      ],
    },
    {
      id: "readiness-ceilings-evidence",
      kind: "matrix",
      eyebrow: "STAGE 2 OF 5 - EVIDENCE CAPS",
      title: "Generated data still runs - it only caps the top score.",
      body: "Nothing stops here: the run continues end to end. Rows declared as generated, or an answer key written by a model, only cap how high the score can go until real rows arrive - a caveat for the summary, not a blocker.",
      bullets: [],
      metrics: [],
      steps: [],
      matrix: [
        {
          startingPoint:
            "Every comparison row is declared generated rather than observed",
          safestNextStep:
            "Ceiling 65; label the demo honestly and connect real rows before a production claim",
          coverage: "coverage-target",
        },
        {
          startingPoint:
            "Rows are declared real, but a model generated the answer key",
          safestNextStep:
            "Ceiling 74; compare cautiously and obtain human review before trusting the margin",
          coverage: "coverage-target",
        },
      ],
      evidenceState: "guide-contract",
      sourceRevision: guideRevision,
      evidence: [readinessEvidence],
      notes: [
        "A fully generated dataset caps at 65, so STRONG and EXCELLENT are arithmetically unreachable until the evidence changes.",
      ],
    },
    {
      id: "stage-baseline",
      kind: "statement",
      eyebrow: "STAGE 3 OF 5 - BASELINE",
      title:
        "Measure the current configuration before searching for a better one.",
      body: "Only after the readiness route and explicit human approval does the coding agent run the customer existing local baseline exactly as defined, or, when none exists, prepare the guide fixed grid of 12 configurations, each run once locally. It uses the approved provider credential, dataset, evaluator, and cost limit.",
      bullets: [
        "Human approves the provider, credential path, data boundary, expected calls, and cost cap",
        "A user-owned baseline keeps its exact configuration space and selection logic; it is never padded. When it is too large for the approved budget, the guide proposes a smaller representative subset - disclosed and approved, never silent",
        "Only a missing baseline gets the guide generated 12-configuration local grid",
        "The run records quality plus available cost and latency evidence for that exact setup",
        "Provider errors, missing credentials, or cost-boundary failures stop loudly; access is never invented",
        "Stage output: the saved baseline result and a separate decision on whether the enhanced run is justified",
      ],
      metrics: [],
      steps: [],
      evidenceState: "guide-contract",
      sourceRevision: guideRevision,
      evidence: [
        `Baseline-stage contract at ${guideRef}; no live baseline supplied`,
      ],
      notes: [
        "The coding-agent service itself may already be remote or billed. Baseline is specifically the first model-provider execution stage in this workflow.",
        "An existing baseline is never replaced: even a one-row baseline is preserved unchanged and measured as it stands. Only a truly missing baseline gets the generated grid.",
      ],
    },
    {
      id: "stage-optimize",
      kind: "statement",
      eyebrow: "STAGE 4 OF 5 - OPTIMIZE",
      title:
        "A first taste of optimization - two small runs, not the full engine.",
      body: "After the baseline, one bounded enhanced run starts under its own approval: Traigent tests up to 12 configurations from the approved space, inside a small budget and time box. Results appear in your Traigent portal; the run closes with a recommended next step, and finding no winner is a reported outcome, not a failure.",
      bullets: [
        "Human separately approves Traigent access, provider use, data movement, the trial bound (maximum number of configurations tested), and spend",
        "Only tunable settings proven to change the request actually sent to the model belong in the search space",
        "The baseline result stays unchanged as the reference; every candidate is compared on the same dataset and evaluator",
        "Credential, service, provider, or budget failures stop; no mock or random result replaces them",
        "Stage output: the exact search space submitted, every configuration tested, and its measured scores",
      ],
      metrics: [],
      steps: [],
      evidenceState: "guide-contract",
      sourceRevision: guideRevision,
      evidence: [
        `Optimization-stage contract at ${guideRef}; no enhanced run supplied`,
      ],
      notes: [
        "Baseline approval does not pre-authorize optimization. The second gate is deliberate because the number of calls and the data boundary can change.",
      ],
    },
    {
      id: "selection-and-heldout",
      kind: "journey",
      eyebrow: "STAGES 3 TO 5 - HONEST COMPARISON",
      title:
        "Choose on tuning evidence; check one recommendation on held-out rows.",
      body: "Two small runs, two spaces: the baseline runs your current configuration (or the fixed 12-configuration grid when none exists); the enhanced run tests up to 12 configurations Traigent picks from a larger approved space. One pick comes from the tuning evidence; the held-out rows then score that single pick once - a check of the winner, never part of choosing it.",
      bullets: [],
      metrics: [],
      steps: [
        {
          label: "Measure the baseline",
          detail:
            "Preserve the user existing local baseline exactly, or use the guide 12-configuration default only when missing; any reduction from that target is disclosed and approved first.",
          executor: "Coding agent",
          humanGate: "Human approves spend",
        },
        {
          label: "Run the enhanced search",
          detail:
            "Traigent tests up to 12 configurations from the approved larger space, using the same tuning rows and evaluator.",
          executor: "Traigent service",
          humanGate: "Human separately approves",
        },
        {
          label: "Lock one recommendation",
          detail:
            "Compare baseline and enhanced-run tuning evidence; include the accuracy-versus-cost trade-off (the frontier) when cost is measured; then select without reading held-out scores.",
          executor: "Coding agent",
        },
        {
          label: "Check held-out rows once",
          detail:
            "Score the locked recommendation once on rows no search evaluated; the guide's held-out check uses ten rows, so its statistical confidence is low - the report discloses it.",
          executor: "Coding agent",
          humanGate: "Human reviews evidence",
        },
      ],
      evidenceState: "guide-contract",
      sourceRevision: guideRevision,
      evidence: [`${guideRef} comparison contract`],
      notes: [
        "Selecting the best of several configurations on the same tuning rows partly selects sample noise. Held-out scoring checks that risk; it does not eliminate it or prove generalization.",
        "When the coding agent has seen or authored the reserved rows, the guide calls the result held-back and non-blind rather than a sealed holdout.",
        "Sizes: the Spider build holds back 60 of its 300 rows (HOLDOUT_SHARE 0.2) as the pool; the guide's held-out check scores ten rows from it. This is a bounded sample check, not a claim about every paid first run.",
      ],
    },
    {
      id: "stage-results",
      kind: "statement",
      eyebrow: "STAGE 5 OF 5 - RESULTS",
      title:
        "Report what changed, what it cost, and what the evidence cannot support.",
      body: "The coding agent compares the approved search with the baseline, identifies the supported trade-offs, retains the exact run record, and gives the human a decision rather than an unexplained winning score.",
      bullets: [
        "Compare the recommended configuration with the best baseline; show the quality-cost frontier when cost was measured",
        "Report the one held-out check with its sample-size and non-blind limits; retain the exact run evidence and failures",
        "Human chooses adoption, more evidence, another bounded search, or no change; nothing is applied automatically",
        "State what the run cannot prove: universal quality, production safety, generalization, or a guaranteed business result",
      ],
      metrics: [],
      steps: [],
      evidenceState: "guide-contract",
      sourceRevision: guideRevision,
      evidence: [
        `Results-stage contract at ${guideRef}; no live result artifact supplied`,
      ],
      notes: [
        "The end goal is an explainable decision. A result without its baseline, evidence boundary, and limitations is not a valid first-run outcome.",
        "If the recommended configuration is the one already in use, that is a useful result: the current settings were not shown to be the problem.",
      ],
    },
    {
      id: "published-scenario-catalog",
      kind: "catalog",
      eyebrow: "SCENARIO CATALOG APPENDIX",
      title: "Spider scenario catalog: setup and expected routing.",
      body: "The Spider catalog entry records component setup, the committed opening card, and the tested layer without claiming an unrecorded run.",
      bullets: [],
      metrics: [],
      steps: [],
      catalogView: "setup-and-route",
      catalogSlug: "spider-text-to-sql-benchmark",
      evidenceState: "scenario-contract",
      evidence: [
        "Companion repo preset ready (build.py PRESETS)",
        readyCardEvidence,
        "Spider 1.0 benchmark dataset under CC BY-SA 4.0",
      ],
      notes: [
        "This appendix documents the preset ready configuration for Spider text-to-SQL: exact-match evaluator, no calibration probes, opening card 45 PARTIAL.",
        "The component definitions reflect real SQLite databases and committed Spider queries.",
      ],
    },
    {
      id: "published-scenario-data",
      kind: "catalog",
      eyebrow: "SCENARIO CATALOG APPENDIX",
      title: "Spider scenario catalog: data characteristics and boundaries.",
      body: "The Spider benchmark data characteristics, the text-comparison evaluation method, and the evidence boundaries stay explicit.",
      bullets: [],
      metrics: [],
      steps: [],
      catalogView: "data-and-limits",
      catalogSlug: "spider-text-to-sql-benchmark",
      evidenceState: "scenario-contract",
      evidence: [
        "Companion repo preset ready (build.py PRESETS)",
        "Spider 1.0 benchmark dataset under CC BY-SA 4.0",
      ],
      notes: [
        "Spider data is licensed under CC BY-SA 4.0 with attribution in ATTRIBUTION.txt.",
        "The ready preset scores by normalised exact match against the gold query text. Execution accuracy against live SQLite exists as a separate evaluator, and the guide stops before running it.",
      ],
    },
  ],
} satisfies PresentationSpec;

const coreSlideIds = [
  "ready-to-optimize",
  "shared-control",
  "one-customer-prompt",
  "different-starting-points",
  "spider-repo-overview",
  "spider-presets-matrix",
  "worked-case-ready",
  "test-layers",
  "trust-boundary",
  "next-step",
] as const;

const appendixSlideIds = [
  "stage-inspect",
  "stage-readiness",
  "readiness-scoring",
  "readiness-ceilings-foundations",
  "readiness-ceilings-evidence",
  "stage-baseline",
  "stage-optimize",
  "selection-and-heldout",
  "stage-results",
  "published-scenario-catalog",
  "published-scenario-data",
] as const;

const sourceSlides: PresentationSpec["slides"] = rawPresentation.slides;
const slidesById = new Map(sourceSlides.map((slide) => [slide.id, slide]));
const slideForId = (id: string): PresentationSpec["slides"][number] => {
  const slide = slidesById.get(id);
  if (slide === undefined) {
    throw new Error(`Presentation order references missing slide ${id}`);
  }
  return slide;
};
const orderedSlideIds = [...coreSlideIds, ...appendixSlideIds];
const orderedSlideIdSet = new Set<string>(orderedSlideIds);
if (
  orderedSlideIdSet.size !== sourceSlides.length ||
  sourceSlides.some((slide) => !orderedSlideIdSet.has(slide.id))
) {
  throw new Error("Presentation order must include every slide exactly once");
}
const coreSlides = coreSlideIds.map((id) => ({
  ...slideForId(id),
  section: "core" as const,
}));
const appendixSlides = appendixSlideIds.map((id) => ({
  ...slideForId(id),
  section: "appendix" as const,
}));

export const coreSlideCount = coreSlides.length;
export const presentation = parsePresentation({
  ...rawPresentation,
  slides: [...coreSlides, ...appendixSlides],
});
export { customerPrompt };
