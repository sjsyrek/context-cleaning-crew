"""Plaintext-secret scan of config and instruction files. Records file + key + token type, never the value."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from typing import Any

from .context import Context, read_text
from .mcp import config_sources
from .redact import classify
from .settings import SettingsFile


def walk(value: Any, path: str) -> Iterator[tuple[str, str]]:
    if isinstance(value, dict):
        for k in sorted(value):
            yield from walk(value[k], f"{path}.{k}" if path else str(k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from walk(v, f"{path}[{i}]")
    elif isinstance(value, str):
        yield path, value


def collect(ctx: Context, files: list[SettingsFile], instruction_files: list[Path]) -> list[dict[str, str]]:
    found: list[dict[str, str]] = []

    def add(display: str, key: str, value: str) -> None:
        for token_type in classify(value, ctx.secret_patterns):
            found.append({"file": display, "key": key, "type": token_type})

    for f in files:
        for key, value in walk(f.data, ""):
            add(ctx.display(f.path), key, value)
    for source in config_sources(ctx):
        for key, value in walk(source["servers"], source["prefix"]):
            add(ctx.display(source["file"]), key, value)
    for path in instruction_files:
        for number, line in enumerate((read_text(path) or "").splitlines(), start=1):
            add(ctx.display(path), f"line {number}", line)
    return sorted(found, key=lambda s: (s["file"], s["key"], s["type"]))
