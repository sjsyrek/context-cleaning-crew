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
from ccc_inventory.runner import CommandResult, FakeRunner  # noqa: E402

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


BD_VERSION = CommandResult(0, "bd version 1.4.0 (Homebrew)\n")
BD_STATS = CommandResult(0, "Total: 12\nOpen: 3\nClosed: 9\n")
REFRESH = ("claude", "plugin", "marketplace", "update")


def online_manifest(refresh: bool = False) -> tuple[dict[str, Any], FakeRunner]:
    runner = FakeRunner(
        {("bd", "--version"): BD_VERSION, ("bd", "stats"): BD_STATS, REFRESH: CommandResult(0, "")}
    )
    ctx = Context(
        home=FIXTURE_HOME,
        cwd=FIXTURE_CWD,
        runner=runner,
        refresh_marketplaces=refresh,
        run_trackers=True,
    )
    return build_manifest(ctx), runner


class VersionDriftTest(unittest.TestCase):
    def test_plugin_behind_its_marketplace_is_reported(self) -> None:
        drift = {d["plugin"]: d for d in manifest()["drift"]["marketplace"]}
        self.assertEqual(drift["beads@beads-marketplace"]["installed"], "1.3.4")
        self.assertEqual(drift["beads@beads-marketplace"]["available"], "1.3.5")
        self.assertEqual(drift["beads@beads-marketplace"]["status"], "behind")

    def test_remote_source_version_is_unknown_not_current(self) -> None:
        drift = {d["plugin"]: d for d in manifest()["drift"]["marketplace"]}
        self.assertEqual(drift["code-simplifier@claude-plugins-official"]["status"], "unknown")

    def test_marketplaces_are_refreshed_before_comparing_only_when_asked(self) -> None:
        m, runner = online_manifest(refresh=True)
        self.assertEqual(runner.calls[0], REFRESH)
        self.assertTrue(m["drift"]["refreshed"])
        m, runner = online_manifest(refresh=False)
        self.assertNotIn(REFRESH, runner.calls)
        self.assertFalse(m["drift"]["refreshed"])

    def test_plugin_behind_the_cli_it_wraps_is_reported(self) -> None:
        m, _ = online_manifest()
        cli = {d["plugin"]: d for d in m["drift"]["cli"]}
        self.assertEqual(cli["beads@beads-marketplace"]["cli_version"], "1.4.0")
        self.assertEqual(cli["beads@beads-marketplace"]["plugin_version"], "1.3.4")
        self.assertEqual(cli["beads@beads-marketplace"]["status"], "differs")

    def test_offline_run_skips_cli_probes(self) -> None:
        cli = {d["plugin"]: d for d in manifest()["drift"]["cli"]}
        self.assertEqual(cli["beads@beads-marketplace"]["status"], "not checked")


class MarketplacesTest(unittest.TestCase):
    def test_marketplace_with_no_installed_plugins_is_flagged(self) -> None:
        self.assertEqual(manifest()["marketplaces"]["unused"], ["empty-mkt"])


class BuiltinOverlapTest(unittest.TestCase):
    def test_plugin_replaced_by_a_builtin_skill_is_flagged(self) -> None:
        hits = {(o["plugin"], o["builtin"]) for o in manifest()["overlap"]["builtin"]}
        self.assertIn(("code-simplifier@claude-plugins-official", "/simplify"), hits)
        self.assertNotIn("beads@beads-marketplace", {p for p, _ in hits})


class TrackerCountsTest(unittest.TestCase):
    def test_tracker_count_uses_the_command_that_includes_closed_items(self) -> None:
        m, runner = online_manifest()
        counts = m["counts"]
        self.assertEqual(len(counts), 1)
        self.assertEqual(counts[0]["tracker"], "beads")
        self.assertEqual(counts[0]["command"], "bd stats")
        self.assertEqual(counts[0]["avoid"], "bd list")
        self.assertIn("Closed: 9", counts[0]["output"])
        self.assertNotIn(("bd", "list"), runner.calls)

    def test_tracker_commands_do_not_run_unless_allowed(self) -> None:
        counts = manifest()["counts"]
        self.assertEqual(counts[0]["output"], "")
        self.assertEqual(counts[0]["status"], "not run")


DETAILS = """beads 1.3.4
  Source: beads@beads-marketplace

Component inventory
  Skills (2)  beads, list
  Hooks (1)

Projected token cost
  Always-on:   ~1.2k tok   added to every session

Per-component (rounded)
  component  always-on  on-invoke
  beads           ~900      ~5.6k
  list            ~300       ~220
"""


