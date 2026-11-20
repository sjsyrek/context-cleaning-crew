#!/usr/bin/env python3
"""Print the Context Cleaning Crew manifest for a Claude Code setup as sorted JSON.

Read-only. `--offline` skips every external command (marketplace refresh, `claude plugin details`,
CLI version probes) so the output depends only on files.
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from ccc_inventory import Context, build_manifest
from ccc_inventory.options import default_sources, expand, load_options, mode_flags
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
    parser.add_argument(
        "--mode",
        choices=("quick", "full", "report"),
        help="skill mode: quick/full refresh marketplaces and run trackers; report follows the options",
    )
    parser.add_argument(
        "--options-settings",
        type=Path,
        action="append",
        help="settings file holding the plugin's options (repeatable, later wins; "
        "default: the running user's settings, then managed settings)",
    )
    out = parser.add_mutually_exclusive_group()
    out.add_argument("--out", type=Path, help="write the manifest to this file instead of stdout")
    out.add_argument(
        "--save", action="store_true", help="write the manifest to <report_dir>/<yyyy-mm-dd>-manifest.json"
    )
    args = parser.parse_args(argv)
    # Options belong to the person running the audit, so they come from the real home even
    # when --home points at a backup or a copy.
    real_home = Path.home()
    loaded = load_options(args.options_settings or default_sources(real_home))
    refresh, trackers = mode_flags(args.mode, loaded.options)
    runner: Runner = FakeRunner({}) if args.offline else SubprocessRunner()
    ctx = Context(
        home=args.home,
        cwd=args.cwd,
        runner=runner,
        secret_patterns=compile_extra([*loaded.options.extra_secret_patterns, *args.secret_pattern]),
        refresh_marketplaces=(args.refresh_marketplaces or refresh) and not args.offline,
        run_trackers=(args.run_trackers or trackers) and not args.offline,
        live=args.home.resolve() == real_home.resolve(),
        options=loaded,
    )
    manifest = build_manifest(ctx)
    text = json.dumps(manifest, sort_keys=True, indent=2) + "\n"
    target: Path | None = args.out
    if args.save:
        report_dir = expand(loaded.options.report_dir, real_home)
        target = report_dir / f"{date.today().isoformat()}-manifest.json"
    if target:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text)
        sys.stdout.write(f"wrote {target}\n")
    else:
        sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
