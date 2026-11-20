# Report template

Save to `<report_dir>/<yyyy-mm-dd>-<mode>.md`.

```markdown
# Context Cleaning Crew — <mode> — <yyyy-mm-dd>

Claude Code <version> · manifest `<yyyy-mm-dd>-manifest.json` · backup `<path or "none (report mode)">`

## Always-on context

| | Before | After |
|---|---|---|
| Plugins (claude plugin details) | ~N tok | ~N tok |
| Instruction files (bytes/4) | ~N tok | ~N tok |
| Memory indexes (bytes/4) | ~N tok | ~N tok |
| **Total** | **~N tok** | **~N tok** |

Context-injecting hooks: N (output not measured: the inventory never runs hooks; sizes, if any, come from reading the scripts).

## Changes made

| # | Target | Change | Verified |
|---|---|---|---|

## Kept or deferred

- <target> — <why: user kept it / advocate's argument / deferred until …>

## Needs you

- <steps only the user can take: revoke a token, toggle a claude.ai connector, sign out a session>

## Options

<only when `options.warnings` or `protected.unmatched` is non-empty: each ignored value and why, and protected entries that match nothing; omit otherwise>

## Since the last report

<new, resolved and unchanged findings vs. the previous manifest; omit on the first run>
```

In `report` mode, "After" is the projected value if every finding were applied, "Changes made" is empty, and every finding is listed under a "Proposed" heading instead.
