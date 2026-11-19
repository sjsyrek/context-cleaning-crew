"""Auto-memory directories: files, broken index links, and memory that reads as global."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .context import Context, approx_tokens, read_text

LINK = re.compile(r"\]\(([^)\s]+\.md)\)")
TYPE = re.compile(r"^\s*type:\s*(\w+)", re.MULTILINE)
GLOBAL_WORDING = re.compile(
    r"\b(?:every|all|any)\s+projects?\b|\beverywhere\b|\bglobal(?:ly)?\b"
    r"|\bacross (?:all )?(?:repos|projects)\b",
    re.IGNORECASE,
)
PERSONAL_TYPES = ("user", "feedback")


def memory_type(text: str) -> str:
    m = TYPE.search(text.split("\n---", 2)[0] if text.startswith("---") else "")
    return m.group(1) if m else ""


def collect_dir(ctx: Context, directory: Path) -> dict[str, Any]:
    files: list[dict[str, Any]] = []
    global_looking: list[str] = []
    for path in sorted(directory.glob("*.md")):
        text = read_text(path) or ""
        size = len(text.encode("utf-8"))
        kind = memory_type(text)
        files.append({"name": path.name, "bytes": size, "approx_tokens": approx_tokens(size), "type": kind})
        if path.name != "MEMORY.md" and kind in PERSONAL_TYPES and GLOBAL_WORDING.search(text):
            global_looking.append(path.name)
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
        "global_looking": global_looking,
    }


def memory_dirs(ctx: Context) -> list[Path]:
    root = ctx.claude_dir / "projects"
    return sorted(p for p in root.glob("*/memory") if p.is_dir()) if root.is_dir() else []


def collect(ctx: Context) -> dict[str, Any]:
    return {"dirs": [collect_dir(ctx, d) for d in memory_dirs(ctx)]}
