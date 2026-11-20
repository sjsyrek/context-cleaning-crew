# Executor rules

Apply only approved items. These rules come from a manual cleanup where each one was learned the hard way.

## Order (partial failure stays safe)

1. **Back up** every file you will touch to `<backup_dir>/<yyyy-mm-dd-hhmm>/`, mirroring paths under `~`. `<backup_dir>` is the manifest's `options.values.backup_dir` (default `~/.claude/backups/context-cleaning-crew/`) — persistent, never a temp or scratch directory (a wiped scratch directory once lost the only backup). Use the helper, which refuses a temporary directory, never overwrites a backup, and snapshots `enabledPlugins` from every settings file it copies:

   ```sh
   python3 "${CLAUDE_SKILL_DIR}/../../scripts/executor.py" backup --backup-dir <backup_dir> <every file you will touch, including each settings file>
   ```

   It prints the backup directory and the snapshot path. If it refuses, stop and tell the user why.
2. Settings edits (permissions, env, hooks).
3. Plugin uninstalls (`claude plugin uninstall`), then restore any `enabledPlugins` entry the uninstall removed but the plan keeps (see scope aliasing), from the snapshot:

   ```sh
   python3 "${CLAUDE_SKILL_DIR}/../../scripts/executor.py" restore-flags --settings <settings file> --snapshot <snapshot> --keep <plugin ids the plan keeps>
   ```

   It touches no other entry and leaves the file alone when nothing is missing.
4. Marketplace removals (`claude plugin marketplace remove`).
5. MCP changes (`claude mcp remove/add`).
6. Instruction-file edits and `move` extractions (write the new skill first, then trim the source).
7. Memory rewrites.
8. **Verify**: rerun the inventory and confirm each approved change landed and nothing else changed.

## Rules

- **Never touch a protected item** (manifest `protected`), even under `go`; if a plan line targets one, skip it and say why.
- **Prefer the CLI** (`claude plugin …`, `claude mcp …`) over editing JSON. When JSON must be edited, parse and re-serialize, validate, and diff against the backup.
- **Scope aliasing:** when the manifest's `settings.scope_aliasing.aliased` is true, or a `plugins.multi_scope` entry has `shares_user_settings` (a project install for the home directory), `~/.claude/settings.json` is both user and project settings. Uninstalling a project-scope copy can delete the user-scope copy's enable flag. Compare `enabledPlugins` with the snapshot after every uninstall and restore only the intended entries.
- **Uninstalling deletes the enable flag** — expected for removals, a surprise for duplicates.
- **"Keep" a disabled plugin usually means enable it.** Ask when ambiguous.
- **Verify memory before rewriting it.** Check each concrete claim cheaply (does the remote exist, is the tool installed, at what version); write current facts with absolute dates; keep decisions, drop narrative.
- **Never echo secret values** in output, reports, logs or tool arguments.
- **Ask before deleting a credentials file,** even an unused one, and tell the user what only they can do: revoke the token or sign out.
- **After swapping an MCP provider,** verify it connects and authenticates and re-check tool names; permission rules keyed on old names silently stop matching.
- **Connectivity failures are out of scope.** Report and move on.
- **Refresh before comparing versions** (the inventory's `--mode quick|full`, or `--refresh-marketplaces`); `claude plugin update` alone only checks the local clone.
- **Validation is not compatibility.** `claude plugin validate` passes plugins that call removed tools.
- Stop at the first failed step, report what was applied and what wasn't, and point to the backup.
