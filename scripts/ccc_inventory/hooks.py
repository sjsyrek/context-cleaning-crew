"""Hooks per event from settings files and installed plugins. Events whose output is injected into
context are marked, and, only with the opt-in, dry-run in a sandbox to measure that output.

The dry run records sizes and whether output that looks like JSON parses; never the output itself.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from typing import Any

from .context import Context, approx_tokens, read_json_object
from .plugins import expand, installed
from .settings import SettingsFile

INJECTING = ("SessionStart", "UserPromptSubmit", "PreCompact", "PostCompact")
OVERSIZED_BYTES = 10_000  # heuristic: about 2.5k tokens injected on every matching event
MAX_TIMEOUT_SECONDS = 10


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


def sources(ctx: Context, files: list[SettingsFile]) -> list[tuple[str, Path | None, Any]]:
    """(label, plugin root or None, hooks object), settings files first."""
    found: list[tuple[str, Path | None, Any]] = [
        (ctx.display(f.path), None, f.data.get("hooks")) for f in files
    ]
    for pid, installs in sorted(installed(ctx).items()):
        roots = sorted({str(i["installPath"]) for i in installs if isinstance(i.get("installPath"), str)})
        for raw in roots[:1]:  # every scope of one plugin shares its install
            root = expand(ctx, raw)
            found.append(
                (f"plugin {pid}", root, read_json_object(root / "hooks" / "hooks.json").get("hooks"))
            )
    return found


def classify_json(stdout: str) -> str:
    text = stdout.strip()
    if not text.startswith("{"):
        return "not json"
    try:
        json.loads(text)
    except ValueError:
        return "malformed"  # Claude Code ignores it silently
    return "valid"


def dry_run(ctx: Context, event: str, hook: dict[str, Any], plugin_root: Path | None) -> dict[str, Any]:
    if event not in INJECTING:
        return {"status": "not run: output not injected"}
    if not ctx.dry_run_hooks:
        return {"status": "not run: opt in with --dry-run-hooks"}
    with tempfile.TemporaryDirectory(prefix="ccc-hook-") as tmp:
        argv = ctx.hook_sandbox(str(hook["command"]), Path(tmp))
        if argv is None:
            return {"status": "not run: no sandbox on this platform"}
        # A minimal environment: the hook can't print a secret it never received.
        env = {
            "PATH": "/usr/local/bin:/opt/homebrew/bin:/usr/bin:/bin:/usr/sbin:/sbin",
            "HOME": str(ctx.home),
            "TMPDIR": tmp,
            "LANG": "C.UTF-8",
            "CLAUDE_PROJECT_DIR": str(ctx.cwd),
        }
        if plugin_root is not None:
            env["CLAUDE_PLUGIN_ROOT"] = str(plugin_root)
        stdin = json.dumps(
            {"hook_event_name": event, "session_id": "ccc-dry-run", "cwd": str(ctx.cwd), "source": "startup"}
        )
        result = ctx.runner.run(argv, stdin=stdin, cwd=ctx.cwd, env=env)
    size = len(result.stdout.encode("utf-8"))
    return {
        "status": "ok" if result.returncode == 0 else f"exit {result.returncode}",
        "bytes": size,
        "approx_tokens": approx_tokens(size),
        "oversized": size > OVERSIZED_BYTES,
        "json": classify_json(result.stdout),
    }


def collect(ctx: Context, files: list[SettingsFile]) -> list[dict[str, Any]]:
    found: list[dict[str, Any]] = []
    for label, plugin_root, hooks in sources(ctx, files):
        for event, matcher, hook in entries(hooks):
            found.append(
                {
                    "event": event,
                    "matcher": matcher,
                    "command": ctx.redact(hook["command"]),
                    "file": label,
                    "injects_context": event in INJECTING,
                    "dry_run": dry_run(ctx, event, hook, plugin_root),
                }
            )
    return found
