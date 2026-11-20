"""Auto-memory directories: files, scope, broken index links, duplicates and stray directories.

Whether a memory reads as global is the reviewer's call, not a regex's.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .context import Context, approx_tokens, read_json_object, read_text
from .plugins import expand

LINK = re.compile(r"\]\(([^)\s]+\.md)\)")
TYPE = re.compile(r"^\s*type:\s*(\w+)", re.MULTILINE)
PERSONAL_TYPES = ("user", "feedback")


def memory_type(text: str) -> str:
    m = TYPE.search(text.split("\n---", 2)[0] if text.startswith("---") else "")
    return m.group(1) if m else ""


def collect_dir(ctx: Context, directory: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    for path in sorted(directory.glob("*.md")):
        text = read_text(path) or ""
        size = len(text.encode("utf-8"))
        kind = memory_type(text)
        files.append({"name": path.name, "bytes": size, "approx_tokens": approx_tokens(size), "type": kind})
    index = read_text(directory / "MEMORY.md") or ""
    broken = sorted({link for link in LINK.findall(index) if not (directory / link).is_file()})
    index_lines = [line for line in index.splitlines() if line.strip()]
    return {
        "path": ctx.display(directory),
        "project_dir": directory.parent.name,
        "files": files,
        "index_lines": len(index_lines),
        "longest_index_line": max((len(line) for line in index_lines), default=0),
        "broken_links": broken,
    }


def memory_dirs(ctx: Context) -> list[Path]:
    root = ctx.claude_dir / "projects"
    return sorted(p for p in root.glob("*/memory") if p.is_dir()) if root.is_dir() else []


NAME = re.compile(r"^name:\s*(.+?)\s*$", re.MULTILINE)


def frontmatter_and_body(text: str) -> tuple[str, str]:
    if text.startswith("---"):
        parts = text.split("\n---", 1)
        if len(parts) == 2:
            return parts[0], parts[1].split("\n", 1)[1] if "\n" in parts[1] else ""
    return "", text


def normalize(body: str) -> str:
    """Case, whitespace and trailing punctuation don't make a different fact."""
    return re.sub(r"\s+", " ", body).strip().strip(".").lower()


def duplicates(ctx: Context, dirs: list[Path]) -> list[dict[str, Any]]:
    """Personal (user or feedback) memories in several project directories with the same body or
    the same `name:`. Linked matches merge into one group: one fact, one move to a global place."""
    files: list[tuple[Path, str]] = []  # path, type
    by_key: dict[tuple[str, str], set[int]] = {}  # ("name" | "body", key) -> file indexes
    for d in dirs:
        for path in sorted(d.glob("*.md")):
            text = read_text(path) or ""
            kind = memory_type(text)
            if path.name == "MEMORY.md" or kind not in PERSONAL_TYPES:
                continue
            front, body = frontmatter_and_body(text)
            m = NAME.search(front)
            for how, key in (("name", m.group(1) if m else ""), ("body", normalize(body))):
                if key:
                    by_key.setdefault((how, key), set()).add(len(files))
            files.append((path, kind))

    groups: list[tuple[set[str], set[int]]] = []  # (how they match, members); pairwise disjoint
    for (how, _), members in sorted(by_key.items()):
        if len({files[i][0].parent for i in members}) < 2:
            continue  # one directory: not a scope problem
        linked = [g for g in groups if g[1] & members]
        groups = [g for g in groups if not g[1] & members]
        groups.append(({how}.union(*(g[0] for g in linked)), members.union(*(g[1] for g in linked))))

    found = []
    for how_matched, members in groups:
        paths = sorted((files[i][0] for i in members), key=str)
        found.append(
            {
                "match": sorted(how_matched),
                "type": "/".join(sorted({files[i][1] for i in members})),
                "files": [ctx.display(path) for path in paths],
                "projects": sorted({path.parent.parent.name for path in paths}),
            }
        )
    return sorted(found, key=lambda g: g["files"])


def seen_projects(ctx: Context) -> list[Path]:
    """Working trees Claude Code has been used in (`projects` in ~/.claude.json)."""
    seen = read_json_object(ctx.home / ".claude.json").get("projects")
    return sorted({expand(ctx, k) for k in (seen if isinstance(seen, dict) else []) if isinstance(k, str)})


def project_paths(ctx: Context) -> list[Path]:
    """Known working trees plus the cwd's ancestry."""
    return sorted({*ctx.cwd_ancestry(), *seen_projects(ctx)})


def stray_dirs(ctx: Context) -> list[dict[str, Any]]:
    """`<project>/.claude/memory` directories: memory-like files auto-memory never loads."""
    found = []
    for project in project_paths(ctx):
        d = project / ".claude" / "memory"
        if d.is_dir():
            count = sum(1 for p in d.rglob("*") if p.is_file())
            found.append({"path": ctx.display(d), "files": count})
    return found


def collect(ctx: Context) -> dict[str, Any]:
    dirs = memory_dirs(ctx)
    return {
        "dirs": [collect_dir(ctx, d) for d in dirs],
        "duplicates": duplicates(ctx, dirs),
        "stray_dirs": stray_dirs(ctx),
    }
