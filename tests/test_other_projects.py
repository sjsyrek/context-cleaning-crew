"""Settings of the other projects Claude Code has seen: secrets and permission counts, nothing else."""

from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from ccc_inventory import Context, build_manifest  # noqa: E402
from ccc_inventory.runner import FakeRunner  # noqa: E402

HOME = ROOT / "tests" / "fixtures" / "projects" / "home"
OTHER = "~/Code/other/.claude/settings.json"
OTHER_LOCAL = "~/Code/other/.claude/settings.local.json"


class OtherProjectsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.runner = FakeRunner({})
        self.manifest: dict[str, Any] = build_manifest(
            Context(home=HOME, cwd=HOME / "Code" / "app", runner=self.runner)
        )

    def test_each_settings_file_gets_rule_counts_per_list_and_finding_counts_per_kind(self) -> None:
        self.assertEqual(
            self.manifest["permissions"]["other_projects"],
            [
                {
                    "path": OTHER,
                    "rules": {"allow": 2, "ask": 0, "deny": 1},
                    "findings": {"redundant-allow": 1},
                },
                {"path": OTHER_LOCAL, "rules": {"allow": 2, "ask": 0, "deny": 0}, "findings": {}},
            ],
        )

    def test_secrets_in_other_projects_are_found_by_file_key_and_type(self) -> None:
        found = {(s["file"], s["key"], s["type"]) for s in self.manifest["secrets"]}
        self.assertIn((OTHER, "env.GITHUB_TOKEN", "github-token"), found)

    def test_no_secret_value_and_no_rule_text_reaches_the_manifest(self) -> None:
        text = json.dumps(self.manifest)
        self.assertNotIn("FAKEFAKEFAKEFAKEFAKEFAKEOTHER1", text)
        self.assertNotIn("Opaque-Pw-7731", text)  # an opaque secret: only no-rule-text keeps it out
        self.assertNotIn("git status", text)

    def test_other_projects_never_feed_flags_hooks_or_the_current_settings(self) -> None:
        self.assertNotIn("planted@elsewhere", json.dumps(self.manifest["plugins"]))
        self.assertNotIn("./other-project-hook.sh", [h["command"] for h in self.manifest["hooks"]])
        paths = [f["path"] for f in self.manifest["settings"]["files"]]
        self.assertEqual(paths, ["~/.claude/settings.json", "~/Code/app/.claude/settings.json"])
        self.assertEqual(len(self.manifest["permissions"]["rules"]), 2)

    def test_the_working_tree_and_missing_projects_are_not_listed_again(self) -> None:
        paths = [p["path"] for p in self.manifest["permissions"]["other_projects"]]
        self.assertNotIn("~/Code/app/.claude/settings.json", paths)

    def test_scanning_other_projects_runs_no_command(self) -> None:
        self.assertEqual(self.runner.calls, [])


if __name__ == "__main__":
    unittest.main()
