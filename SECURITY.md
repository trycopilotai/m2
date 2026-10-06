# Security

## Reporting a vulnerability

Report privately through GitHub:
<https://github.com/trycopilotai/m2/security/advisories/new>

That opens a private security advisory visible only to the
maintainers. Do not put the details of a vulnerability in a
public issue.

If that link shows "Not Found", private reporting is not
turned on for this repository. Open a public issue titled
"Security report waiting" that says only that you have a
report, with no details, and a maintainer will arrange a
private channel.

## What is in scope

- **Prompt content that redirects an agent.** `SKILL.md` and
  the four files under `references/` are instructions an
  agent may follow. Text in any of them that makes an agent
  send data to a place the operator did not name, or that
  makes it act outside its repository or take instructions
  from content in ways the next section does not already
  state, is a valid report.
- **The install blocks.** The two README blocks run
  `mkdir -p`, `mktemp -d`, `git clone`, `cp`, `mv` and
  `rm -rf`, all inside one skills directory under `$HOME`. A
  repository state that makes either block write or delete
  outside its install target is in scope.
- **The build and test scripts.** These are not part of the
  skill and neither install block copies them.
  `assets/build.py` finds a Chrome or Chromium binary from a
  fixed candidate list, runs it headless with a temporary
  profile directory, and writes the preview PNG and its
  stamp. `scripts/generate_demo.py` writes two SVG files;
  `scripts/verify_demo.py` reads files and writes none.
  `scripts/record_session.py` copies `skills/` and
  `tests/test_package.py` into a temporary directory, writes
  a small `python3` launcher beside them, runs the test
  there through `sh`, and rewrites the transcript and the
  manifest. With `RECORD_RAW_DIR` set it also writes the
  unedited capture into that directory.
  `scripts/render_invocation.py` reads a client's raw JSON
  lines and a prompt file, and writes a transcript to
  standard output.
  `tests/test_package.py` reads the files under
  `skills/m2/`. `tests/test_integrations.py` runs `git`
  against the repository root, runs `tests/test_package.py`
  once, and loads the two demo scripts to compare the images
  with the transcript.

## What the documents tell an agent to do

These are properties of the text, stated so you can decide
whether to use it. They are known limits, not findings:

- `references/m2.protocol.md` tells a conductor to keep
  working until its exit conditions are met, and, in a
  turn-based harness, not to send a human-facing message
  between packets while a run is not terminal.
- It tells the conductor to commit, push branches, and open
  or update pull requests as delivery events inside the
  loop, to merge ready pull requests, to close pull requests
  that its own work has superseded, and, in one recovery
  path for an owned branch, to reset that branch and
  force-push with lease.
- It tells the conductor to dispatch other agents as
  managers, workers, testers and reviewers.
- It tells the conductor to read and write outside the
  repository it was started in: the plan store at
  `~/<plan-store>` and that store's Git directory, where
  resume pointers go, and a run directory with worktrees
  beside the repository (`m2-runs` in the parent directory,
  or the directory `M2_RUNS_ROOT` names).
- It tells the conductor to load a saved resume prompt named
  by a pointer file and to treat its text as if the human
  had pasted it. The only check on that text is a hash
  stored in the same record, so anything that can write the
  pointer and the record can supply the prompt.
- `references/m2.protocol.md` and
  `references/m1.protocol.md` tell the agent to read the
  repository's `AGENTS.md`, and `references/m1.protocol.md`
  tells it to honor the repository's instructions.
- It says an agent must not install a hook that blocks its
  own stopping, and leaves such a gate to the operator.
- Nothing in this repository enforces any of that text. An
  agent that follows it acts with whatever permissions its
  host gives it, and nothing here narrows them.

## What is out of scope

The documents name companion protocols, repository commands,
a plan store and a model that are not in this repository.
Their behaviour, and the behaviour of Claude Code, Codex, or
any other host, is out of scope here. Report those to their
own maintainers.
