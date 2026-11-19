# context-cleaning-crew: build plan

**Context Cleaning Crew** (slug `context-cleaning-crew`). A Claude Code plugin that audits a user's Claude Code setup (settings, CLAUDE.md and AGENTS.md files, plugins, skills, agents, hooks, MCP servers, memory) for context cost, redundancy, staleness, conflicts and security, then walks the user through an approved cleanup. It has a full multi-agent review mode, a quick single-agent mode, and a report-only mode for scheduled runs, and it suggests a report run after each Claude Code update.

This plan comes from a manual cleanup session (2026-11-16/17; backups in `~/.claude/backups/config-cleanup-2026-11-17`). The lessons from that session are in "Hard-won rules"; treat them as requirements.

## Goals

- Show what every session pays before the user types anything: always-on context, and how much of it is actually used.
- Find duplicates, dead config, stale memory, conflicting instructions, references to removed tools, version drift and plaintext secrets.
- Recommend; never act without per-item approval, except in an explicit report-only run, which changes nothing.
- Leave an auditable trail: a backup of everything touched, plus a short report of what changed and what's still open.

## Non-goals

- Troubleshooting connectivity or authentication. The audit flags MCP servers that fail to connect, but debugging them is a separate task. Say so and stop.
- Rewriting project code or project-level CLAUDE.md content beyond trimming that the user approves.
- Supporting other agent tools in v1. No adapter interface; instead the inventory is modular (one module per source: settings, instructions, plugins, MCP, memory, …) so another tool's sources can be added later without touching the rest.

## Modes

| Mode | Agents | Changes things? | Use |
|---|---|---|---|
| `full` | Inventory script + 5 parallel reviewer subagents (plugin `agents/`) + one debate round + the coordinating session | After per-item approval | A thorough audit a few times a year, or after big setup changes |
| `quick` | Inventory script + one reviewer (the invoking session) | After per-item approval | Check-in after a Claude Code update |
| `report` | Inventory script + one reviewer | **Never** | Scheduled runs; writes a dated report and exits |

Invocation sketch: `/context-cleaning-crew [full|quick|report] [focus]`, defaulting to `quick`. Trigger phrases: "audit my Claude Code setup", "clean up my config", "what's eating my context", "context cleanup".

## Version-change trigger

A plugin `SessionStart` hook (`scripts/update_check.py`) reads `~/.claude/.last-update-result.json` (`{"outcome": "success", "version_from": …, "version_to": …}`) and compares `version_to` with the last version it saw, kept in the plugin's data directory.

- When a successful update happened since the last seen version: print one line suggesting `/context-cleaning-crew report` (naming the from → to versions), then record the new version so it fires once per update.
- In every other case (no file, unreadable or malformed file, failed update, version already seen, first run): print **nothing** and exit 0. Hook output is injected context; the hook must cost zero tokens on an ordinary session start.
- Fast and side-effect free apart from the one state file; no network.

## Architecture

```
inventory (deterministic script) -> manifest.json -> review (seats or single reviewer) -> findings
  -> plan card (user decides per item) -> executor (backups, ordered changes, verification) -> report
```

### 1. Inventory script (deterministic, testable, no LLM)

Python 3 standard library only, compatible with the stock macOS Python (3.9). It reads only (apart from the opt-in marketplace refresh below), and emits `manifest.json`. One module per source:

- **Settings:** user `~/.claude/settings.json`, `settings.local.json`, project `.claude/settings*.json` for the current working tree, and managed or remote settings if present. Record:
  - env vars that affect reasoning (for example any `*DISABLE*THINKING*`), model, effort level, output style
  - permission allow/deny/ask lists and `defaultMode`, flagging entries for tools from plugins or servers that no longer exist
  - hooks per event, and the marketplace list
- **Permission posture:**
  - a blanket `Bash` (or `Bash(*)`) allow combined with `acceptEdits` or `bypassPermissions`
  - allow rules that do nothing because a broader rule already covers them (`Bash(git status:*)` under `Bash(git:*)`; anything under a blanket allow)
  - rules that match no tool: unknown built-in tool names, `mcp__<server>__…` for servers that aren't configured, plugin tools for plugins that aren't installed
