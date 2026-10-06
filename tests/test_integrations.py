#!/usr/bin/env python3
"""The repository suite.

Facts this repository states in more than one place are
pinned here where a script can compare them: the name and
version, the claim and the transcript behind it, the demo
images, the install blocks, and the evidence hashes.

Runs offline with the standard library and `git`:

    python3 tests/test_integrations.py
"""

from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import re
import struct
import subprocess
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
NAME = "m2"
PACKAGE = ROOT / "skills" / NAME
SKILL = PACKAGE / "SKILL.md"
DOCUMENTS = (
    "references/m1.protocol.md",
    "references/m2-artifact-schemas.md",
    "references/m2.protocol.md",
    "references/writeAC.protocol.md",
)
PACKAGE_TEST = ROOT / "tests" / "test_package.py"
README = ROOT / "README.md"
TRANSCRIPT = ROOT / "evidence" / "transcripts" / "package-check.txt"
MANIFEST = ROOT / "evidence" / "demo-manifest.json"
CLAIM = "m2 ships four protocol documents and no runnable code."
COMMAND = "python3 tests/test_package.py -v"
FILES_LINE = "The package is SKILL.md, agents/openai.yaml and four documents. ... ok"
NO_PROGRAM_LINE = (
    "No package file is executable, has a #! line, or is not .md/.yaml. ... ok"
)
REPOSITORY = "https://github.com/trycopilotai/" + NAME


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments],
        cwd=str(ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
        check=True,
    ).stdout


def load(path: Path, name: str):
    sys.dont_write_bytecode = True
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def manifest(product: str) -> dict:
    return json.loads(read(ROOT / product / "plugin.json"))


def frontmatter(text: str) -> dict:
    """The `key: value` pairs between the two `---` lines."""
    lines = text.splitlines()
    if lines[0] != "---":
        raise AssertionError("SKILL.md does not open with frontmatter")
    end = lines.index("---", 1)
    fields: dict = {}
    key = None
    for line in lines[1:end]:
        match = re.match(r"^([a-z_-]+):\s*(.*)$", line)
        if match:
            key = match.group(1)
            fields[key] = match.group(2).strip()
            continue
        if key is None or not line.startswith(" "):
            raise AssertionError("unexpected frontmatter line: " + line)
        fields[key] = (fields[key] + " " + line.strip()).strip()
    for name, value in fields.items():
        if value.startswith(">-"):
            fields[name] = value[2:].strip()
    return fields


def interface_yaml(text: str) -> dict:
    """The quoted scalars under `interface:` in agents/openai.yaml."""
    lines = text.splitlines()
    if lines[0] != "interface:":
        raise AssertionError("openai.yaml does not start with interface:")
    fields: dict = {}
    key = None
    for line in lines[1:]:
        match = re.match(r"^  ([a-z_]+):\s*(.*)$", line)
        if match:
            key = match.group(1)
            fields[key] = match.group(2).strip()
            continue
        fields[key] = (fields[key] + " " + line.strip()).strip()
    for name, value in fields.items():
        if not (value.startswith('"') and value.endswith('"')):
            raise AssertionError(name + " is not a double-quoted scalar")
        fields[name] = value[1:-1]
    return fields


def install_blocks() -> list:
    return re.findall(r"```sh\nset -eu\n(.*?)```", read(README), flags=re.S)


def result_lines(output: str) -> list:
    """The lines of unittest's verbose output that end in a result."""
    return [line for line in output.splitlines() if line.endswith(" ... ok")]


