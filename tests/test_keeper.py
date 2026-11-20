"""Keeper choice for duplicate plugins: protected first, then preferred marketplaces."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from ccc_inventory import Context, build_manifest  # noqa: E402
from ccc_inventory.keeper import UNDECIDED, pick_keeper  # noqa: E402
from ccc_inventory.options import LoadedOptions, Options  # noqa: E402
from ccc_inventory.runner import FakeRunner  # noqa: E402

HOME = ROOT / "tests" / "fixtures" / "overlap" / "home"
CWD = HOME / "Code" / "app"


def manifest(**options: Any) -> dict[str, Any]:
    loaded = LoadedOptions(options=Options(**options), sources={})
    return build_manifest(Context(home=HOME, cwd=CWD, runner=FakeRunner({}), options=loaded))


class PickKeeperTest(unittest.TestCase):
    PAIR = ("red-team@community-mkt", "red-team@internal-mkt")

    def test_the_earliest_preferred_marketplace_wins(self) -> None:
        opts = Options(preferred_marketplaces=("internal-mkt", "community-mkt"))
        self.assertEqual(pick_keeper(self.PAIR, opts), ("red-team@internal-mkt", "preferred_marketplaces"))
        opts = Options(preferred_marketplaces=("community-mkt", "internal-mkt"))
        self.assertEqual(pick_keeper(self.PAIR, opts), ("red-team@community-mkt", "preferred_marketplaces"))

    def test_a_preferred_marketplace_without_a_candidate_is_skipped(self) -> None:
        opts = Options(preferred_marketplaces=("elsewhere", "community-mkt"))
        self.assertEqual(pick_keeper(self.PAIR, opts), ("red-team@community-mkt", "preferred_marketplaces"))

    def test_protected_beats_preferred(self) -> None:
        opts = Options(preferred_marketplaces=("internal-mkt",), protected=("red-team@community-mkt",))
        self.assertEqual(pick_keeper(self.PAIR, opts), ("red-team@community-mkt", "protected"))

    def test_protecting_the_bare_name_protects_every_copy_so_nothing_is_picked(self) -> None:
        opts = Options(preferred_marketplaces=("internal-mkt",), protected=("red-team",))
        self.assertEqual(pick_keeper(self.PAIR, opts), (None, "protected: keep all"))

    def test_without_options_the_reviewer_decides(self) -> None:
        self.assertEqual(pick_keeper(self.PAIR, Options()), (None, UNDECIDED))


class PluginDuplicatesTest(unittest.TestCase):
    def test_same_plugin_from_two_marketplaces_is_a_duplicate_with_a_keeper(self) -> None:
        dupes = manifest(preferred_marketplaces=("internal-mkt",))["overlap"]["plugin_duplicates"]
        self.assertEqual(
            dupes,
            [
                {
                    "name": "red-team",
                    "plugins": ["red-team@community-mkt", "red-team@internal-mkt"],
                    "keeper": "red-team@internal-mkt",
                    "rule": "preferred_marketplaces",
                }
            ],
        )

    def test_undecided_without_a_preference(self) -> None:
        dupe = manifest()["overlap"]["plugin_duplicates"][0]
        self.assertIsNone(dupe["keeper"])
        self.assertEqual(dupe["rule"], UNDECIDED)

    def test_a_plugin_in_one_marketplace_only_is_not_a_duplicate(self) -> None:
        names = {d["name"] for d in manifest()["overlap"]["plugin_duplicates"]}
        self.assertNotIn("docs-helper", names)


class ProtectedResolutionTest(unittest.TestCase):
    def test_protected_entries_resolve_to_installed_plugins_and_unmatched_ones_are_listed(self) -> None:
        resolved = manifest(protected=("red-team", "docs-helper@community-mkt", "typo-plugin"))["protected"]
        self.assertEqual(
            resolved["plugins"],
            ["docs-helper@community-mkt", "red-team@community-mkt", "red-team@internal-mkt"],
        )
        self.assertEqual(resolved["unmatched"], ["typo-plugin"])

    def test_installed_plugins_carry_a_protected_flag(self) -> None:
        installed = {p["id"]: p for p in manifest(protected=("docs-helper",))["plugins"]["installed"]}
        self.assertTrue(installed["docs-helper@community-mkt"]["protected"])
        self.assertFalse(installed["red-team@internal-mkt"]["protected"])

    def test_memory_files_and_mcp_servers_can_be_protected_by_name(self) -> None:
        messy = ROOT / "tests" / "fixtures" / "messy" / "home"
        loaded = LoadedOptions(options=Options(protected=("prefers-terse.md", "github")), sources={})
        ctx = Context(home=messy, cwd=messy / "Code" / "proj", runner=FakeRunner({}), options=loaded)
        resolved = build_manifest(ctx)["protected"]
        self.assertEqual(
            resolved["memory_files"], ["~/.claude/projects/-home-Code-proj/memory/prefers-terse.md"]
        )
        self.assertEqual(resolved["mcp_servers"], ["github"])
        self.assertEqual(resolved["unmatched"], [])


if __name__ == "__main__":
    unittest.main()