- **Instruction files (CLAUDE.md and AGENTS.md):** every file in the load path — user scope, home directory, the working tree and **all its parent directories** — for both names (a built-in plugin loads AGENTS.md), with size in bytes and approximate tokens. Flag a CLAUDE.md in the home directory that acts as a de facto global file outside `~/.claude/`. Extract imperative lines (must/never/always/only, command names) so the review can flag instructions that contradict settings or each other — for example "use `rm -rf`" vs. a deny rule for it, or "always git push" vs. "push only when asked" — including across files at different levels.
- **Plugins:**
  - every installed plugin with scope(s), version, enabled flag and marketplace
  - always-on and on-invoke token cost per component from `claude plugin details <plugin>` ("Projected token cost", verified on 2.1.326), plus component inventory (skills, agents, hooks, MCP, LSP)
  - flag: installed but disabled; enabled flags with no install behind them (dangling); the same plugin installed at several scopes; two plugins that provide the same MCP server name
- **Version drift:**
  - plugin vs. marketplace: refresh marketplaces first (`claude plugin marketplace update`), then compare installed versions with the marketplace's; `claude plugin update` alone only checks the local clone and reports stale clones as current
  - plugin vs. the CLI it wraps: for plugins that wrap a CLI (for example the beads plugin and `bd --version`), compare the plugin's version with the CLI's
  - refreshing marketplaces writes to the local marketplace clones; it runs in quick and full mode, and in report mode only when the `refresh_marketplaces` option allows it (otherwise the report says the comparison used the cached clones)
- **Built-ins and synced skills:** the list of built-in skills and commands of the running Claude Code (`/code-review`, `/simplify`, `/loop`, `/security-review`, `/init`, `/schedule`, …), kept in a data file with the plugins each may replace, so the review can flag them. Skills synced from claude.ai (`anthropic-skills:*`) are not recorded in any local file; they appear only in the session's own skill list, so the reviewer compares that list with the manifest's plugins — for example the synced `anthropic-skills:red-team` next to the `red-team` plugin.
- **Removed-tool references:** scan the user's own skills, agents and commands (user and project scope, plus plugins the user authors) for tool names and parameters the changelog says were removed. Known cases, kept in a data file: `TeamCreate`, `TeamDelete`, `TaskOutput`, `Agent` `run_in_background`, `SendMessage` to `"*"`, and `TaskCreate`/`TodoWrite` on Opus 4.8+ unless `CLAUDE_CODE_ENABLE_TODO_TOOLS=1`. `claude plugin validate` passes plugins that use these, so validation is not enough.
- **Marketplaces:** configured marketplaces and how many installed plugins come from each. Flag those with zero, and local entries that override a managed entry for the same name.
- **MCP servers:**
  - user, project and plugin servers, plus account-level connectors if visible, grouped by URL or command so duplicates show up
  - transport, flagging deprecated ones such as SSE where the provider offers HTTP
  - connection status if obtainable (`claude mcp list`)
  - flag inline secrets in args or env
- **SessionStart / PreCompact / UserPromptSubmit hooks:** run each hook command in a sandboxed dry run only if the user opts in; otherwise record the command. Hook output is injected context, so its size matters. Flag hooks that print malformed JSON, which is silently ignored.
- **Usage signals:**
  - skill usage counts and last-used dates from `~/.claude.json` (`skillUsage`)
  - MCP tool usage is NOT reliably in `~/.claude.json`, so optionally mine `~/.claude/projects/*/*.jsonl` transcripts for `mcp__<server>__` tool calls over the last N days (opt-in; read-only; counts only, never content)
