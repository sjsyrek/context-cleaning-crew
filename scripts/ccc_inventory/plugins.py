"""Installed and enabled plugins, from the files Claude Code keeps under ~/.claude/plugins."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .context import Context, read_json_object
from .cost import plugin_cost
from .keeper import is_protected
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


def expand(ctx: Context, raw: str) -> Path:
    """Paths in installed_plugins.json are absolute; fixtures may write them as `~/...` or `~`."""
    if raw == "~":
        return ctx.home
    return ctx.home / raw[2:] if raw.startswith("~/") else Path(raw)


def multi_scope(ctx: Context, installs: dict[str, list[dict[str, Any]]]) -> list[dict[str, Any]]:
    """Plugins installed more than once. A project install for the home directory shares the
    user settings file, so uninstalling either copy can remove the other's enable flag."""
    found = []
    for pid in sorted(installs):
        entries = [e for e in installs[pid] if isinstance(e, dict)]
        if len(entries) < 2:
            continue
        scopes = []
        shares = False
        for e in entries:
            raw = e.get("projectPath")
            project = expand(ctx, raw) if isinstance(raw, str) and raw else None
            shares = shares or (project is not None and project.resolve() == ctx.home.resolve())
            scopes.append(
                {"scope": str(e.get("scope", "")), "project": ctx.display(project) if project else ""}
            )
        found.append(
            {
                "plugin": pid,
                "scopes": sorted(scopes, key=lambda s: (s["scope"], s["project"])),
                "shares_user_settings": shares,
            }
        )
    return found


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
                "protected": is_protected(pid, ctx.options.options),
            }
            for pid in sorted(installs)
        ],
        "multi_scope": multi_scope(ctx, installs),
        "dangling_enabled": sorted(p for p, on in enabled.items() if on and p not in installs),
        "installed_disabled": sorted(p for p in installs if not enabled.get(p, False)),
    }
