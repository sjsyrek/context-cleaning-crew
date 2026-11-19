"""Cheap, read-only facts for checking memory claims: tools on PATH, git remotes of the working tree.

Nothing here runs a command. Tools are looked up with `which` (never executed: a name in a memory
file could be any binary), and git remotes are read from `.git/config` as a file.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .context import Context, read_text
from .memory import memory_dirs

SPAN = re.compile(r"`([^`\n]+)`")
COMMAND = re.compile(r"[a-z][a-z0-9_-]+")
AFTER = re.compile(
    r"^`(?:\s+(?:is|was|isn't|wasn't|not|now|still|already|yet)){0,3}\s+(?:installed|on PATH)"
    r"|^`\s+(?:CLI|binary)\b"
)
BEFORE = re.compile(r"\b(?:install(?:ed)?|brew install|npm install -g|pipx install)\s+`$")
REMOTE = re.compile(r'^\[remote "([^"]+)"\]\s*$')
URL = re.compile(r"^\s*url\s*=\s*(.+?)\s*$")


def tool_names(text: str) -> set[str]:
    """First words of backtick spans that read as commands: multi-word spans (`bd ready`), or a
    single word right next to install/PATH wording (`x` is not installed, install `x`)."""
    names: set[str] = set()
    for line in text.splitlines():
        for m in SPAN.finditer(line):
            words = m.group(1).split()
            if not words or not COMMAND.fullmatch(words[0]):
                continue
            beside = AFTER.search(line[m.end() - 1 :]) or BEFORE.search(line[: m.start() + 1])
            if len(words) > 1 or beside:
                names.add(words[0])
    return names


def tools(ctx: Context) -> list[dict[str, Any]]:
    mentions: dict[str, set[str]] = {}
    for directory in memory_dirs(ctx):
        for path in sorted(directory.glob("*.md")):
            for name in tool_names(read_text(path) or ""):
                mentions.setdefault(name, set()).add(ctx.display(path))
    return [
        {"name": name, "on_path": ctx.which(name) is not None, "mentioned_in": sorted(mentions[name])}
        for name in sorted(mentions)
    ]


def git_config(repo: Path) -> Path | None:
    dot = repo / ".git"
    if dot.is_dir():
        return dot / "config"
    text = read_text(dot) if dot.is_file() else None  # a worktree: "gitdir: <path>"
    if text and text.startswith("gitdir:"):
        gitdir = (repo / text.split(":", 1)[1].strip()).resolve()
        common = read_text(gitdir / "commondir")
        return ((gitdir / common.strip()).resolve() if common else gitdir) / "config"
    return None


def remotes(ctx: Context, config: Path) -> list[dict[str, str]]:
    found: dict[str, str] = {}
    current = ""
    for line in (read_text(config) or "").splitlines():
        section = REMOTE.match(line.strip())
        if section:
            current = section.group(1)
            found.setdefault(current, "")
        elif line.strip().startswith("["):
            current = ""
        elif current and (url := URL.match(line)):
            found[current] = ctx.redact(url.group(1))
    return [{"name": n, "url": found[n]} for n in sorted(found)]


def git(ctx: Context) -> list[dict[str, Any]]:
    for repo in reversed(ctx.cwd_ancestry()):  # nearest repository to cwd
        config = git_config(repo)
        if config is not None:
            return [{"repo": ctx.display(repo), "remotes": remotes(ctx, config)}]
    return []


def collect(ctx: Context) -> dict[str, Any]:
    return {"tools": tools(ctx), "git": git(ctx)}
