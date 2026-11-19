---
name: context-cleaning-crew
description: Audit this Claude Code setup (settings, permissions, CLAUDE.md/AGENTS.md, plugins, skills, hooks, MCP servers, memory) for context cost, duplicates, stale or global-looking memory, conflicting instructions, removed tools, version drift and plaintext secrets, then clean up with per-item approval. Use when the user says "audit my Claude Code setup", "clean up my config", "what's eating my context", "context cleanup", or after a Claude Code update. Modes - quick (default), full, report (read-only).
argument-hint: "[quick|full|report] [focus]"
version: 0.0.0
---

# Context Cleaning Crew

Audit the user's Claude Code setup and clean it up **only with per-item approval**. You are the reviewer (quick, report) or the coordinator of five reviewer subagents (full).

## Modes

| Mode | Review | Changes things? |
|---|---|---|
| `quick` (default) | You, one pass over all five lenses | Only after the plan card is approved |
| `full` | Five parallel read-only subagents (`agents/`) + one debate round, then you | Only after the plan card is approved |
| `report` | You, one pass | **Never.** Write the report and stop. |

Parse the first argument as the mode (default `quick`) and the rest as an optional focus (e.g. "permissions", "memory"). A focus narrows the review, not the inventory.

## Phase 1 — Inventory

Run the deterministic, read-only inventory and save its output:

```sh
python3 "${CLAUDE_SKILL_DIR}/../../scripts/inventory.py" --cwd "$PWD" [flags] --out <report_dir>/<yyyy-mm-dd>-manifest.json
```

Use `--out` (it creates `<report_dir>`), not a shell redirect or `mkdir`: headless runs allow only these two script commands.

- `quick` / `full`: add `--refresh-marketplaces --run-trackers` (the refresh updates the local marketplace clones so version drift is real; trackers run their count command, e.g. `bd stats`).
- `report`: add neither, unless the `refresh_marketplaces` option is on. Never run anything that writes outside `<report_dir>`.
- `<report_dir>` defaults to `~/.claude/context-cleaning-crew/reports/`.
- **Another setup** (a backup, a copy, a fixture): when the user names one, pass `--home <its home>` and `--cwd <its working tree>`, and never apply anything: review as asked (`full` still dispatches the seats), then finish as in `report` mode. The `claude plugin`/`claude mcp` commands the executor uses always act on the live setup, so cleaning a different tree is out of scope. Say so in one line. Its manifest has `live_setup: false`, and plugin costs and CLI versions read "not checked: not the live setup" (those commands only describe the live install); say so in the report instead of estimating them.

Read the manifest. It never contains secret values (they appear as `<redacted:<type>>`) — **never print, log or pass a secret value**, even if you find one elsewhere. Identify secrets by file + key + type only.

## Phase 2 — Review

Produce findings in the schema in `references/finding-schema.md`. Work from the manifest; read files only to verify a specific claim (a memory fact, an instruction passage).

In `full` mode, follow `references/full-mode.md`: the five lenses below become five parallel read-only subagents plus one debate round with the workflow advocate, and you dedupe and resolve their findings. In `quick` and `report` mode you cover all five lenses yourself:

1. **Context economist** — always-on token cost (`plugins.installed[].cost`, instruction files, memory, context-injecting hooks) against usage (`usage.skills`); reasoning-affecting env vars (`settings.reasoning_env`); instructions that fight Claude Code's own behavior; instruction conflicts (`instructions.directives`, `deny_conflicts`, across files and levels); `move` candidates (`instructions.move_candidates`).
2. **Overlap analyst** — duplicate MCP servers (`mcp.duplicates`), plugins a built-in replaces (`overlap.builtin`; check the note for partial overlap), and **synced claude.ai skills**: compare the `anthropic-skills:*` entries in your own available-skills list with `plugins.installed` (e.g. `anthropic-skills:red-team` vs a `red-team` plugin). Pick a keeper by the `preferred_marketplaces` option, then capability.
3. **Security reviewer** — `secrets`, `permissions.findings` (blanket allow with a permissive mode, redundant rules, rules matching no tool), deny-list gaps, deprecated MCP transports.
4. **Memory curator** — `memory.dirs` (broken links, oversized index, `global_looking` memory that only loads under one directory), `removed_tool_refs` (`claude plugin validate` does not catch these), `drift` (behind marketplace, differs from wrapped CLI), stale memory claims checked with cheap read-only commands.
5. **Workflow advocate** — before finalizing, argue **for keeping** each proposed cut: heavy usage, a `protected` item, a workflow the cut would break. Attach the argument to the finding (`keep_argument`). Usage beats cost.

Counts: use the manifest's tracker `command` (it includes closed items); never re-count with the `avoid` command.

## Phase 3 — Plan card

Show the plan card from `references/plan-card.md` and **stop**. Accept `go`, `go except 3,7`, `keep 4`, `switch 5 to <alt>`, `explain 6`, `abort`. Items marked `confirm` (secrets, deletion of user-written content, anything irreversible) need an explicit per-item yes even after `go`.

In `report` mode, skip the approval and Phase 4: write the report with every finding as "proposed", then end with the same plan card in chat, headed `REPORT MODE — proposed, nothing applied`, without the reply line. Keep the numbers identical to the report's so the user can later say "apply 3 and 5" in quick mode. Then give the report path and stop.

## Phase 4 — Execute

Follow `references/executor-rules.md` exactly: back up first to a persistent directory, then apply in the fixed order, verifying each step.

## Phase 5 — Report

Write `<report_dir>/<yyyy-mm-dd>-<mode>.md` from `references/report-template.md`, diffing against the previous manifest in `<report_dir>` (the newest older `*-manifest.json`, found with Glob) when one exists. Get the headline numbers from:

```sh
python3 "${CLAUDE_SKILL_DIR}/../../scripts/compare.py" <this manifest> [<previous manifest>]
```

Tell the user the report path and the before/after always-on estimate. In `report` mode, make the **last line** of your reply exactly that `compare.py` line, so a scheduled run's notifier can show it (see `references/routine-setup.md`).

## Out of scope

- Connectivity or authentication failures: report "server X fails to connect (error)" and stop; don't troubleshoot.
- Rewriting project code, or project CLAUDE.md beyond trims the user approves.
