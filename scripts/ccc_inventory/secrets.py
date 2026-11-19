"""Plaintext-secret scan of config files. Records file + key + token type, never the value."""

from __future__ import annotations

import re
from collections.abc import Iterator, Sequence
from typing import Any

from .context import Context
from .mcp import config_sources
from .settings import SettingsFile

PATTERNS: Sequence[tuple[str, re.Pattern[str]]] = (
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
    ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("slack-token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("google-oauth-client-secret", re.compile(r"\bGOCSPX-[A-Za-z0-9_-]{20,}")),
    ("api-key-sk", re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}")),
)


def walk(value: Any, path: str) -> Iterator[tuple[str, str]]:
    if isinstance(value, dict):
        for k in sorted(value):
            yield from walk(value[k], f"{path}.{k}" if path else str(k))
    elif isinstance(value, list):
        for i, v in enumerate(value):
            yield from walk(v, f"{path}[{i}]")
    elif isinstance(value, str):
        yield path, value


def classify(value: str, extra: Sequence[tuple[str, re.Pattern[str]]] = ()) -> list[str]:
    return [name for name, pattern in (*PATTERNS, *extra) if pattern.search(value)]


def collect(
    ctx: Context, files: list[SettingsFile], extra_patterns: Sequence[str] = ()
) -> list[dict[str, str]]:
    extra = [(f"custom-{i}", re.compile(p)) for i, p in enumerate(extra_patterns)]
    found: list[dict[str, str]] = []

    def scan(display: str, root: Any, prefix: str) -> None:
        for key, value in walk(root, prefix):
            for token_type in classify(value, extra):
                found.append({"file": display, "key": key, "type": token_type})

    for f in files:
        scan(ctx.display(f.path), f.data, "")
    for source in config_sources(ctx):
        scan(ctx.display(source["file"]), source["servers"], source["prefix"])
    return sorted(found, key=lambda s: (s["file"], s["key"], s["type"]))
