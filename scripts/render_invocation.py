#!/usr/bin/env python3
"""Render a recorded agent invocation as a plain-text transcript.

Reads the raw JSON lines a client wrote (Claude Code
`--output-format stream-json`, or Codex `exec --json`) and
writes the prompt, every tool call with its arguments, each
call's status where the raw output records one, and the
final message verbatim.

Two kinds of edit are made, and no other.

truncate-tool-arguments: while the text is built, each tool
call's arguments (the JSON of its input, or a Codex command
line) longer than 300 characters are cut to their first 300
characters, followed by ` ...[+N chars]`, where N is the
number of characters cut. Prompts, statuses and the final
message are never cut.

Then path and name replacements are applied, in this order,
to the whole rendered text:

1. replace-plugin-root: the directory the client loaded the
   skill from becomes `/plugin`.
2. replace-capture-root: the fixture's absolute path becomes
   `/work`.
3. replace-scratch-root: a `/private/tmp/claude-<uid>/<slug>`
   prefix becomes `/scratch`.
4. replace-home: the home directory becomes `~`.
5. replace-hostname: the host name becomes `host`.

Standard library only:

    python3 scripts/render_invocation.py --client codex \\
        --raw codex.jsonl --prompt prompt.txt \\
        --capture-root /path/to/fixture \\
        --plugin-root /path/to/fixture/.agents/skills/m2 \\
        --home "$HOME" --hostname "$(hostname)" > out.txt
"""

from __future__ import annotations

import argparse
import json
import re
import sys

LIMIT = 300
CLIENTS = ("claude-code", "codex")


def truncate(text: str, limit: int = LIMIT) -> str:
    if len(text) <= limit:
        return text
    return text[:limit] + " ...[+%d chars]" % (len(text) - limit)


def compact(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def events(raw: str) -> list:
    return [json.loads(line) for line in raw.splitlines() if line.strip()]


def claude_code(records: list) -> tuple:
    """Tool calls and the final message from a stream-json log."""
    calls = []
    status = {}
    final = None
    for record in records:
        kind = record.get("type")
        if kind == "assistant":
            for part in record["message"].get("content", []):
                if part.get("type") == "tool_use":
                    calls.append((part["id"], part["name"], compact(part["input"])))
        elif kind == "user":
            content = record.get("message", {}).get("content", [])
            if isinstance(content, list):
                for part in content:
                    if part.get("type") == "tool_result":
                        failed = part.get("is_error") is True
                        status[part["tool_use_id"]] = "error" if failed else "ok"
        elif kind == "result":
            final = record.get("result")
    rows = [(name, arguments, status.get(ident, "unknown")) for ident, name, arguments in calls]
    return rows, final


def codex(records: list) -> tuple:
    """Tool calls and the final message from an exec --json log."""
    rows = []
    final = None
    for record in records:
        if record.get("type") != "item.completed":
            continue
        item = record["item"]
        kind = item.get("type")
        if kind == "agent_message":
            final = item.get("text")
        elif kind == "reasoning":
            continue
        elif kind == "command_execution":
            code = item.get("exit_code")
            rows.append(
                (
                    "command_execution",
                    item.get("command", ""),
                    "unknown" if code is None else "exit %d" % code,
                )
            )
        else:
            arguments = {k: v for k, v in item.items() if k not in ("id", "type", "status")}
            rows.append((kind, compact(arguments), item.get("status") or "unknown"))
    return rows, final


def replace(text: str, plugin_root: str, capture_root: str, home: str, hostname: str) -> str:
    def prefix(path: str, value: str, body: str) -> str:
        path = path.rstrip("/")
        return re.sub(re.escape(path) + r"(?![\w.-])", value, body)

    text = prefix(plugin_root, "/plugin", text)
    text = prefix(capture_root, "/work", text)
    text = re.sub(r"/private/tmp/claude-\d+/[^/\s\"'`)\]]+", "/scratch", text)
    text = prefix(home, "~", text)
    if hostname:
        text = re.sub(re.escape(hostname), "host", text, flags=re.I)
    return text


def render(client: str, raw: str, prompt: str) -> str:
    rows, final = (claude_code if client == "claude-code" else codex)(events(raw))
    lines = ["client: " + client, "", "== prompt", prompt.rstrip("\n"), "", "== tool calls"]
    for number, (name, arguments, status) in enumerate(rows, 1):
        lines.append("[%d] %s %s" % (number, name, truncate(arguments)))
        lines.append("    status: " + status)
    lines += ["", "== final message", final if final is not None else "(none recorded)"]
    return "\n".join(lines).rstrip("\n") + "\n"


def main(argv: list) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--client", choices=CLIENTS, required=True)
    parser.add_argument("--raw", required=True)
    parser.add_argument("--prompt", required=True)
    parser.add_argument("--capture-root", required=True)
    parser.add_argument("--plugin-root", required=True)
    parser.add_argument("--home", required=True)
    parser.add_argument("--hostname", required=True)
    options = parser.parse_args(argv)
    with open(options.raw, encoding="utf-8") as handle:
        raw = handle.read()
    with open(options.prompt, encoding="utf-8") as handle:
        prompt = handle.read()
    text = render(options.client, raw, prompt)
    text = replace(text, options.plugin_root, options.capture_root, options.home, options.hostname)
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
