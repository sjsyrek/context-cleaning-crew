"""Commands the skill tells Claude to run must match a headless allowlist as written.

Under `--permission-mode dontAsk`, Claude Code won't match a command that contains a shell
expansion such as `$PWD` against a `Bash(...)` allow rule, so the run is denied. Only
`${CLAUDE_SKILL_DIR}`, which Claude Code substitutes before the model sees the text, may appear.
"""

from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from ccc_inventory.options import Options

SKILL = Path(__file__).resolve().parent.parent / "skills" / "context-cleaning-crew"
FENCE = re.compile(r"```sh\n(.*?)```", re.DOTALL)
SUBSTITUTED = "${CLAUDE_SKILL_DIR}"


def commands() -> dict[str, list[str]]:
    """Shell blocks of the files whose commands Claude itself runs."""
    files = [SKILL / "SKILL.md", SKILL / "references" / "executor-rules.md"]
    return {f.name: FENCE.findall(f.read_text(encoding="utf-8")) for f in files}


class SkillCommandsTest(unittest.TestCase):
    def test_the_skill_has_commands_to_check(self) -> None:
        self.assertGreaterEqual(len(commands()["SKILL.md"]), 2)

    def test_no_command_relies_on_shell_expansion(self) -> None:
        for name, blocks in commands().items():
            for block in blocks:
                self.assertNotIn("$", block.replace(SUBSTITUTED, ""), msg=f"{name}: {block.strip()}")


class RoutineSetupTest(unittest.TestCase):
    def test_every_documented_headless_command_allows_writes_to_the_default_report_dir(self) -> None:
        text = (SKILL / "references" / "routine-setup.md").read_text(encoding="utf-8")
        runs = [line for line in text.splitlines() if "claude -p" in line]
        rules = re.findall(r"'Edit\(([^)]*)\)'", text)
        self.assertEqual(len(runs), 3)  # the command, launchd and cron
        self.assertEqual(len(rules), 3)
        self.assertEqual(set(rules), {Options().report_dir + "**"})


if __name__ == "__main__":
    unittest.main()
