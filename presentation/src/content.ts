import {
  parsePresentation,
  type PresentationInput,
  type PresentationSpec,
  type SlideInput,
} from "./model";

// The two-line prompt from README.md "Start with one prompt", verbatim.
const customerPrompt =
  "Help me run my first Traigent optimization.\nClone https://github.com/Traigent/traigent-first-run and follow GUIDE.md.";

const guideRevision = "75d338c31c97643c6a6d28a6aeef582d7b938db8";

// Repository-relative paths of every guide file a slide may cite.
const README = "README.md";
const GUIDE = "GUIDE.md";
const SKILL = "skills/traigent-first-run/SKILL.md";
const GLOSSARY = "skills/traigent-first-run/references/glossary.md";
const RUN_SAFETY = "skills/traigent-first-run/references/run-safety.md";
const SDK_EXECUTION = "skills/traigent-first-run/references/sdk-execution.md";
const EVALUATION =
  "skills/traigent-first-run/references/evaluation-and-dataset.md";
const READINESS = "skills/traigent-first-run/scripts/readiness.py";
const REQUIREMENTS =
  "skills/traigent-first-run/assets/requirements-first-run.txt";

// The five readiness bands, from readiness.py BAND_THRESHOLDS. Drawn on two
// slides: once on their own, once with the cap ceilings pinned to them.
const readinessBands = [
  { label: "Not ready", from: 0, to: 29, tone: "amber" },
  { label: "Partial", from: 30, to: 54, tone: "amber" },
  { label: "Workable", from: 55, to: 74, tone: "blue" },
  { label: "Strong", from: 75, to: 89, tone: "blue" },
  { label: "Excellent", from: 90, to: 100, tone: "violet" },
] as const;

