"""Tracker counts, taken with the command that includes closed or inactive items."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .context import Context, load_data

MAX_OUTPUT_LINES = 20
LITTER = frozenset({".DS_Store", ".gitkeep", "Thumbs.db"})


def is_empty(directory: Path) -> bool:
    """No files at any depth apart from OS litter."""
    return not any(p.is_file() and p.name not in LITTER for p in directory.rglob("*"))


def tracker_dirs(ctx: Context, marker: str) -> list[Path]:
    """Marker directories from the top of the load path down to cwd; the last one is what the CLI uses."""
    return [d / marker for d in ctx.cwd_ancestry() if (d / marker).is_dir()]


def leftovers(ctx: Context) -> list[dict[str, str]]:
    """Empty tracker directories nearest the working tree, which hide a real one higher up."""
    found = []
    for t in load_data("trackers.json").get("trackers", []):
        if not isinstance(t, dict):
            continue
        dirs = tracker_dirs(ctx, str(t["marker"]))
        if dirs and is_empty(dirs[-1]):
            real = [d for d in dirs[:-1] if not is_empty(d)]
            found.append(
                {
                    "kind": "empty-tracker-dir",
                    "tracker": str(t["tracker"]),
                    "path": ctx.display(dirs[-1]),
                    "shadows": ctx.display(real[-1]) if real else "",
                }
            )
    return found


def collect(ctx: Context) -> list[dict[str, Any]]:
    trackers = load_data("trackers.json").get("trackers", [])
    found: list[dict[str, Any]] = []
    for t in trackers:
        if not isinstance(t, dict):
            continue
        markers = tracker_dirs(ctx, str(t["marker"]))
        if not markers:
            continue
        dirs = [m.parent for m in markers]
        command = [str(c) for c in t["command"]]
        entry: dict[str, Any] = {
            "tracker": t["tracker"],
            "path": ctx.display(dirs[-1]),
            "command": " ".join(command),
            "avoid": t["avoid"],
            "why": t["why"],
            "output": "",
            "status": "not run",
            "shadowed_by_empty": ctx.display(markers[-1]) if is_empty(markers[-1]) else "",
        }
        if ctx.run_trackers:
            result = ctx.runner.run(command, cwd=ctx.cwd)
            lines = result.stdout.splitlines()[:MAX_OUTPUT_LINES]
            entry["output"] = ctx.redact("\n".join(lines))
            entry["status"] = "ok" if result.returncode == 0 else f"exit {result.returncode}"
        found.append(entry)
    return found
