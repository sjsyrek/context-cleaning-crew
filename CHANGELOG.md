# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **`context-cleaning-crew` skill, quick and report modes.** Runs the inventory, reviews the manifest through five lenses (context economist, overlap analyst, security reviewer, memory curator, workflow advocate), shows a numbered plan card grouped by category and applies only approved items in a fixed, backed-up order (`references/executor-rules.md`), then writes a dated report. Report mode changes nothing and ends with the same numbered card marked "proposed". Auditing a setup other than the live one (a backup, a copy) always runs read-only.
- **Eval suite** (`evals/`) for `claude plugin eval`: report mode on a copied fixture home (finds the planted problems, no secret value in the output, no uninstall commands, audited tree unchanged by checksum), quick mode via a trigger phrase stopping at the plan card, and a should-not-fire case.
- **README** and MIT license.
- **Build plan** (`PLAN.md`): modes, inventory sources, review seats, plan card, executor order, configuration and the rules learned from a manual cleanup.
- **Inventory script** (`scripts/inventory.py`, Python 3.9+ standard library only): prints a stable, sorted JSON manifest with paths relative to `~`. This first slice covers settings files and reasoning-affecting env vars; permission posture (blanket `Bash` allow with `acceptEdits`/`bypassPermissions`, allow rules covered by a broader rule, rules that match no tool, MCP server or installed plugin); dangling and disabled plugin flags; CLAUDE.md and AGENTS.md files from `~/.claude` down through every parent of the working tree, with directives, instructions that contradict a deny rule, and procedural sections to move into a skill; references to removed tools in the user's own skills, agents and commands; memory directories with broken index links and memory that reads as global; and a plaintext-secret scan that reports file, key and token type, never the value.
- **Version drift, overlap and counts in the manifest.** Installed plugins are compared with their marketplace's version (`behind` / `ahead` / `current`, or `unknown` for remote sources), optionally after `claude plugin marketplace update` (`--refresh-marketplaces`); plugins that wrap a CLI are compared with its version (`bd --version` for beads); marketplaces with no installed plugins are flagged; plugins a built-in skill may replace (`/simplify`, `/code-review`, `/security-review`, `/loop`) are listed as candidates; and tracker counts name the command that includes closed items (`bd stats`, not `bd list`), running it only with `--run-trackers`.
- **Token cost, hooks, skill usage and MCP grouping in the manifest.** Each installed plugin's always-on and per-component on-invoke cost is parsed from `claude plugin details`; hooks are listed per event with the ones whose output is injected into context (`SessionStart`, `UserPromptSubmit`, `PreCompact`, `PostCompact`) marked; skill usage counts and last-used dates come from `~/.claude.json`; MCP servers with the same URL or command are grouped as duplicates and SSE transports are flagged. The marketplace refresh now runs before anything reads plugin state.
- **SessionStart update hook** (`hooks/hooks.json`, `scripts/update_check.py`): after a successful Claude Code update it prints one line suggesting `/context-cleaning-crew report`, once per new version, keeping the last seen version in `${CLAUDE_PLUGIN_DATA}`. On every other start (no update file, malformed file, failed update, version already seen, first run, unwritable state) it prints nothing and exits 0, so it costs no context.
- **Plugin manifest** (`.claude-plugin/plugin.json`).
- **Tests** (`tests/`, `unittest`) against a synthetic `messy` home fixture, plus `pyproject.toml` for the ruff and mypy dev checks.

### Fixed

- **Absolute home paths no longer appear in free-text fields** such as hook commands; they are written as `~`, like every other path in the manifest. Found by a smoke run against a real setup.
- **No secret value reaches the manifest through free text.** Permission rule text, instruction-file lines, section headings and reasoning env values are now redacted (`<redacted:<type>>`), and the secrets scan also covers permission rules and every CLAUDE.md/AGENTS.md line. Extra patterns from `--secret-pattern` apply to both. Found by an automated security review of the first slice.
