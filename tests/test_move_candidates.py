"""Procedural CLAUDE.md sections that belong in an on-demand skill (`move`)."""

from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from ccc_inventory import Context  # noqa: E402
from ccc_inventory.instructions import move_candidates  # noqa: E402
from ccc_inventory.runner import FakeRunner  # noqa: E402

CTX = Context(home=ROOT, cwd=ROOT, runner=FakeRunner({}))

# Shaped like the sections a manual cleanup turned into `release` and `pr-description` skills.
TEXT = """# Preferences

### Test-Driven Development

1. Write a failing test.
2. Make it pass.
3. Refactor.
4. Commit.

### When Cutting a Release

1. Move Unreleased entries into a dated section.
2. Bump the version.
3. Tag.
4. Push.

## Pull Request Guidelines

Describe the change.

1. Summary.
2. Motivation.
3. Testing.
4. Risks.

### Merge strategy

1. Rebase.
2. Squash.

## Long procedure

1. a
2. b
3. c
4. d
5. e
"""


def found() -> dict[str, dict[str, object]]:
    return {str(m["heading"]): m for m in move_candidates(CTX, "~/CLAUDE.md", TEXT)}


class MoveCandidatesTest(unittest.TestCase):
    def test_a_short_procedure_is_left_to_the_reviewer_whatever_its_heading(self) -> None:
        # Whether a heading names a one-off task is judgment: the reviewer's checklist covers it.
        self.assertNotIn("When Cutting a Release", found())
        self.assertNotIn("Pull Request Guidelines", found())

    def test_five_or_more_steps_qualify_under_any_heading(self) -> None:
        self.assertEqual(found()["Long procedure"]["why"], "5 ordered steps")

    def test_an_always_on_rule_list_is_not_a_candidate(self) -> None:
        self.assertNotIn("Test-Driven Development", found())

    def test_two_steps_are_too_few(self) -> None:
        self.assertNotIn("Merge strategy", found())

    def test_a_candidate_lists_its_location_and_step_count(self) -> None:
        self.assertEqual(
            found()["Long procedure"],
            {
                "path": "~/CLAUDE.md",
                "line": 31,
                "heading": "Long procedure",
                "steps": 5,
                "why": "5 ordered steps",
            },
        )


if __name__ == "__main__":
    unittest.main()
