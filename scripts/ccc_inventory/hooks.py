"""Hooks per event from settings files and installed plugins, with the events whose output is
injected into context marked. The inventory lists hooks and never runs one: their output size and
JSON are for the reviewer to judge by reading the hook script.
"""

from __future__ import annotations

from typing import Any

from .context import Context, read_json_object
from .plugins import expand, installed
from .settings import SettingsFile

INJECTING = ("SessionStart", "UserPromptSubmit", "PreCompact", "PostCompact")


def entries(hooks: Any) -> list[tuple[str, str, dict[str, Any]]]:
    """(event, matcher, hook) for every command hook in a `hooks` object."""
    found: list[tuple[str, str, dict[str, Any]]] = []
    if not isinstance(hooks, dict):
        return found
    for event in sorted(hooks):
        groups = hooks[event]
        for group in groups if isinstance(groups, list) else []:
            if not isinstance(group, dict) or not isinstance(group.get("hooks"), list):
                continue
            for hook in group["hooks"]:
                if isinstance(hook, dict) and isinstance(hook.get("command"), str):
                    found.append((event, str(group.get("matcher", "")), hook))
    return found


def sources(ctx: Context, files: list[SettingsFile]) -> list[tuple[str, Any]]:
    """(label, hooks) for settings files first, then installed plugins."""
    found = [(ctx.display(f.path), f.data.get("hooks")) for f in files]
    for pid, installs in sorted(installed(ctx).items()):
        roots = sorted({str(i["installPath"]) for i in installs if isinstance(i.get("installPath"), str)})
        for raw in roots[:1]:  # every scope of one plugin shares its install
            hooks_file = expand(ctx, raw) / "hooks" / "hooks.json"
            found.append((f"plugin {pid}", read_json_object(hooks_file).get("hooks")))
    return found


def collect(ctx: Context, files: list[SettingsFile]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for label, hooks in sources(ctx, files):
        for event, matcher, hook in entries(hooks):
            found.append(
                {
                    "event": event,
                    "matcher": matcher,
                    "command": ctx.redact(hook["command"]),
                    "file": label,
                    "injects_context": event in INJECTING,
                }
            )
    return found
