"""Command execution behind a protocol, so tests can substitute canned output."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CommandResult:
    returncode: int
    stdout: str
    stderr: str = ""


class Runner(Protocol):
    def run(self, argv: Sequence[str]) -> CommandResult: ...


class SubprocessRunner:
    """Runs real commands with a timeout; a missing binary is a non-zero result, not an error."""

    def __init__(self, timeout_seconds: float = 30.0) -> None:
        self.timeout_seconds = timeout_seconds

    def run(self, argv: Sequence[str]) -> CommandResult:
        try:
            done = subprocess.run(
                list(argv),
                capture_output=True,
                text=True,
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

    def run(self, argv: Sequence[str]) -> CommandResult:
        key = tuple(argv)
        self.calls.append(key)
        return self.responses.get(key, CommandResult(returncode=127, stdout="", stderr="not found"))
