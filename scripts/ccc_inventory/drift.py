"""Marketplaces, and version drift: installed plugin vs. marketplace, and plugin vs. the CLI it wraps."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from .context import Context, load_data, read_json_object
from .plugins import installed

REFRESH = ("claude", "plugin", "marketplace", "update")
VERSION = re.compile(r"\d+(?:\.\d+)+")


def parse_version(text: str) -> tuple[int, ...] | None:
    m = VERSION.search(text)
    return tuple(int(p) for p in m.group(0).split(".")) if m else None


def compare(installed_version: str, available: str) -> str:
    a, b = parse_version(installed_version), parse_version(available)
    if a is None or b is None:
        return "unknown"
    return "current" if a == b else ("behind" if a < b else "ahead")


def location(ctx: Context, raw: str) -> Path:
    """installLocation is absolute in real files; `~` is expanded against the audited home."""
    return ctx.home / raw[2:] if raw.startswith("~/") else Path(raw)


def marketplaces(ctx: Context) -> dict[str, dict[str, Any]]:
    """name -> {"location": Path, "plugins": {plugin name: entry}}."""
    known = read_json_object(ctx.claude_dir / "plugins" / "known_marketplaces.json")
    found: dict[str, dict[str, Any]] = {}
    for name in sorted(known):
        entry = known[name]
        if not isinstance(entry, dict) or not isinstance(entry.get("installLocation"), str):
            continue
        loc = location(ctx, entry["installLocation"])
        manifest = read_json_object(loc / ".claude-plugin" / "marketplace.json")
        plugins = manifest.get("plugins")
        entries = {
            p["name"]: p
            for p in (plugins if isinstance(plugins, list) else [])
            if isinstance(p, dict) and "name" in p
        }
        found[name] = {"location": loc, "plugins": entries}
    return found


def available_version(market: dict[str, Any], plugin: str) -> str:
    entry = market["plugins"].get(plugin)
    if not isinstance(entry, dict):
        return ""
    if isinstance(entry.get("version"), str):
        return str(entry["version"])
    source = entry.get("source")
    if isinstance(source, str):  # relative path inside the local clone
        manifest = read_json_object(market["location"] / source / ".claude-plugin" / "plugin.json")
        if isinstance(manifest.get("version"), str):
            return str(manifest["version"])
    return ""  # remote source: not knowable from the clone


def refresh(ctx: Context) -> bool:
    """Refresh marketplace clones; must run before anything reads plugin or marketplace state."""
    return ctx.live and ctx.refresh_marketplaces and ctx.runner.run(REFRESH).returncode == 0


def collect(ctx: Context, refreshed: bool) -> dict[str, Any]:
    markets = marketplaces(ctx)
    installs = installed(ctx)

    marketplace_drift: list[dict[str, str]] = []
    for pid in sorted(installs):
        name, _, market_name = pid.partition("@")
        versions = sorted({str(i.get("version", "")) for i in installs[pid] if isinstance(i, dict)})
        current = versions[-1] if versions else ""
        market = markets.get(market_name)
        available = available_version(market, name) if market else ""
        marketplace_drift.append(
            {
                "plugin": pid,
                "installed": current,
                "available": available,
                "status": compare(current, available) if available else "unknown",
            }
        )

    wrappers = load_data("cli-wrappers.json").get("wrappers", {})
    cli_drift: list[dict[str, str]] = []
    for pid in sorted(installs):
        name = pid.split("@", 1)[0]
        wrapper = wrappers.get(name)
        if not isinstance(wrapper, dict):
            continue
        plugin_version = next(d["installed"] for d in marketplace_drift if d["plugin"] == pid)
        cli = None
        if ctx.live:
            result = ctx.runner.run(list(wrapper["command"]))
            cli = parse_version(result.stdout) if result.returncode == 0 else None
        cli_version = ".".join(str(p) for p in cli) if cli else ""
        if not ctx.live:
            status = ctx.NOT_LIVE
        elif not cli_version:
            status = "not checked"
        else:
            status = "same" if parse_version(plugin_version) == cli else "differs"
        cli_drift.append(
            {
                "plugin": pid,
                "plugin_version": plugin_version,
                "cli": " ".join(wrapper["command"]),
                "cli_version": cli_version,
                "status": status,
            }
        )

    return {
        "refreshed": refreshed,
        "marketplace": marketplace_drift,
        "cli": cli_drift,
        "note": "" if refreshed else "compared against the cached marketplace clones",
    }


def marketplace_summary(ctx: Context) -> dict[str, Any]:
    counts = dict.fromkeys(marketplaces(ctx), 0)
    for pid in installed(ctx):
        market = pid.partition("@")[2]
        if market in counts:
            counts[market] += 1
    return {
        "configured": [{"name": n, "installed_plugins": counts[n]} for n in sorted(counts)],
        "unused": sorted(n for n, c in counts.items() if c == 0),
    }
