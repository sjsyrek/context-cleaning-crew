"""The SessionStart hook speaks once per successful Claude Code update and is silent otherwise."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from update_check import check  # noqa: E402

SCRIPT = ROOT / "scripts" / "update_check.py"


def result(outcome: str = "success", version_from: str = "2.1.327", version_to: str = "2.1.328") -> str:
    return json.dumps(
        {"outcome": outcome, "status": outcome, "version_from": version_from, "version_to": version_to}
    )


class UpdateCheckTest(unittest.TestCase):
    def setUp(self) -> None:
        self._tmp = tempfile.TemporaryDirectory()
        self.dir = Path(self._tmp.name)
        self.result = self.dir / ".last-update-result.json"
        self.state = self.dir / "data" / "last-seen-version"

    def tearDown(self) -> None:
        self._tmp.cleanup()

    def seen(self, version: str) -> None:
        self.state.parent.mkdir(parents=True, exist_ok=True)
        self.state.write_text(version)

    def test_missing_result_file_is_silent(self) -> None:
        self.assertEqual(check(self.result, self.state), "")

    def test_malformed_result_file_is_silent(self) -> None:
        self.result.write_text("{not json")
        self.seen("2.1.327")
        self.assertEqual(check(self.result, self.state), "")

    def test_failed_update_is_silent(self) -> None:
        self.result.write_text(result(outcome="error"))
        self.seen("2.1.327")
        self.assertEqual(check(self.result, self.state), "")

    def test_first_run_records_the_version_silently(self) -> None:
        self.result.write_text(result())
        self.assertEqual(check(self.result, self.state), "")
        self.assertEqual(self.state.read_text(), "2.1.328")

    def test_new_successful_update_suggests_a_report_once(self) -> None:
        self.result.write_text(result())
        self.seen("2.1.327")
        message = check(self.result, self.state)
        self.assertIn("2.1.327", message)
        self.assertIn("2.1.328", message)
        self.assertIn("/context-cleaning-crew report", message)
        self.assertEqual(message.count("\n"), 0)
        self.assertEqual(check(self.result, self.state), "")

    def test_already_seen_version_is_silent(self) -> None:
        self.result.write_text(result())
        self.seen("2.1.328")
        self.assertEqual(check(self.result, self.state), "")

    def test_hook_prints_nothing_and_exits_zero_on_an_ordinary_start(self) -> None:
        self.result.write_text(result())
        self.seen("2.1.328")
        done = subprocess.run(
            [sys.executable, str(SCRIPT), "--result", str(self.result), "--state", str(self.state)],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))

    def test_hook_exits_zero_silently_when_the_state_dir_is_unwritable(self) -> None:
        self.result.write_text(result())
        blocker = self.dir / "file-not-dir"
        blocker.write_text("")
        done = subprocess.run(
            [sys.executable, str(SCRIPT), "--result", str(self.result), "--state", str(blocker / "x")],
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual((done.returncode, done.stdout, done.stderr), (0, "", ""))


if __name__ == "__main__":
    unittest.main()
