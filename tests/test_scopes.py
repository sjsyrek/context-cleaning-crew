"""Scope aliasing (cwd == home) and plugins installed at several scopes (PLAN.md rules 2 and 3)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from ccc_inventory import Context, build_manifest  # noqa: E402
from ccc_inventory.runner import FakeRunner  # noqa: E402

HOME = ROOT / "tests" / "fixtures" / "overlap" / "home"
APP = HOME / "Code" / "app"


def manifest(cwd: Path) -> dict[str, Any]:
    return build_manifest(Context(home=HOME, cwd=cwd, runner=FakeRunner({})))


class ScopeAliasingTest(unittest.TestCase):
    def test_cwd_at_home_loads_user_settings_once_and_says_it_is_aliased(self) -> None:
        settings = manifest(HOME)["settings"]
        self.assertEqual([f["path"] for f in settings["files"]], ["~/.claude/settings.json"])
        aliasing = settings["scope_aliasing"]
        self.assertTrue(aliasing["aliased"])
        self.assertEqual(aliasing["file"], "~/.claude/settings.json")
        self.assertIn("enabledPlugins", aliasing["note"])

    def test_cwd_below_home_is_not_aliased(self) -> None:
        self.assertEqual(manifest(APP)["settings"]["scope_aliasing"], {"aliased": False})


class MultiScopeTest(unittest.TestCase):
    def setUp(self) -> None:
        self.multi = {m["plugin"]: m for m in manifest(HOME)["plugins"]["multi_scope"]}

    def test_every_plugin_installed_at_more_than_one_scope_is_listed_with_its_projects(self) -> None:
        self.assertEqual(sorted(self.multi), ["docs-helper@community-mkt", "red-team@community-mkt"])
        self.assertEqual(
            self.multi["docs-helper@community-mkt"]["scopes"],
            [{"scope": "project", "project": "~/Code/app"}, {"scope": "user", "project": ""}],
        )

    def test_a_project_install_for_the_home_directory_shares_the_user_settings_file(self) -> None:
        self.assertTrue(self.multi["red-team@community-mkt"]["shares_user_settings"])
        self.assertFalse(self.multi["docs-helper@community-mkt"]["shares_user_settings"])

    def test_a_plugin_at_one_scope_is_not_listed(self) -> None:
        self.assertNotIn("red-team@internal-mkt", self.multi)

    def test_installed_scopes_are_still_summarized(self) -> None:
        installed = {p["id"]: p for p in manifest(HOME)["plugins"]["installed"]}
        self.assertEqual(installed["red-team@community-mkt"]["scopes"], ["project", "user"])


if __name__ == "__main__":
    unittest.main()
