# Contributing

This repository is one skill made of four protocol
documents, and the scripts that record the transcript, build
and check the demo images, and test the packaging.

## Run the checks first

```sh
make check
```

That runs `tests/test_package.py` and
`tests/test_integrations.py`. Both need `python3` and
nothing outside the standard library. The second also needs
`git` and a real clone with its history and tags, because it
reads `git log` and the release tag.

**The second suite pins prose.** These will fail on an
innocent-looking edit:

- the claim line at the top of the README must appear
  verbatim;
- each install block must carry its own `release=` pin at
  the version both plugin manifests ship;
- `SKILL.md` must stay under 500 lines;
- `evidence/demo-manifest.json` records the SHA-256 of
  `SKILL.md`, of `agents/openai.yaml`, of the four
  documents, of `tests/test_package.py` and of the
  transcript, so an edit to one of those eight files, prose
  included, fails until the manifest is refreshed as
  described next;
- two docstrings in `tests/test_package.py` are quoted in
  `tests/test_integrations.py` as `FILES_LINE` and
  `NO_PROGRAM_LINE`, so change them together.

If you change one of those, change the thing it describes
too.

## Changing a document, the skill file or the packaging test

After an edit to `SKILL.md`, to `agents/openai.yaml`, to a
file under `skills/m2/references/`, or to
`tests/test_package.py`, run:

```sh
make record
make demo
```

`make record` runs `scripts/record_session.py`. It runs the
command listed in the manifest in a throwaway directory,
writes the transcript with the test duration removed, and
rewrites the manifest's hashes, date and interpreter. If the
test does not pass it rewrites neither the transcript nor
the manifest and exits 1. It needs `sh` and `python3`.
Record with Python 3.11 or newer: older versions print each
test's name in a different form, and the committed
transcript uses the newer one. `make demo` rebuilds the two
images from the transcript. `make assets` rebuilds the
social preview and needs Chrome or Chromium;
`make asset-check` does not.

## What is most useful

Open an issue for any of these. The labels
`good first issue` and `help wanted` mark the ones that are
ready to pick up.

- **A place where two documents disagree** that the README's
  list of known disagreements does not have yet. Quote both
  passages.
- **A dependency the README does not list.** Name the
  passage that needs something this repository does not
  include.
- **A report of trying it.** Say which host ran it, what you
  bound the placeholders to, and where the agent first left
  the protocol.

## Pull requests

Prose changes to the four documents are welcome, including
ones that settle a known disagreement. Say what the text
told an agent to do before the change and what it tells it
after.

Keep `SKILL.md` under 500 lines; the suite enforces it.
Frontmatter carries `name` and `description` and nothing
else. Keep the package free of program files; the packaging
test enforces that.

The top-level `skill` is a symlink to `skills/m2/`. Do not
reverse that orientation.

Commit with your own identity and no `Co-authored-by`
trailer of any kind. The suite fails on one anywhere in
history, so do not apply review suggestions through the
GitHub UI, and do not squash-merge a pull request that has
more than one author.
