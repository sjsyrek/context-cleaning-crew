# context-cleaning-crew eval suite

Regression tests for the skill, run with Claude Code's `claude plugin eval` (2.1.326+). Each case runs a fresh headless Claude in a sandbox. Every case's `scaffold.sh` copies the repo's synthetic `tests/fixtures/messy/home` into the workspace as `./audit-home` and records a checksum of it, so the skill audits a known-bad setup instead of the sandbox's own.

| Case | Tier | Checks |
|---|---|---|
| `01-report-read-only` | 1 | Report mode on `./audit-home`: finds the removed tools, the blanket Bash allow with `acceptEdits`, the dangling flag, the built-in overlap and an instruction conflict; reports secrets without values; runs no uninstall/MCP commands; the audited tree's checksums still match afterwards. |
| `02-quick-plan-card` | 1 | A trigger phrase runs the audit and stops at a numbered, grouped plan card (or the read-only summary, since `./audit-home` isn't the live setup); edits nothing. |
| `03-neg-unrelated` | 1 | Should **not** fire on a factual question about a file. |
| `04-full-mode` | 2 | Full mode on `./audit-home`: five seat subagents dispatched without `name` and with the `full_mode_models` option as `model`, one `SendMessage` debate round, no team-tool lookups, a deduped numbered report with keep arguments, no plugin costs invented for a non-live setup, nothing changed. |

## Running

One case per invocation:

```sh
claude plugin eval . --case 01-report-read-only --runs 1 --ablation none \
  --scaffold --trust-plugin --allow-tools Bash Write --no-publish --max-cost-usd 1.5

claude plugin eval . --case 02-quick-plan-card --runs 1 --ablation none \
  --scaffold --trust-plugin --allow-tools Bash Write --no-publish --max-cost-usd 1.5

claude plugin eval . --case 04-full-mode --runs 1 --ablation none \
  --scaffold --trust-plugin --allow-tools Bash Write Agent SendMessage --no-publish --max-cost-usd 3

claude plugin eval . --case 03-neg-unrelated --runs 1 --ablation with-without \
  --scaffold --trust-plugin --no-publish --max-cost-usd 0.5
```

Results land in `evals/results/` (gitignored).

## Gotchas

Same as the team plugins' suites: `--scaffold` runs the case's bash as you; one `--case` per invocation; write flags out literally in zsh; `case.yaml` can only set `EVAL_*` env vars; grader regexes are JavaScript; a gated tool must be in both `allowed_tools` and `--allow-tools`. On Pro/Max, `costUsd` is notional but counts against plan limits.
