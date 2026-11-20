"""Opt-in sandboxed dry run of context-injecting hooks: output size and malformed JSON."""

from __future__ import annotations

import hashlib
import json
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from ccc_inventory import Context, build_manifest  # noqa: E402
from ccc_inventory.runner import CommandResult, FakeRunner, SubprocessRunner, sandbox_argv  # noqa: E402

HOME = ROOT / "tests" / "fixtures" / "hooks" / "home"
APP = HOME / "Code" / "app"
PLUGIN_HOOK = '"${CLAUDE_PLUGIN_ROOT}/hello.sh"'


def plain_shell(command: str, writable: Path) -> list[str]:
    return ["sh", "-c", command]


def hooks(dry_run: bool, runner: Any = None, home: Path = HOME) -> dict[tuple[str, str], dict[str, Any]]:
    ctx = Context(
        home=home,
        cwd=home / "Code" / "app",
        runner=runner or FakeRunner({}),
        dry_run_hooks=dry_run,
        hook_sandbox=plain_shell if runner is not None and isinstance(runner, FakeRunner) else sandbox_argv,
    )
    return {(h["event"], h["command"]): h for h in build_manifest(ctx)["hooks"]}


def hook_calls(runner: FakeRunner) -> list[tuple[str, ...]]:
    """Hook runs only; the plugin-cost probe (`claude plugin details`) is not a hook."""
    return [c for c in runner.calls if c[0] != "claude"]


def canned() -> FakeRunner:
    return FakeRunner(
        {
            ("sh", "-c", "~/.claude/hooks/big.sh"): CommandResult(0, "x" * 20000 + "\n"),
            ("sh", "-c", "~/.claude/hooks/bad-json.sh"): CommandResult(
                0, '{"hookSpecificOutput": {"additionalContext": "hi",}}'
            ),
            ("sh", "-c", "~/.claude/hooks/writes.sh"): CommandResult(0, "blocked\n"),
            ("sh", "-c", PLUGIN_HOOK): CommandResult(
                0, '{"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext": "hello"}}'
            ),
        }
    )


class PluginHooksTest(unittest.TestCase):
    def test_hooks_shipped_by_installed_plugins_are_listed_with_their_plugin(self) -> None:
        hook = hooks(False)[("SessionStart", PLUGIN_HOOK)]
        self.assertEqual(hook["file"], "plugin greeter@local")
        self.assertEqual(hook["matcher"], "startup")
        self.assertTrue(hook["injects_context"])


class OptInTest(unittest.TestCase):
    def test_nothing_runs_without_the_opt_in(self) -> None:
        runner = canned()
        found = hooks(False, runner)
        self.assertEqual(hook_calls(runner), [])
        self.assertEqual(
            found[("SessionStart", "~/.claude/hooks/big.sh")]["dry_run"],
            {"status": "not run: opt in with --dry-run-hooks"},
        )

    def test_hooks_whose_output_is_not_injected_never_run(self) -> None:
        runner = canned()
        found = hooks(True, runner)
        self.assertNotIn(("sh", "-c", "~/.claude/hooks/never-run.sh"), runner.calls)
        self.assertEqual(
            found[("PreToolUse", "~/.claude/hooks/never-run.sh")]["dry_run"],
            {"status": "not run: output not injected"},
        )


class TrustTest(unittest.TestCase):
    """Only hooks Claude Code would run unprompted: user settings and enabled plugins."""

    def setUp(self) -> None:
        self.runner = canned()
        self.found = hooks(True, self.runner)

    def test_project_hooks_never_run(self) -> None:
        hook = self.found[("SessionStart", "./project-hook.sh")]
        self.assertEqual(hook["file"], "~/Code/app/.claude/settings.json")
        self.assertEqual(
            hook["dry_run"],
            {"status": "not run: project hook; Claude Code runs it only in a trusted project"},
        )
        self.assertNotIn(("sh", "-c", "./project-hook.sh"), self.runner.calls)

    def test_hooks_of_a_disabled_plugin_never_run(self) -> None:
        # The project's settings enable it, but a project file can't vouch for code to run.
        hook = self.found[("SessionStart", '"${CLAUDE_PLUGIN_ROOT}/muted.sh"')]
        self.assertEqual(hook["dry_run"], {"status": "not run: plugin not enabled"})


class TimeoutTest(unittest.TestCase):
    def test_a_hook_timeout_is_honored_but_capped(self) -> None:
        from ccc_inventory.hooks import MAX_TIMEOUT_SECONDS, timeout_of

        self.assertEqual(timeout_of({"timeout": 5}), 5.0)
        self.assertEqual(timeout_of({"timeout": 600}), MAX_TIMEOUT_SECONDS)
        self.assertEqual(timeout_of({}), MAX_TIMEOUT_SECONDS)
        self.assertEqual(timeout_of({"timeout": True}), MAX_TIMEOUT_SECONDS)


