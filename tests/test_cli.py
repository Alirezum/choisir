"""Tests for choosier.cli: flags, exit codes, and output."""

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from choosier.cli import main
from choosier.storage import get_logged_items


class CliTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "target"
        self.target.mkdir()
        (self.target / "a").touch()
        (self.target / "b").touch()
        self.log = self.target / ".choosier.jsonl"

    def _run(self, *argv: str) -> tuple[int, str]:
        buf = io.StringIO()
        with redirect_stdout(buf):
            code = main([str(a) for a in argv])
        return code, buf.getvalue()

    def test_pick_logs_and_returns_zero(self) -> None:
        code, out = self._run(str(self.target), "--seed", "1")
        self.assertEqual(code, 0)
        self.assertIn("The choice:", out)
        self.assertEqual(len(get_logged_items(self.log)), 1)

    def test_exhaustion_returns_four(self) -> None:
        self._run(str(self.target), "--seed", "1")
        self._run(str(self.target), "--seed", "2")
        code, out = self._run(str(self.target))
        self.assertEqual(code, 4)
        self.assertIn("All choices have been selected", out)

    def test_empty_directory_returns_three(self) -> None:
        empty = Path(self.tmp.name) / "empty"
        empty.mkdir()
        code, out = self._run(str(empty))
        self.assertEqual(code, 3)
        self.assertIn("Path Empty.", out)

    def test_invalid_path_returns_one(self) -> None:
        code, _ = self._run(str(self.target / "nope"))
        self.assertEqual(code, 1)

    def test_conflicting_filters_exit_two(self) -> None:
        with self.assertRaises(SystemExit) as ctx:
            self._run(str(self.target), "--files-only", "--dirs-only")
        self.assertEqual(ctx.exception.code, 2)

    def test_dry_run_does_not_write(self) -> None:
        code, out = self._run(str(self.target), "--dry-run", "--seed", "3")
        self.assertEqual(code, 0)
        self.assertIn("Dry run", out)
        self.assertFalse(self.log.exists())

    def test_reset_removes_log(self) -> None:
        self._run(str(self.target), "--seed", "1")
        self.assertTrue(self.log.exists())
        code, out = self._run(str(self.target), "--reset")
        self.assertEqual(code, 0)
        self.assertIn("Removed", out)
        self.assertFalse(self.log.exists())

    def test_reset_without_log_still_zero(self) -> None:
        code, out = self._run(str(self.target), "--reset")
        self.assertEqual(code, 0)
        self.assertIn("No log", out)

    def test_seed_is_deterministic(self) -> None:
        other = Path(self.tmp.name) / "other"
        other.mkdir()
        (other / "a").touch()
        (other / "b").touch()
        _, first = self._run(str(self.target), "--seed", "9", "--dry-run")
        _, second = self._run(str(other), "--seed", "9", "--dry-run")
        self.assertEqual(first, second)

    def test_list_shows_remaining_sorted(self) -> None:
        self._run(str(self.target), "--seed", "1")
        code, out = self._run(str(self.target), "--list")
        self.assertEqual(code, 0)
        lines = out.split()
        self.assertEqual(lines, sorted(lines))
        self.assertEqual(len(lines), 1)

    def test_list_when_exhausted_returns_four(self) -> None:
        self._run(str(self.target), "--seed", "1")
        self._run(str(self.target), "--seed", "2")
        code, _ = self._run(str(self.target), "--list")
        self.assertEqual(code, 4)

    def test_prompt_when_path_omitted(self) -> None:
        buf = io.StringIO()
        with (
            patch("choosier.cli.input", return_value=str(self.target)),
            redirect_stdout(buf),
        ):
            code = main([])
        self.assertEqual(code, 0)
        self.assertIn("The choice:", buf.getvalue())

    def test_custom_log_file(self) -> None:
        custom = Path(self.tmp.name) / "custom.jsonl"
        code, _ = self._run(str(self.target), "--log-file", str(custom))
        self.assertEqual(code, 0)
        self.assertTrue(custom.exists())
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
