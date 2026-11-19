"""Configured MCP server names, from ~/.claude.json and the project's .mcp.json."""

from __future__ import annotations

from typing import Any

from .context import Context, read_json_object


def config_sources(ctx: Context) -> list[dict[str, Any]]:
    """Each source of `mcpServers`, labeled; used for both server names and the secrets scan."""
    sources: list[dict[str, Any]] = []
    user = read_json_object(ctx.home / ".claude.json")
    if isinstance(user.get("mcpServers"), dict):
        sources.append(
            {"file": ctx.home / ".claude.json", "prefix": "mcpServers", "servers": user["mcpServers"]}
        )
    projects = user.get("projects")
    if isinstance(projects, dict):
        entry = projects.get(str(ctx.cwd.resolve()))
        if isinstance(entry, dict) and isinstance(entry.get("mcpServers"), dict):
            sources.append(
                {
                    "file": ctx.home / ".claude.json",
                    "prefix": "projects[cwd].mcpServers",
                    "servers": entry["mcpServers"],
                }
            )
    project = read_json_object(ctx.cwd / ".mcp.json")
    if isinstance(project.get("mcpServers"), dict):
        sources.append(
            {"file": ctx.cwd / ".mcp.json", "prefix": "mcpServers", "servers": project["mcpServers"]}
        )
    return sources


def server_names(ctx: Context) -> list[str]:
    return sorted({name for s in config_sources(ctx) for name in s["servers"]})
