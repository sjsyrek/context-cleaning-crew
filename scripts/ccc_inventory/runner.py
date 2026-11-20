"""Command execution behind a protocol, so tests can substitute canned output."""

from __future__ import annotations

import subprocess
import sys
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str = ""


class Runner(Protocol):
    def run(
        self,
        argv: Sequence[str],
        *,
        stdin: str | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult: ...


class SubprocessRunner:
    """Runs real commands with a timeout; a missing binary is a non-zero result, not an error."""

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds

    def run(
        self,
        argv: Sequence[str],
        *,
        stdin: str | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        try:
            done = subprocess.run(
                list(argv),
                input=stdin,
                cwd=cwd,
                env=dict(env) if env is not None else None,
                capture_output=True,
                text=True,
                errors="replace",
                timeout=self.timeout_seconds,
                check=False,
            )
        except (OSError, subprocess.TimeoutExpired) as exc:
            return CommandResult(returncode=127, stdout="", stderr=str(exc))
        return CommandResult(returncode=done.returncode, stdout=done.stdout, stderr=done.stderr)


class FakeRunner:
    """Returns canned results keyed by argv; unknown commands behave like a missing binary."""

    def __init__(self, responses: dict[tuple[str, ...], CommandResult]) -> None:
        self.responses = responses
        self.calls: list[tuple[str, ...]] = []
        self.cwds: dict[tuple[str, ...], Path | None] = {}  # last cwd per argv

    def run(
        self,
        argv: Sequence[str],
        *,
        stdin: str | None = None,
        cwd: Path | None = None,
        env: Mapping[str, str] | None = None,
    ) -> CommandResult:
        key = tuple(argv)
        self.calls.append(key)
        self.cwds[key] = cwd
        return self.responses.get(key, CommandResult(returncode=127, stdout="", stderr="not found"))


def sandbox_argv(command: str, writable: Path) -> list[str] | None:
    """Run a shell command with no network and no file writes outside `writable`, or None where no
    sandbox is available (only macOS `sandbox-exec` for now: a dry run without one never runs)."""
    if sys.platform != "darwin":
        return None
    root = str(writable.resolve()).replace("\\", "\\\\").replace('"', '\\"')
    profile = (
        "(version 1)(allow default)(deny network*)(deny file-write*)"
        f'(allow file-write* (subpath "{root}"))(allow file-write* (literal "/dev/null"))'
    )
    return ["/usr/bin/sandbox-exec", "-p", profile, "/bin/sh", "-c", command]
