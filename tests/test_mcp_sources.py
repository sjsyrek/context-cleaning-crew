"""The same MCP server from user config, project .mcp.json and a plugin, with a keeper per group."""

from __future__ import annotations

import json
import sys
import tempfile
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


QUERY_KEY = "3f1c9a2e-7b4d-4e8a-9c61-5d2f0b7a8e14"
OTHER_KEY = "a0b1c2d3-e4f5-4a6b-8c7d-9e0f1a2b3c4d"
PASSWORD = "hunter2-opaque-pw"


class UrlSecretsTest(unittest.TestCase):
    """A credential in an MCP URL's query string or userinfo never reaches the manifest."""

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        home = Path(self.tmp.name) / "home"
        (home / "Code" / "app").mkdir(parents=True)
        servers = {
            "query-a": {"type": "http", "url": f"https://mcp.example.invalid/v1?api_key={QUERY_KEY}"},
            "query-b": {"type": "http", "url": f"https://mcp.example.invalid/v1?api_key={OTHER_KEY}"},
            "query-c": {"type": "http", "url": f"https://mcp.example.invalid/v1?api_key={QUERY_KEY}"},
            "userinfo-a": {"type": "http", "url": f"https://bot:{PASSWORD}@auth.example.invalid/mcp"},
            "userinfo-b": {"type": "http", "url": f"https://bot:{PASSWORD}@auth.example.invalid/mcp"},
        }
        (home / ".claude.json").write_text(json.dumps({"mcpServers": servers}))
        ctx = Context(home=home, cwd=home / "Code" / "app", runner=FakeRunner({}))
        self.manifest = build_manifest(ctx)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_no_url_credential_appears_anywhere_in_the_manifest(self) -> None:
        text = json.dumps(self.manifest)
        for secret in (QUERY_KEY, OTHER_KEY, PASSWORD):
            self.assertNotIn(secret, text)

    def test_urls_differing_only_in_their_query_group_as_one_server(self) -> None:
        groups = {d["target"]: d["servers"] for d in self.manifest["mcp"]["duplicates"]}
        self.assertEqual(
            groups,
            {
                "https://mcp.example.invalid/v1?<redacted:query>": ["query-a", "query-b", "query-c"],
                "https://<redacted:userinfo>@auth.example.invalid/mcp": ["userinfo-a", "userinfo-b"],
            },
        )


if __name__ == "__main__":
    unittest.main()
