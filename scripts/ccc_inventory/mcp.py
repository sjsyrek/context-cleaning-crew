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


DEPRECATED_TRANSPORTS = ("sse",)


def target(server: dict[str, Any]) -> str:
    if isinstance(server.get("url"), str):
        return str(server["url"])
    command = server.get("command")
    args = server.get("args")
    parts = [str(command)] if isinstance(command, str) else []
    parts += [str(a) for a in args] if isinstance(args, list) else []
    return " ".join(parts)


def collect(ctx: Context) -> dict[str, Any]:
    by_target: dict[str, set[str]] = {}
    deprecated: list[dict[str, str]] = []
    for source in config_sources(ctx):
        for name, server in sorted(source["servers"].items()):
            if not isinstance(server, dict):
                continue
            key = ctx.redact(target(server))
            if key:
                by_target.setdefault(key, set()).add(name)
            transport = str(server.get("type", ""))
            if transport in DEPRECATED_TRANSPORTS:
                deprecated.append({"server": name, "transport": transport})
    return {
        "servers": server_names(ctx),
        "duplicates": [
            {"target": t, "servers": sorted(names)}
            for t, names in sorted(by_target.items())
            if len(names) > 1
        ],
        "deprecated_transport": sorted(deprecated, key=lambda d: d["server"]),
    }
