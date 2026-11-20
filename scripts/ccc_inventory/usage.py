"""Usage signals: skill counts and last-used dates (UTC) from ~/.claude.json, and, only when the
`mine_transcripts` option is on, MCP calls per server from local transcripts (counts, never content).
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from .context import Context, read_json_object
from .mcp import server_names


def cutoff(ctx: Context) -> date:
    return ctx.today - timedelta(days=ctx.options.options.usage_window_days)


def skills(ctx: Context) -> list[dict[str, Any]]:
    raw = read_json_object(ctx.home / ".claude.json").get("skillUsage")
    usage: dict[str, Any] = raw if isinstance(raw, dict) else {}
    found: list[dict[str, Any]] = []
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
        found.append(
            {
                "skill": name,
                "count": int(entry.get("usageCount", 0)),
                "last_used": last_used,
                "unused": bool(last_used) and last_used < cutoff(ctx).isoformat(),
            }
        )
    return found


def mcp_calls(path: Path) -> Iterator[tuple[str, str]]:
    """(server, yyyy-mm-dd) per MCP tool call in one transcript. Only assistant tool_use blocks
    count; a tool name mentioned in text is not a call. Inputs are never read."""
    try:
        handle = path.open(encoding="utf-8", errors="replace")
    except OSError:
        return
    with handle:
        for line in handle:
            if '"tool_use"' not in line or "mcp__" not in line:
                continue  # cheap filter before parsing
            try:
                record = json.loads(line)
            except ValueError:
                continue
            if not isinstance(record, dict) or record.get("type") != "assistant":
                continue
            content = (
                record.get("message", {}).get("content") if isinstance(record.get("message"), dict) else None
            )
            day = str(record.get("timestamp", ""))[:10]
            for block in content if isinstance(content, list) else []:
                if not isinstance(block, dict) or block.get("type") != "tool_use":
                    continue
                name = block.get("name")
                if isinstance(name, str) and name.startswith("mcp__"):
                    parts = name.split("__")
                    if len(parts) >= 3 and parts[1]:
                        yield parts[1], day


def mine(ctx: Context) -> dict[str, Any]:
    if not ctx.options.options.mine_transcripts:
        return {"status": "not mined: mine_transcripts is off"}
    root = ctx.claude_dir / "projects"
    transcripts = sorted(root.rglob("*.jsonl")) if root.is_dir() else []
    since = cutoff(ctx).isoformat()
    calls: dict[str, int] = {}
    last: dict[str, str] = {}
    for path in transcripts:
        for server, day in mcp_calls(path):
            if day < since:
                continue
            calls[server] = calls.get(server, 0) + 1
            last[server] = max(last.get(server, ""), day)
    return {
        "status": "mined",
        "transcripts": len(transcripts),
        "servers": [{"server": s, "calls": calls[s], "last_used": last[s]} for s in sorted(calls)],
        "unused_servers": [s for s in server_names(ctx) if s not in calls],
    }


def collect(ctx: Context) -> dict[str, Any]:
    return {"window_days": ctx.options.options.usage_window_days, "skills": skills(ctx), "mcp": mine(ctx)}
