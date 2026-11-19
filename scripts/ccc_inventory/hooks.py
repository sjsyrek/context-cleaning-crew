"""Hooks per event from settings files. Events whose output is injected into context are marked."""

from __future__ import annotations

from typing import Any

from .context import Context
from .settings import SettingsFile

INJECTING = ("SessionStart", "UserPromptSubmit", "PreCompact", "PostCompact")


def collect(ctx: Context, files: list[SettingsFile]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for f in files:
        hooks = f.data.get("hooks")
        if not isinstance(hooks, dict):
            continue
        for event in sorted(hooks):
            groups = hooks[event]
            for group in groups if isinstance(groups, list) else []:
                if not isinstance(group, dict):
                    continue
                for hook in group.get("hooks", []) if isinstance(group.get("hooks"), list) else []:
                    if isinstance(hook, dict) and isinstance(hook.get("command"), str):
                        found.append(
                            {
                                "event": event,
                                "matcher": str(group.get("matcher", "")),
                                "command": ctx.redact(hook["command"]),
                                "file": ctx.display(f.path),
                                "injects_context": event in INJECTING,
                            }
                        )
    return found
