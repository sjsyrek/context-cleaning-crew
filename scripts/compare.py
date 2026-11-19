#!/usr/bin/env python3
"""Print a one-line summary of a manifest, compared with the previous one when it exists."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ccc_inventory.summary import summarize


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("current", type=Path)
    parser.add_argument("previous", type=Path, nargs="?")
    args = parser.parse_args(argv)
    current = json.loads(args.current.read_text())
    previous = json.loads(args.previous.read_text()) if args.previous and args.previous.is_file() else None
    sys.stdout.write(summarize(current, previous) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
