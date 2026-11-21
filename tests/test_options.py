"""Plugin options: declared in plugin.json `userConfig`, read from `pluginConfigs` in settings."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from ccc_inventory.options import DEFAULTS, Options, load_options, mode_flags  # noqa: E402

PLUGIN_JSON = ROOT / ".claude-plugin" / "plugin.json"


def write_settings(directory: Path, name: str, configs: dict[str, Any]) -> Path:
    path = directory / name
    path.write_text(json.dumps({"pluginConfigs": configs}))
    return path


class DeclaredOptionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.declared: dict[str, Any] = json.loads(PLUGIN_JSON.read_text())["userConfig"]

    def test_plugin_json_declares_exactly_the_options_the_loader_knows(self) -> None:
        self.assertEqual(sorted(self.declared), sorted(DEFAULTS.as_dict()))

    def test_declared_defaults_match_the_loader_defaults(self) -> None:
        for key, value in DEFAULTS.as_dict().items():
            self.assertEqual(self.declared[key].get("default"), value, key)

    def test_the_default_report_dir_is_outside_the_claude_config_dir(self) -> None:
        # Headless runs can't Write under ~/.claude whatever the allow rules say, so a report
        # there would never be saved by a scheduled run.
        report_dir = Options().report_dir
        self.assertFalse(report_dir.startswith("~/.claude/"), report_dir)
        self.assertTrue(report_dir.startswith("~/"), report_dir)

    def test_every_option_has_a_title_description_and_supported_type(self) -> None:
        for key, spec in self.declared.items():
            self.assertTrue(spec.get("title"), key)
            self.assertTrue(spec.get("description"), key)
            self.assertIn(spec["type"], ("string", "number", "boolean", "directory", "file"), key)
            self.assertFalse(spec.get("sensitive", False), key)

    def test_list_options_are_multiple_strings(self) -> None:
        for key in ("preferred_marketplaces", "protected", "extra_secret_patterns"):
            self.assertEqual(self.declared[key]["type"], "string", key)
            self.assertTrue(self.declared[key].get("multiple"), key)

    def test_seat_model_is_a_closed_choice_that_includes_inherit(self) -> None:
        self.assertIn("inherit", self.declared["full_mode_models"]["options"])
        self.assertIn("sonnet", self.declared["full_mode_models"]["options"])


class LoadOptionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def test_no_settings_means_every_default_with_default_as_source(self) -> None:
        loaded = load_options([self.dir / "missing.json"])
        self.assertEqual(loaded.options, DEFAULTS)
        self.assertEqual(set(loaded.sources.values()), {"default"})
        self.assertEqual(loaded.warnings, [])

    def test_values_are_read_for_the_plugin_whatever_its_marketplace(self) -> None:
        path = write_settings(
            self.dir,
            "settings.json",
            {
                "context-cleaning-crew@claude-plugins": {
                    "options": {"preferred_marketplaces": ["internal", "official"], "usage_window_days": 30}
                },
                "other-plugin@x": {"options": {"usage_window_days": 7}},
            },
        )
        loaded = load_options([path])
        self.assertEqual(loaded.options.preferred_marketplaces, ("internal", "official"))
        self.assertEqual(loaded.options.usage_window_days, 30)
        self.assertEqual(loaded.sources["usage_window_days"], str(path))
        self.assertEqual(loaded.sources["protected"], "default")

    def test_a_later_source_overrides_an_earlier_one(self) -> None:
        user = write_settings(
            self.dir, "user.json", {"context-cleaning-crew@m": {"options": {"protected": ["a"]}}}
        )
        managed = write_settings(
            self.dir, "managed.json", {"context-cleaning-crew@m": {"options": {"protected": ["b"]}}}
        )
        loaded = load_options([user, managed])
        self.assertEqual(loaded.options.protected, ("b",))
        self.assertEqual(loaded.sources["protected"], str(managed))

    def test_a_wrongly_typed_value_falls_back_to_the_default_with_a_warning(self) -> None:
        path = write_settings(
            self.dir,
            "settings.json",
            {
                "context-cleaning-crew@m": {
                    "options": {"usage_window_days": "ninety", "mine_transcripts": "yes", "protected": 5}
                }
            },
        )
        loaded = load_options([path])
        self.assertEqual(loaded.options.usage_window_days, 90)
        self.assertFalse(loaded.options.mine_transcripts)
        self.assertEqual(loaded.options.protected, ())
        self.assertEqual(len(loaded.warnings), 3)

    def test_a_single_string_for_a_list_option_becomes_a_one_item_list(self) -> None:
        # The config dialog may save one entry of a `multiple` field as a plain string.
        path = write_settings(
            self.dir, "settings.json", {"context-cleaning-crew@m": {"options": {"protected": "beads"}}}
        )
        self.assertEqual(load_options([path]).options.protected, ("beads",))

    def test_an_unknown_seat_model_falls_back_with_a_warning(self) -> None:
        path = write_settings(
            self.dir, "settings.json", {"context-cleaning-crew@m": {"options": {"full_mode_models": "gpt"}}}
        )
        loaded = load_options([path])
        self.assertEqual(loaded.options.full_mode_models, "sonnet")
        self.assertEqual(len(loaded.warnings), 1)

    def test_an_invalid_secret_pattern_is_dropped_with_a_warning_and_the_rest_kept(self) -> None:
        path = write_settings(
            self.dir,
            "settings.json",
            {
                "context-cleaning-crew@m": {
                    "options": {"extra_secret_patterns": ["acme_[a-z]{8,}", "(unclosed"]}
                }
            },
        )
        loaded = load_options([path])
        self.assertEqual(loaded.options.extra_secret_patterns, ("acme_[a-z]{8,}",))
        self.assertEqual(len(loaded.warnings), 1)
        self.assertNotIn("(unclosed", loaded.warnings[0])  # a pattern could itself be sensitive

    def test_a_zero_or_negative_window_falls_back(self) -> None:
        path = write_settings(
            self.dir, "settings.json", {"context-cleaning-crew@m": {"options": {"usage_window_days": 0}}}
        )
        self.assertEqual(load_options([path]).options.usage_window_days, 90)

    def test_unknown_keys_are_ignored_with_a_warning(self) -> None:
        path = write_settings(
            self.dir, "settings.json", {"context-cleaning-crew@m": {"options": {"colour": "blue"}}}
        )
        loaded = load_options([path])
        self.assertEqual(loaded.options, DEFAULTS)
        self.assertEqual(len(loaded.warnings), 1)

    def test_malformed_settings_are_skipped(self) -> None:
        path = self.dir / "settings.json"
        path.write_text("{not json")
        self.assertEqual(load_options([path]).options, DEFAULTS)


class OptionsTypeTest(unittest.TestCase):
    def test_options_are_immutable(self) -> None:
        with self.assertRaises(AttributeError):
            DEFAULTS.usage_window_days = 1  # type: ignore[misc]

    def test_as_dict_uses_json_types(self) -> None:
        d = Options(protected=("a",)).as_dict()
        self.assertEqual(d["protected"], ["a"])
        json.dumps(d)


FIXTURE_HOME = ROOT / "tests" / "fixtures" / "messy" / "home"
FIXTURE_CWD = FIXTURE_HOME / "Code" / "proj"
INVENTORY = ROOT / "scripts" / "inventory.py"


def run_inventory(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(INVENTORY), "--home", str(FIXTURE_HOME), "--cwd", str(FIXTURE_CWD), *args],
        capture_output=True,
        text=True,
        check=True,
    )


class ManifestOptionsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self.tmp.name)

    def tearDown(self) -> None:
        self.tmp.cleanup()

    def settings(self, options: dict[str, Any]) -> Path:
        return write_settings(self.dir, "settings.json", {"context-cleaning-crew@m": {"options": options}})

    def test_manifest_records_effective_options_with_their_source(self) -> None:
        path = self.settings({"protected": ["beads"], "colour": "blue"})
        data = json.loads(run_inventory("--offline", "--options-settings", str(path)).stdout)
        self.assertEqual(data["options"]["values"]["protected"], ["beads"])
        self.assertEqual(data["options"]["values"]["usage_window_days"], 90)
        self.assertEqual(data["options"]["sources"]["protected"], str(path))
        self.assertEqual(data["options"]["sources"]["report_dir"], "default")
        self.assertEqual(len(data["options"]["warnings"]), 1)

    def test_extra_secret_patterns_from_options_join_the_scan(self) -> None:
        path = self.settings({"extra_secret_patterns": [r"https://api\.example\.invalid"]})
        data = json.loads(
            run_inventory(
                "--offline", "--options-settings", str(path), "--secret-pattern", "Frobnicate"
            ).stdout
        )
        types = {s["type"] for s in data["secrets"]}
        self.assertIn("custom-0", types)  # from the option
        self.assertIn("custom-1", types)  # from the flag

    def test_save_writes_a_dated_manifest_into_the_report_dir(self) -> None:
        reports = self.dir / "reports"
        path = self.settings({"report_dir": str(reports)})
        done = run_inventory("--offline", "--options-settings", str(path), "--save")
        expected = reports / f"{date.today().isoformat()}-manifest.json"
        self.assertEqual(done.stdout.strip(), f"wrote {expected}")
        self.assertEqual(json.loads(expected.read_text())["schema_version"], 1)


class ModeFlagsTest(unittest.TestCase):
    def test_quick_and_full_refresh_and_count(self) -> None:
        for mode in ("quick", "full"):
            self.assertEqual(mode_flags(mode, DEFAULTS), (True, True))

    def test_report_refreshes_only_when_the_option_allows_and_never_runs_trackers(self) -> None:
        self.assertEqual(mode_flags("report", DEFAULTS), (True, False))
        self.assertEqual(mode_flags("report", Options(refresh_marketplaces=False)), (False, False))

    def test_no_mode_runs_nothing_extra(self) -> None:
        self.assertEqual(mode_flags(None, DEFAULTS), (False, False))


if __name__ == "__main__":
    unittest.main()
