#!/usr/bin/env python3
"""SessionStart hook: after a successful Claude Code update, suggest one report run.

Hook output is injected into the session's context, so on every ordinary start this prints
nothing at all. It speaks once per new version, and only when it can record that it did
(otherwise it would repeat on every start). It never fails the session: any error is silent
and the exit code is always 0.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

DEFAULT_RESULT = Path.home() / ".claude" / ".last-update-result.json"


def default_state() -> Path:
    data = os.environ.get("CLAUDE_PLUGIN_DATA")
    base = Path(data) if data else Path.home() / ".claude" / "context-cleaning-crew"
    return base / "last-seen-version"


def updated_version(result_path: Path) -> str:
    """The version a successful update installed, or "" when there is nothing to report."""
    try:
        data = json.loads(result_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return ""
    if not isinstance(data, dict) or data.get("outcome") != "success":
        return ""
    version = data.get("version_to")
    return version.strip() if isinstance(version, str) else ""


def record(state_path: Path, version: str) -> bool:
    try:
        state_path.parent.mkdir(parents=True, exist_ok=True)
        state_path.write_text(version, encoding="utf-8")
    except OSError:
        return False
    return True


def check(result_path: Path, state_path: Path) -> str:
    version = updated_version(result_path)
    if not version:
        return ""
    try:
        seen = state_path.read_text(encoding="utf-8").strip()
    except OSError:
        seen = ""
    if seen == version:
        return ""
    if not record(state_path, version) or not seen:
        return ""  # first run: remember silently; unrecordable: stay quiet rather than repeat
    return (
        f"Claude Code updated {seen} -> {version}. Consider running `/context-cleaning-crew report` "
        "to check the setup for removed tools, version drift and new built-ins."
    )


def main(argv: list[str]) -> int:
    try:
        parser = argparse.ArgumentParser(add_help=False)
        parser.add_argument("--result", type=Path, default=DEFAULT_RESULT)
        parser.add_argument("--state", type=Path, default=None)
        args, _ = parser.parse_known_args(argv)
        message = check(args.result, args.state or default_state())
        if message:
            sys.stdout.write(message + "\n")
    except Exception:  # a hook must never break session start
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
