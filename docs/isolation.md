# Keeping a demo separate

A demo is a stand-in for a stranger's project. Everything here exists so that when an agent
looks at one, what it sees is that project and nothing else -- not this repository, not the
answers, not the last run.

## Where a demo goes

`build.py` refuses to build into a directory that already exists, and refuses to build
anywhere inside a Git working tree:

```
error: output would land inside the Git working tree at /home/you/code/some-project.
Build demos outside every checkout -- a demo inside one gets picked up as part of that
project, and the guide is supposed to see only the demo.
```

This is not tidiness. An agent asked to work on a project reads outward from it: sibling
directories, the repository root, whatever configuration is above it. A demo built inside a
checkout is read as part of that checkout, and a demo built inside *this* checkout can see
the component library and the licence of every state it might have been in.

Put demos somewhere plain -- `~/demos/`, a scratch directory, anywhere with no `.git` above
it. `build.py` will not create the parent for you: `--out ~/demos/first-try` on a machine with
no `~/demos` exits 2 with `error: the parent directory does not exist`. `mkdir -p ~/demos`
first, once.

## What the agent sees, and what it does not

```
~/demos/first-try/
├── demo.json     <- NOT for the agent
└── project/      <- this is the working directory
```

`demo.json` records which state each component was put in, every file's SHA-256, and the
handoff prompt -- and, for a damaged dataset, what was done to it: which six rows `leaky`
emits twice, which lines `torn` cut, which databases `split-by-database` holds out. An agent
that reads it knows the answer before it starts. Keep it out of the working directory, out of
the prompt, and out of anything pasted into the session.

One project carries a note the customer wrote. `--agent two-agents` ships `PROJECT.md` at the
project root, saying which of the two agents to work on; it is in the customer's voice, it is
part of the project, and the agent is meant to read it. It names no state and no generator,
and `verify` reads it like any other file.

The same goes for the rest of this repository. If the agent can see `components/`, it can
read the file it was given next to the three it was not, and the difference between them is
the whole question.

### The directory name is part of the demo

A bank has the same problem one level up, so `suite` writes `bank.json` at the root and names
every directory `project-<8 hex of the preset's sha256>`:

```
~/demos/bank/
├── bank.json           <- NOT for the agent
├── project-b24d6d33/   ready
├── project-05a193a3/   wrong-answers
└── ...
```

Two reasons, and the second is the one that forced it. A directory called `wrong-answers` says
what the demo is to anything that reads a path -- and with `--venv ready` something will, since
a virtual environment writes its own absolute path into `activate` and into every console
script inside it. `build.py` strips what it can (`pyvenv.cfg` keeps only `home`,
`include-system-site-packages` and `version`; `command` and `executable` recorded the build
path and are dropped) and cannot strip the rest without breaking the environment.

`verify` therefore reads the demo's own resolved path against the same roster of tells it reads
file names and file contents against, and recommends one of two repairs depending on whether
the project holds an environment:

- **no environment** -- `Rename the directory. Nothing inside the demo records where it is, so
  moving it is enough and it does not have to be built again.`
- **an environment** -- `Build it somewhere else. The project's environment has this path
  written into every script in it, so renaming the directory would break the environment rather
  than clean it.`

### The one file a project carries about itself

A project that ships rows also ships `project/ATTRIBUTION.txt`, and that is the only legal
file in it. It has to be there: CC BY-SA 4.0 requires the attribution and a notice of
modification to travel with the data.

It is also the reason the first paragraph of this file is true today and was not before.
Projects used to ship `NOTICE`, `LICENSE` and `LICENSE-DATA` as well. All three named this
repository by name, and `NOTICE` described the directory it was sitting in as a generated demo
-- so every project in every one of the seventeen states there were then arrived telling the
agent exactly what it was looking at, before it read a line of code. `ATTRIBUTION.txt` carries the same
obligations and names nothing: the original work, the licence and its URI, the kinds of
modification made, and a warning not to report a score measured on a modified subset as a
Spider score. No generator, no preset, no state. `verify` reads it like any other file and
finds nothing.

