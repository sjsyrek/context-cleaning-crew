"""Skill usage from ~/.claude.json (`skillUsage`): counts and last-used dates (UTC)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from .context import Context, read_json_object


def collect(ctx: Context) -> dict[str, Any]:
    raw = read_json_object(ctx.home / ".claude.json").get("skillUsage")
    usage: dict[str, Any] = raw if isinstance(raw, dict) else {}
    skills: list[dict[str, Any]] = []
    for name in sorted(usage):
        entry = usage[name]
        if not isinstance(entry, dict):
            continue
        last = entry.get("lastUsedAt")
        last_used = (
            datetime.fromtimestamp(last / 1000, tz=timezone.utc).date().isoformat()
            if isinstance(last, (int, float))
            else ""
        )
        skills.append({"skill": name, "count": int(entry.get("usageCount", 0)), "last_used": last_used})
    return {"skills": skills, "mcp_tools": "not recorded here; opt in to transcript mining for MCP usage"}
