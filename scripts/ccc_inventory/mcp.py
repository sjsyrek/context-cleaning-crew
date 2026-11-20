"""MCP servers from ~/.claude.json, the project's .mcp.json and installed plugins, grouped by target."""

from __future__ import annotations

from typing import Any

from .context import Context, read_json_object
from .keeper import pick_server_keeper
from .plugins import expand, installed


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


def plugin_sources(ctx: Context) -> list[dict[str, Any]]:
    """Servers each installed plugin ships, named `plugin_<plugin>_<server>` like their tool names
    (`mcp__plugin_<plugin>_<server>__<tool>`). Plugin files are the author's, so the secrets scan,
    which covers the user's own config, doesn't read them."""
    sources: list[dict[str, Any]] = []
    for pid, entries in sorted(installed(ctx).items()):
        name = pid.partition("@")[0]
        paths = sorted({str(e["installPath"]) for e in entries if isinstance(e.get("installPath"), str)})
        servers: dict[str, Any] = {}
        for raw in paths:
            root = expand(ctx, raw)
            data = read_json_object(root / ".mcp.json")
            wrapped = data.get("mcpServers")
            servers.update(wrapped if isinstance(wrapped, dict) else data)
            inline = read_json_object(root / ".claude-plugin" / "plugin.json").get("mcpServers")
            if isinstance(inline, dict):
                servers.update(inline)
        if servers:
            sources.append(
                {
                    "plugin": pid,
                    "label": f"plugin {pid}",
                    "servers": {f"plugin_{name}_{s}": v for s, v in servers.items() if isinstance(v, dict)},
                    "raw_names": sorted(s for s, v in servers.items() if isinstance(v, dict)),
                }
            )
    return sources


def server_names(ctx: Context) -> list[str]:
    user = {name for s in config_sources(ctx) for name in s["servers"]}
    return sorted(user | {name for s in plugin_sources(ctx) for name in s["servers"]})


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
    labeled: list[tuple[str, str, dict[str, Any]]] = []  # (label, plugin id or "", servers)
    for source in config_sources(ctx):
        suffix = "" if source["prefix"] == "mcpServers" else f" {source['prefix'].rsplit('.', 1)[0]}"
        labeled.append((ctx.display(source["file"]) + suffix, "", source["servers"]))
    plugin_srcs = plugin_sources(ctx)
    labeled += [(s["label"], s["plugin"], s["servers"]) for s in plugin_srcs]

    by_target: dict[str, list[dict[str, str]]] = {}
    deprecated: list[dict[str, str]] = []
    for label, plugin, servers in labeled:
        for name, server in sorted(servers.items()):
            if not isinstance(server, dict):
                continue
            key = ctx.redact(target(server))
            if key:
                by_target.setdefault(key, []).append({"server": name, "source": label, "plugin": plugin})
            transport = str(server.get("type", ""))
            if transport in DEPRECATED_TRANSPORTS:
                deprecated.append({"server": name, "transport": transport})

    duplicates = []
    for t, members in sorted(by_target.items()):
        if len({m["server"] for m in members}) < 2:
            continue
        members = sorted(members, key=lambda m: (m["server"], m["source"]))
        keeper, rule = pick_server_keeper(members, ctx.options.options)
        duplicates.append(
            {
                "target": t,
                "servers": sorted({m["server"] for m in members}),
                "members": [{"server": m["server"], "source": m["source"]} for m in members],
                "keeper": keeper,
                "rule": rule,
            }
        )

    by_raw: dict[str, list[str]] = {}
    for s in plugin_srcs:
        for raw in s["raw_names"]:
            by_raw.setdefault(raw, []).append(s["plugin"])
    return {
        "servers": server_names(ctx),
        "duplicates": duplicates,
        "plugin_name_clashes": [
            {"server": raw, "plugins": sorted(p)} for raw, p in sorted(by_raw.items()) if len(p) > 1
        ],
        "deprecated_transport": sorted(deprecated, key=lambda d: d["server"]),
    }