class LayoutTest(unittest.TestCase):
    def test_skill_is_a_symlink_into_the_canonical_package(self) -> None:
        link = ROOT / "skill"
        self.assertTrue(link.is_symlink())
        self.assertEqual(os.readlink(str(link)), "skills/" + NAME)
        self.assertFalse(PACKAGE.is_symlink())

    def test_package_holds_what_the_readme_says_it_installs(self) -> None:
        for relative in ("SKILL.md", "agents/openai.yaml") + DOCUMENTS:
            self.assertTrue((PACKAGE / relative).is_file(), relative)
        self.assertFalse((PACKAGE / "scripts").exists())

    def test_history_has_no_co_author_trailer(self) -> None:
        messages = git("log", "--all", "--format=%B")
        self.assertNotIn("co-authored-by", messages.lower())


class SkillTest(unittest.TestCase):
    def test_frontmatter_is_name_and_description_only(self) -> None:
        fields = frontmatter(read(SKILL))
        self.assertEqual(sorted(fields), ["description", "name"])
        self.assertEqual(fields["name"], NAME)
        self.assertRegex(NAME, r"^[a-z0-9]+(-[a-z0-9]+)*$")
        self.assertLessEqual(len(NAME), 64)
        self.assertTrue(fields["description"])
        self.assertLessEqual(len(fields["description"]), 1024)

    def test_skill_stays_under_five_hundred_lines(self) -> None:
        self.assertLess(len(read(SKILL).splitlines()), 500)

    def test_files_the_skill_points_at_exist(self) -> None:
        text = read(SKILL)
        for relative in DOCUMENTS:
            self.assertIn(relative, text)
            self.assertTrue((PACKAGE / relative).is_file(), relative)


class ManifestTest(unittest.TestCase):
    def test_both_manifests_agree(self) -> None:
        claude = manifest(".claude-plugin")
        codex = manifest(".codex-plugin")
        for field in (
            "name",
            "version",
            "description",
            "license",
            "homepage",
            "repository",
            "keywords",
            "skills",
        ):
            self.assertEqual(claude[field], codex[field], field)
        self.assertEqual(claude["name"], NAME)
        self.assertEqual(claude["skills"], "./skills/")
        self.assertEqual(claude["repository"], REPOSITORY)
        self.assertEqual(claude["license"], "MIT")
        self.assertRegex(claude["version"], r"^\d+\.\d+\.\d+$")

    def test_a_release_tag_on_head_is_the_manifest_version(self) -> None:
        tags = git("tag", "--points-at", "HEAD").split()
        releases = [tag for tag in tags if tag.startswith("v")]
        if not releases:
            self.skipTest("HEAD carries no release tag")
        self.assertEqual(releases, ["v" + manifest(".claude-plugin")["version"]])

    def test_codex_interface_matches_the_agent_file(self) -> None:
        interface = manifest(".codex-plugin")["interface"]
        for field in (
            "displayName",
            "shortDescription",
            "longDescription",
            "developerName",
            "category",
            "websiteURL",
        ):
            self.assertTrue(interface.get(field), field)
        prompts = interface["defaultPrompt"]
        self.assertEqual(len(prompts), 1)
        self.assertIn("$" + NAME, prompts[0])
        agent = interface_yaml(read(PACKAGE / "agents" / "openai.yaml"))
        self.assertEqual(agent["default_prompt"], prompts[0])
        self.assertEqual(agent["display_name"], interface["displayName"])
        self.assertEqual(agent["short_description"], interface["shortDescription"])


