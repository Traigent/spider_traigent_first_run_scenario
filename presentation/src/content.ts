import { parsePresentation, type PresentationSpec } from "./model";

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

const rawPresentation = {
  schemaVersion: 3,
  title: "Traigent Guided First Run",
  subtitle:
    "The public guide a coding assistant follows to run a customer's first Traigent optimization on the project they already have.",
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
    {
      id: "ready-to-optimize",
      kind: "hero",
      eyebrow: "TRAIGENT GUIDED FIRST RUN · THE PUBLIC GUIDE",
      title:
        "Start with the project you have. Leave with a justified next step.",
      accent: "justified next step",
      body: "The guide leads a coding assistant through one guided Traigent optimization in one sitting, from whatever the project has today. The assistant inspects the project, preserves any real agent, dataset and evaluation method it finds, and offers to repair a working copy when a real dataset or evaluator is too small, corrupted, narrow, trivial or mismatched to support a meaningful comparison. Temporary walkthrough material is labelled so it cannot be mistaken for production evidence, a no-lift result is reported plainly rather than dressed up as a win, and verified facts are kept apart from inferences and hypotheses.",
      bullets: [],
      metrics: [],
      steps: [],
      sources: [
        `${README} · Traigent - First Run`,
        `${GUIDE} · Traigent First Run - Assistant Guide`,
      ],
      notes: [
        "Lead with honest routing: the guide does not demand a clean benchmark or a perfect agent. It starts from whatever is there.",
        "The deliverable of a first run is a truthful position and one next step, not a score and never a promised uplift.",
        "Repair means a working copy, revalidated, with provenance preserved. Material the run writes is never marked as a real, validated component.",
        "A flat result on demonstration data does not establish what production performance would be; the guide says so itself.",
      ],
    },
    {
      id: "one-customer-prompt",
      kind: "handoff",
      eyebrow: "ONE PROMPT TO THE ASSISTANT ALREADY ON THE PROJECT",
      title:
        "One prompt. The assistant does the work and asks for four things.",
      body: "Paste the prompt into Claude Code, Cursor, Codex, Gemini CLI or another coding assistant. The run uses a dedicated .venv-traigent environment and preserves existing project, shared and dependent environments; if that path already exists or its setup fails, the assistant stops with the path and recommends inspection.",
      quote: customerPrompt,
      bullets: [
        "Alternative install: npx skills add Traigent/traigent-first-run, then ask 'Use $traigent-first-run to run my first Traigent optimization.' Node.js is needed only for that optional command, not for the Python run.",
        "Ask 1 - a choice that materially changes the task: which agent to optimize is the first of them, and the only one asked before the walkthrough starts.",
        "Ask 2 - a key pasted into an owner-only local .env file, ignored when the project uses Git.",
        "Ask 3 - approval before paid model calls or private-data egress.",
        "Ask 4 - approval before judgment-dependent changes to real examples, expected answers or grading policy, and before destructive or production-affecting actions.",
      ],
      metrics: [],
      steps: [],
      sources: [
        `${README} · Start with one prompt`,
        `${README} · Install as an Agent Skill`,
      ],
      notes: [
        "The quote is the exact two-line prompt from the README. Customers paste it as written.",
        "The installed skill resolves its bundled files from its own directory while keeping the customer's project as the working directory; nothing is cloned into their project.",
        "The four asks are the whole list. Everything else the assistant works out from the project or from the guide.",
      ],
    },
    {
      id: "shared-control",
      kind: "journey",
      eyebrow: "ASSISTANT-LED, CUSTOMER-GOVERNED",
      title:
        "Five stages. Two paid approvals. The customer decides at the end.",
      body: "The assistant opens with the five stages exactly as the guide names them and announces each as Stage N/5. Safe discovery is never put to the customer for approval; the run stops only for a genuine agent choice, one task-intent question, secrets, paid or private-data calls, judgment-dependent changes to real answers or grading policy, and destructive or production-affecting changes. Paid work sits behind exactly two approvals.",
      bullets: [],
      metrics: [],
      steps: [
        {
          label: "1 Inspect",
          detail:
            "Preserve your agent, dataset and evaluator. Read-only discovery: no project code is imported or executed, no provider or Traigent call is made.",
          executor: "Coding assistant",
        },
        {
          label: "2 Readiness",
          detail:
            "Run free readiness research and explain its score. Readiness checks the score and setup, not agent accuracy or an optimization result.",
          executor: "Coding assistant",
        },
        {
          label: "3 Baseline",
          detail:
            "Install the SDK, then measure today's setup with calls, cost and time - on the customer's own provider key, with no Traigent account yet.",
          executor: "Coding assistant",
          humanGate: "Paid approval 1 of 2 · provider key",
        },
        {
          label: "4 Optimize",
          detail:
            "The paid baseline result comes first, the Traigent account after it, then a bounded managed search over a materially broader space.",
          executor: "Traigent service",
          humanGate: "Paid approval 2 of 2 · Traigent key",
        },
        {
          label: "5 Results",
          detail:
            "Compare the runs, recommend one next step, and hand over the Traigent skills so the customer can keep going alone.",
          executor: "Coding assistant",
          humanGate: "Customer decides",
        },
      ],
      sources: [
        `${SKILL} · Opening message`,
        `${GUIDE} · User-facing promise`,
        `${GUIDE} · Default run`,
      ],
      notes: [
        "Stages 1 and 2 make no provider or Traigent calls and spend nothing. Stage 3 is the first paid stage, on the customer's approved provider key and stop target.",
        "Stage 4 is a separate approval on purpose: the baseline preserves the customer's own space, the managed search explores a broader one, and the Traigent key is only requested after the baseline result is on screen.",
        "Do not present Readiness as a gate the customer approves. The guide tells the assistant not to make the user approve safe discovery.",
        "Baseline evidence decides the next step; the assistant recommends a route with reason and scope, never a generic menu or a guaranteed gain.",
      ],
    },
    {
      id: "works-from-whatever-you-have",
      kind: "statement",
      eyebrow: "MEETING THE PROJECT WHERE IT IS",
      title:
        "It works from all, some or none of an agent, a dataset and an evaluator.",
      body: "The guide works whether the project already has all, some or none of an agent to optimize, an evaluation dataset and an evaluation method. Nothing is required to see the walkthrough: what exists is preserved and marked, what is missing is asked about once, and whatever the run writes is named as a substitute and priced as weaker evidence.",
      bullets: [
        "✅ marks a real component found and validated; ❗ marks one missing, failed in validation, or too thin in evidence for a credible optimization claim.",
        "A substitute the assistant creates carries no mark: it is listed under walkthrough setup, named in words, and the run never says 3/3 ready when any component is synthetic.",
        "Every gap is one question, however many pieces are absent: what was not found, that written material is weaker evidence than examples from the product and what that costs the result, and two ways to answer - go ahead, or point it at yours.",
        "The assistant never guesses what the agent is for; when nothing in the project says what the task is, it asks a single question and waits before writing anything.",
        "A placeholder agent counts as nothing to go on: a file that returns a constant or echoes its input is judged by what it does, not by the fact that it imports.",
        "Examples written for the walkthrough are weaker evidence than examples collected from the product; a generated evaluation method is a starting point, not the grading policy.",
      ],
      metrics: [],
      steps: [],
      sources: [
        `${GUIDE} · Traigent First Run - Assistant Guide`,
        `${README} · Start with one prompt`,
        `${SKILL} · Status language`,
        `${SKILL} · One ask for every gap`,
      ],
      notes: [
        "The honest line for a prospect: a project with nothing in it still sees the whole workflow, but the result then demonstrates the workflow and is not evidence of expected production performance.",
        "Once an agent is chosen - a dummy or walkthrough agent counts as chosen - the assistant keeps using that one and never asks again.",
        "Substitutes are not production evidence, and the guide makes the assistant say so before the numbers.",
      ],
    },
    {
      id: "readiness-at-a-glance",
      kind: "evidence",
      eyebrow: "THE READINESS SCORE",
      title:
        "Readiness: one number out of 100, taken before anything is written.",
      body: "Before anything is created or repaired, the assistant scores what the project has today: a number out of 100 from three pillars and a named band from Not ready to Excellent. That opening number is the one the report keeps, because it is the only one taken on material the walkthrough did not write. The score is re-run after a repair to check that the repair cleared what it failed on, but no closing number is put beside the opening one and called progress.",
      bullets: [],
      metrics: [
        {
          label: "Score",
          value: "0-100",
          detail:
            "one number from three pillars; a low score never stops the run, it decides which gaps are worth explaining or fixing first",
          tone: "blue",
        },
        {
          label: "Pillar weights",
          value: "40 · 35 · 25",
          detail:
            "dataset 40, evaluation 35, agent 25 - the dataset carries the most weight",
          tone: "violet",
        },
        {
          label: "Bands",
          value: "5",
          detail:
            "Not ready 0-29 · Partial 30-54 · Workable 55-74 · Strong 75-89 · Excellent 90-100",
          tone: "blue",
        },
        {
          label: "Caps",
          value: "Ceilings",
          detail:
            "a cap bounds the number; it is not a deduction and not a refusal to score, and the pre-cap average stays in the report",
          tone: "amber",
        },
      ],
      steps: [],
      sources: [
        `${README} · The readiness score`,
        `${READINESS} · DEFAULT_WEIGHTS`,
        `${READINESS} · BAND_THRESHOLDS`,
      ],
      notes: [
        "The opening score describes the customer's starting point. A re-score after a repair mostly grades the substitutes the run just wrote, so it is read for which caps cleared, never shown as progress.",
        "Do not promise an Excellent opening. A capped or blocked opening is a normal, useful outcome for the material the customer brought.",
        "The score runs before any optimization from evidence on the customer's own machine; the scorer makes no provider or Traigent calls.",
      ],
    },
    {
      id: "caps-blockers-and-asks",
      kind: "matrix",
      eyebrow: "READING THE CARD'S LABELS",
      title:
        "What each label on the card means, and the one that needs an answer.",
      body: "Some conditions cap the whole score rather than costing a few points, because an average can hide a broken evaluator. Whether the paid run may start is a separate question, answered on its own BLOCKER line under the score: the band grades how good the evidence is, the blocker says whether the paid comparison may start yet. A generated walkthrough dataset at 65/100 WORKABLE while blocked is the ordinary outcome, not a contradiction.",
      bullets: [],
      metrics: [],
      steps: [],
      matrix: [
        {
          startingPoint:
            "FIX BEFORE PAID RUN - no dataset, no expected answers, an evaluator that scores a wrong answer as well as a right one, a tuning set that shares examples with the held-out set, or nothing scoreable in the split the search would tune on",
          safestNextStep:
            "Follow the named repair or evidence-gathering action first. The paid comparison waits until it clears; the score itself still stands on the card.",
        },
        {
          startingPoint:
            "LIMITED TO 89 - generated data, or a handful of rows that make the comparison a wiring check",
          safestNextStep:
            "The paid comparison proceeds and asks nothing of you; the evidence bounds what the result may claim, and the line names the number so 'why is this 89' has an answer on the same line.",
        },
        {
          startingPoint:
            "The one kind that asks - an answer key a model wrote end to end, rows whose expected answer does not appear to match their own input, or a dataset that never says where its rows came from",
          safestNextStep:
            "Put to you once, with the material to judge it on and a straight pair of exits, where it is still free to act on or inside the first paid approval; the approval shows what you answered. Never asked twice.",
        },
        {
          startingPoint:
            "WOULD LIMIT TO 89 - a real ceiling that is not the one currently in force",
          safestNextStep:
            "Read it as what you run into next: either something stricter is holding the score down, or the average has not climbed that high yet. It is not why the score is what it is today.",
        },
        {
          startingPoint:
            "89/100 WORKABLE - the band sits below the number because a pillar is thinly measured, e.g. EVALUATION 69/100 (2 of 4 checks measured)",
          safestNextStep:
            "Not a contradiction: the card declines to call a project Strong on evidence it has not seen. Declaring --evaluator-method fills that pillar in; its confidence of 0.55 is what holds 89 at Workable.",
        },
      ],
      sources: [`${README} · The readiness score`],
      notes: [
        "The label is the whole message. FIX BEFORE PAID RUN holds the run; LIMITED TO bounds the claim; the asking kind is the only one that needs something from the customer.",
        "Two conditions can carry the same ceiling and both read LIMITED TO 45; fixing one leaves the number where it is until the other is fixed too.",
        "Stopping a paid run over the assistant's reading of the customer's data would be wrong; showing a ceiling with no way to act on it was the older mistake. The asking kind is the fix.",
      ],
    },
    {
      id: "spend-and-safety-boundaries",
      kind: "statement",
      eyebrow: "SPEND, SECRETS AND SAFETY",
      title:
        "Nothing is paid before the baseline approval, and every boundary is named.",
      body: "Before baseline approval, inspection, setup and local validation make no provider calls and spend nothing. The baseline runs locally on the customer's own provider key and needs no Traigent account, so a real number from their own project is on screen before anyone decides whether to register; the Traigent key is asked for only after that result.",
      bullets: [
        "Baseline preview immediately before its paid calls: runtime, estimated spend, data egress, and a total execution stop target of $5.00 by default - a conservative control, not a guaranteed provider-billing cap.",
        "When the run had to write the dataset or the grading method, the same preview shows what it wrote - full paths, the easiest and the hardest example, what the method counts as correct - and asks to proceed or fix before anything is charged.",
        "Keys go into an owner-only local .env, verified untracked and effectively ignored when the project uses Git; the guide never asks for a secret in chat.",
        "A dedicated .venv-traigent under the project root; never an install into a shared or dependent environment, and never an unversioned pip install traigent.",
        "An evaluator that executes candidate code or SQL ends this guide before it runs: no sandbox is shipped, selected or improvised for it.",
        "Destructive or production-affecting actions need their own separate explicit approval, as do judgment-dependent changes to real answers or grading policy.",
      ],
      metrics: [],
      steps: [],
      sources: [
        `${README} · What the run does`,
        `${README} · Requirements`,
        `${RUN_SAFETY} · Execution evaluators are out of scope`,
        `${SKILL} · Action authorization`,
      ],
      notes: [
        "This is the procurement slide. Keep the boundary concrete: provider key first, Traigent key after the result, two separate approvals, one stop target.",
        "The $5.00 default is the guide's own number and the only price the deck quotes. It is an execution stop target and re-approval trigger, not a billing guarantee.",
        "A task whose answer is code or SQL stays in scope; what is out of scope is an evaluator that executes that answer.",
      ],
    },
    {
      id: "what-leaves-your-machine",
      kind: "statement",
      eyebrow: "PRIVACY",
      title: "What leaves the machine, and what stays on it.",
      body: "Under the pinned SDK 0.26.0 telemetry contract, connected runs can send tuned configuration keys and values, numeric metrics, trial and run state, and content-free metadata needed for optimization and portal history. Except for content deliberately placed in a tuned configuration value and observability content the project explicitly opts into, the contract says the SDK does not send user prompts or inputs, evaluation-dataset contents, expected outputs or model responses in that result metadata.",
      bullets: [
        "Prompt variants are mapped to short content-free labels inside the agent; raw prompt text is not used as a configuration value.",
        "A connected request authenticates with the Traigent API key; the guide never prints or records it, and does not say credentials are 'not transmitted'.",
        "Locally, the run sets TRAIGENT_LOG_EXAMPLE_CONTENT=false before importing Traigent: example ids and metrics are retained, while query, response and expected are written as null.",
        "traigent-runs/run-log.jsonl notes where the run waited, stopped or met something that can bend the result - a class name and one sentence, never a path, id, address, credential or quoted row. Nothing sends the file anywhere.",
        "The selected LLM provider still receives the content the agent normally sends during model calls; the assistant explains which services receive data and asks before paid calls or private-data egress.",
        "The walkthrough does not independently audit network packets; it stops if observed runtime behaviour contradicts the contract.",
      ],
      metrics: [],
      steps: [],
      sources: [`${README} · Privacy`, `${RUN_SAFETY} · The run log`],
      notes: [
        "Say exactly what the README says and no more: the contract is the SDK's own, at the pinned version, and the guide stops if behaviour contradicts it. The guide does not audit packets.",
        "The backend boundary and local retention are two different things; the log setting governs the second.",
        "validate_run_log.py refuses paths, credentials, addresses, hosts, links and long ids in the run log; what a checker cannot settle - a person's name, a provider error body - stays the assistant's to honour.",
      ],
    },
    {
      id: "what-the-customer-gets",
      kind: "statement",
      eyebrow: "THE DELIVERABLE",
      title:
        "Two measurements on the same data, one held-out check, one next step.",
      body: "The default paid path is two measurements with the same tuning data, evaluator, objectives and agent call path: the customer's own baseline preserved exactly - or, only when none exists, a twelve-configuration local fixed grid - followed by one connected managed search that keeps every baseline value, adds meaningful non-model knobs, and tests up to 12 configurations from a materially larger space, choosing which ones as it goes.",
      bullets: [
        "Baseline and enhanced result side by side, with a verified portal link for every persisted run and an explicit local-only label for an unsynced baseline.",
        "The recommended configuration's held-out score on ten examples, with a note saying how little ten examples can settle.",
        "When the search does not beat the baseline, the no-lift result is reported plainly, with verified facts separated from inferences and hypotheses.",
        "Every component's provenance on the result: ✅ real and validated, ❗ missing or evidence-limited, substitutes named in words under walkthrough setup.",
        "One recommended next step with its reason and scope - never a generic menu or a guaranteed gain.",
        "After the result, the Traigent optimization skills are offered so the customer can continue alone, at their full dataset, with more controls and their own iterations.",
      ],
      metrics: [],
      steps: [],
      sources: [
        `${GUIDE} · Default run`,
        `${GUIDE} · Result interpretation`,
        `${README} · What the run does`,
        `${SKILL} · 8. Verify and report`,
      ],
      notes: [
        "Never promise uplift. The guide's two outcomes are a supported recommendation or a plainly reported no-lift result; both are valid first-run deliverables.",
        "If any substitute was used, the interpretation opens by saying the result demonstrates the workflow and is not evidence of expected production performance.",
        "The held-out check on ten rows is a bounded sample check, not a generalization proof; the report says so in one line.",
      ],
    },
    {
      id: "how-presales-runs-it",
      kind: "handoff",
      eyebrow: "PRESALES PLAYBOOK",
      title:
        "How presales runs it: the same prompt, on the prospect's own repository.",
      accent: "the prospect's own repository",
      body: "The free stages need no keys and no spend: pasted into the prospect's coding assistant, the prompt yields a readiness card on their own project before anyone pays anything. Every paid step after that is the customer's own approval on the customer's own key.",
      quote: customerPrompt,
      bullets: [
        "Inspect and Readiness on a prospect's repository produce a readiness card with no provider key, no Traigent account and no spend.",
        "A capped or blocked opening is the ordinary outcome, not a failure: the guide's own example is 65/100 WORKABLE while blocked, with the line saying what has to clear first.",
        "The baseline is approved on the customer's provider key; the managed search is approved separately, after the baseline result and the Traigent key that follows it. The $5.00 default is an execution stop target, not a billing cap.",
        "No prospect repository to hand? Run it on any small sample project of yours: the guide creates what is missing and labels it as walkthrough material.",
        "After the result, offer the Traigent optimization skills as the next step: npx skills add Traigent/traigent-skills --list, then install one or all of them.",
      ],
      metrics: [],
      steps: [],
      sources: [
        `${README} · Start with one prompt`,
        `${README} · What the run does`,
        `${README} · The readiness score`,
        `${SKILL} · 8. Verify and report`,
      ],
      notes: [
        "Quote no duration and no price beyond the guide's own $5.00 stop target. This deck describes the guide; it carries no run of its own and promises no uplift.",
        "The readiness card on a prospect's repository is the executive deliverable of the free half: a graded starting point and the shortest justified next action.",
        "Installing the skills authorizes nothing; every paid step still needs its own approval on the customer's key.",
        "A sample project of your own shows the workflow; say plainly that its result is walkthrough evidence and not what the prospect's production would do.",
      ],
    },
    {
      id: "stage-inspect",
      kind: "statement",
      eyebrow: "STAGE 1 OF 5 · INSPECT",
      title:
        "Preserve the customer's useful work before proposing anything new.",
      body: "Stage 1 of 5 is read-only discovery. The assistant identifies the project's language, dependency system and every existing environment, the selected agent, the examples and grading material that belong to it, and the settings it may already vary - without importing or executing project code, and without asking approval for safe discovery.",
      bullets: [
        "One identity line before any readiness, baseline or result: Target project: <absolute path> · Agent: <absolute path>:<function or command>. A resumed run whose identity differs labels the old artifact historical - different agent.",
        "✅ - real component found and validated. ❗ - real component missing, failed validation, or evidence too limited for a credible optimization claim.",
        "A substitute the assistant creates carries no mark and is listed under walkthrough setup, named in words; the run never says 3/3 ready when any component is synthetic.",
        "With several credible agents it asks which; with exactly one it names it and asks whether to run on it; once chosen, it never asks again.",
        "When nothing anchors the task - no agent performing an identifiable one, no dataset, evaluator, tests or product documentation - it asks exactly one task-intent question: what should the walkthrough agent do?",
        "A placeholder agent counts as nothing to go on: a file that returns a constant or echoes its input is judged by what it does, not by the fact that it imports.",
      ],
      metrics: [],
      steps: [],
      sources: [
        `${SKILL} · 1. Inspect quietly`,
        `${SKILL} · Zero-anchor intent gate`,
        `${GUIDE} · Keep the guide source separate from the project being optimized`,
        `${SKILL} · Status language`,
      ],
      notes: [
        "Inspect is not a runtime test and proves nothing about model quality. It establishes what the project has before the guide changes anything.",
        "The guide clone is not automatically the project being optimized; the assistant resolves the customer's project root and agent at run time.",
        "There are exactly two marks. Synthetic material is never marked as real and validated.",
      ],
    },
    {
      id: "stage-readiness",
      kind: "statement",
      eyebrow: "STAGE 2 OF 5 · READINESS",
      title:
        "Read the card: score, band, what was measured, blocker, ceilings.",
      body: "Stage 2 of 5 shows the readiness card once. It names a score, a band, and for each pillar how much was actually observed - EVALUATION 53/100 (2 of 4 checks measured) is the guide's own example. A low score never stops the run; it decides which gaps are worth explaining and which are worth fixing first.",
      bullets: [
        "A check the tool could not compute is marked unmeasured and excluded rather than scored zero; a check the run asked for and did not get is unmeasured too, but keeps its weight and earns nothing, so withholding never pays.",
        "Confidence is the share of the score actually measured: below 0.75 overall or in any pillar, a number that lands Strong or Excellent is held at Workable. The guide's 89/100 WORKABLE is held there by an evaluation confidence of 0.55.",
        "The BLOCKER line sits under the score, separate from the band: the band grades the evidence, the blocker says whether the paid comparison may start yet and how many things have to clear.",
        "LIMITED TO 45 is the number you are at; WOULD LIMIT TO 89 is a limit not yet reached. Two conditions can share one ceiling and both stay in force.",
        "Every readiness run reads the whole dataset, never the paid comparison's subset: the score is a statement about your data, the subset a limit on this one comparison.",
        "The score is re-run after a repair to check it cleared what it failed on, but no closing number is put beside the opening one and called progress.",
      ],
      metrics: [],
      steps: [],
      sources: [
        `${README} · The readiness score`,
        `${READINESS} · MIN_CONFIDENCE_FOR_TOP_BANDS`,
        `${READINESS} · band_for`,
        `${SKILL} · 2. Show readiness once`,
      ],
      notes: [
        "Confidence here is the share of check weight the scorer could actually observe, not statistical confidence.",
        "The confidence rule is a ceiling on the band, never a floor: it never promotes Not ready or Partial to Workable.",
        "If real material exists but looks too weak for a meaningful comparison, the card carries a short quality advisory with measured evidence and an offer to repair a working copy and re-run validation.",
      ],
    },
    {
      id: "readiness-scoring",
      kind: "statement",
      eyebrow: "STAGE 2 OF 5 · HOW THE SCORE IS BUILT",
      title: "Fourteen checks, three pillars, one number out of 100.",
      body: "The scorer runs 14 checks across the dataset, the evaluation method and the agent, weighted 40, 35 and 25, and names each check on the card as the question it answers. It runs before any optimization, from evidence on the customer's own machine, and makes no provider or Traigent calls.",
      bullets: [
        "Dataset (40): answers to score against · examples to compare on · range of difficulty · repeated or dominant answers · where the rows came from.",
        "Evaluation (35): tried on answers already known right and wrong · right kind of check for this output · same answer every time · separates good answers from bad.",
        "Agent (25): how many settings-combinations there are to try · what the model is told, and shown · whether the answer's shape is pinned down · whether it ends, and on what · tools it declares, and can reach.",
        "Bands: NOT READY 0-29 · PARTIAL 30-54 · WORKABLE 55-74 · STRONG 75-89 · EXCELLENT 90-100.",
        "The agent pillar is read from the selected agent's own code - which parameters it may already vary, each against a checked source line; comments, docstrings, TODOs and example-only bindings are rejected. The four build observations keep their citations but stay out of the opening score until an independent check verifies them.",
        "Two things the pillar is not allowed to guess are named on the card instead: whether your dataset and your evaluation method are wired into the agent - this run builds that afterwards and checks it against the installed SDK.",
      ],
      metrics: [],
      steps: [],
      sources: [
        `${READINESS} · CHECK_DISPLAY_NAMES`,
        `${READINESS} · DEFAULT_WEIGHTS`,
        `${READINESS} · BAND_THRESHOLDS`,
        `${README} · The readiness score`,
      ],
      notes: [
        "The weighting is the argument: 40 points on the dataset says plainly that an optimization cannot outrun the material it is measured on.",
        "A verified source read can earn opening search-space credit, but the separate pre-approval request-difference proof decides whether a paid grid may run.",
        "A source read that finds no usable dimension blocks the paid run, because a search would compare one configuration; where nothing names an agent at all, the score reports that instead.",
      ],
    },
    {
      id: "readiness-ceilings",
      kind: "matrix",
      eyebrow: "STAGE 2 OF 5 · THE CEILINGS",
      title: "The ceilings, from the scorer's own constants.",
      body: "Every cap is a ceiling on the 0-100 score, ranked so a worse condition gets a lower ceiling. A condition routed to a creation or repair blocks the paid run; one that only scopes what the result may claim lets the run proceed. The ceilings below are the scorer's constants at the cited revision.",
      bullets: [],
      metrics: [],
      steps: [],
      matrix: [
        {
          startingPoint:
            "Evaluator invalid - it scores a known-wrong answer as well as a known-right one",
          safestNextStep:
            "Ceiling 25 and blocked: repair and revalidate the evaluator before any paid comparison; the lowest ceiling any evaluator condition carries.",
        },
        {
          startingPoint:
            "Evaluator unvalidated - no calibration on known-good and known-bad answers has run yet",
          safestNextStep:
            "Ceiling 45, not blocking: validate the evaluation method and the ceiling lifts; the card shows the pillar as thinly measured until then.",
        },
        {
          startingPoint:
            "No varying knobs - the agent's settings document or source read establishes no usable dimension",
          safestNextStep:
            "Ceiling 45; blocks where nothing usable is established, because a search would compare one configuration. Advisory where source evidence merely could not be checked.",
        },
        {
          startingPoint:
            "Generated dataset - every row declared generated, or a dataset that declares no provenance at all",
          safestNextStep:
            "Ceiling 65, not blocking and asking nothing: label the walkthrough honestly and connect collected rows before a production claim.",
        },
        {
          startingPoint:
            "A model-written answer key, or fewer comparable examples than a stable comparison needs",
          safestNextStep:
            "Ceiling 74, not blocking - one below the Strong boundary. The answer key is put to you once with two exits; a small set is a wiring check and may get a bounded top-up offer on the same ask.",
        },
      ],
      sources: [
        `${READINESS} · CAP_SEVERITY_ORDER`,
        `${READINESS} · ROUTE_CATEGORY`,
        `${README} · The readiness score`,
        `${GLOSSARY} · Core terms`,
      ],
      notes: [
        "A capped project is not a failed project. A truthful 45 with a named ceiling is more useful than an unsupported 90.",
        "74 rather than 75 is deliberate: 75 is the Strong threshold, and a dataset whose entire answer key a model wrote may be workable but may not present as Strong.",
        "A fully generated dataset caps at 65, so Strong and Excellent are arithmetically unreachable until collected rows arrive; the run still proceeds end to end.",
      ],
    },
    {
      id: "stage-baseline",
      kind: "statement",
      eyebrow: "STAGE 3 OF 5 · BASELINE",
      title:
        "Measure the current configuration before searching for a better one.",
      body: "Stage 3 of 5 is the first thing in the run that costs money. After one explicit approval the assistant runs the customer's existing baseline exactly as defined - or, only when none exists, a credible twelve-configuration local fixed grid - on the customer's own provider key, with no Traigent account or key involved.",
      bullets: [
        "Preview before the paid calls: scope, configurations, calls, metric, runtime, estimated spend, recipients, and one total walkthrough ceiling defaulting to $5.00 - an execution stop target, not a billing guarantee.",
        "A user-owned baseline keeps its exact rows and models in both measurements; one row is correct when that is what the user defined, and it is never padded to twelve.",
        "A generated sweep uses one model family from the route already in hand: a fast tier, a mid tier, and a strong tier one step below the newest flagship - skipped deliberately so the first run stays quick and cheap, priced separately if wanted.",
        "The result - best configuration, primary tuning metric, cost, latency, trial and failure counts, a short note per knob - is on screen before any Traigent account or key request.",
        "Exact upload without a rerun happens only when the installed SDK exposes a public sync id; otherwise the baseline stays local and is labelled local-only.",
        "It is a local fixed grid, not Traigent choosing what to test - and local is not free: provider calls spend from the same approved total.",
      ],
      metrics: [],
      steps: [],
      sources: [
        `${GUIDE} · Default run`,
        `${README} · Requirements`,
        `${RUN_SAFETY} · Approval and budgets`,
        `${SDK_EXECUTION} · Walkthrough model ladder`,
      ],
      notes: [
        "An existing baseline is never replaced or padded: even a one-row baseline is preserved unchanged and run as it stands. Only a truly missing baseline gets the generated grid.",
        "The generated grid is 3 models x 2 prompt styles x 2 thinking shapes = 12 configurations, run as 12 trials so every one of them executes.",
        "Provider errors, missing credentials or stop-target breaches stop loudly; nothing is mocked or invented to fill the gap.",
      ],
    },
    {
      id: "stage-optimize",
      kind: "statement",
      eyebrow: "STAGE 4 OF 5 · OPTIMIZE",
      title:
        "One bounded managed search, separately approved, with its space named.",
      body: "Stage 4 of 5 starts only after the baseline result and the Traigent key that follows it. A zero-LLM portal probe - a stub agent that returns a constant, so it costs $0 in LLM spend - proves the key is present, authenticates, is scoped for experiment.write, and that a session and a cloud_url come back before any connected paid trial.",
      bullets: [
        "Approved on its own card after the baseline: Traigent access, recipients and data, scope, runtime and ceiling. Baseline approval never pre-authorizes it.",
        "The card names the space's total combination count beside the ceiling of 12, so the 12 reads against the space it is drawn from; Traigent chooses which configurations as it goes rather than working through a fixed list.",
        "It keeps every baseline value and model and adds only meaningful non-model controls the agent consumes; any new model is a separately disclosed experiment.",
        "A disclosed runtime, cost or plan limit can make the approved comparison smaller; the report gives the number of configurations actually tested and the concrete shortfall reason.",
        "On more than about 100 usable rows the paid comparison is bounded to a small subset spread across the difficulty range, drawn inside each split with the selected row ids recorded; the report names the subset size beside the full row count.",
        "Readiness is never scored on that subset: every readiness run reads the whole dataset.",
      ],
      metrics: [],
      steps: [],
      sources: [
        `${RUN_SAFETY} · Connected-run readiness`,
        `${README} · What the run does`,
        `${SKILL} · 7. Run the honest comparison`,
        `${EVALUATION} · First-run subset for a large dataset`,
      ],
      notes: [
        "The second gate is deliberate: the recipients, the number of calls and the data boundary change when the Traigent service enters.",
        "Frame the managed search as a deliberately small enhancement: a few evidence-driven knobs, a small slice of what Traigent can drive, not its full capability.",
        "If the probe fails on any rung, the run stops before any connected paid trial and shows a sanitized reason.",
      ],
    },
    {
      id: "selection-and-heldout",
      kind: "journey",
      eyebrow: "STAGES 4 TO 5 · THE HONEST COMPARISON",
      title:
        "Choose on tuning evidence; check one recommendation on held-out rows.",
      body: "Scoring several candidate configurations on the same rows and keeping the best one selects partly on real signal and partly on that sample's noise, so the winner's tuning score is inflated by the act of choosing it. The held-out rows exist to check that risk - not to eliminate it, and never to choose.",
      bullets: [],
      metrics: [],
      steps: [
        {
          label: "Reserve ten rows",
          detail:
            "10 held-out rows (2 easy, 3 medium, 3 hard, 2 very hard) reserved at creation time, in their own file, before any component design, calibration or optimization touches the dataset. A project with its own held-out split keeps it as it stands.",
          executor: "Coding assistant",
        },
        {
          label: "Select on tuning scores",
          detail:
            "One recommendation from the tuning scores across the baseline grid and the managed search; the search's winner is not the answer by position, and at a tie the cheaper configuration is preferred.",
          executor: "Coding assistant",
        },
        {
          label: "Score it once",
          detail:
            "Only that configuration runs against the reserved rows, inside the same approved paid work. Scoring two and keeping the higher would be selection, and a set used for selection is not held out.",
          executor: "Coding assistant",
          humanGate: "Inside the approved paid work",
        },
        {
          label: "Disclose the limit",
          detail:
            "Counts, not percentages: on ten rows one standard error is about 15 points near 50%. The report says the held-out number can land lower, level or higher and that ten examples cannot settle which - and never that Traigent prevents it.",
          executor: "Coding assistant",
          humanGate: "Customer reads the caveat",
        },
      ],
      sources: [
        `${EVALUATION} · Held-out set and claims`,
        `${GLOSSARY} · Core terms`,
        `${README} · Traigent - First Run`,
      ],
      notes: [
        "Wording matters: a held-out set is a sealed holdout only when its split and labels stayed hidden until the candidate was locked. Because the assistant creates and can inspect the walkthrough split, the guide calls it held-back and non-blind.",
        "The default walkthrough data is 28 rows split 18 tuning and 10 held-out, reserved at creation.",
        "A gap between the tuning and held-out score is expected and is not called overfitting; it is the ordinary result of picking the best of several configurations on a small sample.",
        "A flat result on demonstration data says nothing about production; the guide forbids describing measured lift on synthetic rows as expected customer lift.",
      ],
    },
    {
      id: "stage-results",
      kind: "statement",
      eyebrow: "STAGE 5 OF 5 · RESULTS",
      title:
        "Report what changed, what it cost, and what the evidence cannot support.",
      body: "Stage 5 of 5 leads with a layered summary: outcome, what the evidence establishes, current state and limits, one next action, then details - configurations, objectives, trials, failures, cost, stop reason, artifacts and verified links. Before saying the run succeeded, every post-run check applies, including that portal links exist and were verified.",
      bullets: [
        "Best baseline configuration against best enhanced configuration on the tuning set, each run's accuracy-cost frontier in the details layer, and the recommended configuration's held-out score with its small-sample note shown first.",
        "Cost, the configurations tested out of the space's total, failures and stop reason, plus the approved total, what this run spent against it, and what is left.",
        "Artifacts under traigent-runs/ (ignored when the project uses Git), the append-only run-log.jsonl, and a direct verified link for every persisted portal experiment; an unsynced baseline is labelled local-only, and nothing is deleted as cleanup.",
        "Component provenance on every result: ✅ real and validated, ❗ missing or evidence-limited, substitutes named under walkthrough setup. When any substitute was used, the interpretation opens by saying the result is not evidence of expected production performance.",
        "No lift is a valid result: the flat or negative delta first, then verified facts, evidence-backed inferences and untested hypotheses, with 'cause not established by this run' unless the evidence rules a cause in.",
        "One next action the recorded opening state earns; advanced learning links and lifecycle suggestions only after the customer has seen the result.",
      ],
      metrics: [],
      steps: [],
      sources: [
        `${SKILL} · 8. Verify and report`,
        `${RUN_SAFETY} · Post-run verification`,
        `${GUIDE} · Result interpretation`,
        `${README} · Repository layout`,
      ],
      notes: [
        "The end goal is an explainable decision. A result without its baseline, evidence boundary and limitations is not a valid first-run outcome.",
        "If the configuration already in use is the recommendation, that is a useful result: the current settings were not shown to be the problem.",
        "The run's scope is stated in its own recorded numbers - rows scored beside usable rows, trials beside the space's combination count - as a scope statement, never a pitch.",
        "No configuration is promoted from a fully synthetic run; for real components, promotion still needs explicit approval and a later validation check.",
      ],
    },
    {
      id: "requirements-and-licensing",
      kind: "statement",
      eyebrow: "REQUIREMENTS AND LICENSING",
      title: "Requirements and licensing, stated once.",
      body: "Python 3.11-3.13 in an isolated environment, the tested first-run SDK stack pinned in skills/traigent-first-run/assets/requirements-first-run.txt, and one supported LLM-provider key with a small amount of credit for the real run. A Traigent portal key that can write experiments is activated after the first result is on screen, not before; if none is present, the assistant asks for a full-access key then.",
      bullets: [
        "Pinned stack: traigent==0.26.0, litellm==1.93.0, python-dotenv==1.2.2 - installed into the dedicated environment whatever the project declares for itself; never an unversioned pip install traigent.",
        "Provider key first, into an owner-only local .env verified untracked and effectively ignored; a preserved Traigent key is activated, or one requested, only after the baseline checkpoint.",
        "This repository - the walkthrough, bundled skill, scripts and references - is Apache-2.0; using it inside a proprietary project does not relicense that project's unrelated code, data, prompts or outputs.",
        "The Traigent SDK is distributed under separate terms: AGPL-3.0-only, or a Traigent commercial license under a separate written agreement. Installing the package grants no commercial terms; contact legal@traigent.ai.",
        "Node.js is needed only for the optional npx skills add installation, not for the Traigent Python run.",
      ],
      metrics: [],
      steps: [],
      sources: [
        `${README} · Requirements`,
        `${README} · License`,
        `${README} · SDK licensing`,
        `${REQUIREMENTS} · pinned versions`,
      ],
      notes: [
        "Two licences, two artifacts: the guide is Apache-2.0, the SDK it installs is AGPL-3.0-only or commercial. Apache-2.0 rights in the guide do not relicense the SDK.",
        "The baseline needs no Traigent account, so the customer sees a real number from their own project before deciding whether to register.",
      ],
    },
    {
      id: "repository-layout",
      kind: "statement",
      eyebrow: "REPOSITORY LAYOUT",
      title: "What is in the repository.",
      body: "The repository is small: an entry point for a cloned run, one self-contained installable skill that carries the same workflow, a reference environment file, and the guide's own tests and guards. During a run, the assistant writes only under traigent-runs/ in the customer's project.",
      bullets: [
        "GUIDE.md - entry point for a cloned-repository run; it routes to skills/traigent-first-run/SKILL.md and loads each reference at the stage that needs it.",
        "skills/traigent-first-run/ - SKILL.md, references (glossary, run-safety, sdk-execution, evaluation-and-dataset, component-creation), scripts (preflight.py, readiness.py, validate_run_log.py), assets (run-plan.md, requirements-first-run.txt).",
        ".env.example - reference environment settings.",
        "traigent-runs/ (created during a run) - walkthrough artifacts, run-log.jsonl, and one readiness/<YYYYMMDDTHHMMSSZ>/ directory per scoring; ignored when the project uses Git.",
        "reports/ - field-test evidence and methodology research behind the safeguards.",
        "tests/ and tools/ - the guide's own quality gates and CI guards. They test the guide, not your project; you never need to run them.",
      ],
      metrics: [],
      steps: [],
      sources: [
        `${README} · Repository layout`,
        `${GUIDE} · Keep the guide source separate from the project being optimized`,
        `${SKILL} · Bundled guidance index`,
      ],
      notes: [
        "The skill directory is exactly what the Agent Skill installer copies, so the clone path and the installed-skill path follow one workflow.",
        "traigent-runs/ belongs to the customer's project, never to the guide clone; the assistant keeps the customer's project as the working directory.",
      ],
    },
  ],
} satisfies PresentationSpec;

const coreSlideIds = [
  "ready-to-optimize",
  "one-customer-prompt",
  "shared-control",
  "works-from-whatever-you-have",
  "readiness-at-a-glance",
  "caps-blockers-and-asks",
  "spend-and-safety-boundaries",
  "what-leaves-your-machine",
  "what-the-customer-gets",
  "how-presales-runs-it",
] as const;

const appendixSlideIds = [
  "stage-inspect",
  "stage-readiness",
  "readiness-scoring",
  "readiness-ceilings",
  "stage-baseline",
  "stage-optimize",
  "selection-and-heldout",
  "stage-results",
  "requirements-and-licensing",
  "repository-layout",
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
