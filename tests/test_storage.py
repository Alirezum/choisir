"""Tests for choosier.storage: JSONL history, legacy fallback, rotation."""

import json
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from choosier.storage import (
    _maybe_rotate_log,
    _parse_log_line,
    get_logged_items,
    log_selection,
    reset_log,
)


class ParseLogLineTest(unittest.TestCase):
    def test_json_line(self) -> None:
        self.assertEqual(
            _parse_log_line('{"ts": "2026-01-01T00:00:00+00:00", "item": "a"}'),
            "a",
        )

    def test_json_item_with_separator(self) -> None:
        self.assertEqual(
            _parse_log_line('{"ts": "t", "item": "a - b"}'),
            "a - b",
        )

    def test_legacy_line(self) -> None:
        self.assertEqual(
            _parse_log_line("2026-01-01T00:00:00+00:00 - legacy - name"),
            "legacy - name",
        )

    def test_plain_line(self) -> None:
        self.assertEqual(_parse_log_line("just-a-name"), "just-a-name")

    def test_blank_and_malformed_lines_ignored(self) -> None:
        for bad in ["", "   ", "[1, 2]", "42", '{"noitem": 1}', "null"]:
            self.assertIsNone(_parse_log_line(bad), bad)


class LogSelectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "test.jsonl"

    def test_roundtrip_with_special_names(self) -> None:
        names = ["plain", "a - b", "with spaces", "ünïcodé ✓"]
        for name in names:
            log_selection(name, self.log)
        self.assertEqual(get_logged_items(self.log), set(names))

    def test_lines_are_valid_jsonl(self) -> None:
        log_selection("a - b", self.log)
        lines = self.log.read_text(encoding="utf-8").splitlines()
        self.assertEqual(len(lines), 1)
        obj = json.loads(lines[0])
        self.assertEqual(obj["item"], "a - b")
        self.assertIn("ts", obj)

    def test_missing_file_returns_empty(self) -> None:
        self.assertEqual(get_logged_items(self.log), set())

    def test_mixed_legacy_and_json_content(self) -> None:
        self.log.write_text(
            "2026-01-01T00:00:00+00:00 - old - item\n"
            '{"ts": "2026-01-02T00:00:00+00:00", "item": "new"}\n'
            "\n",
            encoding="utf-8",
        )
        self.assertEqual(get_logged_items(self.log), {"old - item", "new"})

    def test_unwritable_log_raises(self) -> None:
        with self.assertRaises(OSError):
            log_selection("x", Path(self.tmp.name))


class RotateLogTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "history.jsonl"

    def test_big_file_rotates_with_timestamp(self) -> None:
        self.log.write_text("x" * 1_000_001, encoding="utf-8")
        _maybe_rotate_log(self.log)
        self.assertFalse(self.log.exists())
        backups = list(Path(self.tmp.name).glob("history-*.jsonl.old"))
        self.assertEqual(len(backups), 1)

    def test_consecutive_rotations_preserve_history(self) -> None:
        self.log.write_text("x" * 1_000_001, encoding="utf-8")
        _maybe_rotate_log(self.log)
        self.log.write_text("y" * 1_000_001, encoding="utf-8")
        _maybe_rotate_log(self.log)
        backups = list(Path(self.tmp.name).glob("history-*.jsonl.old"))
        self.assertEqual(len(backups), 2)

    def test_same_second_collision_uses_counter(self) -> None:
        fixed = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
        with patch("choosier.storage.datetime") as mock_dt:
            mock_dt.now.return_value = fixed
            self.log.write_text("x" * 1_000_001, encoding="utf-8")
            _maybe_rotate_log(self.log)
            self.log.write_text("y" * 1_000_001, encoding="utf-8")
            _maybe_rotate_log(self.log)
        names = sorted(p.name for p in Path(self.tmp.name).glob("history-*.jsonl.old"))
        self.assertEqual(
            names,
            [
                "history-20260102T030405Z.jsonl.old",
                "history-20260102T030405Z_2.jsonl.old",
            ],
        )

    def test_small_file_untouched(self) -> None:
        self.log.write_text("hi", encoding="utf-8")
        _maybe_rotate_log(self.log)
        self.assertTrue(self.log.exists())
        self.assertEqual(list(Path(self.tmp.name).glob("history-*.old")), [])

    def test_missing_file_is_noop(self) -> None:
        _maybe_rotate_log(self.log)


class ResetLogTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "history.jsonl"

    def test_removes_existing_log(self) -> None:
        self.log.write_text("data", encoding="utf-8")
        self.assertTrue(reset_log(self.log))
        self.assertFalse(self.log.exists())

    def test_missing_log_returns_false(self) -> None:
        self.assertFalse(reset_log(self.log))

    def test_unremovable_path_raises(self) -> None:
        with self.assertRaises(OSError):
            reset_log(Path(self.tmp.name))


if __name__ == "__main__":
    unittest.main()
