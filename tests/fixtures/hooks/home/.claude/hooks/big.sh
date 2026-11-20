#!/bin/sh
# Prints ~20 KB: an oversized SessionStart hook.
head -c 20000 /dev/zero | tr "\\0" "x"
echo
