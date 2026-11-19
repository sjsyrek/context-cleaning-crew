"""Installed and enabled plugins, from the files Claude Code keeps under ~/.claude/plugins."""

from __future__ import annotations

from typing import Any

from .context import Context, read_json_object
from .cost import plugin_cost
from .settings import SettingsFile


def installed(ctx: Context) -> dict[str, list[dict[str, Any]]]:
    data = read_json_object(ctx.claude_dir / "plugins" / "installed_plugins.json")
    plugins = data.get("plugins")
    if not isinstance(plugins, dict):
        return {}
    return {k: v for k, v in plugins.items() if isinstance(v, list)}


def plugin_names(ids: list[str]) -> list[str]:
    """`name@marketplace` -> `name`."""
    return sorted({i.split("@", 1)[0] for i in ids})


def collect(ctx: Context, files: list[SettingsFile]) -> dict[str, Any]:
    installs = installed(ctx)
    enabled: dict[str, bool] = {}
    for f in files:
        flags = f.data.get("enabledPlugins")
        if isinstance(flags, dict):
            enabled.update({k: bool(v) for k, v in flags.items()})
    return {
        "installed": [
            {
                "id": pid,
                "scopes": sorted({str(i.get("scope", "")) for i in installs[pid] if isinstance(i, dict)}),
                "versions": sorted({str(i.get("version", "")) for i in installs[pid] if isinstance(i, dict)}),
                "enabled": enabled.get(pid, False),
                "cost": plugin_cost(ctx, pid),
            }
            for pid in sorted(installs)
        ],
        "dangling_enabled": sorted(p for p, on in enabled.items() if on and p not in installs),
        "installed_disabled": sorted(p for p in installs if not enabled.get(p, False)),
    }
