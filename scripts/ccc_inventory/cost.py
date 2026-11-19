"""Per-plugin token cost, parsed from `claude plugin details <plugin>` ("Projected token cost")."""

from __future__ import annotations

import re
from typing import Any

from .context import Context

ALWAYS_ON = re.compile(r"Always-on:\s*~?([\d.]+k?)\s*tok")
ROW = re.compile(r"^\s{2}(\S+)\s+~?([\d.]+k?)\s+~?([\d.]+k?)\s*$")


def tokens(text: str) -> int:
    """`~295` -> 295, `~5.6k` -> 5600."""
    return round(float(text[:-1]) * 1000) if text.endswith("k") else int(float(text))


def parse(output: str) -> dict[str, Any]:
    total = ALWAYS_ON.search(output)
    components: list[dict[str, Any]] = []
    in_table = False
    for line in output.splitlines():
        if line.strip().startswith("component"):
            in_table = True
            continue
        if in_table:
            row = ROW.match(line)
            if not row:
                if line.strip():
                    in_table = False
                continue
            components.append(
                {
                    "component": row.group(1),
                    "always_on": tokens(row.group(2)),
                    "on_invoke": tokens(row.group(3)),
                }
            )
    if not total:
        return {"status": "unparsed"}
    return {"always_on": tokens(total.group(1)), "components": components}


def plugin_cost(ctx: Context, plugin_id: str) -> dict[str, Any]:
    result = ctx.runner.run(["claude", "plugin", "details", plugin_id])
    if result.returncode != 0:
        return {"status": "not checked"}
    return parse(result.stdout)
