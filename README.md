# Context Cleaning Crew

A Claude Code plugin that audits your Claude Code setup and cleans it up with your approval, item by item.

It looks at settings and permissions, CLAUDE.md and AGENTS.md files (including parent directories), plugins and marketplaces, skills, hooks, MCP servers and auto-memory, and reports:

- **Context cost:** always-on tokens per plugin (from `claude plugin details`), instruction files and memory, against how often you use them.
- **Duplicates:** MCP servers configured twice, and plugins a built-in skill now covers (`/code-review`, `/simplify`, `/loop`, `/security-review`) or a synced claude.ai skill duplicates.
- **Staleness:** your own skills, agents and commands calling tools Claude Code removed (`TeamCreate`, broadcast `SendMessage`, …) — `claude plugin validate` doesn't catch these; plugins behind their marketplace or the CLI they wrap; broken memory links; memory that only loads in one directory but reads as global.
- **Conflicts:** instructions that contradict each other or a permission rule.
- **Permission posture:** a blanket `Bash` allow with `acceptEdits`/`bypassPermissions`, redundant rules, rules that match no tool; for the other projects you've used, the same as counts per settings file.
- **Secrets:** plaintext tokens, reported by file, key and type — never the value.

## Installation

```
/plugin marketplace add sjsyrek/claude-plugins
/plugin install context-cleaning-crew@sjsyrek
```

Or from a shell: `claude plugin install context-cleaning-crew --marketplace sjsyrek/claude-plugins`. Requires `python3` on `PATH` (see Requirements).

## Usage

```
/context-cleaning-crew:context-cleaning-crew [quick|full|report] [focus]
```

- `quick` (default): one reviewer, then a plan card; nothing changes until you approve each item. Run it interactively: headless runs can't edit settings files.
- `full`: five parallel, read-only reviewer subagents (context economist, overlap analyst, security reviewer, memory curator, workflow advocate), one debate round in which the advocate argues for keeping what you use, then the plan card. No agent teams needed. Grant `SendMessage` in headless runs, or the debate round is skipped.
- `report`: read-only; writes a dated report and exits. Safe to schedule: see `skills/context-cleaning-crew/references/routine-setup.md` for launchd/cron and the minimal headless allowlist.

After a Claude Code update, a SessionStart hook suggests a report run once. On every other start it prints nothing.

Reports go to `~/.local/state/context-cleaning-crew/reports/`; backups of anything changed go to `~/.claude/backups/context-cleaning-crew/`.

## Options

Set with `claude plugin configure context-cleaning-crew` (or `/plugin` → manage). Claude Code stores them under `pluginConfigs` in your user settings; the inventory reads them from there and records the effective values, and where each came from, in the manifest.

| Option | Default | What it does |
|---|---|---|
| `preferred_marketplaces` | none | Marketplaces in order of preference; when two plugins do the same job, keep the one from the earliest listed |
| `protected` | none | Plugins, MCP servers or memory files never proposed for removal |
| `backup_dir` | `~/.claude/backups/context-cleaning-crew/` | Backups before any change; keep it persistent |
| `report_dir` | `~/.local/state/context-cleaning-crew/reports/` | Manifests and reports |
| `usage_window_days` | `90` | Not used within this many days counts as unused |
| `mine_transcripts` | off | Count MCP tool calls per server from local transcripts (counts only) |
| `refresh_marketplaces` | on | Refresh marketplace clones in report mode too (quick and full always do) |
| `extra_secret_patterns` | none | Extra regexes for the secrets scan |
| `full_mode_models` | `sonnet` | Model for the five full-mode seats (`sonnet`, `opus`, `haiku`, `inherit`) |

## Requirements

- Claude Code 2.1.326 or later.
- Python 3.9+ (the stock macOS `python3` works). The scripts use only the standard library.
- `python3` must be on `PATH`: the skill and the SessionStart update hook call it by that name, not by an absolute path.
- No environment variables are required.

## Known limitations

- **Opaque secrets in MCP arguments.** Tokens in known formats (GitHub, Slack, AWS, `sk-`, …) are redacted everywhere, and URL credentials and query strings are always masked. An opaque value passed as a command-line argument (`--token abc123`) is not recognized; it can appear in the manifest's `mcp.duplicates` target when two servers share that command line. Add an `extra_secret_patterns` regex for such values.
- **Opaque secrets in the current project's permission rules.** Rule text is redaction-checked against the same patterns, so an opaque value inside an allow rule appears in the manifest verbatim. Other projects' settings report counts only, never rule text.
- **Auditing a copy of a home directory.** Absolute paths in the copy's `~/.claude.json` (`projects`) and plugin registry point at the live setup, so an audit of a backup also reads the live project settings and plugin files (read-only).
- **Hook output isn't measured.** The inventory lists hooks and never runs them; the reviewer reads the scripts.
- Manifests and reports stay on your machine. The scripts upload nothing; their only network use is the marketplace refresh (`claude plugin marketplace update`), which you can turn off with `refresh_marketplaces`. The review itself runs in your Claude Code session, like any other prompt.

## Development

```sh
python3 -m venv .venv && .venv/bin/pip install mypy ruff   # dev tools only
python3 -m unittest discover -s tests
.venv/bin/ruff check scripts tests && .venv/bin/mypy scripts tests
```

See `evals/README.md` for the `claude plugin eval` suite and `PLAN.md` for the design.

## License

MIT