// The deck is delivered live to customers. Each slide carries one visual and
// a few short lines the room can scan while the presenter talks; the talk
// track and every detail cut from the slide live in the speaker notes. Every
// fact traces to the guide at the revision above, and the deck records no run
// of its own.
const rawPresentation = {
  schemaVersion: 4,
  title: "Traigent Guided First Run",
  subtitle:
    "How your coding assistant runs your first Traigent optimization on the project you already have, and what you see, approve and keep along the way.",
  source: {
    repository: "Traigent/traigent-first-run",
    revision: guideRevision,
    files: [
      README,
      GUIDE,
      SKILL,
      GLOSSARY,
      RUN_SAFETY,
      SDK_EXECUTION,
      EVALUATION,
      READINESS,
      REQUIREMENTS,
    ],
  },
  slides: [
    // ------------------------------------------------------------------
    // Overview
    // ------------------------------------------------------------------
    {
      id: "ready-to-optimize",
      kind: "hero",
      eyebrow: "TRAIGENT GUIDED FIRST RUN",
      title:
        "Start with the project you have. Leave with a justified next step.",
      accent: "justified next step",
      body: "A public guide your coding assistant follows to run your first Traigent optimization in one sitting, on your own project.",
      sources: [
        `${README} · Traigent - First Run`,
        `${GUIDE} · Traigent First Run - Assistant Guide`,
      ],
      notes: [
        "Talk track: the guide does not need a clean benchmark or a finished agent. It meets the project where it is, keeps what is real, tells you plainly what is missing, and ends with one measured comparison and one recommended next step.",
        "Nothing is paid for until the customer approves it, and a result that shows no improvement is reported as exactly that. Never promise an uplift; the guide itself forbids it.",
        "Everything on these slides comes from the public guide at the revision printed in each footer. The deck records no run of its own.",
      ],
    },
    {
      id: "what-the-guide-does",
      kind: "tiles",
      eyebrow: "IN ONE SENTENCE",
      title: "It meets your project where it is.",
      body: "Four promises the guide makes before anything runs.",
      tiles: [
        {
          icon: "🔍",
          label: "Starts from today",
          detail: "Reads what your project already has.",
        },
        {
          icon: "✅",
          label: "Keeps what is real",
          detail: "Your data, grading and settings are preserved.",
        },
        {
          icon: "❗",
          label: "Says what is missing",
          detail: "Gaps are named plainly, never papered over.",
        },
        {
          icon: "🎯",
          label: "Ends with one step",
          detail: "One measured comparison, one recommended next action.",
        },
      ],
      sources: [
        `${README} · Traigent - First Run`,
        `${README} · What the run does`,
      ],
      notes: [
        "Talk track: these four tiles are the whole promise. Everything that follows is how the guide keeps each one.",
        "'Preserved' is literal: the customer's dataset, evaluator and settings are validated and kept; the guide never rewrites originals. Anything it writes for the walkthrough is listed separately as a substitute.",
        "'One next action' means exactly one, with its reason and scope. Never a menu, never a guaranteed gain.",
      ],
    },
    {
      id: "the-words-your-project",
      kind: "tiles",
      eyebrow: "BEFORE WE START · YOUR SIDE",
      title: "Three words for what you already have.",
      body: "None of these assumes prior knowledge of Traigent.",
      tiles: [
        {
          icon: "🤖",
          label: "Coding assistant",
          detail: "Claude Code, Cursor, Codex or Gemini CLI: it does the work.",
        },
        {
          icon: "🧩",
          label: "Agent",
          detail: "The program in your project that calls a language model.",
        },
        {
          icon: "📚",
          label: "Dataset and evaluator",
          detail:
            "Examples with expected answers, and the method that grades them.",
        },
      ],
      sources: [`${GLOSSARY} · Core terms`, `${README} · What the run does`],
      notes: [
        "Presenter: read this slide and the next slowly if the room has not seen Traigent before. Every later slide leans on these six terms.",
        "The coding assistant is a tool that reads the project and runs commands on the customer's instruction. It does the work in this guide; Traigent's own service appears only in stage 4, to run the managed search.",
        "The agent is the thing being optimized: whatever program in the project calls a language model to do a task.",
        "A dataset is examples of the task, each with the answer the customer expects. The evaluator is the method that grades an agent's answer against that expectation.",
      ],
    },
    {
      id: "the-words-of-the-run",
      kind: "tiles",
      eyebrow: "BEFORE WE START · THE RUN'S SIDE",
      title: "Three words for what the run produces.",
      body: "Every later slide leans on these.",
      tiles: [
        {
          icon: "⚙️",
          label: "Configuration and baseline",
          detail:
            "One setting of the knobs; the baseline is today's setting, measured.",
        },
        {
          icon: "📊",
          label: "Readiness score and cap",
          detail: "A number out of 100; a cap is a named ceiling.",
        },
        {
          icon: "🔒",
          label: "Held-out rows and portal",
          detail:
            "Rows kept aside for one final check; Traigent's web record of runs.",
        },
      ],
      sources: [`${GLOSSARY} · Core terms`],
      notes: [
        "A configuration is one setting of the agent's adjustable knobs: which model, which prompt style, what temperature. The baseline is the configuration in use today, measured before anything changes.",
        "The readiness score says how well the dataset, evaluator and agent can support a fair comparison. A cap is a ceiling on that number, set by one named weakness.",
        "Held-out rows are kept aside during tuning and used once, at the end, to check the recommended configuration. The portal is Traigent's web service where connected runs are recorded.",
        "If someone asks what 'optimization' means here: trying a bounded set of configurations of the same agent on the same examples, and reporting which one measured best and at what cost.",
      ],
    },
    {
      id: "one-customer-prompt",
      kind: "handoff",
      eyebrow: "ONE PROMPT",
      title: "One prompt starts everything.",
      body: "Paste it into your coding assistant. It clones the guide, reads your project and works in its own separate environment.",
      quote: customerPrompt,
      bullets: [
        "Clones the guide, not into your project",
        "Reads your project before proposing anything",
        "Installs into its own .venv-traigent, never yours",
        "Stops and says so if that environment exists",
      ],
      sources: [
        `${README} · Start with one prompt`,
        `${GUIDE} · Keep the guide source separate from the project being optimized`,
      ],
      notes: [
        "The quote is the exact two-line prompt from the guide's README. It is pasted as written.",
        "The guide clone is not the project being optimized; the assistant resolves the customer's project root and agent at run time. If .venv-traigent already exists or cannot be created, the assistant stops and says so rather than working around it.",
        "Prefer an install? 'npx skills add Traigent/traigent-first-run', then ask 'Use $traigent-first-run to run my first Traigent optimization.' Node.js is needed only for that command, not for the run. The installed skill keeps the customer's project as the working directory; nothing is cloned into it.",
      ],
    },
    {
      id: "four-asks",
      kind: "tiles",
      eyebrow: "WHAT IT ASKS YOU",
      title: "The assistant asks you four things. Nothing else.",
      body: "Everything else it works out from your project or the guide.",
      tiles: [
        {
          icon: "🎯",
          label: "Which agent",
          detail:
            "Confirm the one candidate, or choose between several. Asked once.",
        },
        {
          icon: "🔑",
          label: "Your provider key",
          detail: "Pasted into a local .env only you can read. Never in chat.",
        },
        {
          icon: "💳",
          label: "Approval to spend",
          detail: "Before any paid call or any data leaving your machine.",
        },
        {
          icon: "🛡️",
          label: "Approval to change",
          detail:
            "Before touching your real answers, grading rules, or anything destructive.",
        },
      ],
      sources: [
        `${README} · Start with one prompt`,
        `${SKILL} · Action authorization`,
      ],
      notes: [
        "Those four asks are the whole list. With one credible agent the assistant names it and asks for confirmation; with several it asks the customer to choose. Once chosen, it never asks again.",
        "The provider key goes into a local .env file that only the customer can read and that Git ignores. The assistant never asks for a secret in chat.",
        "Approval is asked before it happens for any paid model call and for any step that sends data outside the machine; separately, before any change to real examples, expected answers or grading rules, and before anything destructive or production-affecting.",
        "One more question can come up, and only when nothing in the project explains the task: what should the agent do? That is covered on the starting-point slide.",
      ],
    },
    {
      id: "shared-control",
      kind: "journey",
      eyebrow: "THE FIVE STAGES",
      title: "Five stages. Two paid approvals. You decide at the end.",
      body: "The assistant announces each stage as Stage N/5 and never asks you to approve safe, read-only work.",
      steps: [
        {
          label: "Inspect",
          detail: "Reads your project. Nothing runs, nothing is sent anywhere.",
          executor: "Coding assistant",
        },
        {
          label: "Readiness",
          detail: "Scores what it found out of 100. Free and local.",
          executor: "Coding assistant",
        },
        {
          label: "Baseline",
          detail:
            "Measures your current configuration on your own provider key.",
          executor: "Coding assistant",
          humanGate: "Approval 1 · your key",
        },
        {
          label: "Optimize",
          detail: "Traigent runs a bounded search for a better configuration.",
          executor: "Traigent service",
          humanGate: "Approval 2 · Traigent key",
        },
        {
          label: "Results",
          detail:
            "Compares the two, names the limits, recommends one next step.",
          executor: "Coding assistant",
          humanGate: "You decide",
        },
      ],
      sources: [
        `${SKILL} · Opening message`,
        `${GUIDE} · User-facing promise`,
        `${GUIDE} · Default run`,
      ],
      notes: [
        "Stages 1 and 2 make no provider or Traigent calls and spend nothing. Stage 3 is the first paid stage, on the customer's own key and stop target. Only after that result does the assistant ask for a Traigent key.",
        "Stage 4 is a separate approval on purpose: the baseline stays inside the customer's own settings, the search explores a broader space, and Traigent's service enters only here.",
        "The assistant stops only for a real choice between agents, one question about the task when nothing in the project explains it, a key, a paid or data-sending step, a change to real answers or grading rules, or a destructive change. Do not present Readiness as something the customer approves.",
        "Stage 5 also hands over the Traigent optimization skills, so the customer can continue on their full dataset without the guide.",
      ],
    },
    {
      id: "free-first-paid-later",
      kind: "columns",
      eyebrow: "WHEN MONEY ENTERS",
      title: "Free first. Paid only after you approve.",
      body: "You see a real number from your own project before deciding whether to register with Traigent at all.",
      columns: [
        {
          heading: "Free and local",
          tone: "blue",
          items: [
            "Inspect and readiness",
            "Environment setup and validation",
            "No provider or Traigent calls",
            "No account needed",
          ],
        },
        {
          heading: "Approval 1 · your key",
          tone: "amber",
          items: [
            "Baseline on your provider key",
            "Preview shown before paying",
            "$5.00 default stop target",
            "Result on screen before any Traigent key",
          ],
        },
        {
          heading: "Approval 2 · Traigent key",
          tone: "violet",
          items: [
            "Asked for only after the baseline result",
            "Its own approval card",
            "Bounded search, up to 12 configurations",
            "Never pre-approved by approval 1",
          ],
        },
      ],
      sources: [
        `${README} · What the run does`,
        `${RUN_SAFETY} · Approval and budgets`,
        `${README} · Requirements`,
      ],
      notes: [
        "This is the procurement slide. Keep it concrete: provider key first, Traigent key after the result, two separate approvals, one stop target.",
        "The $5.00 default is the guide's own number and the only price the deck quotes. It is a conservative control the run stops at and a re-approval trigger, not a guaranteed billing cap.",
        "Local is not free: the baseline's provider calls spend from the same approved total. The baseline needs no Traigent account, which is why the customer sees a real number before deciding whether to register.",
      ],
    },
    {
      id: "your-starting-point",
      kind: "matrix",
      eyebrow: "WHAT HAPPENS IN YOUR SITUATION",
      title: "Every starting point is supported. None is a failure.",
      body: "What exists is kept and marked ✅ real or ❗ missing. Anything written for the walkthrough is listed as a substitute.",
      matrix: [
        {
          startingPoint: "Agent, dataset and evaluator all present",
          safestNextStep:
            "All three validated and preserved; the run goes straight to the baseline approval.",
        },
        {
          startingPoint: "Agent, but no examples or expected answers",
          safestNextStep:
            "One question first: go ahead with written examples, or point it at your data.",
        },
        {
          startingPoint: "Agent and examples, but no grading method",
          safestNextStep:
            "One question; then a proposed evaluator, checked on known answers, labelled a starting point.",
        },
        {
          startingPoint: "Nothing yet, or a placeholder agent",
          safestNextStep:
            "One question: what should the agent do? Then a walkthrough set is prepared, labelled as such.",
        },
      ],
      sources: [
        `${GUIDE} · Traigent First Run - Assistant Guide`,
        `${README} · What the run does`,
        `${SKILL} · One ask for every gap`,
      ],
      notes: [
        "This is the slide for 'but our project is not ready'. Every row is a supported starting point; none is a failure. One question per gap, however many pieces are missing; the assistant never guesses what the agent is for.",
        "Row 1: the evaluator is checked against answers already known to be right and wrong before anything is paid for.",
        "Row 2: before anything is written the customer is told what was not found, that written examples are weaker evidence than examples from their product, and given two answers: go ahead, or point the assistant at their data.",
        "Row 3: the proposed grading method fits the task, is checked on known-right and known-wrong answers, and is labelled a starting point, not the customer's grading policy.",
        "Row 4: a placeholder agent that echoes its input or returns a constant counts as nothing. The assistant asks one question and waits, then prepares a coherent agent, dataset and evaluator for the walkthrough. That result demonstrates the workflow, not production performance.",
      ],
    },
    {
      id: "when-material-is-weak",
      kind: "tiles",
      eyebrow: "WHAT HAPPENS IN YOUR SITUATION · WEAK MATERIAL",
      title: "Too small, corrupted, or off-task? You get three exits.",
      body: "The assistant shows the evidence first. Your originals are never rewritten.",
      tiles: [
        {
          icon: "🛠️",
          label: "Repair a copy",
          detail: "Fix a working copy, then re-check it.",
        },
        {
          icon: "🧪",
          label: "Continue as demo",
          detail: "Go on with the limit stated in the report.",
        },
        {
          icon: "⏸️",
          label: "Pause",
          detail: "Stop here and come back with better material.",
        },
      ],
      sources: [
        `${README} · What the run does`,
        `${SKILL} · One ask for every gap`,
      ],
      notes: [
        "This row covers a dataset or evaluator that exists but is too small, corrupted, repetitive, or does not match the task.",
        "The assistant shows the evidence and offers the three exits. Repairing means editing a working copy and re-checking it; the originals stay untouched. Continuing means the report carries the limit in plain words.",
      ],
    },
    {
      id: "special-cases",
      kind: "matrix",
      eyebrow: "WHAT HAPPENS IN YOUR SITUATION · SPECIAL CASES",
      title: "Four cases the guide handles differently, and says so first.",
      body: "In each, the guide states what it will do before doing it.",
      matrix: [
        {
          startingPoint: "You already have a baseline",
          safestNextStep:
            "Kept exactly: same rows, same models. Never padded to look bigger.",
        },
        {
          startingPoint: "More than about 100 usable rows",
          safestNextStep:
            "Readiness reads all of it; the paid comparison runs on a recorded, difficulty-spread subset.",
        },
        {
          startingPoint: "One fixed model, one fixed prompt",
          safestNextStep:
            "Nothing to search over, so the paid search waits; the card names the setting to add.",
        },
        {
          startingPoint: "Evaluator runs the answer as code or SQL",
          safestNextStep:
            "The guide stops before executing it: no sandbox is shipped or improvised.",
        },
      ],
      sources: [
        `${GUIDE} · Default run`,
        `${EVALUATION} · First-run subset for a large dataset`,
        `${RUN_SAFETY} · Execution evaluators are out of scope`,
      ],
      notes: [
        "An existing baseline is preserved exactly; one row is correct if that is what the customer defined.",
        "Over about 100 usable rows, the paid comparison uses a small subset spread from easy to hard, with the chosen row ids recorded, and the report names the subset size beside the full count. Readiness is never scored on that subset.",
        "The fixed-agent row is the most common surprise: a search needs something to search over, or it would compare one configuration with itself. The readiness card names the missing dimension.",
        "The code-or-SQL row is the only place the guide stops rather than routes. A task whose answer is code stays in scope; what is out of scope is grading by executing that answer.",
      ],
    },
    {
      id: "readiness-at-a-glance",
      kind: "evidence",
      eyebrow: "THE READINESS SCORE",
      title:
        "Readiness: one number out of 100, taken before anything is written.",
      body: "It scores what your project has today. A low score never stops the run; it decides what to explain and fix first.",
      metrics: [
        {
          label: "Score",
          value: "0-100",
          detail: "one number from three pillars, on your own machine",
          tone: "blue",
        },
        {
          label: "Pillar weights",
          value: "40/35/25",
          detail: "dataset 40, evaluation 35, agent 25",
          tone: "violet",
        },
        {
          label: "Bands",
          value: "5",
          detail: "Not ready to Excellent; see the next slide",
          tone: "blue",
        },
        {
          label: "Caps",
          value: "Ceilings",
          detail: "a named weakness bounds the number; never a deduction",
          tone: "amber",
        },
      ],
      sources: [
        `${README} · The readiness score`,
        `${READINESS} · DEFAULT_WEIGHTS`,
        `${READINESS} · BAND_THRESHOLDS`,
      ],
      notes: [
        "The scorer runs on the customer's own machine from what it can read there; it makes no provider or Traigent calls.",
        "The weighting is the argument: 40 points on the dataset says plainly that an optimization cannot outrun the material it is measured on.",
        "A cap bounds the number; it is not a deduction and not a refusal to score, and the uncapped average stays in the report. Do not promise an Excellent opening: a capped or blocked opening is a normal, useful outcome for the material the customer brought.",
      ],
    },
    {
      id: "readiness-bands",
      kind: "scale",
      eyebrow: "THE READINESS SCORE · BANDS",
      title: "Five bands on one scale.",
      body: "The band grades the evidence. A separate line under the score says whether the paid comparison may start.",
      scale: {
        bands: [...readinessBands],
        markers: [
          { value: 55, label: "Held at Workable when thinly measured" },
          { value: 75, label: "Strong and above need confidence 0.75" },
        ],
      },
      sources: [
        `${README} · The readiness score`,
        `${READINESS} · BAND_THRESHOLDS`,
        `${READINESS} · MIN_CONFIDENCE_FOR_TOP_BANDS`,
      ],
      notes: [
        "Bands: NOT READY 0-29, PARTIAL 30-54, WORKABLE 55-74, STRONG 75-89, EXCELLENT 90-100.",
        "Confidence here means the share of the score the scorer could actually measure, not statistical confidence. Below 0.75 overall or in any pillar, a number that lands Strong or Excellent is held at Workable; the guide's own example is 89/100 WORKABLE, held there by an evaluation confidence of 0.55.",
        "The confidence rule is a ceiling on the band, never a floor: it never lifts Not ready or Partial to Workable.",
        "The BLOCKER line under the score says whether the paid comparison may start and how many things must clear first. The band grades the evidence; the blocker gates the spend.",
      ],
    },
    {
      id: "caps-blockers-and-asks",
      kind: "matrix",
      eyebrow: "READING THE CARD",
      title: "What each label on the readiness card means.",
      body: "Some weaknesses cap the whole score instead of costing points, because an average could hide a broken evaluator.",
      matrix: [
        {
          startingPoint: "FIX BEFORE PAID RUN",
          safestNextStep:
            "Something must be created or repaired first. The card names it; the paid step waits.",
        },
        {
          startingPoint: "LIMITED TO 89",
          safestNextStep:
            "The comparison can run; the evidence bounds the claim. Nothing is asked of you.",
        },
        {
          startingPoint: "A question for you",
          safestNextStep:
            "Only a person can judge it. Asked once, with the material and two choices.",
        },
        {
          startingPoint: "WOULD LIMIT TO 89",
          safestNextStep:
            "A limit you have not reached yet. Read it as what comes next.",
        },
        {
          startingPoint: "89/100 WORKABLE",
          safestNextStep:
            "The band sits below the number when a pillar was thinly measured.",
        },
      ],
      sources: [`${README} · The readiness score`],
      notes: [
        "The label is the whole message: FIX BEFORE PAID RUN holds the run, LIMITED TO bounds the claim, and the question is the only label that needs something from the customer.",
        "FIX BEFORE PAID RUN causes: no dataset, no expected answers, an evaluator that grades a wrong answer as well as a right one, or tuning rows that overlap the held-out rows.",
        "LIMITED TO causes: generated examples, or too few rows for a stable comparison. Two conditions can carry the same ceiling and both read LIMITED TO 45; fixing one leaves the number where it is until the other is fixed too.",
        "The three questions only a person can judge: an answer key a model wrote, rows whose answer does not match their own question, or data with no stated origin.",
        "89/100 WORKABLE example: an evaluation pillar with only 2 of 4 checks observed. The card says which pillar and what fills it in. A generated walkthrough dataset at 65/100 WORKABLE while blocked is the ordinary case, not a contradiction.",
      ],
    },
    {
      id: "the-opening-score",
      kind: "callout",
      eyebrow: "THE READINESS SCORE · ONE NUMBER",
      title: "The opening score is the one the report keeps.",
      body: "It is the only score taken on material the walkthrough did not write.",
      callout:
        "Scored once, before anything is written. Never re-scored as progress.",
      bullets: [
        "Taken on material the walkthrough did not write",
        "Re-run after a repair only to confirm it",
        "A capped or blocked opening is normal",
        "It names the shortest useful next action",
      ],
      sources: [
        `${README} · The readiness score`,
        `${SKILL} · 2. Show readiness once`,
      ],
      notes: [
        "After a repair the score is run again to confirm the repair cleared what it failed on. That re-score mostly grades the material the run just wrote, which is why it is never shown beside the opening number as progress.",
        "The readiness card on the customer's own repository is the free half's deliverable: a graded starting point and the shortest justified next action. The run continues either way.",
      ],
    },
    {
      id: "secrets-and-safety",
      kind: "tiles",
      eyebrow: "SECRETS AND SAFETY",
      title: "Every boundary is named before it is reached.",
      body: "Six rules the assistant follows without being asked.",
      tiles: [
        {
          icon: "🔑",
          label: "Keys stay local",
          detail: "A .env only you can read; never a secret in chat.",
        },
        {
          icon: "📦",
          label: "Own environment",
          detail: "Installs into .venv-traigent, never a shared environment.",
        },
        {
          icon: "📌",
          label: "Pinned install",
          detail: "Never an unpinned pip install traigent.",
        },
        {
          icon: "🚫",
          label: "No code execution",
          detail: "An evaluator that runs answers as code ends the guide.",
        },
        {
          icon: "✍️",
          label: "Your real material",
          detail:
            "Changing real answers or grading rules needs its own approval.",
        },
        {
          icon: "⚠️",
          label: "Destructive steps",
          detail:
            "Anything destructive or production-affecting needs explicit approval.",
        },
      ],
      sources: [
        `${README} · What the run does`,
        `${SKILL} · Action authorization`,
        `${RUN_SAFETY} · Execution evaluators are out of scope`,
      ],
      notes: [
        "Keys live in a local .env that only the customer can read and that Git ignores. The run installs into its own .venv-traigent, never into a shared environment, and never runs an unpinned pip install traigent.",
        "An evaluator that executes the agent's answer as code or SQL ends the guide before it runs; no sandbox is shipped or improvised.",
        "Changes to real answers or grading rules, and anything destructive or production-affecting, each need their own explicit approval. Approving one step never pre-approves another.",
      ],
    },
    {
      id: "the-preview-before-paying",
      kind: "tiles",
      eyebrow: "BEFORE ANY PAID STEP",
      title: "You see the preview. Then you decide.",
      body: "Every paid step shows the same preview card before a single call is made.",
      tiles: [
        {
          icon: "⏱️",
          label: "Runtime",
          detail: "How long the step is expected to take.",
        },
        {
          icon: "💵",
          label: "Estimated spend",
          detail: "And the $5.00 default stop target it runs under.",
        },
        {
          icon: "🌐",
          label: "Who receives data",
          detail: "Every recipient named, provider and Traigent alike.",
        },
        {
          icon: "📝",
          label: "What was written",
          detail:
            "Any dataset or grading method the run created, shown exactly.",
        },
        {
          icon: "✔️",
          label: "Proceed or fix",
          detail: "Your choice, before anything is charged.",
        },
      ],
      sources: [
        `${RUN_SAFETY} · Approval and budgets`,
        `${README} · What the run does`,
      ],
      notes: [
        "The preview before the baseline: scope, configurations, calls, metric, runtime, estimated spend, who receives data, and the $5.00 default stop target.",
        "If the run had to write the dataset or grading method, the same preview shows exactly what it wrote and asks the customer to proceed or fix before anything is charged.",
        "The stop target is a conservative control the run stops at and a re-approval trigger, not a billing guarantee. Provider errors, missing credentials or a breached stop target stop the run loudly; nothing is mocked or invented to fill the gap.",
      ],
    },
    {
      id: "what-leaves-your-machine",
      kind: "columns",
      eyebrow: "PRIVACY",
      title: "Traigent sees settings and scores, not your content.",
      body: "Under the pinned SDK's telemetry contract (version 0.26.0), connected runs send metadata, not material.",
      columns: [
        {
          heading: "Sent to Traigent",
          tone: "blue",
          items: [
            "Tuned setting names and values",
            "Numeric metrics and run state",
            "Content-free metadata",
            "Prompt variants as short labels",
          ],
        },
        {
          heading: "Never sent",
          tone: "violet",
          items: [
            "Your prompts",
            "Dataset rows and expected answers",
            "Model responses",
            "Unless you place content in a setting",
          ],
        },
        {
          heading: "Stays on your machine",
          tone: "amber",
          items: [
            "Example content nulled in local logs",
            "A run log, one plain sentence per event",
            "Yours to read or delete",
            "Your provider still gets your agent's normal calls",
          ],
        },
      ],
      sources: [`${README} · Privacy`, `${RUN_SAFETY} · The run log`],
      notes: [
        "Say exactly what the guide's README says and no more: the contract is the SDK's own, at the pinned version 0.26.0, and the guide stops if what it observes contradicts it. The guide does not inspect network traffic itself.",
        "Connected runs send the tuned setting names and values, numeric metrics, run state and content-free metadata. They do not send prompts, dataset rows, expected answers or model responses, unless the customer deliberately places content in a tuned setting value or opts into recording it.",
        "The model provider still receives what the agent normally sends it during calls. The assistant names every recipient and asks before any paid or data-sending step.",
        "Local retention is a separate thing: with TRAIGENT_LOG_EXAMPLE_CONTENT=false, ids and metrics are kept in the optimization logs while the query, response and expected answer are written as null. The run log records where the run waited or stopped as one plain sentence per event, never a path, id, credential or quoted row.",
      ],
    },
    {
      id: "what-you-get",
      kind: "tiles",
      eyebrow: "WHAT YOU GET",
      title: "Two measurements, one held-out check, one next step.",
      body: "Same data, same evaluator, same task, so the two numbers can be compared.",
      tiles: [
        {
          icon: "📏",
          label: "Baseline measured",
          detail:
            "Your current configuration, or a twelve-configuration grid if you had none.",
        },
        {
          icon: "🔎",
          label: "Search result",
          detail: "Up to 12 more configurations from a much larger space.",
        },
        {
          icon: "🔒",
          label: "Held-out check",
          detail: "The recommendation scored once on ten reserved rows.",
        },
        {
          icon: "🏷️",
          label: "Everything labelled",
          detail: "✅ real, ❗ thin, and substitutes named as such.",
        },
        {
          icon: "🧭",
          label: "One next step",
          detail: "With its reason and scope. Never a menu.",
        },
        {
          icon: "🚀",
          label: "Skills to continue",
          detail: "Traigent's optimization skills for your full dataset.",
        },
      ],
      sources: [
        `${GUIDE} · Default run`,
        `${GUIDE} · Result interpretation`,
        `${README} · What the run does`,
      ],
      notes: [
        "Baseline and search result appear side by side, with a verified portal link for every run that was recorded, and a local-only label for a baseline that was not uploaded.",
        "The held-out check comes with a plain note that ten rows cannot settle much.",
        "If any substitute was used, the interpretation opens by saying the result demonstrates the workflow and is not evidence of production performance.",
      ],
    },
    {
      id: "two-honest-outcomes",
      kind: "columns",
      eyebrow: "WHAT YOU GET · TWO VALID OUTCOMES",
      title: "A supported recommendation, or no lift said plainly.",
      body: "The guide never promises an uplift. Both outcomes are complete first-run results.",
      columns: [
        {
          heading: "A supported recommendation",
          tone: "blue",
          items: [
            "Best baseline beside best searched configuration",
            "Held-out score with its small-sample note",
            "Cost, failures and stop reason",
            "One next action the evidence earns",
          ],
        },
        {
          heading: "No lift, said plainly",
          tone: "amber",
          items: [
            "The flat or negative difference first",
            "Facts, then evidence-backed inferences",
            "Untested hypotheses marked as such",
            "Cause not established unless the evidence rules it in",
          ],
        },
      ],
      sources: [
        `${GUIDE} · Result interpretation`,
        `${SKILL} · 8. Verify and report`,
      ],
      notes: [
        "Never promise uplift. The guide's two valid outcomes are a supported recommendation or a plainly reported no-lift result.",
        "A no-lift report gives the flat or negative difference first, then facts, evidence-backed inferences and untested hypotheses, with 'cause not established by this run' unless the evidence rules a cause in.",
        "If the configuration already in use is the recommendation, that is a useful result: the current settings were not shown to be the problem.",
      ],
    },
    {
      id: "how-to-start",
      kind: "handoff",
      eyebrow: "HOW TO START",
      title: "What you do, what you see, what you keep.",
      body: "The first two stages need no key and cost nothing, so the first thing you see is an honest readiness card.",
      quote: customerPrompt,
      bullets: [
        "You do: paste, answer four questions, approve twice",
        "You see: readiness, preview, baseline, then comparison",
        "You keep: artifacts, run log, portal links, skills",
      ],
      sources: [
        `${README} · Start with one prompt`,
        `${README} · What the run does`,
        `${README} · Repository layout`,
      ],
      notes: [
        "Presenter: quote no duration and no price beyond the guide's own $5.00 stop target. This deck describes the guide and promises no result.",
        "You see: a readiness card before anything is written, a preview before anything is paid, the baseline result before any Traigent key, and the comparison at the end.",
        "You keep: the artifacts under traigent-runs/ in the project, the run log, portal links for recorded runs, and the skills to continue. Installing the skills authorizes nothing; every paid step still needs its own approval on the customer's key.",
      ],
    },
    {
      id: "no-project-yet",
      kind: "callout",
      eyebrow: "HOW TO START · NO PROJECT READY",
      title: "No project ready? Run it on a small sample project.",
      body: "The whole workflow still shows, on material the run writes and labels.",
      callout:
        "The assistant creates what is missing and labels it walkthrough material.",
      bullets: [
        "You still see the whole workflow",
        "Everything written is named as a substitute",
        "The result is a demonstration, not production evidence",
        "Bring real examples later for a production claim",
      ],
      sources: [
        `${README} · What the run does`,
        `${GUIDE} · Result interpretation`,
      ],
      notes: [
        "A project with nothing in it still sees the whole workflow. The assistant creates what is missing, labels it as walkthrough material, and the result then demonstrates the workflow rather than predicting production performance.",
        "The guide forbids describing measured lift on written rows as expected customer lift. A fully generated dataset caps readiness at 65, so Strong and Excellent are unreachable until collected rows arrive; the run still proceeds end to end.",
      ],
    },
    // ------------------------------------------------------------------
    // Technical appendix
    // ------------------------------------------------------------------
    {
      id: "stage-inspect",
      kind: "statement",
      eyebrow: "STAGE 1 OF 5 · INSPECT",
      title: "Preserve your useful work before proposing anything new.",
      body: "Stage 1 is read-only: language, environments, the agent, its examples and grading material, and the settings it already varies.",
      bullets: [
        "Does not import or run your code",
        "Needs no approval to read",
        "States one identity line: project path and agent",
        "One credible agent: named and confirmed",
        "Several agents: you choose, once",
        "No task evidence at all: one question, then waits",
        "A placeholder returning a constant counts as nothing",
      ],
      sources: [
        `${SKILL} · 1. Inspect quietly`,
        `${SKILL} · Zero-anchor intent gate`,
        `${GUIDE} · Keep the guide source separate from the project being optimized`,
      ],
      notes: [
        "Inspect is not a runtime test and proves nothing about model quality. It establishes what the project has before the guide changes anything.",
        "Before any score or result the assistant states one identity line: Target project: <path> · Agent: <path>:<function or command>. A resumed run whose target differs marks the old result as historical.",
        "If nothing in the project says what the task is - no working agent, no data, no evaluator, tests or documentation - the assistant asks one question and waits. Once an agent is chosen, it never asks again.",
      ],
    },
    {
      id: "status-marks",
      kind: "tiles",
      eyebrow: "STAGE 1 OF 5 · STATUS MARKS",
      title: "Three marks, and what each one means.",
      body: "The assistant never reports 3/3 ready when any component is a substitute.",
      tiles: [
        {
          icon: "✅",
          label: "Real and validated",
          detail: "Your own material, checked and preserved.",
        },
        {
          icon: "❗",
          label: "Missing or thin",
          detail:
            "Absent, failed validation, or too thin for a credible claim.",
        },
        {
          icon: "📝",
          label: "Substitute",
          detail:
            "Written by the run for the walkthrough; never counted as yours.",
        },
      ],
      sources: [`${SKILL} · Status language`, `${README} · What the run does`],
      notes: [
        "Substitutes the assistant creates carry no mark and are listed under walkthrough setup, so a reader can never mistake written material for the customer's own.",
        "The same three marks appear on every result, so provenance travels with the number.",
      ],
    },
    {
      id: "stage-readiness",
      kind: "statement",
      eyebrow: "STAGE 2 OF 5 · READINESS",
      title: "Reading the card: score, band, coverage, blocker, ceilings.",
      body: "Shown once. The guide's own example reads EVALUATION 53/100 (2 of 4 checks measured).",
      bullets: [
        "Unmeasured checks are left out, not scored zero",
        "A check you withheld keeps its weight, earns nothing",
        "BLOCKER line: may the paid comparison start?",
        "Band grades evidence; blocker gates spend",
        "LIMITED TO 45: where you are now",
        "WOULD LIMIT TO 89: not reached yet",
        "Readiness reads the whole dataset, never the subset",
      ],
      sources: [
        `${README} · The readiness score`,
        `${SKILL} · 2. Show readiness once`,
        `${READINESS} · band_for`,
      ],
      notes: [
        "A check the scorer could not compute is marked unmeasured and left out rather than scored zero. A check the run asked the customer for and did not get is unmeasured too, but keeps its weight and earns nothing, so withholding never pays.",
        "For each pillar the card shows how much was actually measured. The BLOCKER line under the score says whether the paid comparison may start and how many things must clear first.",
        "Two conditions can share one ceiling and both stay in force. After a repair the score is run again only to confirm the repair cleared what it failed on.",
      ],
    },
    {
      id: "readiness-confidence",
      kind: "callout",
      eyebrow: "STAGE 2 OF 5 · CONFIDENCE",
      title: "Confidence is the share of the score actually measured.",
      body: "It is a ceiling on the band, never a floor.",
      callout:
        "Below 0.75 overall or in any pillar, Strong and Excellent are held at Workable.",
      bullets: [
        "The guide's example: 89/100 WORKABLE",
        "Held there by an evaluation confidence of 0.55",
        "Never lifts Not ready or Partial upward",
        "The card says which pillar, and what fills it",
      ],
      sources: [
        `${READINESS} · MIN_CONFIDENCE_FOR_TOP_BANDS`,
        `${README} · The readiness score`,
      ],
      notes: [
        "Confidence here means the share of check weight the scorer could observe, not statistical confidence.",
        "The 0.75 threshold is the scorer's own constant, MIN_CONFIDENCE_FOR_TOP_BANDS. The band sits below the number when a pillar was thinly measured, for example an evaluation pillar with only 2 of 4 checks observed.",
      ],
    },
    {
      id: "readiness-scoring",
      kind: "columns",
      eyebrow: "STAGE 2 OF 5 · HOW THE SCORE IS BUILT",
      title: "Fourteen checks, three pillars, one number.",
      body: "Run before any optimization, from evidence on your own machine, with no provider or Traigent calls.",
      columns: [
        {
          heading: "Dataset · 40",
          tone: "violet",
          items: [
            "Answers to score against",
            "Examples to compare on",
            "Range of difficulty",
            "Repeated or dominant answers",
            "Where the rows came from",
          ],
        },
        {
          heading: "Evaluation · 35",
          tone: "blue",
          items: [
            "Tried on known right and wrong answers",
            "Right kind of check for this output",
            "Same answer every time",
            "Separates good answers from bad",
          ],
        },
        {
          heading: "Agent · 25",
          tone: "amber",
          items: [
            "How many settings-combinations to try",
            "What the model is told and shown",
            "Whether the answer's shape is pinned down",
            "Whether it ends, and on what",
            "Tools it declares, and can reach",
          ],
        },
      ],
      sources: [
        `${READINESS} · CHECK_DISPLAY_NAMES`,
        `${READINESS} · DEFAULT_WEIGHTS`,
        `${README} · The readiness score`,
      ],
      notes: [
        "Each check is named on the card as the question it answers. Five dataset checks, four evaluation checks, five agent checks: fourteen in all, weighted 40, 35 and 25.",
        "The agent pillar is read from the agent's own code: which settings it can already vary, each traced to a source line. Comments, docstrings and example-only values do not count. A source read that finds no setting to vary blocks the paid run.",
        "Two things the scorer refuses to guess are named on the card instead: whether the dataset and the evaluator are actually wired into the agent. The run builds and checks that later.",
      ],
    },
    {
      id: "readiness-ceilings",
      kind: "scale",
      eyebrow: "STAGE 2 OF 5 · THE CEILINGS",
      title: "Every cap is a ceiling on the same scale.",
      body: "A worse condition gets a lower ceiling. The uncapped average stays in the report.",
      scale: {
        bands: [...readinessBands],
        markers: [
          { value: 25, label: "Evaluator invalid · holds run" },
          { value: 45, label: "Evaluator unvalidated · nothing to vary" },
          { value: 65, label: "Generated dataset" },
          { value: 74, label: "Model-written key · small set" },
        ],
      },
      sources: [
        `${READINESS} · CAP_SEVERITY_ORDER`,
        `${READINESS} · ROUTE_CATEGORY`,
        `${README} · The readiness score`,
      ],
      notes: [
        "The ceilings come from the scorer's own constants: evaluator invalid 25, evaluator unvalidated 45, nothing to vary 45, generated dataset 65, model-written answer key or fewer comparable examples than a stable comparison needs 74.",
        "74 rather than 75 is deliberate: 75 is the Strong threshold, and a dataset whose whole answer key a model wrote may be workable but may not present as Strong.",
        "A capped project is not a failed project. A truthful 45 with a named ceiling is more useful than an unsupported 90.",
      ],
    },
    {
      id: "ceiling-rules",
      kind: "matrix",
      eyebrow: "STAGE 2 OF 5 · WHAT EACH CEILING DOES",
      title:
        "Which ceilings hold the paid run, and which only bound the claim.",
      body: "A condition that requires creating or repairing something holds the run; one that only limits the claim lets it proceed.",
      matrix: [
        {
          startingPoint: "Evaluator invalid · ceiling 25",
          safestNextStep:
            "Holds the paid run. Repair and re-check the evaluator first.",
        },
        {
          startingPoint: "Evaluator unvalidated · ceiling 45",
          safestNextStep: "Not blocking. Validate it and the ceiling lifts.",
        },
        {
          startingPoint: "Nothing to vary · ceiling 45",
          safestNextStep:
            "Holds the run when nothing usable is found; advisory when the code could not be checked.",
        },
        {
          startingPoint: "Generated dataset · ceiling 65",
          safestNextStep:
            "Not blocking, nothing asked. Add rows from your product before a production claim.",
        },
        {
          startingPoint: "Model-written key or small set · ceiling 74",
          safestNextStep:
            "Not blocking. The key is put to you once; a small set may get a bounded top-up offer.",
        },
      ],
      sources: [
        `${READINESS} · CAP_SEVERITY_ORDER`,
        `${READINESS} · ROUTE_CATEGORY`,
        `${GLOSSARY} · Core terms`,
      ],
      notes: [
        "Evaluator invalid means it scores a known-wrong answer as well as a known-right one: a broken ruler measures nothing, so this is the lowest ceiling any evaluator condition carries and it holds the paid run.",
        "Evaluator unvalidated means it has not yet been tried on known-right and known-wrong answers; until it is, the card shows the pillar as thinly measured.",
        "Generated dataset means every row was written by a model, or the dataset says nothing about where its rows came from. Label the walkthrough honestly; add rows collected from the product before making a production claim.",
        "A small set is called a wiring check and may get a bounded top-up offer; the model-written answer key is put to the customer once with two choices.",
      ],
    },
    {
      id: "stage-baseline",
      kind: "statement",
      eyebrow: "STAGE 3 OF 5 · BASELINE",
      title:
        "Measure the current configuration before searching for a better one.",
      body: "The first paid step, on your own provider key. No Traigent account is involved yet.",
      bullets: [
        "Your own baseline runs exactly as defined",
        "Never padded; one row is fine if defined",
        "No baseline? A twelve-configuration local grid",
        "Result on screen before any Traigent key",
        "Uploaded to the portal only without re-running",
        "Otherwise it stays local, labelled local-only",
        "Local is not free: it spends the approved total",
      ],
      sources: [
        `${GUIDE} · Default run`,
        `${README} · Requirements`,
        `${RUN_SAFETY} · Approval and budgets`,
      ],
      notes: [
        "An existing baseline is never replaced or padded; only a truly missing baseline gets the generated grid.",
        "The result - best configuration, main metric, cost, latency, trial and failure counts, a note per knob - is on screen before any Traigent key is requested.",
        "The baseline is uploaded to the portal without re-running only when the installed SDK supports an exact upload; otherwise it stays local and is labelled local-only.",
        "Provider errors, missing credentials or a breached stop target stop the run loudly. Nothing is mocked or invented to fill the gap.",
      ],
    },
    {
      id: "baseline-grid",
      kind: "columns",
      eyebrow: "STAGE 3 OF 5 · THE TWELVE-CONFIGURATION GRID",
      title: "Three models × two prompt styles × two answer styles = twelve.",
      body: "Used only when you had no baseline. One model family from the provider you set up, all twelve run.",
      columns: [
        {
          heading: "3 models",
          tone: "blue",
          items: [
            "A fast tier",
            "A mid tier",
            "A strong tier, one below the flagship",
            "Newest flagship skipped: quick and cheap first",
          ],
        },
        {
          heading: "2 prompt styles",
          tone: "violet",
          items: [
            "Two prompt styles for the same task",
            "Sent as short labels, never prompt text",
          ],
        },
        {
          heading: "2 answer styles",
          tone: "amber",
          items: ["Direct answer", "Reasoning step by step"],
        },
      ],
      sources: [
        `${SDK_EXECUTION} · Walkthrough model ladder`,
        `${GUIDE} · Default run`,
      ],
      notes: [
        "A generated grid uses one model family from the provider the customer set up: a fast tier, a mid tier and a strong tier one step below the newest flagship, skipped on purpose so the first run stays quick and cheap.",
        "3 models × 2 prompt styles × 2 answer styles (direct, or reasoning step by step) = 12 configurations, all run. This grid is used only when the customer had no baseline of their own.",
      ],
    },
    {
      id: "stage-optimize",
      kind: "statement",
      eyebrow: "STAGE 4 OF 5 · OPTIMIZE",
      title:
        "One bounded managed search, separately approved, with its space named.",
      body: "Starts only after the baseline result and the Traigent key that follows it.",
      bullets: [
        "A $0 probe proves the key and portal first",
        "Its own approval card: recipients, scope, runtime, ceiling",
        "Whole search space shown beside the ceiling of 12",
        "Traigent chooses which configurations to test as it goes",
        "Any limit that shrinks it is named",
      ],
      sources: [
        `${RUN_SAFETY} · Connected-run readiness`,
        `${SKILL} · 7. Run the honest comparison`,
      ],
      notes: [
        "The $0 probe is a stub agent that returns a constant. It proves the key works, can write experiments, and that the portal answers, before any paid connected trial. If the probe fails at any step, the run stops before any connected paid trial and shows a sanitized reason.",
        "The second gate is deliberate: the recipients, the number of calls and the data boundary change when Traigent's service enters. Approving the baseline never pre-approves this step.",
        "The card shows the size of the whole search space beside the ceiling of 12 tests, so the 12 reads against what it is drawn from. A disclosed runtime, cost or plan limit can shrink the comparison; the report gives the number actually tested and the concrete reason.",
        "Frame the managed search as a deliberately small first enhancement: a few evidence-driven settings, a small slice of what Traigent can drive.",
      ],
    },
    {
      id: "what-the-search-may-change",
      kind: "columns",
      eyebrow: "STAGE 4 OF 5 · WHAT THE SEARCH MAY CHANGE",
      title: "It keeps your baseline and adds only what your agent uses.",
      body: "The search explores a broader space without moving the ground the baseline stands on.",
      columns: [
        {
          heading: "Kept",
          tone: "blue",
          items: [
            "Every baseline value and model",
            "Your dataset and evaluator",
            "The same task and rows",
          ],
        },
        {
          heading: "Added",
          tone: "violet",
          items: [
            "Only settings your agent actually uses",
            "Up to 12 configurations to test",
            "Over ~100 rows: a recorded, difficulty-spread subset",
            "A new model only as a disclosed experiment",
          ],
        },
      ],
      sources: [
        `${SKILL} · 7. Run the honest comparison`,
        `${EVALUATION} · First-run subset for a large dataset`,
        `${README} · What the run does`,
      ],
      notes: [
        "The search keeps every baseline value and model and adds only settings the agent actually uses. Any new model would be a separately disclosed experiment.",
        "On more than about 100 usable rows the paid comparison uses a small subset spread across difficulty, with the chosen row ids recorded; the report names the subset size beside the full count. Readiness is never scored on that subset.",
      ],
    },
    {
      id: "selection-and-heldout",
      kind: "journey",
      eyebrow: "STAGES 4 TO 5 · THE HONEST COMPARISON",
      title: "Choose on tuning evidence. Check once on held-out rows.",
      body: "Picking the best of several on the same rows picks partly on luck, so the winner's score is inflated by the choosing.",
      steps: [
        {
          label: "Reserve ten rows",
          detail:
            "2 easy, 3 medium, 3 hard, 2 very hard, set aside before any tuning.",
          executor: "Coding assistant",
        },
        {
          label: "Select on tuning",
          detail:
            "One recommendation from baseline grid and search; at a tie, the cheaper wins.",
          executor: "Coding assistant",
        },
        {
          label: "Score it once",
          detail:
            "Only that configuration runs on the reserved rows. Scoring two would be selecting again.",
          executor: "Coding assistant",
          humanGate: "Inside approved paid work",
        },
        {
          label: "Disclose the limit",
          detail:
            "Ten rows cannot settle much: the held-out number can land lower, level or higher.",
          executor: "Coding assistant",
          humanGate: "You read the caveat",
        },
      ],
      sources: [
        `${EVALUATION} · Held-out set and claims`,
        `${GLOSSARY} · Core terms`,
      ],
      notes: [
        "The held-out rows exist to check the selection risk, not to remove it, and never to choose. A project with its own held-out split keeps it as it is; the walkthrough split goes into its own file before any design, calibration or tuning touches the data.",
        "Wording matters: a held-out set is a sealed holdout only when its split and labels stayed hidden until the candidate was locked. Because the assistant creates and can inspect the walkthrough split, the guide calls it held-back and non-blind.",
        "Counts, not percentages: on ten rows one standard error is about 15 points near 50%. A gap between the tuning and held-out score is expected and is not called overfitting; it is the ordinary result of picking the best of several configurations on a small sample. Never say that Traigent prevents it.",
        "A set used to select is no longer held out. A flat result on demonstration data says nothing about production.",
      ],
    },
    {
      id: "stage-results",
      kind: "statement",
      eyebrow: "STAGE 5 OF 5 · RESULTS",
      title:
        "Report what changed, what it cost, and what the evidence cannot support.",
      body: "Not called successful until every post-run check, including verified portal links, passes.",
      bullets: [
        "Leads with outcome, evidence, limits, one next action",
        "Then configurations, trials, failures, cost, stop reason",
        "Best baseline against best searched, on tuning rows",
        "Held-out score with its small-sample note first",
        "Spent, approved, and what is left",
        "Provenance on every result: ✅, ❗, substitutes",
      ],
      sources: [
        `${SKILL} · 8. Verify and report`,
        `${RUN_SAFETY} · Post-run verification`,
        `${GUIDE} · Result interpretation`,
      ],
      notes: [
        "The end goal is an explainable decision. A result without its baseline, evidence boundary and limitations is not a valid first-run outcome.",
        "The report leads with the outcome, what the evidence establishes, the current state and its limits, and one next action; then the details: configurations, objectives, trials, failures, cost, stop reason, artifacts and verified links. Each run's accuracy-cost frontier is in the details.",
        "Cost is reported as configurations tested out of the space's total, failures and stop reason, the approved total, what was spent, and what is left.",
        "No configuration is promoted from a fully synthetic run; for real components, promotion still needs explicit approval and a later validation check. Learning links and lifecycle suggestions come only after the customer has seen the result.",
      ],
    },
    {
      id: "what-you-keep",
      kind: "tiles",
      eyebrow: "STAGE 5 OF 5 · WHAT STAYS WITH YOU",
      title: "Everything the run produced stays in your project.",
      body: "Nothing is deleted as cleanup, and nothing is sent anywhere you did not approve.",
      tiles: [
        {
          icon: "🗂️",
          label: "Artifacts",
          detail: "Under traigent-runs/ in your project, ignored by Git.",
        },
        {
          icon: "📜",
          label: "Run log",
          detail: "Append-only, one plain sentence per event.",
        },
        {
          icon: "🔗",
          label: "Portal links",
          detail: "A verified direct link for every recorded experiment.",
        },
        {
          icon: "💻",
          label: "Local-only label",
          detail: "For a baseline that was not uploaded.",
        },
      ],
      sources: [
        `${README} · Repository layout`,
        `${RUN_SAFETY} · Post-run verification`,
        `${RUN_SAFETY} · The run log`,
      ],
      notes: [
        "Artifacts live under traigent-runs/ in the customer's project, never in the guide clone, and are ignored when the project uses Git. Each readiness scoring gets its own readiness/<timestamp>/ directory.",
        "An unsynced baseline is labelled local-only; nothing is deleted as cleanup. The run log is not sent anywhere; it is the customer's to read or delete.",
      ],
    },
    {
      id: "requirements",
      kind: "tiles",
      eyebrow: "REQUIREMENTS",
      title: "What a first run needs.",
      body: "Stated once, so there are no surprises mid-run.",
      tiles: [
        {
          icon: "🐍",
          label: "Python 3.11 to 3.13",
          detail: "In an isolated environment the run creates itself.",
        },
        {
          icon: "📌",
          label: "Pinned SDK stack",
          detail: "traigent 0.26.0, litellm 1.93.0, python-dotenv 1.2.2.",
        },
        {
          icon: "🔑",
          label: "One provider key",
          detail: "With a small amount of credit for the paid steps.",
        },
        {
          icon: "🪪",
          label: "Traigent key, later",
          detail: "Activated or requested only after the first result.",
        },
        {
          icon: "🟢",
          label: "Node.js, optional",
          detail: "Only for the npx skills add install, not the run.",
        },
      ],
      sources: [
        `${README} · Requirements`,
        `${REQUIREMENTS} · pinned versions`,
        `${README} · Install as an Agent Skill`,
      ],
      notes: [
        "Python 3.11 to 3.13 in an isolated environment, the tested SDK stack pinned in the guide's requirements file (traigent==0.26.0, litellm==1.93.0, python-dotenv==1.2.2), installed into the dedicated environment whatever the project declares for itself. Never an unpinned pip install traigent.",
        "One supported LLM-provider key with a small amount of credit for the paid steps goes first, into a local .env. A Traigent portal key that can write experiments is activated after the first result is on screen, not before; if none is present, the assistant asks for one then.",
      ],
    },
    {
      id: "licensing",
      kind: "columns",
      eyebrow: "LICENSING",
      title: "Two licences, two artifacts.",
      body: "Rights in the guide do not relicense the SDK it installs, and neither relicenses your project.",
      columns: [
        {
          heading: "The guide · Apache-2.0",
          tone: "blue",
          items: [
            "Walkthrough, skill, scripts and references",
            "Use inside a proprietary project",
            "Your code, data, prompts and outputs stay yours",
          ],
        },
        {
          heading: "The SDK · separate terms",
          tone: "amber",
          items: [
            "AGPL-3.0-only, or",
            "A Traigent commercial licence by written agreement",
            "Installing grants no commercial terms",
            "Contact legal@traigent.ai",
          ],
        },
      ],
      sources: [`${README} · License`, `${README} · SDK licensing`],
      notes: [
        "The guide - walkthrough, bundled skill, scripts and references - is Apache-2.0. Using it inside a proprietary project does not relicense that project's code, data, prompts or outputs.",
        "The Traigent SDK is distributed under separate terms: AGPL-3.0-only, or a Traigent commercial license under a separate written agreement. Installing the package grants no commercial terms; contact legal@traigent.ai.",
      ],
    },
    {
      id: "repository-layout",
      kind: "tiles",
      eyebrow: "REPOSITORY LAYOUT",
      title: "What is in the repository.",
      body: "Small on purpose. During a run, the assistant writes only under traigent-runs/ in your project.",
      tiles: [
        {
          icon: "📄",
          label: "GUIDE.md",
          detail: "Entry point for a cloned run; hands over to the skill.",
        },
        {
          icon: "🧠",
          label: "skills/traigent-first-run/",
          detail:
            "SKILL.md, references, scripts and assets: the same workflow, installable.",
        },
        {
          icon: "⚙️",
          label: ".env.example",
          detail: "Reference environment settings.",
        },
        {
          icon: "🗂️",
          label: "traigent-runs/",
          detail: "Created in your project during a run; Git-ignored.",
        },
        {
          icon: "📑",
          label: "reports/",
          detail:
            "Field-test evidence and methodology research behind the safeguards.",
        },
        {
          icon: "🧪",
          label: "tests/ and tools/",
          detail:
            "The guide's own quality gates. They test the guide, not your project.",
        },
      ],
      sources: [
        `${README} · Repository layout`,
        `${SKILL} · Bundled guidance index`,
      ],
      notes: [
        "GUIDE.md hands over to skills/traigent-first-run/SKILL.md, which loads each reference at the stage that needs it: glossary, run-safety, sdk-execution, evaluation-and-dataset, component-creation; scripts preflight.py, readiness.py, validate_run_log.py; assets run-plan.md and requirements-first-run.txt.",
        "The skill directory is exactly what the Agent Skill installer copies, so the clone path and the installed-skill path follow one workflow. traigent-runs/ belongs to the customer's project, never to the guide clone.",
        "tests/ and tools/ are the guide's own quality gates and CI guards. The customer never needs to run them.",
      ],
    },
  ],
} satisfies PresentationInput;

const coreSlideIds = [
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
] as const;

const appendixSlideIds = [
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
  "selection-and-heldout",
  "stage-results",
  "what-you-keep",
  "requirements",
  "licensing",
  "repository-layout",
] as const;

const sourceSlides: readonly SlideInput[] = rawPresentation.slides;
const slidesById = new Map(sourceSlides.map((slide) => [slide.id, slide]));
const slideForId = (id: string): SlideInput => {
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
export const presentation: PresentationSpec = parsePresentation({
  ...rawPresentation,
  slides: [...coreSlides, ...appendixSlides],
});
export { customerPrompt };
