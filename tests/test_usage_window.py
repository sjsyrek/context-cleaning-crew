"""usage_window_days marks unused skills; mine_transcripts counts MCP calls per server."""

from __future__ import annotations

import json
import sys
import unittest
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from ccc_inventory import Context, build_manifest  # noqa: E402
from ccc_inventory.options import LoadedOptions, Options  # noqa: E402
from ccc_inventory.runner import FakeRunner  # noqa: E402

HOME = ROOT / "tests" / "fixtures" / "messy" / "home"
CWD = HOME / "Code" / "proj"
TODAY = date(2026, 11, 20)


def usage(**options: Any) -> dict[str, Any]:
    loaded = LoadedOptions(options=Options(**options), sources={})
    ctx = Context(home=HOME, cwd=CWD, runner=FakeRunner({}), options=loaded, today=TODAY)
    section: dict[str, Any] = build_manifest(ctx)["usage"]
    return section


class SkillWindowTest(unittest.TestCase):
    def test_a_skill_last_used_before_the_window_is_unused(self) -> None:
        skills = {s["skill"]: s for s in usage()["skills"]}
        self.assertTrue(skills["old-council"]["unused"])  # last used 2023-11-14
        self.assertEqual(usage()["window_days"], 90)

    def test_a_wide_enough_window_makes_it_used(self) -> None:
        skills = {s["skill"]: s for s in usage(usage_window_days=3650)["skills"]}
        self.assertFalse(skills["old-council"]["unused"])


class TranscriptMiningTest(unittest.TestCase):
    def test_transcripts_are_not_read_unless_opted_in(self) -> None:
        self.assertEqual(usage()["mcp"], {"status": "not mined: mine_transcripts is off"})

    def test_mcp_calls_are_counted_per_server_within_the_window(self) -> None:
        mcp = usage(mine_transcripts=True)["mcp"]
        servers = {s["server"]: s for s in mcp["servers"]}
        self.assertEqual(servers["github"], {"server": "github", "calls": 2, "last_used": "2026-11-01"})
        self.assertEqual(servers["plugin_docs_search"]["calls"], 1)  # subagent transcript counts
        self.assertNotIn("github-sse", servers)  # outside the 90-day window
        self.assertNotIn("ghost", servers)  # named in text, never called
        self.assertEqual(mcp["status"], "mined")
        self.assertEqual(mcp["transcripts"], 2)

    def test_configured_servers_without_calls_in_the_window_are_listed(self) -> None:
        self.assertEqual(usage(mine_transcripts=True)["mcp"]["unused_servers"], ["github-sse"])

    def test_no_transcript_content_reaches_the_manifest(self) -> None:
        text = json.dumps(usage(mine_transcripts=True))
        self.assertNotIn("SECRET-CONTENT", text)
        self.assertNotIn("get_issue", text)  # tool names stay out too: counts per server only


if __name__ == "__main__":
    unittest.main()
