"""Which copy of a duplicated plugin to keep, decided by the user's options before any judgment.

Order: a `protected` entry wins outright; then the earliest `preferred_marketplaces` entry that
has a candidate. Anything else (capability, usage) is the reviewer's call, so the result says so.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from .context import Context
from .options import Options

UNDECIDED = "undecided: compare capability, then usage"


def matches(entry: str, plugin_id: str) -> bool:
    """A protected entry names a plugin by `name@marketplace` or by bare `name` (every copy)."""
    return entry == plugin_id or ("@" not in entry and entry == plugin_id.partition("@")[0])


def is_protected(plugin_id: str, options: Options) -> bool:
    return any(matches(entry, plugin_id) for entry in options.protected)


def pick_keeper(candidates: Sequence[str], options: Options) -> tuple[str | None, str]:
    protected = [c for c in candidates if is_protected(c, options)]
    if len(protected) == 1:
        return protected[0], "protected"
    if len(protected) > 1:
        return None, "protected: keep all"
    for market in options.preferred_marketplaces:
        for candidate in sorted(candidates):
            if candidate.partition("@")[2] == market:
                return candidate, "preferred_marketplaces"
    return None, UNDECIDED


def pick_server_keeper(members: Sequence[dict[str, str]], options: Options) -> tuple[str | None, str]:
    """Keeper among MCP servers with the same target. A member is protected by its own name or,
    for a plugin's server, by its plugin; a plugin's marketplace counts for preferred_marketplaces."""
    protected = sorted(
        {
            m["server"]
            for m in members
            if m["server"] in options.protected or (m.get("plugin") and is_protected(m["plugin"], options))
        }
    )
    if len(protected) == 1:
        return protected[0], "protected"
    if len(protected) > 1:
        return None, "protected: keep all"
    for market in options.preferred_marketplaces:
        for m in sorted(members, key=lambda m: m["server"]):
            if m.get("plugin") and m["plugin"].partition("@")[2] == market:
                return m["server"], "preferred_marketplaces"
    return None, UNDECIDED


def plugin_duplicates(ids: Sequence[str], options: Options) -> list[dict[str, Any]]:
    """Plugins with the same name installed from more than one marketplace."""
    by_name: dict[str, list[str]] = {}
    for pid in sorted(ids):
        by_name.setdefault(pid.partition("@")[0], []).append(pid)
    found = []
    for name, group in sorted(by_name.items()):
        if len(group) < 2:
            continue
        keeper, rule = pick_keeper(group, options)
        found.append({"name": name, "plugins": group, "keeper": keeper, "rule": rule})
    return found


def resolve_protected(
    ctx: Context, plugin_ids: Sequence[str], servers: Sequence[str], memory_files: Sequence[str]
) -> dict[str, list[str]]:
    """What each `protected` entry refers to, and the entries that match nothing (likely typos)."""
    entries = ctx.options.options.protected
    plugins = sorted(p for p in plugin_ids if is_protected(p, ctx.options.options))
    hit_servers = sorted(s for s in servers if s in entries)
    hit_memory = sorted(m for m in memory_files if m in entries or m.rsplit("/", 1)[-1] in entries)
    used = set(hit_servers)
    used |= {e for e in entries for p in plugin_ids if matches(e, p)}
    used |= {e for e in entries for m in hit_memory if e in (m, m.rsplit("/", 1)[-1])}
    return {
        "plugins": plugins,
        "mcp_servers": hit_servers,
        "memory_files": hit_memory,
        "unmatched": sorted(e for e in entries if e not in used),
    }