- **Counts that hide items:** when the inventory counts things through a tool, use the command that includes closed or inactive items (for example `bd stats`, not `bd list`, which hides closed issues), and record which command produced each count. A data file names the command to use and the one to avoid per tracker; the command runs only with `--run-trackers`, otherwise the manifest names it and leaves the count to the user.
- **Memory:** every auto-memory directory under `~/.claude/projects/*/memory/`, with file sizes, age, index line lengths and links to missing files. Also look for stray memory-like directories elsewhere (for example `<project>/.claude/memory/`) that are not loaded.
- **Memory scope:** auto-memory is per working directory. Record which directory each memory belongs to and flag memory the user evidently expects to apply everywhere (user-preference or feedback memories, "always"/"every project" wording, the same fact in several project memories) but that only loads under one directory; the fix is usually `~/.claude/CLAUDE.md` or a user skill.
- **Facts for staleness checks:** cheap, read-only, deterministic checks the memory curator would otherwise run itself — does a named git remote exist, is a named tool on `PATH` and at what version — recorded in the manifest so review seats need no shell.
- **Secrets scan:** patterns for common token formats (Slack `xox?-`, GitHub `gh?_`, AWS keys, OAuth client secrets, `sk-`) in config files only. Record file + key + token type, **never the value**.
- **Empty or leftover state:** for example an empty tracker directory that shadows a real one higher up the tree.

The manifest must be stable and diffable, so a scheduled run can compare against the last report.

### 2. Review

The seats read the manifest, not the filesystem, except where verification needs a targeted read (memory claims, instruction-file passages). Each finding has: `id`, `seat`, `category` (cut | keep | switch | fix | move | ask), `target`, `evidence` (numbers from the manifest), `impact` (tokens per session, risk), `default_action`, `reversible` (bool).

`move` means: content that belongs somewhere cheaper, mainly procedural CLAUDE.md content (step-by-step workflows, checklists for one task) that should become an on-demand skill, so it costs context only when used.

Full-mode seats are plain parallel subagents defined in the plugin's `agents/` directory — no agent teams, and no `CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS` requirement. Each agent definition sets `omitClaudeMd: true` (so the seat audits CLAUDE.md as data rather than following it), read-only tools (`Read`, `Grep`, `Glob`), and its own model and effort (defaults from the `full_mode_models` option). The coordinating session synthesizes.

| Seat | Owns |
|---|---|
| Context economist | Always-on cost vs. usage; reasoning-affecting settings; injected instructions that conflict with Claude Code's own behavior (a hook banning the built-in task list or memory, for example); instruction-file conflicts (with settings and with each other, across directory levels); `move` candidates |
| Overlap analyst | Duplicate plugins, connectors and MCP servers; **plugins replaced by built-in skills** (`/code-review`, `/simplify`, `/loop`, `/security-review`, …) and by synced claude.ai skills; picks a keeper using the preferred-marketplace setting, then capability |
| Security reviewer | Plaintext secrets, inline credentials, deny-list gaps, unused high-privilege servers; permission posture (blanket allows with permissive modes, redundant and dead rules) |
| Memory curator | Staleness: checks concrete claims (remotes exist, versions, tools installed, open tasks) against the manifest's facts; references to removed tools; plugin version drift; memory scope; proposes rewrites that keep decisions and drop narrative history |
| Workflow advocate | Argues to **keep** heavily used or user-protected items even when costly; flags proposed cuts that would break a workflow. Exists so the panel doesn't optimize only for cutting. |

**One debate round.** After all five seats return, the coordinator resumes the Workflow advocate with `SendMessage`, sending it the other seats' proposed cuts, removals and moves; the advocate answers with keep arguments per item, which appear on the plan card. Seats are spawned without a `name` and resumed by the agent ID from the spawn result: with agent teams enabled in settings, a `name` turns a spawn into a teammate. `SendMessage` must be available (and granted in headless runs).

Quick and report modes: one reviewer covers all five lenses in one pass, with a short checklist per lens.

### 3. Plan card

One screen, grouped by category, each line: target, the one-line reason with its number, the default action, reversible yes/no, and the advocate's keep argument where there is one. Replies: `go`, `go except 3,7`, `keep 4`, `switch 5 to <alt>`, `explain 6`, `abort`. Items touching secrets, deletions of user-written content, or anything irreversible need explicit per-item confirmation even when `go` is given.

### 4. Executor

Ordered so partial failure is safe: backups → settings edits → plugin uninstalls → marketplace removals → MCP changes → instruction-file edits and skill extraction (`move`) → memory rewrites → verification. After each step, re-read the file or re-run the inventory slice and confirm the change landed.

