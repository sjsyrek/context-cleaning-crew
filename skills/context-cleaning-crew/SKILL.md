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
python3 "${CLAUDE_SKILL_DIR}/../../scripts/inventory.py" --cwd "$PWD" --mode <mode> --save
```

- `--mode` applies the mode's rules: `quick`/`full` refresh the marketplace clones (so version drift is real) and run tracker counts (e.g. `bd stats`); `report` refreshes only when the `refresh_marketplaces` option is on and never runs trackers.
- `--save` writes `<report_dir>/<yyyy-mm-dd>-manifest.json` (creating the directory) and prints the path. `<report_dir>` is the `report_dir` option. When the user names a report directory, use `--out <that dir>/<yyyy-mm-dd>-manifest.json` instead, and write the report there too. Never use a shell redirect or `mkdir`: headless runs allow only the two script commands.
- The inventory lists hooks and **never runs one**, so hook output is never measured. Say so in the report.
- **Options** are in the manifest: `options.values` (effective values), `options.sources`, `options.warnings` (values that were ignored; mention them in the report), and `protected` (what each `protected` entry matched, plus `unmatched` entries, likely typos). Don't ask the user for option values, and don't read settings files for them.
- **Another setup** (a backup, a copy, a fixture): when the user names one, pass `--home <its home>` and `--cwd <its working tree>` and `--mode report` (whatever mode was asked), and never apply anything: review as asked (`full` still dispatches the seats), then finish as in `report` mode. The `claude plugin`/`claude mcp` commands the executor uses always act on the live setup, so cleaning a different tree is out of scope. Say so in one line. Its manifest has `live_setup: false`, and plugin costs and CLI versions read "not checked: not the live setup" (those commands only describe the live install); say so in the report instead of estimating them.

Read the manifest. It never contains secret values (they appear as `<redacted:<type>>`) — **never print, log or pass a secret value**, even if you find one elsewhere. Identify secrets by file + key + type only.

## Phase 2 — Review

Produce findings in the schema in `references/finding-schema.md`. Work from the manifest; read files only to verify a specific claim (a memory fact, an instruction passage).

In `full` mode, follow `references/full-mode.md`: the five lenses below become five parallel read-only subagents plus one debate round with the workflow advocate, and you dedupe and resolve their findings. In `quick` and `report` mode you cover all five lenses yourself:

1. **Context economist** — always-on token cost (`plugins.installed[].cost`, instruction files, memory, context-injecting hooks: `hooks` with `injects_context: true`; read the hook script statically for output size and malformed JSON) against usage (`usage.skills`); reasoning-affecting env vars (`settings.reasoning_env`); instructions that fight Claude Code's own behavior; instruction conflicts (`instructions.deny_conflicts`, plus contradicting instructions you find by reading the files in `instructions.files`, across files and levels); `move` candidates (`instructions.move_candidates`, plus one-off task procedures under a task heading such as "When cutting a release" that you find while reading); a CLAUDE.md or AGENTS.md in a directory above several of the working trees in `projects` (such as `~/Code/CLAUDE.md`), which acts as a partly global file.
2. **Overlap analyst** — duplicate MCP servers (`mcp.duplicates`: each group's `members` and sources, including plugins' servers, and a `keeper` when the options decide one; `mcp.plugin_name_clashes`), plugins a built-in replaces (`overlap.builtin`; check the note for partial overlap), and **synced claude.ai skills**: compare the `anthropic-skills:*` entries in your own available-skills list with `plugins.installed` (e.g. `anthropic-skills:red-team` vs a `red-team` plugin). Plugins at several scopes are in `plugins.multi_scope` (`shares_user_settings` marks the scope-aliasing risk). For plugins installed from several marketplaces use `overlap.plugin_duplicates[].keeper` and its `rule`; when the rule is `undecided` (or for differently named plugins with the same job), decide by `protected`, then `options.values.preferred_marketplaces`, then capability, then usage.
3. **Security reviewer** — `secrets`, `permissions.findings` (blanket allow with a permissive mode, redundant rules, rules matching no tool), `permissions.other_projects` (the same counts for the other known projects' settings files, no rule text), deny-list gaps, deprecated MCP transports.
4. **Memory curator** — `memory.dirs` (broken links, oversized index; read the `user` and `feedback` memories for any that read as global but load only under their `project_dir`), `memory.duplicates` (one personal fact in several projects: one move), `memory.stray_dirs` (never loaded), `removed_tool_refs` (`claude plugin validate` does not catch these), `drift` (behind marketplace, differs from wrapped CLI), stale memory claims checked with cheap read-only commands, `leftovers` (an empty tracker directory that shadows the real one: remove it).
5. **Workflow advocate** — before finalizing, argue **for keeping** each proposed cut: heavy usage, a `protected` item (manifest `protected`; never propose removing one), a workflow the cut would break. Skills marked `unused` (outside `usage.window_days`) and `usage.mcp.unused_servers` are cut candidates, not cuts: say what the evidence covers (`usage.mcp` is `not mined` unless the `mine_transcripts` option is on). Attach the argument to the finding (`keep_argument`). Usage beats cost.

Counts: use the manifest's tracker `command` (it includes closed items); never re-count with the `avoid` command.

## Phase 3 — Plan card

Show the plan card from `references/plan-card.md` and **stop**. Accept `go`, `go except 3,7`, `keep 4`, `switch 5 to <alt>`, `explain 6`, `abort`. Items marked `confirm` (secrets, deletion of user-written content, anything irreversible) need an explicit per-item yes even after `go`.

In `report` mode, skip the approval and Phase 4: write the report with every finding as "proposed", then end with the same plan card in chat, headed `REPORT MODE — proposed, nothing applied`, without the reply line. Keep the numbers identical to the report's so the user can later say "apply 3 and 5" in quick mode. Then give the report path and stop.

## Phase 4 — Execute

Follow `references/executor-rules.md` exactly: back up first to a persistent directory, then apply in the fixed order, verifying each step.

## Phase 5 — Report

Write `<report_dir>/<yyyy-mm-dd>-<mode>.md` (the directory the manifest went to) from `references/report-template.md`, diffing against the previous manifest in `<report_dir>` (the newest older `*-manifest.json`, found with Glob) when one exists. Get the headline numbers from:

```sh
python3 "${CLAUDE_SKILL_DIR}/../../scripts/compare.py" <this manifest> [<previous manifest>]
```

Tell the user the report path and the before/after always-on estimate. In `report` mode, make the **last line** of your reply exactly that `compare.py` line, so a scheduled run's notifier can show it (see `references/routine-setup.md`).

## Out of scope

- Connectivity or authentication failures: report "server X fails to connect (error)" and stop; don't troubleshoot.
- Rewriting project code, or project CLAUDE.md beyond trims the user approves.