class ReadmeTest(unittest.TestCase):
    def test_claim_is_on_its_own_line(self) -> None:
        self.assertIn(CLAIM, read(README).splitlines())
        self.assertLessEqual(len(CLAIM), 60)

    def test_transcript_shows_the_two_results_behind_the_claim(self) -> None:
        lines = read(TRANSCRIPT).splitlines()
        self.assertEqual(lines[0], "$ " + COMMAND)
        self.assertIn(FILES_LINE, lines)
        self.assertIn(NO_PROGRAM_LINE, lines)
        self.assertEqual(lines[-3:], ["OK", '$ echo "exit status: $?"', "exit status: 0"])

    def test_each_install_block_pins_the_manifest_version(self) -> None:
        version = manifest(".claude-plugin")["version"]
        blocks = install_blocks()
        self.assertEqual(len(blocks), 2)
        roots = []
        for block in blocks:
            self.assertEqual(
                re.findall(r"^release=(\S+)$", block, flags=re.M),
                ["v" + version],
            )
            self.assertIn(REPOSITORY + " \\\n", block)
            self.assertIn('--branch "$release"', block)
            target = re.findall(r'^install_target="\$HOME/(\S+)"$', block, flags=re.M)
            self.assertEqual(len(target), 1)
            roots.append(target[0])
        self.assertEqual(
            sorted(roots),
            [".agents/skills/" + NAME, ".claude/skills/" + NAME],
        )

    def test_relative_links_resolve(self) -> None:
        targets = re.findall(r"\]\(([^)#]+)\)", read(README))
        self.assertTrue(targets)
        for target in targets:
            if target.startswith("http"):
                continue
            self.assertTrue((ROOT / target).exists(), target)

    def test_readme_says_what_was_not_measured(self) -> None:
        text = " ".join(read(README).split())
        self.assertIn("no m2 run is evidenced here", text)
        self.assertIn("No m2 run produced the evidence here", text)
        self.assertIn("has not been measured", text)
        self.assertIn("are not included", text)

    def test_demo_is_offered_with_a_reduced_motion_poster(self) -> None:
        text = read(README)
        picture = re.search(r"<picture>(.*?)</picture>", text, flags=re.S)
        self.assertIsNotNone(picture)
        body = picture.group(1)
        self.assertIn('media="(prefers-reduced-motion: reduce)"', body)
        self.assertIn('srcset="assets/poster.svg"', body)
        self.assertIn('src="assets/demo.svg"', body)


class EvidenceTest(unittest.TestCase):
    def test_manifest_hashes_match_the_files(self) -> None:
        record = json.loads(read(MANIFEST))
        self.assertEqual(record["skill"]["path"], str(SKILL.relative_to(ROOT)))
        self.assertEqual(record["skill"]["sha256"], sha256(SKILL))
        interface = PACKAGE / "agents" / "openai.yaml"
        self.assertEqual(
            record["interface"],
            {"path": str(interface.relative_to(ROOT)), "sha256": sha256(interface)},
        )
        documents = {item["path"]: item["sha256"] for item in record["documents"]}
        self.assertEqual(
            documents,
            {
                str((PACKAGE / relative).relative_to(ROOT)): sha256(PACKAGE / relative)
                for relative in DOCUMENTS
            },
        )
        programs = {item["path"]: item["sha256"] for item in record["programs"]}
        self.assertEqual(
            programs,
            {str(PACKAGE_TEST.relative_to(ROOT)): sha256(PACKAGE_TEST)},
        )
        self.assertEqual(record["output"]["sha256"], sha256(TRANSCRIPT))
        self.assertIs(record["output"]["edited"], True)
        self.assertIs(record["agent"]["invoked_the_skill"], False)

    def test_manifest_command_is_the_one_in_the_transcript(self) -> None:
        record = json.loads(read(MANIFEST))
        commands = [
            line[2:]
            for line in read(TRANSCRIPT).splitlines()
            if line.startswith("$ ") and not line.startswith("$ echo")
        ]
        self.assertEqual(record["invocation"]["commands"], commands)
        self.assertEqual(commands, [COMMAND])

    def test_readme_names_the_edit_the_manifest_declares(self) -> None:
        record = json.loads(read(MANIFEST))
        names = [entry["name"] for entry in record["output"]["transforms"]]
        self.assertEqual(names, ["strip-test-duration"])
        self.assertIn("`strip-test-duration`", read(README))
        counts = [
            line for line in read(TRANSCRIPT).splitlines() if line.startswith("Ran ")
        ]
        self.assertEqual(len(counts), 1)
        self.assertRegex(counts[0], r"^Ran \d+ tests?$")

    def test_a_fresh_run_reports_what_the_transcript_reports(self) -> None:
        fresh = subprocess.run(
            [sys.executable, str(PACKAGE_TEST), "-v"],
            cwd=str(ROOT),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
        )
        self.assertEqual(fresh.returncode, 0, fresh.stdout)
        recorded = result_lines(read(TRANSCRIPT))
        self.assertEqual(result_lines(fresh.stdout), recorded)
        count = [line for line in read(TRANSCRIPT).splitlines() if line.startswith("Ran ")]
        self.assertEqual(count, ["Ran %d tests" % len(recorded)])