### 5. Report

Markdown at `<report_dir>/<yyyy-mm-dd>-<mode>.md`:
- before/after always-on token estimate
- table of changes made
- items deferred or kept, and why
- items needing the user (connector toggles in a web UI, signing out of a leaked session, and so on)
- a diff against the previous report when one exists

## Configuration

Plugin options via `userConfig` in `plugin.json` (the current mechanism, verified on 2.1.326; set with `claude plugin configure`). No fallback config file.

| Option | Default | Purpose |
|---|---|---|
| `preferred_marketplaces` | `[]` | Ordered list; when two plugins overlap, prefer one from these. Lets an organization default to its internal marketplace. |
| `protected` | `[]` | Plugins, servers or memory files never proposed for removal |
| `backup_dir` | `~/.claude/backups/context-cleaning-crew/` | Persistent, never a temp or scratch directory |
| `report_dir` | `~/.claude/context-cleaning-crew/reports/` | Where reports land |
| `usage_window_days` | `90` | "Unused" threshold |
| `mine_transcripts` | `false` | Opt-in for MCP usage from transcripts |
| `refresh_marketplaces` | `true` | Refresh marketplace clones before version-drift checks (report mode included) |
| `extra_secret_patterns` | `[]` | Additional regexes |
| `full_mode_models` | `{analytical: sonnet, synthesis: inherit}` | Seat models |

No organization names, hostnames or marketplace URLs are hardcoded anywhere in the plugin.

## Scheduled routine (report mode)

- Cloud-scheduled agents cannot read a laptop's `~/.claude`, so the routine must run locally. Ship a documented example of headless invocation, for example `claude -p "/context-cleaning-crew report"`, wired to `launchd` (macOS) or `cron`/systemd timers (Linux), weekly or monthly. The SessionStart update hook covers the common case without a schedule.
- Report mode is strictly read-only and safe to run unattended. It writes the report and optionally a one-line summary (biggest finding, token delta since the last run) to stdout for notification hooks.
- Confirm how a headless run grants the needed read-only permissions without interactive prompts, and document the minimal allowlist.

## Hard-won rules (from the manual run)

1. **Back up to a persistent location before the first change.** A scratch directory was wiped between sessions and the backups were lost.
2. **Scope aliasing:** when the working directory is the home directory, `~/.claude/settings.json` is both user settings and "project" settings. Uninstalling a project-scope copy can delete the shared `enabledPlugins` flag for the user-scope copy. Snapshot `enabledPlugins` before uninstalling, then restore only the intended entries.
3. **Uninstalling deletes the enable flag.** Expected for removals, a surprise for duplicates; see rule 2.
4. **"Keep" a disabled plugin usually means enable it.** Ask when ambiguous.
5. **Usage beats cost.** A costly hook or plugin the user runs daily is a keep; propose trimming its side effects instead (in the manual run, that meant updating a stale plugin and deleting an empty directory that shadowed the real tracker).
6. **Verify memory before rewriting it.** Memories are point-in-time; several "facts" were stale (remotes now existed, tools now installed). Check cheaply, then write current facts with absolute dates.
7. **Never echo secret values** in output, reports, logs or tool arguments. Identify by file + key + type.
8. **Ask before deleting a credentials file,** even an unused one, and tell the user the step only they can do: revoke or sign out to invalidate the leaked token.
9. **After swapping an MCP provider, verify it connects and authenticates, and re-check tool names.** A plugin's server can be routed through an account-level connector, which changes tool name prefixes; permission allowlists keyed on the old names silently stop matching. Disabling that connector can break the plugin.
10. **Connectivity failures are out of scope.** Report "server X fails to connect (error)" and stop. The manual run lost a long detour to a DNS problem.
11. **Dangling enable flags** (enabled, nothing installed) and plugins removed from their marketplace are common; report both.
12. **Prefer the documented CLI** (`claude plugin …`, `claude mcp …`) over editing JSON by hand. When JSON must be edited, parse and re-serialize, validate, and diff against the backup.
13. **Refresh before comparing versions.** `claude plugin update` only checks the local marketplace clone; refresh the marketplaces first.
14. **Count with the tool that shows everything.** `bd list` hid closed issues; `bd stats` didn't.
15. **Validation is not compatibility.** `claude plugin validate` passed plugins that called removed tools (`TeamCreate`, broadcast `SendMessage`).

