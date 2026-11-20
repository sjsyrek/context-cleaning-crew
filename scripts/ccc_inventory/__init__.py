"""Deterministic, read-only inventory of a Claude Code setup. Emits a stable, diffable manifest."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import (
    counts,
    drift,
    facts,
    hooks,
    instructions,
    mcp,
    memory,
    overlap,
    permissions,
    plugins,
    removed_tools,
    secrets,
    settings,
    usage,
)
from .context import Context

SCHEMA_VERSION = 1

__all__ = ["SCHEMA_VERSION", "Context", "build_manifest"]


def options_section(ctx: Context) -> dict[str, Any]:
    """Effective option values, where each came from, and why any value was ignored."""
    loaded = ctx.options
    home = str(Path.home())
    return {
        "values": loaded.options.as_dict(),
        "sources": {
            k: "~" + v[len(home) :] if v.startswith(home + "/") else v for k, v in loaded.sources.items()
        },
        "warnings": loaded.warnings,
    }


def build_manifest(ctx: Context) -> dict[str, Any]:
    refreshed = drift.refresh(ctx)  # first: later sections read the refreshed clones
    files = settings.settings_files(ctx)
    plugin_section = plugins.collect(ctx, files)
    installed_names = plugins.plugin_names([p["id"] for p in plugin_section["installed"]])
    servers = mcp.server_names(ctx)
    rules = permissions.all_rules(ctx, files)
    return {
        "schema_version": SCHEMA_VERSION,
        "live_setup": ctx.live,
        "options": options_section(ctx),
        "settings": settings.collect(ctx, files),
        "permissions": permissions.collect(ctx, files, servers, installed_names),
        "plugins": plugin_section,
        "mcp": mcp.collect(ctx),
        "hooks": hooks.collect(ctx, files),
        "usage": usage.collect(ctx),
        "instructions": instructions.collect(ctx, rules),
        "removed_tool_refs": removed_tools.collect(ctx),
        "memory": memory.collect(ctx),
        "facts": facts.collect(ctx),
        "marketplaces": drift.marketplace_summary(ctx),
        "drift": drift.collect(ctx, refreshed),
        "overlap": overlap.collect(ctx),
        "counts": counts.collect(ctx),
        "secrets": secrets.collect(ctx, files, instructions.load_path(ctx)),
    }
