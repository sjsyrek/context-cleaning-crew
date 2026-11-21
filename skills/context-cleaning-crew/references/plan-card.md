# Plan card: content rules

The card's shape (card standard v1, rendered markdown, no code fence) is in `SKILL.md`, Phase 3. Use that one copy. These rules decide what goes in it.

- **One screen.** Group by category in this order: fix, cut, switch, move, ask, keep. One table per non-empty group, under the group's bold name.
- **Numbers are the manifest's findings, numbered 1..N continuously across groups.** Replies such as `go except 3` and `explain 4` resolve against the `#` column, so it is always a plain integer and never changes between the card and the report.
- **Every row cites evidence** (a number, path or rule from the manifest) and a default action. No claim without evidence.
- **Item is a short name** (`code-simplifier`, `"Release procedure" section`). A long path goes in Evidence. Never put a secret value in any cell: identify secrets by file, key and type.
- **Flags are words in the Action cell:** `(reversible)` or `(confirm)`. `(confirm)` items (secrets, deletion of user-written content, anything irreversible) need an explicit per-item yes even after `go`.
- **The advocate's keep argument** goes in a bullet below the table that holds the item: `- **Item 2, keep?** "<argument>" (advocate)`.
- **Steps only the user can take** (revoke a token, toggle a claude.ai connector) are ASK items.
- **The title names the mode:** `quick`, `full`, or `report mode: proposed, nothing applied` (report mode has no reply line).
