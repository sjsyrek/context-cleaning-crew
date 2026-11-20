#!/bin/sh
# Prints JSON with a trailing comma, which Claude Code silently ignores.
printf  '{"hookSpecificOutput": {"additionalContext": "hi",}}'
