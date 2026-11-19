"""Tracker counts, taken with the command that includes closed or inactive items."""

from __future__ import annotations

from typing import Any

from .context import Context, load_data

MAX_OUTPUT_LINES = 20


def collect(ctx: Context) -> list[dict[str, Any]]:
    trackers = load_data("trackers.json").get("trackers", [])
    found: list[dict[str, Any]] = []
    for t in trackers:
        if not isinstance(t, dict):
            continue
        dirs = [d for d in ctx.cwd_ancestry() if (d / str(t["marker"])).is_dir()]
        if not dirs:
            continue
        command = [str(c) for c in t["command"]]
        entry: dict[str, Any] = {
            "tracker": t["tracker"],
            "path": ctx.display(dirs[-1]),
            "command": " ".join(command),
            "avoid": t["avoid"],
            "why": t["why"],
            "output": "",
            "status": "not run",
        }
        if ctx.run_trackers:
            result = ctx.runner.run(command)
            lines = result.stdout.splitlines()[:MAX_OUTPUT_LINES]
            entry["output"] = ctx.redact("\n".join(lines))
            entry["status"] = "ok" if result.returncode == 0 else f"exit {result.returncode}"
        found.append(entry)
    return found
