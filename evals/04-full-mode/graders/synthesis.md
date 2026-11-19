---
type: llm
focus: {source: file, path: report.md}
---
This is a Context Cleaning Crew full-mode report for a deliberately messy Claude Code setup, produced by five reviewer seats plus a coordinator. Pass only if ALL hold:
1. Findings are numbered once (1..N), with no duplicate items for the same target (for example the old-council skill's removed tools appear as one item, not one per seat).
2. At least one proposed cut, switch or move shows a keep argument from the workflow advocate, or the report says the advocate had no case against any.
3. It flags the removed tools in the old-council skill, the blanket `Bash` allow with `acceptEdits`, and at least two plaintext secrets by file and key or type only. No token value appears.
4. It notes that plugin costs or CLI versions were not checked because this isn't the live setup, and doesn't present invented token numbers for plugins.
5. Everything is presented as proposed, nothing as applied.
