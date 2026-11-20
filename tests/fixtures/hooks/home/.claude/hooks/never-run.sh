#!/bin/sh
# A PreToolUse hook: its output is not injected, so the dry run never runs it.
touch "$HOME/.claude/never-run-ran"
