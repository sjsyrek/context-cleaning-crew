"""Behavioral tests for the inventory script against the synthetic `messy` home."""

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

FIXTURE_HOME = ROOT / "tests" / "fixtures" / "messy" / "home"
FIXTURE_CWD = FIXTURE_HOME / "Code" / "proj"


def manifest() -> dict[str, Any]:
    ctx = Context(home=FIXTURE_HOME, cwd=FIXTURE_CWD, runner=FakeRunner({}))
    return build_manifest(ctx)


def kinds(findings: list[dict[str, Any]], kind: str) -> list[dict[str, Any]]:
    return [f for f in findings if f["kind"] == kind]


class PermissionPostureTest(unittest.TestCase):
    def setUp(self) -> None:
        self.findings: list[dict[str, Any]] = manifest()["permissions"]["findings"]

    def test_blanket_bash_allow_with_accept_edits_is_flagged(self) -> None:
        hits = kinds(self.findings, "blanket-allow-with-permissive-mode")
        self.assertEqual(len(hits), 1)
        self.assertEqual(hits[0]["rule"], "Bash")
        self.assertEqual(hits[0]["mode"], "acceptEdits")

    def test_allow_rules_covered_by_a_broader_rule_are_flagged(self) -> None:
        redundant = {(f["rule"], f["covered_by"]) for f in kinds(self.findings, "redundant-allow")}
        self.assertIn(("Bash(git status:*)", "Bash"), redundant)
        # A project rule is redundant under a user-scope blanket allow too.
        self.assertIn(("Bash(npm test:*)", "Bash"), redundant)
        self.assertNotIn("Read", {r for r, _ in redundant})

    def test_rules_matching_no_tool_are_flagged(self) -> None:
        dead = {f["rule"]: f["reason"] for f in kinds(self.findings, "rule-matches-no-tool")}
        self.assertEqual(dead.get("Frobnicate"), "unknown tool")
        self.assertEqual(dead.get("mcp__ghost__search"), "MCP server not configured")
        self.assertEqual(dead.get("mcp__plugin_gone_server__tool"), "plugin not installed")
        self.assertNotIn("mcp__github", dead)
        self.assertNotIn("WebFetch(domain:example.com)", dead)


class SettingsTest(unittest.TestCase):
    def test_reasoning_affecting_env_vars_are_listed(self) -> None:
        keys = {e["key"] for e in manifest()["settings"]["reasoning_env"]}
        self.assertEqual(keys, {"MAX_THINKING_TOKENS", "CLAUDE_CODE_DISABLE_THINKING", "REASONING_PROXY_KEY"})

    def test_dangling_enable_flag_is_flagged(self) -> None:
        dangling = manifest()["plugins"]["dangling_enabled"]
        self.assertEqual(dangling, ["ghost@nowhere"])


class SecretsTest(unittest.TestCase):
    def test_planted_secrets_are_found_by_file_key_and_type(self) -> None:
        found = {(s["file"], s["key"], s["type"]) for s in manifest()["secrets"]}
        self.assertIn(("~/.claude/settings.json", "env.GITHUB_TOKEN", "github-token"), found)
        self.assertIn(("~/.claude.json", "mcpServers.github.headers.Authorization", "slack-token"), found)

    def test_secrets_in_rules_and_instruction_files_are_found(self) -> None:
        found = {(s["file"], s["key"], s["type"]) for s in manifest()["secrets"]}
        self.assertIn(("~/.claude/settings.json", "permissions.allow[9]", "github-token"), found)
        self.assertIn(("~/.claude/settings.json", "env.REASONING_PROXY_KEY", "api-key-sk"), found)
        self.assertIn(("~/Code/proj/CLAUDE.md", "line 4", "slack-token"), found)

    def test_free_text_fields_carry_a_redaction_marker_instead_of_the_value(self) -> None:
        m = manifest()
        rules = [r["rule"] for r in m["permissions"]["rules"]]
        self.assertTrue(any("<redacted:github-token>" in r for r in rules))
        lines = [d["text"] for d in m["instructions"]["directives"]]
        self.assertTrue(any("<redacted:slack-token>" in t for t in lines))
        env = {e["key"]: e["value"] for e in m["settings"]["reasoning_env"]}
        self.assertEqual(env["REASONING_PROXY_KEY"], "<redacted:api-key-sk>")

    def test_no_secret_value_appears_in_the_manifest(self) -> None:
        text = json.dumps(manifest())
        self.assertNotIn("FAKEFAKE", text)
        self.assertNotIn("ghp_", text)
        self.assertNotIn("xoxb-", text)


class InstructionFilesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.instructions: dict[str, Any] = manifest()["instructions"]

    def test_claude_and_agents_files_are_found_at_every_level(self) -> None:
        paths = [f["path"] for f in self.instructions["files"]]
        self.assertEqual(
            paths,
            [
                "~/.claude/CLAUDE.md",
                "~/CLAUDE.md",
                "~/Code/AGENTS.md",
                "~/Code/proj/CLAUDE.md",
            ],
        )
        for f in self.instructions["files"]:
            self.assertEqual(f["approx_tokens"], (f["bytes"] + 3) // 4)

    def test_home_directory_claude_md_is_flagged_as_de_facto_global(self) -> None:
        self.assertEqual(self.instructions["home_dir_global"], ["~/CLAUDE.md"])

    def test_directives_are_extracted_with_location(self) -> None:
        texts = {(d["path"], d["text"]) for d in self.instructions["directives"]}
        self.assertIn(("~/.claude/CLAUDE.md", "Always git push after every commit."), texts)
        self.assertIn(("~/Code/AGENTS.md", "Push only when asked."), texts)

    def test_instruction_contradicting_a_deny_rule_is_flagged(self) -> None:
        conflicts = self.instructions["deny_conflicts"]
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["path"], "~/Code/proj/CLAUDE.md")
        self.assertEqual(conflicts[0]["deny_rule"], "Bash(rm -rf:*)")

    def test_procedural_section_is_a_move_candidate(self) -> None:
        moves = self.instructions["move_candidates"]
        self.assertEqual(
            [(m["path"], m["heading"], m["steps"]) for m in moves],
            [("~/Code/proj/CLAUDE.md", "Release procedure", 6)],
        )


class RemovedToolsTest(unittest.TestCase):
    def test_removed_tools_in_user_skills_are_flagged(self) -> None:
        refs = manifest()["removed_tool_refs"]
        skill = {r["tool"] for r in refs if r["path"] == "~/.claude/skills/old-council/SKILL.md"}
        self.assertEqual(
            skill,
            {"TeamCreate", "TeamDelete", "TaskOutput", "Agent run_in_background", 'SendMessage to "*"'},
        )

    def test_todo_tools_are_flagged_with_their_condition(self) -> None:
        refs = [r for r in manifest()["removed_tool_refs"] if r["path"] == "~/.claude/commands/todo.md"]
        self.assertEqual(len(refs), 1)
        self.assertEqual(refs[0]["tool"], "TodoWrite")
        self.assertIn("CLAUDE_CODE_ENABLE_TODO_TOOLS", refs[0]["condition"])

    def test_clean_agent_has_no_hits(self) -> None:
        paths = {r["path"] for r in manifest()["removed_tool_refs"]}
        self.assertNotIn("~/.claude/agents/clean-agent.md", paths)


class MemoryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.dirs: list[dict[str, Any]] = manifest()["memory"]["dirs"]

    def test_index_links_to_missing_files_are_reported(self) -> None:
        self.assertEqual(self.dirs[0]["broken_links"], ["missing-file.md"])

    def test_memory_that_reads_as_global_is_flagged_with_its_scope(self) -> None:
        self.assertEqual(self.dirs[0]["project_dir"], "-home-Code-proj")
        self.assertEqual(self.dirs[0]["global_looking"], ["prefers-terse.md"])


class StabilityTest(unittest.TestCase):
    def test_manifest_is_byte_stable_across_runs(self) -> None:
        a = json.dumps(manifest(), sort_keys=True)
        b = json.dumps(manifest(), sort_keys=True)
        self.assertEqual(a, b)

    def test_manifest_never_contains_the_absolute_home_path(self) -> None:
        self.assertNotIn(str(FIXTURE_HOME), json.dumps(manifest()))


if __name__ == "__main__":
    unittest.main()


class CommandLineTest(unittest.TestCase):
    def test_cli_prints_the_manifest_as_sorted_json(self) -> None:
        import subprocess

        done = subprocess.run(
            [
                sys.executable,
                str(ROOT / "scripts" / "inventory.py"),
                "--home",
                str(FIXTURE_HOME),
                "--cwd",
                str(FIXTURE_CWD),
                "--offline",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
        data = json.loads(done.stdout)
        self.assertEqual(data["schema_version"], 1)
        self.assertEqual(done.stdout, json.dumps(data, sort_keys=True, indent=2) + "\n")
