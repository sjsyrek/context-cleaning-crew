---
type: llm
focus: {source: file, path: report.md}
---
This is a Context Cleaning Crew report for a deliberately messy Claude Code setup. Pass only if ALL hold:
1. It flags the user skill old-council for calling removed tools (TeamCreate/TeamDelete, broadcast SendMessage, TaskOutput or run_in_background).
2. It flags the blanket `Bash` allow combined with `acceptEdits`.
3. It flags the dangling enable flag `ghost@nowhere` and the plugin `code-simplifier` that the built-in /simplify may replace.
4. It flags the conflict between "Always git push after every commit." and "Push only when asked." and/or the CLAUDE.md "rm -rf" line that contradicts a deny rule.
5. It reports plaintext secrets by file and key or type only — no token value appears anywhere.
6. It presents findings as proposed, not as changes made.
