---
name: old-council
description: Convene a small council.
---

1. Create the team with TeamCreate(team_name: "council").
2. Spawn each seat with Agent(name: "seat", run_in_background: true).
3. Announce with SendMessage(to: "*", message: "go").
4. Read results with TaskOutput.
5. Delete the team with TeamDelete.
