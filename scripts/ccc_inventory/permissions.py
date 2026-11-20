"""Permission posture: permissive combinations, redundant rules, and rules that match no tool."""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from typing import Any

from .context import Context, load_data, read_json_object
from .memory import seen_projects
from .settings import SettingsFile

PERMISSIVE_MODES = ("acceptEdits", "bypassPermissions")
RULE = re.compile(r"^(?P<tool>[A-Za-z0-9_\-]+)(?:\((?P<spec>.*)\))?$")


@dataclass(frozen=True)
class Rule:
    text: str
    tool: str
    spec: str | None
    list_name: str
    file: str

    @property
    def is_blanket(self) -> bool:
        return self.spec is None or self.spec.strip() in ("", "*")

    def prefix(self) -> str | None:
        """`git:*` / `git *` / `git` -> `git`; None for a spec that isn't a prefix pattern."""
        if self.spec is None:
            return None
        spec = self.spec.strip()
        for suffix in (":*", " *", "*"):
            if spec.endswith(suffix):
                return spec[: -len(suffix)].strip()
        return spec


def parse(text: str, list_name: str, file: str) -> Rule | None:
    m = RULE.match(text.strip())
    if not m:
        return None
    return Rule(text=text, tool=m.group("tool"), spec=m.group("spec"), list_name=list_name, file=file)


def covers(broad: Rule, narrow: Rule) -> bool:
    if broad.text == narrow.text or broad.tool != narrow.tool:
        return False
    if broad.is_blanket:
        return not narrow.is_blanket
    if narrow.is_blanket or broad.tool != "Bash":
        return False
    bp, np_ = broad.prefix(), narrow.prefix()
    if not bp or np_ is None or not broad.spec or not broad.spec.strip().endswith("*"):
        return False
    return np_ == bp or np_.startswith(bp + " ") or np_.startswith(bp + ":")


def all_rules(ctx: Context, files: list[SettingsFile]) -> list[Rule]:
    rules: list[Rule] = []
    for f in files:
        perms = f.data.get("permissions")
        if not isinstance(perms, dict):
            continue
        for list_name in ("allow", "ask", "deny"):
            entries = perms.get(list_name)
            if isinstance(entries, list):
                for entry in entries:
                    if isinstance(entry, str):
                        rule = parse(entry, list_name, ctx.display(f.path))
                        if rule:
                            rules.append(rule)
    return rules


def other_project_files(ctx: Context, files: list[SettingsFile]) -> list[SettingsFile]:
    """Settings of the other projects in ~/.claude.json. Kept apart from `files`: they never feed
    enable flags, hooks or options, only the secrets scan and `other_projects` counts."""
    loaded = {f.path.resolve() for f in files}
    found = []
    for project in seen_projects(ctx):
        for name, scope in (("settings.json", "project"), ("settings.local.json", "project-local")):
            path = project / ".claude" / name
            if path.is_file() and path.resolve() not in loaded:
                loaded.add(path.resolve())
                found.append(SettingsFile(path=path, scope=scope, data=read_json_object(path)))
    return found


def other_projects(
    ctx: Context,
    files: list[SettingsFile],
    others: list[SettingsFile],
    servers: list[str],
    plugins: list[str],
) -> list[dict[str, Any]]:
    """Per project (with the user's settings, never another project's): rule counts per list and
    finding counts per kind for each of its files. No rule text: redaction is pattern-only."""
    user = [f for f in files if f.scope.startswith("user")]
    found = []
    for project in sorted({f.path.parent.parent for f in others}):
        own = [f for f in others if f.path.parent.parent == project]
        result = collect(ctx, [*user, *own], servers, plugins)
        for f in own:
            shown = ctx.display(f.path)
            rules = Counter(r["list"] for r in result["rules"] if r["file"] == shown)
            kinds = Counter(x["kind"] for x in result["findings"] if x["file"] == shown)
            lists = {name: rules[name] for name in ("allow", "ask", "deny")}
            found.append({"path": shown, "rules": lists, "findings": dict(sorted(kinds.items()))})
    return found


def default_mode(files: list[SettingsFile]) -> str | None:
    mode: str | None = None
    for f in files:  # later (project) scopes override earlier (user) ones
        perms = f.data.get("permissions")
        if isinstance(perms, dict) and isinstance(perms.get("defaultMode"), str):
            mode = perms["defaultMode"]
    return mode


def mcp_reason(tool: str, servers: list[str], plugins: list[str]) -> str | None:
    """Why an `mcp__…` rule matches nothing, or None if it may match."""
    rest = tool[len("mcp__") :]
    if rest.startswith("claude_ai_"):
        return None  # account-level connector; not visible from local files
    if rest.startswith("plugin_"):
        body = rest[len("plugin_") :]
        if any(body.startswith(p.replace("-", "_") + "_") or body.startswith(p + "_") for p in plugins):
            return None
        return "plugin not installed"
    server = rest.split("__", 1)[0]
    return None if server in servers else "MCP server not configured"


def collect(
    ctx: Context, files: list[SettingsFile], servers: list[str], plugins: list[str]
) -> dict[str, Any]:
    rules = all_rules(ctx, files)
    known = set(load_data("builtin-tools.json").get("tools", []))
    mode = default_mode(files)
    allows = [r for r in rules if r.list_name == "allow"]
    findings: list[dict[str, Any]] = []

    if mode in PERMISSIVE_MODES:
        for r in allows:
            if r.tool == "Bash" and r.is_blanket:
                findings.append(
                    {
                        "kind": "blanket-allow-with-permissive-mode",
                        "rule": ctx.redact(r.text),
                        "file": r.file,
                        "mode": mode,
                    }
                )

    for r in allows:
        broader = next((b for b in allows if covers(b, r)), None)
        if broader:
            findings.append(
                {
                    "kind": "redundant-allow",
                    "rule": ctx.redact(r.text),
                    "file": r.file,
                    "covered_by": ctx.redact(broader.text),
                }
            )

    for r in rules:
        reason: str | None
        if r.tool.startswith("mcp__"):
            reason = mcp_reason(r.tool, servers, plugins)
        else:
            reason = None if r.tool in known else "unknown tool"
        if reason:
            findings.append(
                {
                    "kind": "rule-matches-no-tool",
                    "rule": ctx.redact(r.text),
                    "file": r.file,
                    "list": r.list_name,
                    "reason": reason,
                }
            )

    return {
        "default_mode": mode,
        "rules": [{"rule": ctx.redact(r.text), "list": r.list_name, "file": r.file} for r in rules],
        "findings": findings,
    }
