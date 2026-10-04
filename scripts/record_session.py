#!/usr/bin/env python3
"""Record the packaging test again and refresh the evidence manifest.

    python3 scripts/record_session.py

The command is the one listed in ``evidence/demo-manifest.json``.
It runs in a throwaway directory that holds a copy of ``skills/``
and of ``tests/test_package.py``. The transcript is what a shell
would show: the command line, the test's output, and the exit
status. One edit is made before it is written: the elapsed time
that unittest prints after the test count is removed, so that
line ends after the count.

The manifest's hashes of ``SKILL.md``, ``agents/openai.yaml``,
the four documents, the packaging test and the transcript are
then rewritten, with the date and the interpreter. Run
``make demo`` afterwards to rebuild the images.

If the test does not pass, or its output has no duration line,
the script prints why, writes neither file, and exits 1.

Set ``RECORD_RAW_DIR`` to a directory to also keep the unedited
capture there.

This records a test of the package's files. It runs no part of
the m2 protocol and starts no agent.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import platform
import re
import shlex
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "evidence" / "demo-manifest.json"
DURATION = re.compile(r"^(Ran \d+ tests?) in [0-9.]+s$", flags=re.M)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def strip_duration(raw: str) -> str:
    """Remove the elapsed time from the ``Ran N tests in 0.001s`` line."""
    return DURATION.sub(r"\1", raw)


def record(commands: list, workdir: Path, bindir: Path) -> tuple:
    environment = {"PATH": "%s:/usr/bin:/bin" % bindir, "PYTHONDONTWRITEBYTECODE": "1"}
    lines = []
    failed = False
    for command in commands:
        result = subprocess.run(
            ["sh", "-c", command],
            cwd=str(workdir),
            env=environment,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        lines.append("$ " + command)
        lines.extend(result.stdout.splitlines())
        lines.append('$ echo "exit status: $?"')
        lines.append("exit status: %d" % result.returncode)
        if result.returncode != 0:
            failed = True
    return "\n".join(lines) + "\n", failed


def main() -> int:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    commands = manifest["invocation"]["commands"]
    with tempfile.TemporaryDirectory() as scratch:
        base = Path(scratch).resolve()
        workdir = base / "capture"
        bindir = base / "bin"
        bindir.mkdir()
        launcher = bindir / "python3"
        launcher.write_text(
            '#!/bin/sh\nexec %s "$@"\n' % shlex.quote(sys.executable),
            encoding="utf-8",
        )
        launcher.chmod(0o755)
        shutil.copytree(
            str(ROOT / "skills"),
            str(workdir / "skills"),
            ignore=shutil.ignore_patterns("__pycache__", ".DS_Store"),
        )
        (workdir / "tests").mkdir()
        shutil.copy2(
            str(ROOT / "tests" / "test_package.py"),
            str(workdir / "tests" / "test_package.py"),
        )
        raw, failed = record(commands, workdir, bindir)

    raw_dir = os.environ.get("RECORD_RAW_DIR")
    if raw_dir:
        Path(raw_dir, "package-check.source.txt").write_text(raw, encoding="utf-8")

    if failed:
        sys.stdout.write(raw)
        print("the packaging test did not pass; nothing written")
        return 1
    edited = strip_duration(raw)
    if edited == raw:
        print("the capture has no test duration line to remove; nothing written")
        return 1
    transcript = ROOT / manifest["output"]["path"]
    transcript.write_text(edited, encoding="utf-8")

    manifest["date"] = datetime.date.today().isoformat()
    manifest["invocation"]["interpreter"] = "Python " + platform.python_version()
    manifest["skill"]["sha256"] = sha256(ROOT / manifest["skill"]["path"])
    manifest["interface"]["sha256"] = sha256(ROOT / manifest["interface"]["path"])
    for group in ("documents", "programs"):
        for item in manifest[group]:
            item["sha256"] = sha256(ROOT / item["path"])
    manifest["output"]["sha256"] = sha256(transcript)
    MANIFEST.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    print("wrote %s" % transcript.relative_to(ROOT))
    print("wrote %s" % MANIFEST.relative_to(ROOT))
    return 0


if __name__ == "__main__":
    sys.exit(main())
