"""Plugins that a built-in skill of current Claude Code may replace. Candidates; the reviewer decides."""

from __future__ import annotations

from typing import Any

from .context import Context, load_data
from .plugins import installed


def collect(ctx: Context) -> dict[str, Any]:
    builtins = load_data("builtin-skills.json").get("builtins", [])
    hits: list[dict[str, str]] = []
    for pid in sorted(installed(ctx)):
        name = pid.split("@", 1)[0]
        for b in builtins:
            if isinstance(b, dict) and name in b.get("plugins", []):
                hits.append({"plugin": pid, "builtin": str(b["builtin"]), "note": str(b.get("note", ""))})
    return {
        "builtin": hits,
        "synced_skills": (
            "not visible in local files; compare the session's anthropic-skills:* list with plugins"
        ),
    }
