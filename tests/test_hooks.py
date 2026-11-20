"""Hooks are listed from settings and installed plugins; the inventory never runs one."""

from __future__ import annotations

import subprocess
import sys
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from ccc_inventory import Context, build_manifest  # noqa: E402
from ccc_inventory.runner import FakeRunner  # noqa: E402

HOME = ROOT / "tests" / "fixtures" / "hooks" / "home"
APP = HOME / "Code" / "app"
PLUGIN_HOOK = '"${CLAUDE_PLUGIN_ROOT}/hello.sh"'


def hooks(runner: FakeRunner | None = None) -> dict[tuple[str, str], dict[str, Any]]:
    ctx = Context(home=HOME, cwd=APP, runner=runner or FakeRunner({}))
    return {(h["event"], h["command"]): h for h in build_manifest(ctx)["hooks"]}


class PluginHooksTest(unittest.TestCase):
    def test_hooks_shipped_by_installed_plugins_are_listed_with_their_plugin(self) -> None:
        hook = hooks()[("SessionStart", PLUGIN_HOOK)]
        self.assertEqual(hook["file"], "plugin greeter@local")
        self.assertEqual(hook["matcher"], "startup")
        self.assertTrue(hook["injects_context"])


class ListedNotRunTest(unittest.TestCase):
    def test_a_context_injecting_hook_is_listed_but_never_run(self) -> None:
        runner = FakeRunner({})
        hook = hooks(runner)[("SessionStart", "~/.claude/hooks/big.sh")]
        self.assertEqual(
            hook,
            {
                "event": "SessionStart",
                "matcher": "",
                "command": "~/.claude/hooks/big.sh",
                "file": "~/.claude/settings.json",
                "injects_context": True,
            },
        )
        self.assertEqual([c for c in runner.calls if c[0] != "claude"], [])

    def test_the_command_line_has_no_flag_to_run_hooks(self) -> None:
        script = str(ROOT / "scripts" / "inventory.py")
        done = subprocess.run(
            [sys.executable, script, "--home", str(HOME), "--cwd", str(APP), "--offline", "--dry-run-hooks"],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(done.returncode, 2)
        self.assertIn("unrecognized arguments: --dry-run-hooks", done.stderr)


if __name__ == "__main__":
    unittest.main()
