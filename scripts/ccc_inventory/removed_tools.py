"""References to removed (or conditionally unavailable) tools in the user's own skills, agents, commands."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .context import Context, load_data, read_text

KINDS = ("skills", "agents", "commands")


def authored_files(ctx: Context) -> list[Path]:
    roots = [ctx.claude_dir, ctx.cwd / ".claude"]
    seen: set[Path] = set()
    files: list[Path] = []
    for root in roots:
        for kind in KINDS:
            base = root / kind
            if not base.is_dir():
                continue
            for path in sorted(base.rglob("*.md")):
                if path.resolve() not in seen:
                    seen.add(path.resolve())
                    files.append(path)
    return files


def collect(ctx: Context) -> list[dict[str, Any]]:
    data = load_data("removed-tools.json")
    entries = [(e, "") for e in data.get("removed", [])] + [
        (e, str(e.get("condition", ""))) for e in data.get("conditional", [])
    ]
    compiled = [(e, cond, re.compile(str(e["pattern"]))) for e, cond in entries]
    refs: list[dict[str, Any]] = []
    for path in authored_files(ctx):
        lines = (read_text(path) or "").splitlines()
        for entry, condition, pattern in compiled:
            hits = [n for n, line in enumerate(lines, start=1) if pattern.search(line)]
            if hits:
                ref: dict[str, Any] = {
                    "path": ctx.display(path),
                    "tool": entry["tool"],
                    "first_line": hits[0],
                    "count": len(hits),
                }
                if condition:
                    ref["condition"] = condition
                ref["replacement"] = entry.get("replacement", "")
                refs.append(ref)
    return refs
