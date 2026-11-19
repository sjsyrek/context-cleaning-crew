"""One-line summary of a manifest, optionally against the previous one, for scheduled report runs."""

from __future__ import annotations

from typing import Any


def always_on(manifest: dict[str, Any]) -> tuple[int, int]:
    """(approximate always-on tokens, number of plugins whose cost was not checked)."""
    total, uncosted = 0, 0
    for plugin in manifest.get("plugins", {}).get("installed", []):
        cost = plugin.get("cost", {})
        if isinstance(cost.get("always_on"), int):
            total += cost["always_on"]
        else:
            uncosted += 1
    total += sum(f.get("approx_tokens", 0) for f in manifest.get("instructions", {}).get("files", []))
    return total, uncosted


def plural(n: int, word: str, rest: str = "") -> str:
    return f"{n} {word}{'' if n == 1 else 's'}{rest}"


def issues(manifest: dict[str, Any]) -> list[str]:
    behind = sum(1 for d in manifest.get("drift", {}).get("marketplace", []) if d.get("status") == "behind")
    counts = [
        (len(manifest.get("secrets", [])), "plaintext secret", ""),
        (len(manifest.get("permissions", {}).get("findings", [])), "permission finding", ""),
        (len(manifest.get("removed_tool_refs", [])), "removed-tool reference", ""),
        (behind, "plugin", " behind its marketplace"),
        (len(manifest.get("mcp", {}).get("duplicates", [])), "duplicate MCP server group", ""),
    ]
    return [plural(n, word, rest) for n, word, rest in counts if n]


def summarize(current: dict[str, Any], previous: dict[str, Any] | None = None) -> str:
    tokens, uncosted = always_on(current)
    head = f"always-on ~{tokens} tokens"
    if previous is not None:
        head += f" ({tokens - always_on(previous)[0]:+d} since last run)"
    if uncosted:
        head += f", {plural(uncosted, 'plugin')} not costed"
    return "; ".join([head, *issues(current)])
