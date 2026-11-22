---
type: llm
---
standard: v1 (card standard, claude-plugins/docs/card-standard.md, Grader section; layout only, the content graders check what the card says)

The final message's plan card follows the card standard v1. Pass only if ALL hold:
1. The card is not inside a code fence.
2. The card begins with a bold title line naming the plugin (Context Cleaning Crew), then an em dash and the mode or scope. A short lead-in sentence before the card is fine; judge the card itself.
3. Single values are a bulleted list with bold labels.
4. Seats or findings, if listed, are a markdown table with a header row, one table per category, with each finding keeping its number.
5. It contains no hand-drawn box characters and no `=====` underline.
6. Either its last line starts with `Reply:` and lists the plugin's verbs, each in backticks, separated by `|`; or, because the audited setup is a copy, the card is titled as report mode (proposed, nothing applied) and has no reply line.
