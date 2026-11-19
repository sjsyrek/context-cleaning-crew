# Changelog

All notable changes to this project are documented here. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/), and the project uses [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added

- **Build plan** (`PLAN.md`): modes, inventory sources, review seats, plan card, executor order, configuration and the rules learned from a manual cleanup.
- **Inventory script** (`scripts/inventory.py`, Python 3.9+ standard library only): prints a stable, sorted JSON manifest with paths relative to `~`. This first slice covers settings files and reasoning-affecting env vars; permission posture (blanket `Bash` allow with `acceptEdits`/`bypassPermissions`, allow rules covered by a broader rule, rules that match no tool, MCP server or installed plugin); dangling and disabled plugin flags; CLAUDE.md and AGENTS.md files from `~/.claude` down through every parent of the working tree, with directives, instructions that contradict a deny rule, and procedural sections to move into a skill; references to removed tools in the user's own skills, agents and commands; memory directories with broken index links and memory that reads as global; and a plaintext-secret scan that reports file, key and token type, never the value.
- **SessionStart update hook** (`hooks/hooks.json`, `scripts/update_check.py`): after a successful Claude Code update it prints one line suggesting `/context-cleaning-crew report`, once per new version, keeping the last seen version in `${CLAUDE_PLUGIN_DATA}`. On every other start (no update file, malformed file, failed update, version already seen, first run, unwritable state) it prints nothing and exits 0, so it costs no context.
- **Plugin manifest** (`.claude-plugin/plugin.json`).
- **Tests** (`tests/`, `unittest`) against a synthetic `messy` home fixture, plus `pyproject.toml` for the ruff and mypy dev checks.

### Fixed

- **No secret value reaches the manifest through free text.** Permission rule text, instruction-file lines, section headings and reasoning env values are now redacted (`<redacted:<type>>`), and the secrets scan also covers permission rules and every CLAUDE.md/AGENTS.md line. Extra patterns from `--secret-pattern` apply to both. Found by an automated security review of the first slice.