## The environment

What the first-run guide does about an environment changed on 2026-09-14 (traigent-first-run
#545). It looks for a virtual environment directly under the project root and proposes
installing the SDK into it -- one candidate proposes itself, several are offered as a lettered
choice -- after an approval card that shows what the install would add and which installed
packages would change version; a `traigent` or `litellm` already at or above the tested pin is
kept. With no usable environment and the `.venv` name free, it offers to create a persistent
project `.venv` for the customer to keep. `.venv-traigent` is the throwaway fallback, taken
only when the customer declines the install into their own environment, refuses a version
change, or `.venv` is occupied. Three consequences for a demo:

**A demo never ships `.venv-traigent`.** The guide never adopts a throwaway environment from
another run, and on the fallback route it stops when that path already exists without a
verified setup of its own, reports the path, and asks for it to be inspected. A demo carrying
one would either be passed over as a candidate or stop the fallback route -- neither is a
starting state anyone arrives with. No combination of flags produces one, `build.py` checks
before it finishes, and a test asserts it.

**A demo ships no dependency declaration either.** The guide reads `requirements.txt`,
`pyproject.toml` and `setup.py` only to see whether the project already lists `traigent`
(preflight's `existing-traigent-use` check); it never edits them and never installs from them.
Anything declared here would add nothing and could only disagree with what is about to be
installed.

**`--venv ready` now changes the route the run takes.** A demo used to be able to ship an
*empty* pre-existing environment as scenery; measured at `6ec2b9c1`, all of its settings
produced byte-identical preflight and readiness output, because the guide then built its own
environment regardless and never read a project's, so that option was removed. What
`--venv ready` builds today is a working environment -- `.venv`, on the newest supported
Python, with the agent's dependency installed -- and since `9eaabbb2` there is something to
observe: the guide finds it, proposes it by absolute path, and shows an approval card for
installing into it, where a demo without one is offered a fresh `.venv` instead. The run
records the route it took and the environment's path and versions in
`traigent-runs/run-plan.md`.

## Running one

```bash
mkdir -p ~/demos
python3 build.py demo --preset ready --out ~/demos/first-try
cd ~/demos/first-try/project
```

(`--out` must not already exist. Every `--out` in this file is a different path for that
reason; reusing one exits 2.)

Start a fresh agent with that directory as its working directory. A fresh one matters: an
agent that has already seen this repository in the same session has seen the answers.

Give it exactly this, and nothing else:

```text
Help me run my first Traigent optimization.
Clone https://github.com/Traigent/traigent-first-run and follow GUIDE.md.
```

No hints, no mention of what was left out, no "check whether the evaluator is any good". The
prompt is the whole input. Adding to it tests a different thing than the one a customer gets.

For a run pinned to a particular revision of the guide, or a run with no network, copy a
reviewed checkout in instead:

```bash
python3 build.py demo --preset ready --guide local \
    --guide-src ~/code/traigent-first-run --out ~/demos/pinned
```

The guide then lands at `project/traigent-first-run/`, the handoff points at it rather than
at a clone, and `demo.json` records the checkout's commit.

The guide's `GUIDE.md` tells the assistant to clone beside the project, never inside it, and to
announce an exclusion of the checkout root when the guide source is already inside the project
-- which is what a `--guide local` demo is. That is the assistant's rule, not the customer's: the
customer prompt says nothing about where the clone goes. A `--guide local` demo is a documented
divergence from the layout the guide recommends to itself.

**`verify` goes red on that demo, and it is not the demo that is wrong.** Measured on
2026-09-02 against guide revision `6ec2b9c1`: `build.py verify --demo ~/demos/pinned` exits 1
with **28 findings**, every one of them a file under `project/traigent-first-run/`, and every
one of them a word from the blinding roster appearing in the guide's own prose:

```
  pinned
      traigent-first-run/CLAUDE.md contains 'fixture', which says this is a test
      traigent-first-run/README.md contains 'deliberate', which says this is a test
      traigent-first-run/skills/traigent-first-run/scripts/readiness.py contains 'preset', ...
      ... 25 more, all under traigent-first-run/
```

That roster -- `preset`, `fixture`, `plant`, `scenario`, `deliberate`, `is observed`,
`generated demo`, `spider_traigent`, `first_run_scenario`, `build.py`, `demo.json`, plus every
hyphenated preset and component name longer than six characters (from `agent-and-logs` to
`wrong-wiring`; the nine ported presets added `holdout-labelled`, `holdout-only`,
`leaky-split`, `length-blind`, `opaque-scorer`, `raw-export`, `split-by-database`,
`torn-lines`, `two-agents` and `undeclared-source`, and the provenance and cost round after
them added nine: the preset names `generated-answer-key`, `mostly-generated-answer-key`,
`mostly-synthetic-source`, `mostly-undeclared-source` and `slow-scorer`, and the dataset-state
names `generated-answers`, `mostly-generated-answers`, `mostly-synthetic` and
`mostly-undeclared`. `slow`, the evaluator state, is four characters and below the
threshold) --
exists to catch *this repository* leaking into a project. The first-run guide is a document about running first-run evaluations, so it uses
those words for their ordinary meaning: `readiness.py` has a `--preset`-shaped vocabulary,
`run-safety.md` says "deliberate", `component-creation.md` says "fixture", and `hand-written`
and `exact-match` -- two of this repository's preset and component names -- appear in the
guide's scripts in their ordinary sense. None of that names a state, a preset or a generator.
The same demo built with `--guide clone` verifies clean, which is the control.

So, for an operator:

- **Read the findings, do not silence them.** Confirm every path is under
  `traigent-first-run/`. A finding on `agent.py`, `evaluator.py`, `dataset.jsonl`,
  `catalog.json`, `README.md`, `.env.example` or `ATTRIBUTION.txt` is a real leak and the demo
  should not be used.
- **Verify the blinding separately if you want a green gate.** Build the same preset with
  `--guide clone` into a second directory and run `verify` on that; it exercises every file the
  `--guide local` demo has except the copied checkout.
- **Do not chase it in the roster.** Dropping `preset` or `deliberate` from the tell list to
  make this recipe green would blind the check against the leak it was written for -- the
  roster was widened once already, after "Spider Traigent First Run Scenario" passed a list
  that held `spider_traigent`.

The honest summary is that `verify` and `--guide local` answer different questions and the
current check cannot tell one body of text from the other. Nothing is worked around here; the
red is documented instead.

## Afterwards

`demo.json` lists every file with its hash as it was built. Comparing against it afterwards
shows what the run changed:

```bash
cd ~/demos/first-try
python3 - <<'PY'
import hashlib, json, pathlib
record = json.loads(pathlib.Path("demo.json").read_text())
project = pathlib.Path(record["project_directory"])
for entry in record["files"]:
    path = project / entry["path"]
    if not path.exists():
        print("gone     ", entry["path"])
    elif hashlib.sha256(path.read_bytes()).hexdigest() != entry["sha256"]:
        print("changed  ", entry["path"])
PY
```

Anything the run added will not be in the record, because it was not there when the demo was
built: `.env`, a `.venv-traigent` or a `.venv` the run created, and everything the guide
writes under `traigent-runs/` -- `run-plan.md`, `readiness/<timestamp>/`, `run-log.jsonl`, and
on the copied-actor route a copy of the evaluator under `calibration/`. Packages the run
installs into a `.venv` the demo shipped do not show either, because `inventory()` in
`build.py` leaves `.venv` out of the record. (With `--calibration present` the project already
has one file under `traigent-runs/`, its probe answers, and that one *is* in the record.)

Demos are disposable. Build a new one rather than reusing one that has been run: a project
that has already been through a run carries its notes, its environment and its results, and
the next run reads them.
