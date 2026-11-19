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
from ccc_inventory.redact import compile_extra
from ccc_inventory.runner import FakeRunner, Runner, SubprocessRunner


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--home", type=Path, default=Path.home(), help="home directory to audit")
    parser.add_argument("--cwd", type=Path, default=Path.cwd(), help="working tree to audit")
    parser.add_argument("--offline", action="store_true", help="run no external commands")
    parser.add_argument("--secret-pattern", action="append", default=[], help="extra secret regex")
    parser.add_argument(
        "--refresh-marketplaces",
        action="store_true",
        help="run `claude plugin marketplace update` before version checks (writes the local clones)",
    )
    parser.add_argument(
        "--run-trackers", action="store_true", help="run tracker count commands such as `bd stats`"
    )
    args = parser.parse_args(argv)
    runner: Runner = FakeRunner({}) if args.offline else SubprocessRunner()
    ctx = Context(
        home=args.home,
        cwd=args.cwd,
        runner=runner,
        secret_patterns=compile_extra(args.secret_pattern),
        refresh_marketplaces=args.refresh_marketplaces and not args.offline,
        run_trackers=args.run_trackers and not args.offline,
    )
    manifest = build_manifest(ctx)
    sys.stdout.write(json.dumps(manifest, sort_keys=True, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
