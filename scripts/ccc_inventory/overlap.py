"""Overlap: plugins a built-in skill may replace, and plugins installed from several marketplaces."""

from __future__ import annotations

from typing import Any

from .context import Context, load_data
from .keeper import plugin_duplicates
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
        "plugin_duplicates": plugin_duplicates(sorted(installed(ctx)), ctx.options.options),
        "synced_skills": (
            "not visible in local files; compare the session's anthropic-skills:* list with plugins"
        ),
    }
