"""Stray memory directories that never load, and personal memories duplicated across projects."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from ccc_inventory import Context, build_manifest  # noqa: E402
from ccc_inventory.runner import FakeRunner  # noqa: E402

HOME = ROOT / "tests" / "fixtures" / "memory" / "home"
MEM = "~/.claude/projects/{}/memory/{}"


def memory() -> dict[str, Any]:
    section: dict[str, Any] = build_manifest(
        Context(home=HOME, cwd=HOME / "Code" / "b", runner=FakeRunner({}))
    )["memory"]
    return section


class StrayDirsTest(unittest.TestCase):
    def test_a_project_claude_memory_dir_is_reported_as_never_loaded(self) -> None:
        self.assertEqual(memory()["stray_dirs"], [{"path": "~/Code/a/.claude/memory", "files": 1}])


class DuplicatesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dupes: list[dict[str, Any]] = memory()["duplicates"]

    def test_same_body_or_same_name_across_projects_is_one_group(self) -> None:
        # a and b say the same thing under different names; c shares a's name with other wording.
        self.assertEqual(
            self.dupes,
            [
                {
                    "match": ["body", "name"],
                    "type": "feedback",
                    "files": [
                        MEM.format("-home-Code-a", "feedback-commits.md"),
                        MEM.format("-home-Code-b", "commit-style.md"),
                        MEM.format("-home-Code-c", "small-commits.md"),
                    ],
                    "projects": ["-home-Code-a", "-home-Code-b", "-home-Code-c"],
                }
            ],
        )

    def test_project_memories_are_not_duplicates_of_personal_ones(self) -> None:
        files = {f for d in self.dupes for f in d["files"]}
        self.assertNotIn(MEM.format("-home-Code-c", "deadline.md"), files)

    def test_a_group_spans_several_project_dirs(self) -> None:
        for d in self.dupes:
            self.assertGreater(len(d["projects"]), 1)


if __name__ == "__main__":
    unittest.main()
