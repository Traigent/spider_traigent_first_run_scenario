import { parsePresentation, type PresentationSpec } from "./model";

const customerPrompt =
  "Help me run my first Traigent optimization.\nClone https://github.com/Traigent/traigent-first-run and follow GUIDE.md.";

const guideRevision = "75d338c31c97643c6a6d28a6aeef582d7b938db8";
const readinessEvidence = `Traigent/traigent-first-run@${guideRevision.slice(0, 8)} readiness scorer`;

const rawPresentation = {
  schemaVersion: 2,
  title: "Traigent First Run: Presales Showcase",
  subtitle:
    "How Traigent Guided First Run leads customer projects from inspection to graded readiness, gap repair, and a justified next step",
  scenario: {
    slug: "spider-text-to-sql-benchmark",
    legacyId: 1,
    title: "Spider Text-to-SQL First-Run Scenario",
    expectedBand: "EXCELLENT" as const,
    phase: "phase-a-opening" as const,
  },
  catalog: [
    {
      slug: "spider-text-to-sql-benchmark",
      label: "Spider Text-to-SQL Preset: Ready",
      publication: "published" as const,
      startingState:
        "Ready: complete agent, 300 Spider questions across 18 SQLite databases, and execution-match evaluator present.",
      components: [
        "Agent (ready): tunable temperature, model, prompt template, and SQL dialect",
        "Dataset (ready): 300 Spider questions and queries across 18 SQLite schemas",
        "Evaluator (ready): SQL execution accuracy on target database",
        "Calibration: deterministic test queries checking table structures and output rows",
      ],
      dataset:
        "Spider 1.0 benchmark data (Yu et al., EMNLP 2018) under CC BY-SA 4.0; 300 questions across 18 SQLite databases, with easy, medium, hard, and extra-hard strata. Limitations: text-to-SQL specific domain.",
      evaluator:
        "Execution match against live SQLite database; evaluates whether the candidate query returns identical result sets to gold SQL.",
      expectedRouting:
        "Preset ready: band EXCELLENT, status OK, action continue to baseline approval; no foundation caps trigger.",
      testedLayer:
        "First-run discovery, static readiness scoring, and baseline preparation on real SQL data. No coding agent run is claimed in this release.",
      notProven: [
        "Universal model accuracy across unseen schemas",
        "Production deployment performance on non-SQLite engines",
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
      body: "Traigent Guided First Run meets customer repositories where they actually are. It inspects without touching production or spending money, grades readiness honestly, repairs evaluation and data gaps, and leads to an approved, bounded first run.",
      bullets: [],
      metrics: [],
      steps: [],
      evidenceState: "guide-contract",
      sourceRevision: guideRevision,
      evidence: [
        `Guided First Run contract at Traigent/traigent-first-run@${guideRevision.slice(0, 8)}; no fresh coding-agent run supplied`,
      ],
      notes: [
        "Lead with honest routing: we do not demand a clean, pre-built benchmark or a perfect agent.",
        "The customer own assets determine their score and route; we never sell a guaranteed uplift.",
        "Talk track: the deliverable of the first run is a truthful position and a next step, not a score.",
      ],
    },
    {
      id: "shared-control",
      kind: "journey",
      eyebrow: "AGENT-LED, HUMAN-GOVERNED",
      title: "Five stages. Three actors. Human approval stays explicit.",
      body: "Every project enters Inspect. Gaps loop through transparent diagnosis and coherent repair. Ready foundations move only after explicit approval. The coding agent coordinates, the human governs, and Traigent runs only the approved managed optimization.",
      bullets: [],
      metrics: [],
      steps: [
        {
          label: "1 Inspect",
          detail:
            "Find the agent, dataset, and evaluator; preserve what is usable. Reads files locally only: no project code runs, no provider or Traigent calls.",
          executor: "Coding agent",
        },
        {
          label: "2 Readiness",
          detail:
            "Score the evidence, apply caps - score ceilings set by the material - and explain the safest next route. Stop before paid work when the evaluator cannot tell good from bad answers.",
          executor: "Coding agent",
          humanGate: "Human decides",
        },
        {
          label: "3 Baseline",
          detail:
            "Preserve and measure the existing baseline, or prepare a fixed 12-configuration grid only when none exists. The first model-provider stage.",
          executor: "Coding agent",
          humanGate: "Human approves",
        },
        {
          label: "4 Optimize",
          detail:
            "Search the approved space and compare it with the preserved baseline.",
          executor: "Traigent service",
          humanGate: "Human approves",
        },
        {
          label: "5 Results",
          detail:
            "Report the comparison, cost evidence, and limits, closing with one recommended next action; the human decides.",
          executor: "Coding agent",
          humanGate: "Human reviews",
        },
      ],
      evidenceState: "guide-contract",
      sourceRevision: guideRevision,
      evidence: [
        `First-run stages and approval boundaries at Traigent/traigent-first-run@${guideRevision.slice(0, 8)}`,
      ],
      notes: [
        "The boundary the presenter must draw: stages 1-2 make no calls to the customer project-model provider or the Traigent service and incur no spend with either.",
        "Stage 3 is the first project-model stage, on the customer approved key and cost boundary.",
        "Stage 4 is a separate approval from stage 3 on purpose: the baseline preserves the user existing local space, while enhanced search explores a broader space.",
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
        `Published real-project handoff at Traigent/traigent-first-run@${guideRevision.slice(0, 8)}; outcome not demonstrated here`,
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
      evidence: [
        `Route behavior at Traigent/traigent-first-run@${guideRevision.slice(0, 8)}`,
      ],
      notes: [
        "Do not promise an Excellent opening. A gap, cap, repair, or stop can be the correct and useful outcome for the material the customer brought.",
        "The six bullets summarize next-action families; they are not an exhaustive taxonomy of every project condition.",
      ],
    },
    {
      id: "spider-repo-overview",
      kind: "statement",
      eyebrow: "COMPANION REPOSITORY · SPIDER SCENARIOS",
      title: "The Spider companion repo: instant, realistic SQL demo projects.",
      body: "https://github.com/Traigent/spider_traigent_first_run_scenario generates complete, offline text-to-SQL projects from real Spider data. Presales engineers use it to demonstrate first-run onboarding live in under 15 minutes without touching customer code or requiring NDAs.",
      bullets: [
        "Standard-library build CLI: python3 build.py demo --preset ready --out ~/demos/first-try",
        "Real benchmark data: 300 Spider questions, 18 SQLite schemas, easy-to-extra-hard difficulty",
        "100% offline & self-contained: agent inspects a realistic user project, never the scenario generator",
        "Realistic agent: text-to-SQL agent with tunable model, prompt, dialect, and temperature settings",
        "Real evaluation: execution-match evaluator running queries against live SQLite databases",
        "No cloud keys needed: inspect and score readiness completely free and local",
      ],
      metrics: [],
      steps: [],
      evidenceState: "scenario-contract",
      evidence: [
        "spider_traigent_first_run_scenario README and build CLI",
        "Spider 1.0 benchmark dataset under CC BY-SA 4.0",
      ],
      notes: [
        "Presales positioning: Spider is a scenario generator for demonstrations and testing, while traigent-first-run is the customer guide.",
        "This repository gives presales an offline, reproducible benchmark to demonstrate onboarding live.",
      ],
    },
    {
      id: "spider-presets-matrix",
      kind: "matrix",
      eyebrow: "TESTING ONBOARDING RESILIENCE",
      title: "Seventeen presets to test every onboarding branch live.",
      body: "The Spider scenario bank provides 17 presets covering every real-world condition. Presales engineers can run the exact customer prompt against any preset to demonstrate how first-run guides, grades, and repairs live.",
      bullets: [],
      metrics: [],
      steps: [],
      scenarioMatrix: [
        {
          family: "Preset: ready / best-case",
          setup:
            "Agent, dataset, and evaluator are present and tunable in a complete text-to-SQL demo project",
          expectedRoute:
            "Demonstrate the happy path: inspect, grade readiness, and continue to baseline approval with clear human gates",
          coverage: "published",
        },
        {
          family: "Preset: no-eval",
          setup: "Usable agent and data, but no evaluator to score outputs",
          expectedRoute:
            "Show how first-run identifies the missing scorer, builds or repairs the dependency, and re-checks before paid comparison",
          coverage: "coverage-target",
        },
        {
          family: "Preset: no-data",
          setup:
            "Agent and evaluator are present, but no comparison rows are available",
          expectedRoute:
            "Show onboarding gap fill for missing dataset material, then rerun readiness before baseline",
          coverage: "coverage-target",
        },
        {
          family: "Preset: fake-ruler",
          setup:
            "Evaluator marks almost everything correct, so it cannot separate good from bad outputs",
          expectedRoute:
            "Show readiness caps and blocker behavior when evaluation quality is not credible",
          coverage: "coverage-target",
        },
        {
          family: "Preset: wrong-answers",
          setup:
            "Rows exist, but each expected answer is intentionally mismatched",
          expectedRoute:
            "Show evidence-first diagnosis and repair of broken labels so grading becomes trustworthy",
          coverage: "coverage-target",
        },
      ],
      evidenceState: "scenario-contract",
      evidence: [
        "spider_traigent_first_run_scenario preset catalog",
        "traigent-first-run readiness, caps, and progression gates",
      ],
      notes: [
        "Presales script: choose a preset, run the same customer prompt, and narrate the route as evidence-driven behavior instead of a canned success path.",
        "This slide is about behavior coverage and trust boundaries, not promised uplift metrics.",
      ],
    },
    {
      id: "case-46",
      kind: "evidence",
      eyebrow: "WORKED DEMO EVIDENCE",
      title: "Worked proof: text-to-SQL project under first-run inspection.",
      body: "A complete demonstration project under first-run inspection. The assistant identifies all components, verifies execution safety, and scores readiness before proposing a baseline.",
      bullets: [],
      metrics: [
        {
          label: "Rows",
          value: "300",
          detail: "18 SQLite schemas, 4 difficulty strata",
          tone: "blue",
        },
        {
          label: "Agent knobs",
          value: "4",
          detail: "model, prompt, temperature, dialect",
          tone: "violet",
        },
        {
          label: "Evaluator",
          value: "Execution",
          detail: "SQL result-set execution match",
          tone: "blue",
        },
        {
          label: "Expected route",
          value: "Baseline approval",
          detail: "Score 90+, status OK, not blocked",
          tone: "amber",
        },
      ],
      steps: [],
      evidenceState: "scenario-contract",
      evidence: [
        "spider_traigent_first_run_scenario preset ready",
        "Spider 1.0 benchmark dataset under CC BY-SA 4.0",
      ],
      notes: [
        "Talk track: this is the ready-components route in the matrix, showing what a complete project looks like.",
        "Expected top band because this case starts complete. It is a reference, not a product success threshold.",
      ],
    },
    {
      id: "test-layers",
      kind: "matrix",
      eyebrow: "VERIFICATION LAYERS",
      title: "Three checks, three different proofs.",
      body: "Passing one check proves only that check - never the next one. Today this repository ships the scenario files and the expected result to compare against; no recorded agent run is included yet. Nothing here requires a prior run: anyone can run all three from a fresh clone - the paid layer with their own approved keys and spend.",
      bullets: [],
      metrics: [],
      testMatrix: [
        {
          layer: "Catalog check",
          action:
            "Validate scenario package structure and data integrity (build.py check)",
          passSupports: "Package is structurally ready to prepare",
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
        "Catalog check validates the package; it does not run a coding agent.",
        "Phase A covers Inspect and Readiness. Phase B covers approved Baseline, Optimize, and Results.",
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
      evidence: [
        `Phase A and Phase B boundary at Traigent/traigent-first-run@${guideRevision.slice(0, 8)}`,
      ],
      notes: [
        "This is the security and procurement slide. Keep the boundary concrete.",
      ],
    },
    {
      id: "next-step",
      kind: "statement",
      eyebrow: "PRESALES PLAYBOOK & NEXT STEPS",
      title: "How presales engineers run this with prospects today.",
      accent: "run this with prospects",
      body: "Presales can run a live 15-minute walkthrough using Spider demo presets, or run the free 5-minute inspection directly inside a prospect repository to uncover their readiness score and gap roadmap.",
      bullets: [
        "Option 1 (Demo): build a Spider preset (python3 build.py demo --preset ready) and show the journey live",
        "Option 2 (Prospect Repo): paste the single prompt into their agent for a zero-cost readiness card",
        "Executive Deliverable: a 14-check readiness score and concrete gap-remediation plan",
        "Paid Pilot: approve a $5-budget baseline and connected optimization",
        "Long-term Handover: install traigent-skills (npx skills add Traigent/traigent-skills) for continuous tuning",
      ],
      metrics: [],
      steps: [],
      evidenceState: "guide-contract",
      sourceRevision: guideRevision,
      evidence: [
        `Published guide and scenario handoff boundaries at Traigent/traigent-first-run@${guideRevision.slice(0, 8)}; no live outcome claimed`,
      ],
      notes: [
        "The two available paths are alternatives: demo with the Spider benchmark, or run on the customer own project.",
        "The SDK skills are Apache-2.0 documentation; installing skills authorizes nothing - Phase B still needs its own approval.",
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
        "Stage output: a list of the components found, each marked present, limited, missing, or invalid",
        "Next route: continue to Readiness; do not replace usable material merely to make a demo easier",
      ],
      metrics: [],
      steps: [],
      evidenceState: "guide-contract",
      sourceRevision: guideRevision,
      evidence: [
        `Inspect-stage contract at Traigent/traigent-first-run@${guideRevision.slice(0, 8)}`,
      ],
      notes: [
        "Inspect is not a runtime test and does not prove model quality. It establishes what the project has before the guide changes anything.",
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
      evidence: [
        `Readiness and routing contract at Traigent/traigent-first-run@${guideRevision.slice(0, 8)}`,
      ],
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
      body: "A cap is a ceiling on the total score out of 100 - the maximum the evidence allows, applied after the three weighted areas are summed; it is not a deduction. The ready row matches the worked example; the other rows are shipped scorer rules whose example scenarios are planned; not yet published.",
      bullets: [],
      metrics: [],
      steps: [],
      matrix: [
        {
          startingPoint: "Agent, data, and evaluator are usable; no cap fires",
          safestNextStep:
            "No ceiling from a cap; explain readiness and stop at baseline approval",
          coverage: "published",
        },
        {
          startingPoint:
            "The evaluator rates a known-bad answer as highly as a known-good answer",
          safestNextStep:
            "Ceiling 25 and BLOCKED; repair and revalidate the evaluator first",
          coverage: "coverage-target",
        },
        {
          startingPoint:
            "The evaluator is unvalidated, or nothing in the agent varies",
          safestNextStep:
            "Ceiling 45; validate the evaluator or wire a setting worth searching",
          coverage: "coverage-target",
        },
      ],
      evidenceState: "guide-contract",
      sourceRevision: guideRevision,
      evidence: [readinessEvidence],
      notes: [
        "A capped project is not a failed project. A truthful 65 with visible limits is more useful than an unsupported 90.",
        "Only the ready-reference route has a downloadable scenario here. Do not say the other rows passed a public scenario test.",
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
        `Baseline-stage contract at Traigent/traigent-first-run@${guideRevision.slice(0, 8)}; no live baseline supplied`,
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
        `Optimization-stage contract at Traigent/traigent-first-run@${guideRevision.slice(0, 8)}; no enhanced run supplied`,
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
            "Score the locked recommendation once on rows no search evaluated; small held-out sets mean low statistical confidence - the report discloses it.",
          executor: "Coding agent",
          humanGate: "Human reviews evidence",
        },
      ],
      evidenceState: "guide-contract",
      sourceRevision: guideRevision,
      evidence: [
        `Traigent/traigent-first-run@${guideRevision.slice(0, 8)} comparison contract`,
      ],
      notes: [
        "Selecting the best of several configurations on the same tuning rows partly selects sample noise. Held-out scoring checks that risk; it does not eliminate it or prove generalization.",
        "When the coding agent has seen or authored the reserved rows, the guide calls the result held-back and non-blind rather than a sealed holdout.",
        "This is a bounded sample check, not a claim that every paid first run uses all 120 rows.",
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
        `Results-stage contract at Traigent/traigent-first-run@${guideRevision.slice(0, 8)}; no live result artifact supplied`,
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
      body: "The published Spider catalog entry records component setup, expected routing, and tested layers without claiming an unrecorded run.",
      bullets: [],
      metrics: [],
      steps: [],
      catalogView: "setup-and-route",
      catalogSlug: "spider-text-to-sql-benchmark",
      evidenceState: "scenario-contract",
      evidence: [
        "spider_traigent_first_run_scenario preset ready",
        "Spider 1.0 benchmark dataset under CC BY-SA 4.0",
      ],
      notes: [
        "This appendix documents the preset ready configuration for Spider text-to-SQL.",
        "The component definitions reflect real SQLite databases and committed Spider queries.",
      ],
    },
    {
      id: "published-scenario-data",
      kind: "catalog",
      eyebrow: "SCENARIO CATALOG APPENDIX",
      title: "Spider scenario catalog: data characteristics and boundaries.",
      body: "The Spider benchmark data characteristics, execution evaluation methodology, and evidence boundaries stay explicit.",
      bullets: [],
      metrics: [],
      steps: [],
      catalogView: "data-and-limits",
      catalogSlug: "spider-text-to-sql-benchmark",
      evidenceState: "scenario-contract",
      evidence: [
        "spider_traigent_first_run_scenario preset ready",
        "Spider 1.0 benchmark dataset under CC BY-SA 4.0",
      ],
      notes: [
        "Spider data is licensed under CC BY-SA 4.0 with attribution in ATTRIBUTION.txt.",
        "Execution accuracy is measured against live SQLite database schemas.",
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
  "case-46",
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