class DryRunResultTest(unittest.TestCase):
    def setUp(self) -> None:
        self.found = hooks(True, canned())

    def test_an_oversized_hook_is_flagged_with_its_size(self) -> None:
        dry = self.found[("SessionStart", "~/.claude/hooks/big.sh")]["dry_run"]
        self.assertEqual(dry["status"], "ok")
        self.assertEqual(dry["bytes"], 20001)
        self.assertEqual(dry["approx_tokens"], 5001)
        self.assertTrue(dry["oversized"])
        self.assertEqual(dry["json"], "not json")

    def test_output_that_looks_like_json_but_does_not_parse_is_malformed(self) -> None:
        dry = self.found[("UserPromptSubmit", "~/.claude/hooks/bad-json.sh")]["dry_run"]
        self.assertEqual(dry["json"], "malformed")
        self.assertFalse(dry["oversized"])

    def test_valid_json_output_is_recognized(self) -> None:
        self.assertEqual(self.found[("SessionStart", PLUGIN_HOOK)]["dry_run"]["json"], "valid")

    def test_hook_output_never_reaches_the_manifest(self) -> None:
        text = json.dumps(list(self.found.values()))
        self.assertNotIn("xxxxxxxx", text)
        self.assertNotIn("additionalContext", text)

    def test_a_failing_hook_reports_its_exit_code(self) -> None:
        runner = FakeRunner({("sh", "-c", "~/.claude/hooks/big.sh"): CommandResult(2, "")})
        dry = hooks(True, runner)[("SessionStart", "~/.claude/hooks/big.sh")]["dry_run"]
        self.assertEqual(dry["status"], "exit 2")


def digest(root: Path) -> dict[str, str]:
    return {
        str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest()
        for f in sorted(root.rglob("*"))
        if f.is_file()
    }


@unittest.skipUnless(sys.platform == "darwin", "sandbox-exec is macOS only")
class RealSandboxTest(unittest.TestCase):
    """The real sandbox: hooks run, but can't write into the audited tree."""

    def test_real_dry_run_measures_output_and_leaves_the_tree_unchanged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            shutil.copytree(HOME, home)
            before = digest(home)
            found = hooks(True, SubprocessRunner(timeout_seconds=10), home=home)
            self.assertEqual(digest(home), before)
            self.assertFalse((home / ".claude" / "written-by-hook.txt").exists())
            self.assertFalse((home / ".claude" / "never-run-ran").exists())
        self.assertTrue(found[("SessionStart", "~/.claude/hooks/big.sh")]["dry_run"]["oversized"])
        self.assertEqual(
            found[("UserPromptSubmit", "~/.claude/hooks/bad-json.sh")]["dry_run"]["json"], "malformed"
        )
        self.assertEqual(found[("SessionStart", PLUGIN_HOOK)]["dry_run"]["json"], "valid")
        self.assertEqual(found[("PreCompact", "~/.claude/hooks/writes.sh")]["dry_run"]["status"], "ok")


@unittest.skipUnless(sys.platform == "darwin", "sandbox-exec is macOS only")
class SandboxProfileTest(unittest.TestCase):
    """No route out of the sandbox through other processes: launchd, LaunchServices, AppleEvents."""

    def run_sandboxed(self, command: str) -> str:
        with tempfile.TemporaryDirectory() as tmp:
            argv = sandbox_argv(command, Path(tmp))
            assert argv is not None
            return SubprocessRunner(timeout_seconds=10).run(argv).stdout

    def test_mach_services_are_unreachable(self) -> None:
        # `defaults read` is read-only and goes through the preferences daemon over Mach.
        probe = "defaults read -g AppleLocale >/dev/null 2>&1 && echo reachable || echo blocked"
        self.assertEqual(self.run_sandboxed(probe), "blocked\n")

    def test_the_profile_denies_launching_apps_and_sending_apple_events(self) -> None:
        argv = sandbox_argv("true", Path("/nonexistent"))
        assert argv is not None
        for rule in ("(deny mach-lookup)", "(deny lsopen)", "(deny appleevent-send)", "(deny network*)"):
            self.assertIn(rule, argv[2])

    def test_ordinary_tools_still_work(self) -> None:
        self.assertEqual(self.run_sandboxed("python3 -c 'print(6*7)'"), "42\n")


class CommandLineTest(unittest.TestCase):
    def run_cli(self, *flags: str) -> dict[tuple[str, str], dict[str, Any]]:
        import subprocess

        done = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "inventory.py"),
                "--home",
                str(HOME),
                "--cwd",
                str(APP),
                *flags,
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        return {(h["event"], h["command"]): h for h in json.loads(done.stdout)["hooks"]}

    def test_offline_wins_over_the_dry_run_flag(self) -> None:
        dry = self.run_cli("--offline", "--dry-run-hooks")[("SessionStart", "~/.claude/hooks/big.sh")][
            "dry_run"
        ]
        self.assertEqual(dry, {"status": "not run: opt in with --dry-run-hooks"})

    @unittest.skipUnless(sys.platform == "darwin", "sandbox-exec is macOS only")
    def test_the_flag_turns_the_dry_run_on(self) -> None:
        dry = self.run_cli("--dry-run-hooks")[("SessionStart", "~/.claude/hooks/big.sh")]["dry_run"]
        self.assertTrue(dry["oversized"])


class NoSandboxTest(unittest.TestCase):
    def test_without_a_sandbox_nothing_runs(self) -> None:
        runner = canned()
        ctx = Context(
            home=HOME, cwd=APP, runner=runner, dry_run_hooks=True, hook_sandbox=lambda command, writable: None
        )
        found = {(h["event"], h["command"]): h for h in build_manifest(ctx)["hooks"]}
        self.assertEqual(hook_calls(runner), [])
        self.assertEqual(
            found[("SessionStart", "~/.claude/hooks/big.sh")]["dry_run"],
            {"status": "not run: no sandbox on this platform"},
        )


if __name__ == "__main__":
    unittest.main()
