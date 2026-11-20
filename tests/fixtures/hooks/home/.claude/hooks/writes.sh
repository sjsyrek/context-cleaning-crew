#!/bin/sh
# Tries to write into the home; the dry-run sandbox must block it.
(echo leak > "$HOME/.claude/written-by-hook.txt") 2>/dev/null && echo wrote || echo blocked
