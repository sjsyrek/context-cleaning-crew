"""The one-line summary a scheduled report run prints for notification hooks."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from ccc_inventory.summary import always_on, summarize  # noqa: E402


def manifest(plugin_costs: list[int | None], instruction_tokens: list[int], **extra: Any) -> dict[str, Any]:
    installed: list[dict[str, Any]] = [
        {"id": f"p{i}@m", "cost": {"status": "not checked"} if c is None else {"always_on": c}}
        for i, c in enumerate(plugin_costs)
    ]
    base: dict[str, Any] = {
        "schema_version": 1,
        "plugins": {"installed": installed},
        "instructions": {"files": [{"approx_tokens": t} for t in instruction_tokens]},
        "secrets": [],
        "permissions": {"findings": []},
        "removed_tool_refs": [],
        "drift": {"marketplace": []},
        "mcp": {"duplicates": []},
    }
    base.update(extra)
    return base


class AlwaysOnTest(unittest.TestCase):
    def test_sums_costed_plugins_and_instruction_files(self) -> None:
        self.assertEqual(always_on(manifest([5600, 400], [21, 81])), (6102, 0))

    def test_counts_plugins_whose_cost_was_not_checked(self) -> None:
        self.assertEqual(always_on(manifest([None, 300], [])), (300, 1))


class SummarizeTest(unittest.TestCase):
    def test_first_run_has_no_delta(self) -> None:
        line = summarize(manifest([1000], [100]))
        self.assertIn("always-on ~1100 tokens", line)
        self.assertNotIn("since", line)
        self.assertEqual(line.count("\n"), 0)

    def test_reports_the_signed_delta_since_the_previous_manifest(self) -> None:
        self.assertIn("(-500 since last run)", summarize(manifest([500], [100]), manifest([1000], [100])))
        self.assertIn("(+200 since last run)", summarize(manifest([1200], [100]), manifest([1000], [100])))

    def test_mentions_uncosted_plugins_so_the_number_is_not_mistaken_for_a_total(self) -> None:
        self.assertIn("2 plugins not costed", summarize(manifest([None, None], [10])))

    def test_lists_only_nonzero_issue_counts(self) -> None:
        current = manifest(
            [],
            [],
            secrets=[{"file": "~/.claude.json", "key": "k", "type": "github-token"}],
            drift={"marketplace": [{"status": "behind"}, {"status": "current"}]},
        )
        line = summarize(current)
        self.assertIn("1 plaintext secret", line)
        self.assertIn("1 plugin behind its marketplace", line)
        self.assertNotIn("duplicate", line)
        self.assertNotIn("github-token", line)


class CompareCommandTest(unittest.TestCase):
    def run_compare(self, *paths: Path) -> str:
        done = subprocess.run(
            [sys.executable, str(ROOT / "scripts" / "compare.py"), *map(str, paths)],
            capture_output=True,
            text=True,
            check=True,
        )
        return done.stdout

    def test_prints_one_line_comparing_with_the_previous_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            old, new = Path(tmp) / "old.json", Path(tmp) / "new.json"
            old.write_text(json.dumps(manifest([1000], [])))
            new.write_text(json.dumps(manifest([700], [])))
            self.assertEqual(self.run_compare(new, old), "always-on ~700 tokens (-300 since last run)\n")

    def test_missing_previous_manifest_is_a_first_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            new = Path(tmp) / "new.json"
            new.write_text(json.dumps(manifest([700], [])))
            self.assertEqual(self.run_compare(new, Path(tmp) / "absent.json"), "always-on ~700 tokens\n")


if __name__ == "__main__":
    unittest.main()
