#!/usr/bin/env python3
"""The packaging test for the skill package under skills/m2/.

It reads the package's files and their modes. It starts no
agent and runs no part of the m2 protocol. Its verbose output
is recorded in evidence/transcripts/package-check.txt.

Runs offline with the standard library:

    python3 tests/test_package.py -v
"""

from __future__ import annotations

import os
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "skills" / "m2"
DOCUMENTS = {
    "references/m1.protocol.md": "# m1 protocol",
    "references/m2-artifact-schemas.md": "# m2 Artifact Schemas",
    "references/m2.protocol.md": "# m2 protocol",
    "references/writeAC.protocol.md": "# writeAC protocol",
}
OTHER_FILES = {"SKILL.md", "agents/openai.yaml"}
TEXT_SUFFIXES = {".md", ".yaml"}
POINTER = re.compile(r"references/[A-Za-z0-9_.-]+\.md")


def package_files() -> set:
    found = set()
    for directory, _names, files in os.walk(str(PACKAGE)):
        for name in files:
            path = Path(directory) / name
            found.add(path.relative_to(PACKAGE).as_posix())
    return found


def read(relative: str) -> str:
    return (PACKAGE / relative).read_text(encoding="utf-8")


class PackageTest(unittest.TestCase):
    def test_1_files(self) -> None:
        """The package is SKILL.md, agents/openai.yaml and four documents."""
        self.assertEqual(package_files(), OTHER_FILES | set(DOCUMENTS))

    def test_2_documents(self) -> None:
        """Each of the four documents opens with its protocol heading."""
        self.assertEqual(len(DOCUMENTS), 4)
        for relative, heading in DOCUMENTS.items():
            self.assertEqual(read(relative).splitlines()[0], heading, relative)

    def test_3_no_program(self) -> None:
        """No package file is executable, has a #! line, or is not .md/.yaml."""
        for relative in sorted(package_files()):
            path = PACKAGE / relative
            self.assertFalse(path.is_symlink(), relative)
            self.assertIn(path.suffix, TEXT_SUFFIXES, relative)
            self.assertFalse(os.access(str(path), os.X_OK), relative)
            self.assertFalse(path.read_bytes().startswith(b"#!"), relative)

    def test_4_pointers(self) -> None:
        """Every references/ path the package names is a file in it."""
        named = set()
        for relative in sorted(package_files()):
            named.update(POINTER.findall(read(relative)))
        self.assertEqual(named, set(DOCUMENTS))

    def test_5_skill_points_at_each_document(self) -> None:
        """SKILL.md names each of the four documents."""
        text = read("SKILL.md")
        for relative in DOCUMENTS:
            self.assertIn(relative, text)


if __name__ == "__main__":
    unittest.main()