class PluginCostTest(unittest.TestCase):
    def test_token_cost_is_parsed_from_plugin_details(self) -> None:
        runner = FakeRunner(
            {("claude", "plugin", "details", "beads@beads-marketplace"): CommandResult(0, DETAILS)}
        )
        m = build_manifest(Context(home=FIXTURE_HOME, cwd=FIXTURE_CWD, runner=runner))
        cost = {p["id"]: p["cost"] for p in m["plugins"]["installed"]}
        self.assertEqual(cost["beads@beads-marketplace"]["always_on"], 1200)
        self.assertEqual(
            cost["beads@beads-marketplace"]["components"],
            [
                {"component": "beads", "always_on": 900, "on_invoke": 5600},
                {"component": "list", "always_on": 300, "on_invoke": 220},
            ],
        )

    def test_cost_is_marked_not_checked_offline(self) -> None:
        cost = {p["id"]: p["cost"] for p in manifest()["plugins"]["installed"]}
        self.assertEqual(cost["beads@beads-marketplace"], {"status": "not checked"})


class HooksTest(unittest.TestCase):
    def test_context_injecting_hooks_are_marked(self) -> None:
        hooks = {(h["event"], h["command"]): h for h in manifest()["hooks"]}
        self.assertTrue(hooks[("SessionStart", "bd prime")]["injects_context"])
        self.assertFalse(hooks[("PreToolUse", "~/.claude/hooks/guard.sh")]["injects_context"])
        self.assertEqual(hooks[("PreToolUse", "~/.claude/hooks/guard.sh")]["matcher"], "Bash")


class SkillUsageTest(unittest.TestCase):
    def test_usage_counts_and_last_used_dates_are_recorded(self) -> None:
        usage = {u["skill"]: u for u in manifest()["usage"]["skills"]}
        self.assertEqual(
            usage["old-council"], {"skill": "old-council", "count": 3, "last_used": "2023-11-14"}
        )


class McpServersTest(unittest.TestCase):
    def test_servers_with_the_same_url_are_grouped_as_duplicates(self) -> None:
        dupes = manifest()["mcp"]["duplicates"]
        self.assertEqual(
            dupes, [{"target": "https://api.example.invalid/mcp", "servers": ["github", "github-sse"]}]
        )

    def test_deprecated_sse_transport_is_flagged(self) -> None:
        self.assertEqual(
            manifest()["mcp"]["deprecated_transport"], [{"server": "github-sse", "transport": "sse"}]
        )


class FreeTextPathTest(unittest.TestCase):
    def test_absolute_home_path_in_free_text_becomes_tilde(self) -> None:
        ctx = Context(home=FIXTURE_HOME, cwd=FIXTURE_CWD, runner=FakeRunner({}))
        text = f'"{FIXTURE_HOME}/.config/tool" run --dir={FIXTURE_HOME}'
        self.assertEqual(ctx.redact(text), '"~/.config/tool" run --dir=~')


def tree_digest(root: Path) -> dict[str, str]:
    import hashlib

    return {
        str(f.relative_to(root)): hashlib.sha256(f.read_bytes()).hexdigest()
        for f in sorted(root.rglob("*"))
        if f.is_file()
    }


class ReadOnlyRunTest(unittest.TestCase):
    """Report mode's inventory run must leave the audited tree byte-identical."""

    def test_cli_run_writes_only_the_out_file_and_leaves_the_home_untouched(self) -> None:
        import shutil
        import subprocess
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            shutil.copytree(FIXTURE_HOME, home)
            before = tree_digest(home)
            out = Path(tmp) / "reports" / "nested" / "manifest.json"
            done = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "inventory.py"),
                    "--home",
                    str(home),
                    "--cwd",
                    str(home / "Code" / "proj"),
                    "--offline",
                    "--out",
                    str(out),
                ],
                capture_output=True,
                text=True,
                check=True,
            )
            self.assertEqual(tree_digest(home), before)
            self.assertEqual(json.loads(out.read_text())["schema_version"], 1)
            self.assertEqual(done.stdout.strip(), f"wrote {out}")


