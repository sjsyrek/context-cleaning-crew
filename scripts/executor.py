#!/usr/bin/env python3
"""Deterministic helpers for the executor (references/executor-rules.md).

  backup         copy files to <backup-dir>/<stamp>/, mirroring paths under home, and snapshot
                 enabledPlugins from every settings file being backed up. Refuses a temporary
                 directory (a wiped scratch directory once lost the only backup) and never
                 overwrites an existing backup.
  restore-flags  after an uninstall, put back the enabledPlugins entries of plugins the plan
                 keeps, from the snapshot, without touching any other entry.

Standard library only. Prints JSON; exits 2 on a refused backup.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import tempfile
from collections.abc import Sequence
from datetime import datetime
from pathlib import Path
from typing import Any

SNAPSHOT = "enabledPlugins.json"


class BackupError(Exception):
    pass


def system_temp_roots() -> tuple[Path, ...]:
    roots = {
        "/tmp",
        "/private/tmp",
        "/var/folders",
        "/private/var/folders",
        "/var/tmp",
        tempfile.gettempdir(),
    }
    if os.environ.get("TMPDIR"):
        roots.add(os.environ["TMPDIR"])
    return tuple(Path(r) for r in sorted(roots))


def is_under(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
    except ValueError:
        return False
    return True


def display(home: Path, path: Path) -> str:
    return "~/" + path.resolve().relative_to(home.resolve()).as_posix()


def backup(
    home: Path,
    files: Sequence[Path],
    backup_root: Path,
    stamp: str,
    temp_roots: Sequence[Path] | None = None,
) -> Path:
    """Copy `files` into `backup_root/stamp`, mirroring their paths under `home`. Returns the dir."""
    roots = system_temp_roots() if temp_roots is None else tuple(temp_roots)
    target = Path(os.path.abspath(backup_root))
    for root in roots:
        if is_under(target, Path(os.path.abspath(root))) or is_under(target.resolve(), root.resolve()):
            raise BackupError(f"{backup_root} is a temporary directory; back up somewhere persistent")
    home_r = home.resolve()
    for f in files:
        if not is_under(f.resolve(), home_r):
            raise BackupError(f"{f} is outside {home}; only files under home are backed up")
    dest = target / stamp
    if dest.exists():
        raise BackupError(f"{dest} already exists; never overwrite a backup")
    dest.mkdir(parents=True)
    snapshot: dict[str, Any] = {}
    for f in files:
        rel = f.resolve().relative_to(home_r)
        copy = dest / rel
        copy.parent.mkdir(parents=True, exist_ok=True)
        if f.is_dir():
            shutil.copytree(f, copy, symlinks=True)
        else:
            shutil.copy2(f, copy)
            if f.name.startswith("settings") and f.suffix == ".json":
                flags = read_object(f).get("enabledPlugins")
                snapshot[display(home, f)] = flags if isinstance(flags, dict) else {}
    (dest / SNAPSHOT).write_text(json.dumps(snapshot, indent=2, sort_keys=True) + "\n")
    return dest


def read_object(path: Path) -> dict[str, Any]:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def restore_flags(home: Path, settings: Path, snapshot: Path, keep: Sequence[str]) -> list[str]:
    """Re-add the snapshot's enabledPlugins entries for `keep` that are now missing or changed in
    `settings`. Parses and re-serializes only when something changes, then re-reads to validate."""
    before = read_object(snapshot).get(display(home, settings), {})
    data: Any = {}
    if settings.exists():
        try:
            data = json.loads(settings.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            data = None
    if not isinstance(data, dict):  # `{}` is a valid, empty settings file
        raise ValueError(f"{settings} is not a JSON object; restore it from the backup by hand")
    flags = data.get("enabledPlugins")
    current: dict[str, Any] = flags if isinstance(flags, dict) else {}
    restored = sorted(p for p in keep if p in before and current.get(p) != before[p])
    if not restored:
        return []
    for p in restored:
        current[p] = before[p]
    data["enabledPlugins"] = current
    settings.write_text(json.dumps(data, indent=2) + "\n")
    if read_object(settings).get("enabledPlugins") != current:
        raise ValueError(f"{settings} did not re-read as written")
    return restored


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=(__doc__ or "").splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    b = sub.add_parser("backup", help="back up files and snapshot enabledPlugins")
    b.add_argument("--home", type=Path, default=Path.home())
    b.add_argument("--backup-dir", type=Path, required=True)
    b.add_argument("--stamp", default=datetime.now().strftime("%Y-%m-%d-%H%M"))
    b.add_argument("files", type=Path, nargs="+")
    r = sub.add_parser("restore-flags", help="restore enabledPlugins entries for kept plugins")
    r.add_argument("--home", type=Path, default=Path.home())
    r.add_argument("--settings", type=Path, required=True)
    r.add_argument("--snapshot", type=Path, required=True)
    r.add_argument("--keep", nargs="+", required=True)
    args = parser.parse_args(argv)
    if args.command == "backup":
        try:
            dest = backup(args.home, args.files, args.backup_dir.expanduser(), args.stamp)
        except BackupError as exc:
            sys.stderr.write(f"refused: {exc}\n")
            return 2
        sys.stdout.write(json.dumps({"backup": str(dest), "snapshot": str(dest / SNAPSHOT)}) + "\n")
        return 0
    restored = restore_flags(args.home, args.settings, args.snapshot, args.keep)
    sys.stdout.write(json.dumps({"restored": restored}) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
