# Full mode: five seats and one debate round

Load this only in `full` mode. You coordinate. The seats review, and you synthesize. Seats are plain subagents defined in the plugin's `agents/`. **No agent teams are needed**, and none are created.

## 1. Dispatch (one message, five Agent calls)

Send all five Agent calls in a **single message** so they run in parallel:

| `subagent_type` | Seat |
|---|---|
| `context-cleaning-crew:context-economist` | always-on cost, conflicts, move candidates |
| `context-cleaning-crew:overlap-analyst` | duplicates and built-in or synced replacements |
| `context-cleaning-crew:security-reviewer` | secrets and permission posture |
| `context-cleaning-crew:memory-curator` | staleness, removed tools, drift, memory scope |
| `context-cleaning-crew:workflow-advocate` | what to keep |

- **Never pass `name`.** With agent teams enabled in settings, a `name` turns the spawn into a teammate. Unnamed spawns are subagents you can resume by the agent ID in the spawn result. Record the advocate's ID.
- Pass `model` from the `full_mode_models` option (`analytical`, default `sonnet`). Omit it when the option is `inherit`.
- Each prompt contains: the manifest path, the mode, the focus (if any), the `protected` and `preferred_marketplaces` values, and, for the overlap analyst only, the `anthropic-skills:*` names from your own available-skills list (seats can't see them). Don't paste the manifest itself, and never paste a secret.

Seats run in the background, and you're notified as each finishes. Don't poll, and don't start the synthesis until all five are back. If a seat fails or returns no JSON, re-spawn it once. If it fails again, cover that lens yourself from the quick-mode checklist and say so in the report.

## 2. Debate round (one round, advocate only)

Collect the other four seats' `cut`, `switch` and `move` findings. Resume the advocate with **SendMessage to its agent ID** (not a name), sending those findings as a compact JSON array (`id`, `target`, `category`, `evidence`, `default_action`). It answers with `keep_argument` and `breaks` per item it contests. Stop after one round: don't forward its answer to the other seats.

If SendMessage is unavailable (a headless run without it granted), skip the round, use the advocate's round-1 `keep` findings only, and note "debate round skipped" in the report.

## 3. Synthesis (you)

1. **Dedupe.** Two findings with the same `target` merge into one. Keep the more specific action, combine the evidence, and list both lenses.
2. **Resolve conflicts between seats.** When one seat says `cut` and the advocate has a `keep_argument` backed by usage numbers, the default becomes `keep` with a trim action (usage beats cost), and the cut stays visible as the alternative. When the advocate's argument has no numbers, keep the cut and show the argument under it. A security `ask` (secrets, posture) is never downgraded by a keep argument.
3. **`breaks`.** A non-empty `breaks` turns the item into `confirm: true` and adds the side effect to its line.
4. **Renumber** findings 1..N in plan-card order (fix, cut, switch, move, ask, keep). The report uses the same numbers.

Then continue with Phase 3 (the plan card) exactly as in quick mode. The card header says `full`, and each advocate argument appears as the `keep?` line under the item it defends.
