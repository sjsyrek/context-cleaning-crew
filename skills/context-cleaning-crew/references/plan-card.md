# Plan card

One screen. Group by category in this order: fix, cut, switch, move, ask, keep. One line per finding:

```
CONTEXT CLEANING CREW — quick — always-on now ~14.2k tok, after plan ~9.8k tok (bytes/4 + plugin details)

FIX
 1. ~/.claude/skills/old-council/SKILL.md — calls TeamCreate, TeamDelete (removed) → rewrite for the implicit team   [reversible]
CUT
 2. code-simplifier@claude-plugins-official — ~420 tok, 0 uses/90d, built-in /simplify → uninstall   [reversible]
      keep? "used by the weekly refactor routine" (advocate)
MOVE
 3. ~/Code/proj/CLAUDE.md "Release procedure" — 6 steps, ~180 tok every session → user skill `release`   [reversible] [confirm]
ASK
 4. ~/.claude/settings.json env.GITHUB_TOKEN — plaintext github-token → move to the keychain/env; revoke the old token   [confirm]

Reply: go | go except 3 | keep 2 | switch 2 to <alt> | explain 4 | abort
```

- Every line has a number from the manifest; no claim without evidence.
- `[confirm]` items need an explicit per-item yes even after `go`.
- Show the advocate's keep argument under the item it defends.
- Name steps only the user can take (revoke a token, toggle a claude.ai connector) as ASK items.
