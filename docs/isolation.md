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
it.

## What the agent sees, and what it does not

```
~/demos/first-try/
├── demo.json     <- NOT for the agent
└── project/      <- this is the working directory
```

`demo.json` records which state each component was put in, every file's SHA-256, and the
handoff prompt. An agent that reads it knows the answer before it starts. Keep it out of the
working directory, out of the prompt, and out of anything pasted into the session.

The same goes for the rest of this repository. If the agent can see `components/`, it can
read the file it was given next to the three it was not, and the difference between them is
the whole question.

## The environment

The first-run guide creates its own environment, `.venv-traigent`, inside the project. Two
consequences:

**A demo never ships one.** If `.venv-traigent` already exists the guide stops, reports the
path, and asks for it to be inspected -- so a demo carrying one cannot be run at all. No
combination of flags produces one, `build.py` checks before it finishes, and a test asserts
it.

**A demo ships no dependency declaration either.** The guide installs its own tested pins,
which already cover what these projects need. Anything declared here would add nothing and
could only disagree with what is about to be installed.

`--existing-venv` is separate from both. It puts an environment into the project as
*scenery* -- a project that already has one, which is how most projects arrive:

| | |
|---|---|
| `none` | no environment. The default. |
| `one-compatible` | one environment on a supported interpreter, inside the project root. |
| `old-python` | one environment on Python 3.10, below the supported floor. |

Nothing in the demo runs from it. It is there so a run can start from a project that has one
and what happens next can be observed. This repository asserts nothing about what the guide
does with it -- that behaviour belongs to the guide, and testing it from here would only pin
someone else's decision in place.

## Running one

```bash
python build.py demo --preset ready --out ~/demos/first-try
cd ~/demos/first-try/project
```

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
python build.py demo --preset ready --guide local \
    --guide-src ~/code/traigent-first-run --out ~/demos/pinned
```

The guide then lands at `project/traigent-first-run/`, the handoff points at it rather than
at a clone, and `demo.json` records the checkout's commit.

## Afterwards

`demo.json` lists every file with its hash as it was built. Comparing against it afterwards
shows what the run changed:

```bash
cd ~/demos/first-try
python - <<'PY'
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

Anything the run added -- `.venv-traigent`, `.env`, and everything the guide writes under
`traigent-runs/` -- will not be in the record, because it was not there when the demo was
built. (With `--calibration present` the project already has one file under `traigent-runs/`,
its probe answers, and that one *is* in the record.)

Demos are disposable. Build a new one rather than reusing one that has been run: a project
that has already been through a run carries its notes, its environment and its results, and
the next run reads them.
