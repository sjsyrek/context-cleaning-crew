"""Plugin options (`userConfig` in plugin.json), read from `pluginConfigs` in settings files.

Claude Code saves non-sensitive option values to `pluginConfigs["<plugin>@<marketplace>"].options`
in user, `--settings` or managed settings (never project settings). Reading them here, rather than
through `${user_config.*}` substitution in skill text, keeps list values intact: substitution joins
arrays with commas, which would corrupt regexes such as `{20,}`.
"""

from __future__ import annotations

import json
import re
from collections.abc import Sequence
from dataclasses import dataclass, field, fields, replace
from pathlib import Path
from typing import Any


def read_json_object(path: Path) -> dict[str, Any]:
    """Own copy of context.read_json_object: context imports this module."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


PLUGIN = "context-cleaning-crew"
SEAT_MODELS = ("sonnet", "opus", "haiku", "inherit")


@dataclass(frozen=True)
class Options:
    preferred_marketplaces: tuple[str, ...] = ()
    protected: tuple[str, ...] = ()
    backup_dir: str = "~/.claude/backups/context-cleaning-crew/"
    report_dir: str = "~/.local/state/context-cleaning-crew/reports/"
    usage_window_days: int = 90
    mine_transcripts: bool = False
    refresh_marketplaces: bool = True
    extra_secret_patterns: tuple[str, ...] = ()
    full_mode_models: str = "sonnet"

    def as_dict(self) -> dict[str, Any]:
        out: dict[str, Any] = {}
        for f in fields(self):
            value = getattr(self, f.name)
            out[f.name] = list(value) if isinstance(value, tuple) else value
        return out


DEFAULTS = Options()


@dataclass(frozen=True)
class LoadedOptions:
    options: Options
    sources: dict[str, str]  # option -> settings file it came from, or "default"
    warnings: list[str] = field(default_factory=list)


def _string_list(value: Any) -> tuple[str, ...] | None:
    if isinstance(value, str):
        return (value,) if value else ()
    if isinstance(value, list) and all(isinstance(v, str) for v in value):
        return tuple(v for v in value if v)
    return None


def _coerce(key: str, value: Any, default: Any, warnings: list[str]) -> Any | None:
    """The value in the option's type, or None (with a warning) when it can't be used."""
    if isinstance(default, tuple):
        items = _string_list(value)
        if items is None:
            warnings.append(f"{key}: expected a list of strings; using the default")
            return None
        if key == "extra_secret_patterns":
            kept = []
            for i, pattern in enumerate(items):
                try:
                    re.compile(pattern)
                    kept.append(pattern)
                except re.error:
                    warnings.append(f"{key}[{i}]: not a valid regular expression; skipped")
            return tuple(kept)
        return items
    if isinstance(default, bool):
        if isinstance(value, bool):
            return value
        warnings.append(f"{key}: expected true or false; using the default")
        return None
    if isinstance(default, int):
        if isinstance(value, int) and not isinstance(value, bool) and value > 0:
            return value
        warnings.append(f"{key}: expected a positive whole number; using the default")
        return None
    if not isinstance(value, str) or not value:
        warnings.append(f"{key}: expected text; using the default")
        return None
    if key == "full_mode_models" and value not in SEAT_MODELS:
        warnings.append(f"{key}: must be one of {', '.join(SEAT_MODELS)}; using the default")
        return None
    return value


def _plugin_entries(settings: dict[str, Any]) -> list[dict[str, Any]]:
    configs = settings.get("pluginConfigs")
    if not isinstance(configs, dict):
        return []
    entries = []
    for plugin_id in sorted(configs):
        if plugin_id != PLUGIN and not plugin_id.startswith(PLUGIN + "@"):
            continue
        options = configs[plugin_id].get("options") if isinstance(configs[plugin_id], dict) else None
        if isinstance(options, dict):
            entries.append(options)
    return entries


def load_options(sources: Sequence[Path]) -> LoadedOptions:
    """Merge option values from settings files in precedence order (later wins) over the defaults."""
    defaults = DEFAULTS.as_dict()
    values: dict[str, Any] = {}
    origin = dict.fromkeys(defaults, "default")
    warnings: list[str] = []
    for path in sources:
        for entry in _plugin_entries(read_json_object(path)):
            for key in sorted(entry):
                if key not in defaults:
                    warnings.append(f"{key}: not an option of {PLUGIN}; ignored")
                    continue
                coerced = _coerce(key, entry[key], getattr(DEFAULTS, key), warnings)
                if coerced is not None:
                    values[key] = coerced
                    origin[key] = str(path)
    return LoadedOptions(options=replace(DEFAULTS, **values), sources=origin, warnings=warnings)


def mode_flags(mode: str | None, options: Options) -> tuple[bool, bool]:
    """(refresh marketplaces, run trackers) for a skill mode.

    Quick and full mode refresh the clones and run tracker counts. Report mode never runs
    trackers and refreshes only when `refresh_marketplaces` allows. No mode adds nothing.
    """
    if mode in ("quick", "full"):
        return True, True
    if mode == "report":
        return options.refresh_marketplaces, False
    return False, False


def default_sources(home: Path) -> list[Path]:
    """Where Claude Code keeps option values, lowest precedence first. Project settings never count."""
    return [
        home / ".claude" / "settings.json",
        Path("/etc/claude-code/managed-settings.json"),
        Path("/Library/Application Support/ClaudeCode/managed-settings.json"),
    ]


def expand(path: str, home: Path) -> Path:
    return home / path[2:] if path.startswith("~/") else (home if path == "~" else Path(path))
