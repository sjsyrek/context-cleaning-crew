"""Leftover state: an empty tracker directory that shadows a real one higher up the tree."""

from __future__ import annotations

import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from ccc_inventory import Context, build_manifest  # noqa: E402
from ccc_inventory.runner import FakeRunner  # noqa: E402

FIXTURE = ROOT / "tests" / "fixtures" / "trackers" / "home"


class EmptyTrackerShadowTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.home = Path(self.tmp.name) / "home"
        shutil.copytree(FIXTURE, self.home)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def manifest(self, cwd: Path) -> dict[str, Any]:
        return build_manifest(Context(home=self.home, cwd=cwd, runner=FakeRunner({})))

    def test_an_empty_tracker_dir_nearer_the_working_tree_is_reported_with_what_it_shadows(self) -> None:
        (self.home / "Code" / "app" / ".beads").mkdir()
        leftovers = self.manifest(self.home / "Code" / "app" / "src")["leftovers"]
        self.assertEqual(
            leftovers,
            [
                {
                    "kind": "empty-tracker-dir",
                    "tracker": "beads",
                    "path": "~/Code/app/.beads",
                    "shadows": "~/Code/.beads",
                }
            ],
        )

    def test_a_directory_holding_only_finder_litter_counts_as_empty(self) -> None:
        empty = self.home / "Code" / "app" / ".beads"
        empty.mkdir()
        (empty / ".DS_Store").write_bytes(b"\0")
        self.assertEqual(len(self.manifest(self.home / "Code" / "app")["leftovers"]), 1)

    def test_an_empty_tracker_dir_with_nothing_above_it_shadows_nothing(self) -> None:
        shutil.rmtree(self.home / "Code" / ".beads")
        (self.home / "Code" / "app" / ".beads").mkdir()
        leftovers = self.manifest(self.home / "Code" / "app")["leftovers"]
        self.assertEqual(leftovers[0]["shadows"], "")

    def test_a_real_tracker_is_not_a_leftover(self) -> None:
        self.assertEqual(self.manifest(self.home / "Code" / "app")["leftovers"], [])

    def test_the_count_says_the_tracker_it_would_use_is_the_empty_one(self) -> None:
        (self.home / "Code" / "app" / ".beads").mkdir()
        counts = self.manifest(self.home / "Code" / "app")["counts"]
        self.assertEqual(counts[0]["path"], "~/Code/app")
        self.assertEqual(counts[0]["shadowed_by_empty"], "~/Code/app/.beads")


if __name__ == "__main__":
    unittest.main()
