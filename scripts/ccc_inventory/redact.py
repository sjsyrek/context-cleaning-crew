"""Secret patterns, shared by the secrets scan and by every free-text field of the manifest."""

from __future__ import annotations

import re
from collections.abc import Sequence

Pattern = tuple[str, "re.Pattern[str]"]

PATTERNS: tuple[Pattern, ...] = (
    ("github-token", re.compile(r"\bgh[pousr]_[A-Za-z0-9]{20,}")),
    ("github-pat", re.compile(r"\bgithub_pat_[A-Za-z0-9_]{20,}")),
    ("slack-token", re.compile(r"\bxox[abposr]-[A-Za-z0-9-]{10,}")),
    ("aws-access-key", re.compile(r"\bAKIA[0-9A-Z]{16}\b")),
    ("google-oauth-client-secret", re.compile(r"\bGOCSPX-[A-Za-z0-9_-]{20,}")),
    ("api-key-sk", re.compile(r"\bsk-(?:ant-|proj-)?[A-Za-z0-9_-]{20,}")),
)


def compile_extra(extra: Sequence[str]) -> tuple[Pattern, ...]:
    return tuple((f"custom-{i}", re.compile(p)) for i, p in enumerate(extra))


def classify(value: str, extra: Sequence[Pattern] = ()) -> list[str]:
    return [name for name, pattern in (*PATTERNS, *extra) if pattern.search(value)]


def redact(text: str, extra: Sequence[Pattern] = ()) -> str:
    """Replace every secret-looking span with `<redacted:<type>>`."""
    for name, pattern in (*PATTERNS, *extra):
        text = pattern.sub(f"<redacted:{name}>", text)
    return text