class NotLiveSetupTest(unittest.TestCase):
    """`claude plugin ...` and CLI probes describe the live install, so they must not leak into
    an audit of another home (a backup, a copy, a fixture)."""

    def setUp(self) -> None:
        self.runner = FakeRunner(
            {
                ("claude", "plugin", "details", "beads@beads-marketplace"): CommandResult(0, DETAILS),
                ("bd", "--version"): BD_VERSION,
                REFRESH: CommandResult(0, ""),
            }
        )
        ctx = Context(
            home=FIXTURE_HOME, cwd=FIXTURE_CWD, runner=self.runner, refresh_marketplaces=True, live=False
        )
        self.m = build_manifest(ctx)

    def test_no_live_only_command_runs(self) -> None:
        self.assertEqual([c for c in self.runner.calls if c[0] in ("claude", "bd")], [])

    def test_costs_and_cli_versions_say_why_they_were_not_checked(self) -> None:
        for plugin in self.m["plugins"]["installed"]:
            self.assertEqual(plugin["cost"], {"status": "not checked: not the live setup"})
        self.assertEqual({d["status"] for d in self.m["drift"]["cli"]}, {"not checked: not the live setup"})
        self.assertFalse(self.m["drift"]["refreshed"])

    def test_manifest_records_whether_it_describes_the_live_setup(self) -> None:
        self.assertFalse(self.m["live_setup"])
        self.assertTrue(manifest()["live_setup"])

    def test_cli_marks_a_home_other_than_the_real_one_as_not_live(self) -> None:
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
        self.assertFalse(json.loads(done.stdout)["live_setup"])


def fake_which(installed: set[str]) -> Any:
    return lambda name: f"/usr/local/bin/{name}" if name in installed else None


class StalenessFactsTest(unittest.TestCase):
    """Cheap, read-only facts the memory curator checks memory claims against."""

    def test_tools_named_in_memory_are_looked_up_on_path_without_running_them(self) -> None:
        runner = FakeRunner({})
        ctx = Context(home=FIXTURE_HOME, cwd=FIXTURE_CWD, runner=runner, which=fake_which({"bd", "npm"}))
        tools = {t["name"]: t for t in build_manifest(ctx)["facts"]["tools"]}
        self.assertEqual(sorted(tools), ["bd", "frobnicatectl", "npm"])
        self.assertTrue(tools["bd"]["on_path"])
        self.assertFalse(tools["frobnicatectl"]["on_path"])
        self.assertEqual(
            tools["frobnicatectl"]["mentioned_in"], ["~/.claude/projects/-home-Code-proj/memory/tooling.md"]
        )
        live_probes = {("claude", "plugin", "details"), ("bd", "--version")}
        self.assertEqual(
            [c for c in runner.calls if tuple(c[:3]) not in live_probes and tuple(c[:2]) not in live_probes],
            [],
        )

    def test_git_remotes_of_the_working_tree_are_read_from_its_config_file(self) -> None:
        import shutil
        import tempfile

        with tempfile.TemporaryDirectory() as tmp:
            home = Path(tmp) / "home"
            shutil.copytree(FIXTURE_HOME, home)
            git = home / "Code" / "proj" / ".git"
            git.mkdir()
            (git / "config").write_text(
                '[core]\n\tbare = false\n[remote "origin"]\n'
                "\turl = https://x:ghp_FAKEFAKEFAKEFAKEFAKEFAKE1234@example.invalid/proj.git\n"
                '[remote "backup"]\n\turl = ~/backups/proj.git\n'
            )
            ctx = Context(home=home, cwd=home / "Code" / "proj", runner=FakeRunner({}))
            facts = build_manifest(ctx)["facts"]
        self.assertEqual(
            facts["git"],
            [
                {
                    "repo": "~/Code/proj",
                    "remotes": [
                        {"name": "backup", "url": "~/backups/proj.git"},
                        {
                            "name": "origin",
                            "url": "https://<redacted:userinfo>@example.invalid/proj.git",
                        },
                    ],
                }
            ],
        )

    def test_a_working_tree_without_git_has_no_git_facts(self) -> None:
        self.assertEqual(manifest()["facts"]["git"], [])


class RemoteUrlCredentialsTest(unittest.TestCase):
    def test_userinfo_and_query_strings_are_masked_whatever_the_token_format(self) -> None:
        from ccc_inventory.facts import mask_url

        self.assertEqual(
            mask_url("https://alice:hunter2@git.example.invalid/p.git"),
            "https://<redacted:userinfo>@git.example.invalid/p.git",
        )
        self.assertEqual(
            mask_url("https://glpat-abc123@gitlab.example.invalid/p.git"),
            "https://<redacted:userinfo>@gitlab.example.invalid/p.git",
        )
        self.assertEqual(
            mask_url("https://h.example.invalid/p.git?private_token=abc"),
            "https://h.example.invalid/p.git?<redacted:query>",
        )
        self.assertEqual(mask_url("git@github.com:owner/repo.git"), "git@github.com:owner/repo.git")
        self.assertEqual(mask_url("~/backups/proj.git"), "~/backups/proj.git")


if __name__ == "__main__":
    unittest.main()
