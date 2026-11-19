#!/usr/bin/env python3
"""Print the Context Cleaning Crew manifest for a Claude Code setup as sorted JSON.

Read-only. `--offline` skips every external command (marketplace refresh, `claude plugin details`,
CLI version probes) so the output depends only on files.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ccc_inventory import Context, build_manifest
from ccc_inventory.runner import FakeRunner, Runner, SubprocessRunner


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--home", type=Path, default=Path.home(), help="home directory to audit")
    parser.add_argument("--cwd", type=Path, default=Path.cwd(), help="working tree to audit")
    parser.add_argument("--offline", action="store_true", help="run no external commands")
    parser.add_argument("--secret-pattern", action="append", default=[], help="extra secret regex")
    args = parser.parse_args(argv)
    runner: Runner = FakeRunner({}) if args.offline else SubprocessRunner()
    manifest = build_manifest(
        Context(home=args.home, cwd=args.cwd, runner=runner), extra_secret_patterns=args.secret_pattern
    )
    sys.stdout.write(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
