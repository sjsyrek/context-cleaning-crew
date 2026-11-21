# Scheduled report runs

Report mode is read-only, so it can run unattended. Cloud-scheduled agents can't read this machine's `~/.claude`, so the routine runs **locally** under `launchd` (macOS) or `cron` / a systemd timer (Linux). The plugin's SessionStart hook already suggests a report after each Claude Code update, so a schedule is optional: weekly or monthly is plenty.

## The command

```sh
claude -p "/context-cleaning-crew:context-cleaning-crew report" \
  --permission-mode dontAsk \
  --allowedTools 'Bash(python3 *context-cleaning-crew/*scripts/inventory.py*)' \
                 'Bash(python3 *context-cleaning-crew/*scripts/compare.py*)' \
                 Read Glob Grep \
                 'Edit(~/.local/state/context-cleaning-crew/reports/**)' \
  --max-budget-usd 1 \
  --output-format json
```

- **`--permission-mode dontAsk`** denies everything that isn't on the allowlist instead of waiting for a prompt nobody will answer. A denied call shows up in the JSON output's `permission_denials`, and the run says what it couldn't do instead of guessing.
- **The allowlist is the minimum report mode needs:** the two read-only scripts, file reads, and writes under the report directory only (`Edit(...)` rules cover the Write tool too). Nothing else is allowed: no `claude plugin`, no `claude mcp`, no network.
- The script patterns end in `*` rather than `* *` because the skill quotes the script path (`python3 ".../inventory.py" --cwd …`). A pattern like `inventory.py *` would never match.
- Run it from the directory whose project setup you want audited; `$HOME` is used for the user scope.
- The `Edit(...)` rule names the default `report_dir`. If you set the `report_dir` option elsewhere, change the rule to match, or the report write is denied. Keep it outside `~/.claude`: a headless run can't write there with the Write tool whatever the allow rules say, so a report there would never be saved.
- Report mode refreshes marketplace clones only when the `refresh_marketplaces` option is on. Otherwise the report says version drift was checked against the cached clones.

The run writes `<yyyy-mm-dd>-manifest.json` and `<yyyy-mm-dd>-report.md` to the report directory. The **last line** of the reply is a one-line summary for notifications, for example:

```
always-on ~857 tokens (-120 since last run); 1 plaintext secret; 2 permission findings
```

With `--output-format json`, that's the last line of the `result` field.

## macOS: launchd

Save as `~/Library/LaunchAgents/com.example.context-cleaning-crew.plist`, adjust the paths, then `launchctl load` it. This one runs on Mondays at 09:00:

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>Label</key><string>com.example.context-cleaning-crew</string>
  <key>WorkingDirectory</key><string>/Users/YOU</string>
  <key>ProgramArguments</key>
  <array>
    <string>/bin/zsh</string><string>-lc</string>
    <string>claude -p "/context-cleaning-crew:context-cleaning-crew report" --permission-mode dontAsk --allowedTools 'Bash(python3 *context-cleaning-crew/*scripts/inventory.py*)' 'Bash(python3 *context-cleaning-crew/*scripts/compare.py*)' Read Glob Grep 'Edit(~/.local/state/context-cleaning-crew/reports/**)' --max-budget-usd 1 --output-format json &gt; ~/.local/state/context-cleaning-crew/last-run.json</string>
  </array>
  <key>StartCalendarInterval</key>
  <dict><key>Weekday</key><integer>1</integer><key>Hour</key><integer>9</integer><key>Minute</key><integer>0</integer></dict>
</dict>
</plist>
```

`zsh -lc` gives the job your login `PATH`, so `claude` and `python3` resolve. A missed run (laptop asleep) fires at the next wake.

## Linux: cron

```cron
0 9 * * 1  cd "$HOME" && claude -p "/context-cleaning-crew:context-cleaning-crew report" --permission-mode dontAsk --allowedTools 'Bash(python3 *context-cleaning-crew/*scripts/inventory.py*)' 'Bash(python3 *context-cleaning-crew/*scripts/compare.py*)' Read Glob Grep 'Edit(~/.local/state/context-cleaning-crew/reports/**)' --max-budget-usd 1 --output-format json > "$HOME/.local/state/context-cleaning-crew/last-run.json" 2>&1
```

cron's `PATH` is minimal: put the full path to `claude` in the line, or set `PATH=` at the top of the crontab. A systemd user timer (`OnCalendar=Mon 09:00`, `Persistent=true`) also catches up on runs missed while the machine was off.

## Checking a run

- `permission_denials` in the JSON should be empty. If it isn't, the run stopped short, and the denied commands show what to allow.
- The manifest and report should be the only new files. To check that for yourself, hash `~/.claude` before and after a run and compare (report mode changes nothing outside the report directory).
- Each run costs roughly $0.20–0.50 of API usage. `--max-budget-usd` caps it.
