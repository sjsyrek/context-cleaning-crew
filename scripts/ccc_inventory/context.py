"""Shared inputs for every inventory module, and small file helpers."""

from __future__ import annotations

import json
import re
import shutil
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .options import LoadedOptions, load_options
from .redact import Pattern, redact
from .runner import Runner

DATA_DIR = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class Context:
    home: Path
    cwd: Path
    runner: Runner
    secret_patterns: tuple[Pattern, ...] = ()
    refresh_marketplaces: bool = False  # writes the local marketplace clones
    run_trackers: bool = False  # runs tracker CLIs (e.g. `bd stats`) in the working tree
    which: Callable[[str], str | None] = shutil.which  # looks a tool up on PATH; never runs it
    live: bool = True  # home is the running user's: `claude plugin ...` and CLI probes describe it
    options: LoadedOptions = field(default_factory=lambda: load_options([]))  # defaults unless given

    NOT_LIVE = "not checked: not the live setup"

    @property
    def claude_dir(self) -> Path:
        return self.home / ".claude"

    def redact(self, text: str) -> str:
        """Every free-text manifest field goes through this: no secret value, no absolute home path."""
        text = redact(text, self.secret_patterns)
        for home in sorted({str(self.home.resolve()), str(self.home)}, key=len, reverse=True):
            text = re.sub(re.escape(home) + r"(?=/|\b|$|[\s\"'=])", "~", text)
        return text

    def display(self, path: Path) -> str:
        """Render a path relative to home as `~/...` so manifests are portable and diffable."""
        try:
            rel = path.resolve().relative_to(self.home.resolve())
        except ValueError:
            return str(path)
        return "~" if str(rel) == "." else "~/" + rel.as_posix()

    def cwd_ancestry(self) -> list[Path]:
        """Directories from the top of the load path down to cwd.

        When cwd is under home, the walk stops at home: files above it are outside the
        user's tree, and stopping there keeps fixture homes isolated from the real one.
        """
        cwd = self.cwd.resolve()
        home = self.home.resolve()
        chain = [cwd, *cwd.parents]
        if home in chain:
            chain = chain[: chain.index(home) + 1]
        return list(reversed(chain))


def read_json(path: Path) -> Any | None:
    """Parse a JSON file; a missing or malformed file is `None`, never an exception."""
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None


def read_json_object(path: Path) -> dict[str, Any]:
    data = read_json(path)
    return data if isinstance(data, dict) else {}


def load_data(name: str) -> dict[str, Any]:
    return read_json_object(DATA_DIR / name)


def read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return None


def approx_tokens(byte_count: int) -> int:
    """bytes/4, rounded up. A labeled heuristic, not a tokenizer."""
    return (byte_count + 3) // 4
