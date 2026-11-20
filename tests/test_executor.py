"""Executor helpers against a temp copy of a fixture: persistent backups, the enabledPlugins
snapshot, and restoring only the intended flags after an uninstall (PLAN.md rules 1-3, 12)."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from executor import BackupError, backup, restore_flags  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "overlap" / "home"
STAMP = "2026-11-20-0900"


def read(path: Path) -> Any:
    return json.loads(path.read_text())


class ScopeAliasingReplayTest(unittest.TestCase):
    """cwd == home: removing the project-scope copy of red-team@community-mkt deletes the enable
    flag the user-scope copy shares. The executor snapshots, uninstalls, then restores the flag."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        shutil.copytree(FIXTURE, self.home)
        self.settings = self.home / ".claude" / "settings.json"
        self.original = self.settings.read_bytes()
        self.backups = self.home / ".claude" / "backups" / "context-cleaning-crew"

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def simulate_uninstall(self, plugin: str) -> None:
        """What `claude plugin uninstall --scope project` does when the project is home."""
        data = read(self.settings)
        del data["enabledPlugins"][plugin]
        self.settings.write_text(json.dumps(data, indent=2) + "\n")

    def test_backup_mirrors_paths_under_home_and_snapshots_enabled_plugins(self) -> None:
        dest = backup(self.home, [self.settings], self.backups, STAMP, temp_roots=())
        self.assertEqual(dest, self.backups / STAMP)
        self.assertEqual((dest / ".claude" / "settings.json").read_bytes(), self.original)
        snapshot = read(dest / "enabledPlugins.json")
        self.assertEqual(snapshot["~/.claude/settings.json"]["red-team@community-mkt"], True)

    def test_the_kept_copys_flag_comes_back_and_nothing_else_changes(self) -> None:
        dest = backup(self.home, [self.settings], self.backups, STAMP, temp_roots=())
        self.simulate_uninstall("red-team@community-mkt")
        restored = restore_flags(
            self.home, self.settings, dest / "enabledPlugins.json", ["red-team@community-mkt"]
        )
        self.assertEqual(restored, ["red-team@community-mkt"])
        self.assertEqual(read(self.settings), json.loads(self.original))

    def test_a_flag_removed_on_purpose_is_not_resurrected(self) -> None:
        dest = backup(self.home, [self.settings], self.backups, STAMP, temp_roots=())
        self.simulate_uninstall("docs-helper@community-mkt")
        self.simulate_uninstall("red-team@community-mkt")
        restore_flags(self.home, self.settings, dest / "enabledPlugins.json", ["red-team@community-mkt"])
        flags = read(self.settings)["enabledPlugins"]
        self.assertNotIn("docs-helper@community-mkt", flags)
        self.assertTrue(flags["red-team@community-mkt"])

    def test_a_flag_that_survived_is_left_alone(self) -> None:
        dest = backup(self.home, [self.settings], self.backups, STAMP, temp_roots=())
        self.assertEqual(
            restore_flags(self.home, self.settings, dest / "enabledPlugins.json", ["red-team@internal-mkt"]),
            [],
        )
        self.assertEqual(self.settings.read_bytes(), self.original)  # not even re-serialized

    def test_an_empty_settings_object_gets_the_flag_back(self) -> None:
        # `claude plugin uninstall` can leave `{}` behind: a valid settings file, not a broken one.
        dest = backup(self.home, [self.settings], self.backups, STAMP, temp_roots=())
        self.settings.write_text("{}\n")
        restored = restore_flags(
            self.home, self.settings, dest / "enabledPlugins.json", ["red-team@community-mkt"]
        )
        self.assertEqual(restored, ["red-team@community-mkt"])
        self.assertEqual(read(self.settings), {"enabledPlugins": {"red-team@community-mkt": True}})

    def test_a_settings_file_that_is_not_a_json_object_is_refused(self) -> None:
        dest = backup(self.home, [self.settings], self.backups, STAMP, temp_roots=())
        snapshot = dest / "enabledPlugins.json"
        for broken in ("[]\n", "{not json\n"):
            self.settings.write_text(broken)
            with self.assertRaises(ValueError, msg=broken):
                restore_flags(self.home, self.settings, snapshot, ["red-team@community-mkt"])
            self.assertEqual(self.settings.read_text(), broken)

    def test_an_existing_backup_is_never_overwritten(self) -> None:
        backup(self.home, [self.settings], self.backups, STAMP, temp_roots=())
        with self.assertRaises(BackupError):
            backup(self.home, [self.settings], self.backups, STAMP, temp_roots=())


class BackupGuardTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        shutil.copytree(FIXTURE, self.home)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_a_temporary_backup_dir_is_refused(self) -> None:
        for temp in (
            "/tmp/ccc-backups",
            "/private/tmp/x",
            "/var/folders/ab/T/x",
            tempfile.gettempdir() + "/x",
        ):
            with self.assertRaises(BackupError, msg=temp):
                backup(self.home, [self.home / ".claude" / "settings.json"], Path(temp), STAMP)

    def test_a_file_outside_home_is_refused(self) -> None:
        with self.assertRaises(BackupError):
            backup(self.home, [ROOT / "README.md"], self.home / "backups", STAMP)

    def test_the_cli_refuses_a_temporary_dir_without_writing_anything(self) -> None:
        done = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "executor.py"),
                "backup",
                "--home",
                str(self.home),
                "--backup-dir",
                "/tmp/ccc-backups-test",
                str(self.home / ".claude" / "settings.json"),
            ],
            capture_output=True,
            text=True,
        )
        self.assertEqual(done.returncode, 2)
        self.assertIn("temporary", done.stderr)
        self.assertFalse(Path("/tmp/ccc-backups-test").exists())


if __name__ == "__main__":
    unittest.main()
