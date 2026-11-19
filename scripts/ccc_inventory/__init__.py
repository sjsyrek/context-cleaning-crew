"""Deterministic, read-only inventory of a Claude Code setup. Emits a stable, diffable manifest."""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from . import instructions, mcp, memory, permissions, plugins, removed_tools, secrets, settings
from .context import Context

SCHEMA_VERSION = 1

__all__ = ["SCHEMA_VERSION", "Context", "build_manifest"]


def build_manifest(ctx: Context, extra_secret_patterns: Sequence[str] = ()) -> dict[str, Any]:
    files = settings.settings_files(ctx)
    plugin_section = plugins.collect(ctx, files)
    installed_names = plugins.plugin_names([p["id"] for p in plugin_section["installed"]])
    servers = mcp.server_names(ctx)
    rules = permissions.all_rules(ctx, files)
    return {
        "schema_version": SCHEMA_VERSION,
        "settings": settings.collect(ctx, files),
        "permissions": permissions.collect(ctx, files, servers, installed_names),
        "plugins": plugin_section,
        "mcp": {"servers": servers},
        "instructions": instructions.collect(ctx, rules),
        "removed_tool_refs": removed_tools.collect(ctx),
        "memory": memory.collect(ctx),
        "secrets": secrets.collect(ctx, files, extra_secret_patterns),
    }
