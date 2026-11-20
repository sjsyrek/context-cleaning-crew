"""CLAUDE.md and AGENTS.md files in the load path: size, deny-rule conflicts and long procedures.

What the text means (contradictions, one-off task procedures) is the reviewer's call, not a regex's.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .context import Context, approx_tokens, read_text
from .permissions import Rule

NAMES = ("CLAUDE.md", ".claude/CLAUDE.md", "CLAUDE.local.md", "AGENTS.md")
ORDERED_STEP = re.compile(r"^\s*\d+[.)]\s+")
MOVE_MIN_STEPS = 5


def load_path(ctx: Context) -> list[Path]:
    """User file first, then each directory from the top of the tree down to cwd."""
    paths: list[Path] = []
    user = ctx.claude_dir / "CLAUDE.md"
    if user.is_file():
        paths.append(user)
    for directory in ctx.cwd_ancestry():
        for name in NAMES:
            candidate = directory / name
            if candidate.is_file() and candidate.resolve() != user.resolve():
                paths.append(candidate)
    return paths


def prose_lines(text: str) -> Iterator[tuple[int, str]]:
    """(line number, line) outside fenced code blocks."""
    fenced = False
    for number, line in enumerate(text.splitlines(), start=1):
        if line.lstrip().startswith("```"):
            fenced = not fenced
            continue
        if not fenced:
            yield number, line


def deny_command(rule: Rule) -> str:
    """`Bash(rm -rf:*)` -> `rm -rf`; empty when the rule isn't a Bash command pattern."""
    if rule.tool != "Bash" or rule.is_blanket:
        return ""
    return rule.prefix() or ""


def deny_conflicts(ctx: Context, display: str, text: str, denies: list[Rule]) -> list[dict[str, Any]]:
    conflicts: list[dict[str, Any]] = []
    for rule in denies:
        command = deny_command(rule)
        if not command:
            continue
        pattern = re.compile(r"(?<![\w-])" + re.escape(command) + r"(?![\w-])")
        for number, line in prose_lines(text):
            if pattern.search(line):
                conflicts.append(
                    {
                        "path": display,
                        "line": number,
                        "text": ctx.redact(line.strip()),
                        "deny_rule": ctx.redact(rule.text),
                        "deny_file": rule.file,
                    }
                )
    return conflicts


def move_candidates(ctx: Context, display: str, text: str) -> list[dict[str, Any]]:
    """Sections with five or more ordered steps: cheaper as an on-demand skill."""
    found: list[dict[str, Any]] = []
    heading = ""
    start = 0
    steps = 0

    def close() -> None:
        if heading and steps >= MOVE_MIN_STEPS:
            why = f"{steps} ordered steps"
            found.append({"path": display, "line": start, "heading": heading, "steps": steps, "why": why})

    for number, line in prose_lines(text):
        if re.match(r"^#{2,6}\s", line):
            close()
            heading, start, steps = ctx.redact(line.lstrip("#").strip()), number, 0
        elif ORDERED_STEP.match(line):
            steps += 1
    close()
    return found


def collect(ctx: Context, rules: list[Rule]) -> dict[str, Any]:
    denies = [r for r in rules if r.list_name == "deny"]
    files: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    moves: list[dict[str, Any]] = []
    for path in load_path(ctx):
        text = read_text(path) or ""
        size = len(text.encode("utf-8"))
        display = ctx.display(path)
        files.append(
            {"path": display, "name": path.name, "bytes": size, "approx_tokens": approx_tokens(size)}
        )
        conflicts.extend(deny_conflicts(ctx, display, text, denies))
        moves.extend(move_candidates(ctx, display, text))
    home_file = ctx.home / "CLAUDE.md"
    in_home = ctx.home.resolve() in [ctx.cwd.resolve(), *ctx.cwd.resolve().parents]
    return {
        "files": files,
        "token_estimate": "bytes/4 heuristic",
        "home_dir_global": [ctx.display(home_file)] if in_home and home_file.is_file() else [],
        "deny_conflicts": conflicts,
        "move_candidates": moves,
    }