TRANSFORMS = [
    "replace-plugin-root",
    "replace-capture-root",
    "replace-scratch-root",
    "replace-home",
    "replace-hostname",
]


class InvocationTest(unittest.TestCase):
    def invocations(self) -> list:
        return json.loads(read(MANIFEST))["invocations"]

    def test_one_published_invocation_per_client(self) -> None:
        products = [entry["product"] for entry in self.invocations()]
        self.assertEqual(products, ["Claude Code", "Codex"])
        for entry in self.invocations():
            self.assertIs(entry["invoked_the_skill"], True)
            self.assertRegex(entry["raw_output_sha256"], r"^[0-9a-f]{64}$")
            self.assertEqual(entry["renderer"], "scripts/render_invocation.py")
            self.assertEqual([t["name"] for t in entry["transforms"]], TRANSFORMS)
            for field in ("version", "model", "invocation", "fixture", "date", "outcome"):
                self.assertTrue(entry[field], field)

    def test_transcript_hashes_match_the_manifest(self) -> None:
        for entry in self.invocations():
            path = ROOT / entry["transcript"]["path"]
            self.assertEqual(entry["transcript"]["sha256"], sha256(path))
            client = "claude-code" if entry["product"] == "Claude Code" else "codex"
            self.assertEqual(path.name, entry["date"] + "-" + client + "-invocation.txt")
            self.assertTrue(read(path).startswith("client: " + client + "\n"))

    def test_transcript_set_is_what_the_manifest_names(self) -> None:
        named = {TRANSCRIPT.name} | {
            Path(entry["transcript"]["path"]).name for entry in self.invocations()
        }
        present = {path.name for path in TRANSCRIPT.parent.iterdir()}
        self.assertEqual(present, named)

    def test_transcripts_show_the_skill_being_loaded(self) -> None:
        claude, codex = (ROOT / e["transcript"]["path"] for e in self.invocations())
        self.assertIn('[1] Skill {"skill": "m2:m2"}', read(claude))
        self.assertIn(".agents/skills/m2/SKILL.md", read(codex))

    def test_transcripts_hold_no_local_paths(self) -> None:
        for entry in self.invocations():
            text = read(ROOT / entry["transcript"]["path"])
            self.assertIsNone(re.search(r"/(Users|home|private|tmp)/", text))
            self.assertNotIn("/tmp/claude-", text)

    def test_readme_links_both_transcripts(self) -> None:
        text = read(README)
        self.assertIn("### Agent invocations", text)
        for entry in self.invocations():
            self.assertIn("(" + entry["transcript"]["path"] + ")", text)