## Deliverables

```
context-cleaning-crew/
  .claude-plugin/plugin.json        # name, version, userConfig options
  commands/context-cleaning-crew.md
  hooks/hooks.json                  # SessionStart -> scripts/update_check.py
  agents/{context-economist,overlap-analyst,security-reviewer,memory-curator,workflow-advocate}.md
  skills/context-cleaning-crew/
    SKILL.md                        # triggers, modes, protocol, plan-card format
    references/
      finding-schema.md
      plan-card.md
      executor-rules.md             # the hard-won rules, operationalized
      report-template.md
      routine-setup.md              # launchd / cron examples
  scripts/
    inventory/                      # package: one module per source, plus __main__
    update_check.py                 # SessionStart hook
    ccc_inventory/data/             # removed tools, built-in tools and skills, CLI wrappers, trackers
  tests/
    fixtures/                       # synthetic ~/.claude trees (see Testing)
    test_*.py                       # unittest, stdlib only
  evals/                            # claude plugin eval suite, modeled on the team plugins'
  README.md
  CHANGELOG.md
```

## Build order

1. **Inventory script + fixtures + tests** (TDD). Done when it produces a stable manifest for each fixture and redacts every planted secret.
2. **SessionStart update hook + tests**, including the zero-output cases.
3. **Quick mode** end to end on a fixture: manifest → findings → plan card → executor (against a temp copy) → report.
4. **Report mode** + routine docs; verify the headless run changes nothing (hash the config tree before and after).
5. **Full mode:** seat agents in `agents/` and parallel dispatch, reusing the finding schema; one debate round with the Workflow advocate; the coordinating session dedupes and resolves seat conflicts, with the advocate's keep arguments shown on the card.
6. **Options + preferred-marketplace logic.**
7. **`evals/` suite** modeled on the team plugins' (Tier 1: trigger, plan card, should-not-fire, report mode changes nothing; Tier 2: a full-mode run on a fixture home), once there is a skill to test.
8. **Dogfood on a real setup in report mode first,** then quick mode with approvals. Compare against the 2026-11-16/17 manual cleanup (`~/.claude/backups/config-cleanup-2026-11-17`): the audit of the pre-cleanup state should find what the manual run found.
9. **Register in the `claude-plugins` marketplace** only after the user approves.

## Testing

Synthetic `~/.claude` fixtures covering:
- the scope-aliasing case (rule 2)
- a duplicate MCP server across three sources
- a dangling enable flag
- planted fake secrets
- a stale memory whose claim a test command can disprove
- an oversized SessionStart hook, and one with malformed JSON
- an empty directory shadowing a real tracker
- an unused marketplace
- a plugin behind its marketplace, and one behind the CLI it wraps
- a plugin duplicated by a built-in skill and by a synced claude.ai skill
- a user skill calling `TeamCreate` and `SendMessage` to `"*"`
- CLAUDE.md and AGENTS.md at several directory levels with contradicting instructions, and an instruction contradicting a deny rule
- a blanket Bash allow with `acceptEdits`, a redundant allow rule, and a rule matching no tool
- a procedural CLAUDE.md section (a `move` candidate)
- a feedback memory under one project directory that reads as global
- `.last-update-result.json`: missing, malformed, failed update, already-seen version, new version

The executor runs against a copy of the fixture, and tests assert the resulting tree. Non-negotiable tests: report mode leaves the fixture byte-identical, and the update hook prints nothing except after a new successful update.

## Open questions

- Whether to estimate tokens for CLAUDE.md and memory with a tokenizer or a bytes/4 heuristic (the heuristic is probably fine; label it).
- How much of account-level connector state is visible from the CLI, versus only in the web UI.
- Where the built-in skill list comes from at runtime (a maintained data file vs. something the CLI exposes); start with a data file versioned with the plugin.

Resolved: name (Context Cleaning Crew); full mode uses plain parallel subagents with one debate round, not agent teams.
