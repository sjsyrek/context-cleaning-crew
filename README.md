# Context Cleaning Crew

A Claude Code plugin that audits your Claude Code setup and cleans it up with your approval, item by item.

It looks at settings and permissions, CLAUDE.md and AGENTS.md files (including parent directories), plugins and marketplaces, skills, hooks, MCP servers and auto-memory, and reports:

- **Context cost:** always-on tokens per plugin (from `claude plugin details`), instruction files and memory, against how often you use them.
- **Duplicates:** MCP servers configured twice, and plugins a built-in skill now covers (`/code-review`, `/simplify`, `/loop`, `/security-review`) or a synced claude.ai skill duplicates.
- **Staleness:** your own skills, agents and commands calling tools Claude Code removed (`TeamCreate`, broadcast `SendMessage`, …) — `claude plugin validate` doesn't catch these; plugins behind their marketplace or the CLI they wrap; broken memory links; memory that only loads in one directory but reads as global.
- **Conflicts:** instructions that contradict each other or a permission rule.
- **Permission posture:** a blanket `Bash` allow with `acceptEdits`/`bypassPermissions`, redundant rules, rules that match no tool.
- **Secrets:** plaintext tokens, reported by file, key and type — never the value.

## Usage

```
/context-cleaning-crew:context-cleaning-crew [quick|full|report] [focus]
```

- `quick` (default): one reviewer, then a plan card; nothing changes until you approve each item.
- `full`: five parallel reviewer subagents and one debate round, then the plan card.
- `report`: read-only; writes a dated report and exits. Safe to schedule.

After a Claude Code update, a SessionStart hook suggests a report run once. On every other start it prints nothing.

Reports go to `~/.claude/context-cleaning-crew/reports/`; backups of anything changed go to `~/.claude/backups/context-cleaning-crew/`.

## Requirements

- Claude Code 2.1.326 or later.
- Python 3.9+ (the stock macOS `python3` works). The scripts use only the standard library.
- No environment variables are required.

## Development

```sh
python3 -m venv .venv && .venv/bin/pip install mypy ruff   # dev tools only
python3 -m unittest discover -s tests
.venv/bin/ruff check scripts tests && .venv/bin/mypy scripts tests
```

See `evals/README.md` for the `claude plugin eval` suite and `PLAN.md` for the design.

## License

MIT
