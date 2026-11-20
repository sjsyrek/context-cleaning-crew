"""The same MCP server from user config, project .mcp.json and a plugin, with a keeper per group."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from ccc_inventory import Context, build_manifest  # noqa: E402
from ccc_inventory.keeper import UNDECIDED  # noqa: E402
from ccc_inventory.options import LoadedOptions, Options  # noqa: E402
from ccc_inventory.runner import FakeRunner  # noqa: E402

HOME = ROOT / "tests" / "fixtures" / "overlap" / "home"
APP = HOME / "Code" / "app"
URL = "https://docs.example.invalid/mcp"


def mcp(**options: Any) -> dict[str, Any]:
    loaded = LoadedOptions(options=Options(**options), sources={})
    ctx = Context(home=HOME, cwd=APP, runner=FakeRunner({}), options=loaded)
    section: dict[str, Any] = build_manifest(ctx)["mcp"]
    return section


class ThreeSourcesTest(unittest.TestCase):
    def test_one_url_from_three_sources_is_one_duplicate_group_naming_each_source(self) -> None:
        group = next(d for d in mcp()["duplicates"] if d["target"] == URL)
        self.assertEqual(group["servers"], ["docs", "docs-local", "plugin_docs-helper_search"])
        self.assertEqual(
            group["members"],
            [
                {"server": "docs", "source": "~/.claude.json"},
                {"server": "docs-local", "source": "~/Code/app/.mcp.json"},
                {"server": "plugin_docs-helper_search", "source": "plugin docs-helper@community-mkt"},
            ],
        )

    def test_plugin_servers_are_listed_with_the_prefix_their_tool_names_use(self) -> None:
        servers = mcp()["servers"]
        self.assertIn("plugin_docs-helper_search", servers)
        self.assertIn("plugin_red-team_search", servers)  # flat .mcp.json format

    def test_two_plugins_shipping_the_same_server_name_are_flagged(self) -> None:
        self.assertEqual(
            mcp()["plugin_name_clashes"],
            [{"server": "search", "plugins": ["docs-helper@community-mkt", "red-team@internal-mkt"]}],
        )


class McpKeeperTest(unittest.TestCase):
    def group(self, **options: Any) -> dict[str, Any]:
        return next(d for d in mcp(**options)["duplicates"] if d["target"] == URL)

    def test_without_options_the_reviewer_decides(self) -> None:
        group = self.group()
        self.assertIsNone(group["keeper"])
        self.assertEqual(group["rule"], UNDECIDED)

    def test_a_protected_server_is_the_keeper(self) -> None:
        group = self.group(protected=("docs-local",), preferred_marketplaces=("community-mkt",))
        self.assertEqual((group["keeper"], group["rule"]), ("docs-local", "protected"))

    def test_a_plugin_server_from_a_preferred_marketplace_is_the_keeper(self) -> None:
        group = self.group(preferred_marketplaces=("community-mkt",))
        self.assertEqual(
            (group["keeper"], group["rule"]), ("plugin_docs-helper_search", "preferred_marketplaces")
        )

    def test_a_protected_plugin_protects_its_server(self) -> None:
        group = self.group(protected=("docs-helper",))
        self.assertEqual((group["keeper"], group["rule"]), ("plugin_docs-helper_search", "protected"))


if __name__ == "__main__":
    unittest.main()