class RendererTest(unittest.TestCase):
    def renderer(self):
        return load(ROOT / "scripts" / "render_invocation.py", "render_invocation")

    def test_claude_code_stream_is_rendered(self) -> None:
        raw = "\n".join(
            json.dumps(record)
            for record in (
                {"type": "system", "subtype": "init", "model": "m"},
                {
                    "type": "assistant",
                    "message": {
                        "content": [
                            {"type": "tool_use", "id": "a", "name": "Read", "input": {"file_path": "/f/x"}},
                            {"type": "tool_use", "id": "b", "name": "Bash", "input": {"command": "x" * 400}},
                        ]
                    },
                },
                {
                    "type": "user",
                    "message": {
                        "content": [
                            {"type": "tool_result", "tool_use_id": "a"},
                            {"type": "tool_result", "tool_use_id": "b", "is_error": True},
                        ]
                    },
                },
                {"type": "result", "result": "done\n  verbatim"},
            )
        )
        text = self.renderer().render("claude-code", raw, "go\n")
        self.assertIn('[1] Read {"file_path": "/f/x"}\n    status: ok\n', text)
        self.assertIn("    status: error\n", text)
        self.assertIn(" ...[+", text)
        self.assertTrue(text.endswith("== final message\ndone\n  verbatim\n"))

    def test_codex_stream_is_rendered(self) -> None:
        raw = "\n".join(
            json.dumps(record)
            for record in (
                {"type": "item.completed", "item": {"id": "1", "type": "reasoning", "text": "r"}},
                {"type": "item.completed", "item": {"id": "2", "type": "command_execution", "command": "ls", "exit_code": 2}},
                {"type": "item.completed", "item": {"id": "3", "type": "agent_message", "text": "first"}},
                {"type": "item.completed", "item": {"id": "4", "type": "agent_message", "text": "last"}},
            )
        )
        text = self.renderer().render("codex", raw, "go")
        self.assertIn("[1] command_execution ls\n    status: exit 2\n", text)
        self.assertNotIn("[2]", text)
        self.assertTrue(text.endswith("== final message\nlast\n"))

    def test_replacements_cover_whole_prefixes_in_order(self) -> None:
        replace = self.renderer().replace
        text = (
            "/h/r/fixture/.agents/skills/m2/SKILL.md /h/r/fixture/GOAL.md "
            "/h/r/fixture-old /private/tmp/claude-1000/-h-slug/tasks/1 /h/other box.local"
        )
        self.assertEqual(
            replace(text, "/h/r/fixture/.agents/skills/m2", "/h/r/fixture", "/h", "box.local"),
            "/plugin/SKILL.md /work/GOAL.md ~/r/fixture-old /scratch/tasks/1 ~/other host",
        )


class DemoTest(unittest.TestCase):
    def test_images_agree_with_the_transcript(self) -> None:
        verifier = load(ROOT / "scripts" / "verify_demo.py", "verify_demo")
        generator = verifier.load_generator()
        self.assertEqual(verifier.problems_in(generator, read(TRANSCRIPT)), [])


class SocialPreviewTest(unittest.TestCase):
    def test_preview_is_the_size_github_expects(self) -> None:
        header = (ROOT / "assets" / "social-preview.png").read_bytes()[:24]
        self.assertEqual(header[:8], b"\x89PNG\r\n\x1a\n")
        self.assertEqual(struct.unpack(">II", header[16:24]), (1280, 640))

    def test_stamp_binds_the_source_and_the_render(self) -> None:
        recorded = {}
        for line in read(ROOT / "assets" / "social-preview.sha256").splitlines():
            value, name = line.split()
            recorded[name] = value
        for name in ("social-preview.html", "social-preview.png"):
            self.assertEqual(recorded[name], sha256(ROOT / "assets" / name), name)

    def test_preview_source_carries_the_claim(self) -> None:
        text = " ".join(read(ROOT / "assets" / "social-preview.html").split())
        self.assertIn(CLAIM, text)


class SupportFilesTest(unittest.TestCase):
    def test_license_is_mit(self) -> None:
        self.assertTrue(read(ROOT / "LICENSE").startswith("MIT License\n"))

    def test_security_names_this_repository_for_reports(self) -> None:
        self.assertIn(
            REPOSITORY + "/security/advisories/new",
            read(ROOT / "SECURITY.md"),
        )

    def test_contributing_names_the_check_command(self) -> None:
        self.assertIn("make check", read(ROOT / "CONTRIBUTING.md"))


if __name__ == "__main__":
    unittest.main()
