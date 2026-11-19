# Finding schema

One finding per item the user could act on. Keep `evidence` to numbers and paths from the manifest.

```json
{
  "id": 1,
  "lens": "context-economist | overlap-analyst | security-reviewer | memory-curator | workflow-advocate",
  "category": "cut | keep | switch | fix | move | ask",
  "target": "plugin code-simplifier@claude-plugins-official",
  "evidence": "always-on ~420 tok; 0 uses in 90 days; built-in /simplify covers it",
  "impact": {"tokens_per_session": 420, "risk": "none | low | medium | high"},
  "default_action": "uninstall the plugin",
  "reversible": true,
  "confirm": false,
  "keep_argument": ""
}
```

- `category`: **cut** removes; **keep** is an explicit decision not to act (record why); **switch** replaces with an alternative (name it); **fix** corrects something broken (dangling flag, removed tool, stale memory, conflicting instruction); **move** relocates content somewhere cheaper (procedural CLAUDE.md section → on-demand skill; project memory that reads as global → `~/.claude/CLAUDE.md` or a user skill); **ask** needs the user's judgment.
- `confirm: true` for secrets, deletion of user-written content (CLAUDE.md text, memory, skills), and anything with `reversible: false`.
- `keep_argument`: the workflow advocate's case for keeping it, or empty.
- Never put a secret value in any field.
