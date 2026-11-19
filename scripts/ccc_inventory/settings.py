"""Settings files in load order, and the reasoning-affecting values in them."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .context import Context, read_json_object

REASONING_ENV = re.compile(r"THINKING|EFFORT|REASONING")


@dataclass(frozen=True)
class SettingsFile:
    path: Path
    scope: str
    data: dict[str, Any]


def settings_files(ctx: Context) -> list[SettingsFile]:
    """User, then project settings. A path loaded at two scopes (cwd == home) is listed once."""
    candidates = [
        (ctx.claude_dir / "settings.json", "user"),
        (ctx.claude_dir / "settings.local.json", "user-local"),
        (ctx.cwd / ".claude" / "settings.json", "project"),
        (ctx.cwd / ".claude" / "settings.local.json", "project-local"),
    ]
    seen: set[Path] = set()
    found: list[SettingsFile] = []
    for path, scope in candidates:
        resolved = path.resolve()
        if resolved in seen or not path.is_file():
            continue
        seen.add(resolved)
        found.append(SettingsFile(path=path, scope=scope, data=read_json_object(path)))
    return found


def collect(ctx: Context, files: list[SettingsFile]) -> dict[str, Any]:
    reasoning_env: list[dict[str, str]] = []
    model: dict[str, str] = {}
    for f in files:
        env = f.data.get("env")
        if isinstance(env, dict):
            for key in sorted(env):
                if REASONING_ENV.search(key):
                    reasoning_env.append({"key": key, "value": str(env[key]), "file": ctx.display(f.path)})
        for key in ("model", "effortLevel", "outputStyle"):
            if isinstance(f.data.get(key), str):
                model[key] = f.data[key]
    return {
        "files": [{"path": ctx.display(f.path), "scope": f.scope} for f in files],
        "reasoning_env": reasoning_env,
        "selected": model,
    }
