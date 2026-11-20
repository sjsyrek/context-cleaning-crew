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

from executor import BackupError, RestoreError, backup, restore_flags  # noqa: E402

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

    def test_a_snapshot_without_this_settings_file_is_refused(self) -> None:
        # A snapshot of another file says nothing about this one: never guess "no flags".
        local = self.home / ".claude" / "settings.local.json"
        local.write_text('{"enabledPlugins": {}}\n')
        dest = backup(self.home, [local], self.backups, STAMP, temp_roots=())
        self.simulate_uninstall("red-team@community-mkt")
        after = self.settings.read_bytes()
        with self.assertRaises(ValueError) as caught:
            restore_flags(self.home, self.settings, dest / "enabledPlugins.json", ["red-team@community-mkt"])
        self.assertIn("~/.claude/settings.json", str(caught.exception))
        self.assertEqual(self.settings.read_bytes(), after)

    def test_a_snapshot_with_no_flags_for_this_file_restores_nothing(self) -> None:
        self.settings.write_text('{"model": "opus"}\n')
        dest = backup(self.home, [self.settings], self.backups, STAMP, temp_roots=())
        self.assertEqual(read(dest / "enabledPlugins.json"), {"~/.claude/settings.json": {}})
        snapshot = dest / "enabledPlugins.json"
        self.assertEqual(restore_flags(self.home, self.settings, snapshot, ["red-team@community-mkt"]), [])

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

    def tree(self) -> list[str]:
        return sorted(str(p.relative_to(self.tmp.name)) for p in Path(self.tmp.name).rglob("*"))

    def test_a_stamp_that_is_not_a_plain_name_is_refused_and_nothing_is_written(self) -> None:
        settings = self.home / ".claude" / "settings.json"
        before = self.tree()
        for stamp in ("../x", "a/b", ".hidden", "..", "", "a b", "/abs", "x\n"):
            with self.assertRaises(BackupError, msg=repr(stamp)):
                backup(self.home, [settings], self.home / "backups", stamp, temp_roots=())
            self.assertEqual(self.tree(), before, msg=repr(stamp))

    def test_a_plain_stamp_is_accepted(self) -> None:
        dest = backup(self.home, [self.home / ".claude" / "settings.json"], self.home / "b", "v1.2_x-3", ())
        self.assertEqual(dest, self.home / "b" / "v1.2_x-3")

    def test_the_cli_refuses_a_path_stamp_with_exit_code_2(self) -> None:
        before = self.tree()
        argv = [sys.executable, str(ROOT / "scripts" / "executor.py"), "backup", "--home", str(self.home)]
        argv += ["--backup-dir", str(self.home / "backups"), "--stamp", "../x"]
        argv += [str(self.home / ".claude" / "settings.json")]
        done = subprocess.run(argv, capture_output=True, text=True)
        self.assertEqual(done.returncode, 2)
        self.assertIn("stamp", done.stderr)
        self.assertEqual(self.tree(), before)

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


class RestoreGuardTest(unittest.TestCase):
    """restore-flags edits only a settings file that really lives under home."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        shutil.copytree(FIXTURE, self.home)
        self.settings = self.home / ".claude" / "settings.json"
        dest = backup(self.home, [self.settings], self.home / "backups", STAMP, temp_roots=())
        self.snapshot = dest / "enabledPlugins.json"
        self.outside = Path(self.tmp.name) / "elsewhere" / "settings.json"
        self.outside.parent.mkdir()
        self.outside.write_text('{"enabledPlugins": {}}\n')

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_a_settings_file_outside_home_is_refused(self) -> None:
        with self.assertRaises(RestoreError) as caught:
            restore_flags(self.home, self.outside, self.snapshot, ["red-team@community-mkt"])
        self.assertIn("outside", str(caught.exception))
        self.assertEqual(self.outside.read_text(), '{"enabledPlugins": {}}\n')

    def test_a_settings_file_symlinked_out_of_home_is_refused(self) -> None:
        self.settings.unlink()
        self.settings.symlink_to(self.outside)
        with self.assertRaises(RestoreError):
            restore_flags(self.home, self.settings, self.snapshot, ["red-team@community-mkt"])
        self.assertEqual(self.outside.read_text(), '{"enabledPlugins": {}}\n')

    def test_the_cli_refuses_with_exit_code_2_and_no_traceback(self) -> None:
        argv = [sys.executable, str(ROOT / "scripts" / "executor.py"), "restore-flags"]
        argv += ["--home", str(self.home), "--settings", str(self.outside), "--snapshot", str(self.snapshot)]
        argv += ["--keep", "red-team@community-mkt"]
        done = subprocess.run(
            argv,
            capture_output=True,
            text=True,
        )
        self.assertEqual(done.returncode, 2)
        self.assertIn("refused:", done.stderr)
        self.assertIn("outside", done.stderr)
        self.assertNotIn("Traceback", done.stderr)


if __name__ == "__main__":
    unittest.main()
