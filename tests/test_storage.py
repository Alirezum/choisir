"""Tests for choosier.storage: JSONL history, legacy fallback, rotation."""

import hashlib
import json
import tempfile
import threading
import time
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from choosier.locking import exclusive_lock
from choosier.storage import (
    UndoReceipt,
    _maybe_rotate_log,
    _parse_log_line,
    append_log_entry,
    archive_log,
    get_logged_items,
    load_log,
    log_selection,
    parse_log_line,
    read_log_entries,
    remove_log_item,
    remove_log_items,
    reset_log,
    undo_log_entry,
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


class ReadLogEntriesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "history.jsonl"

    def test_missing_log_returns_empty(self) -> None:
        self.assertEqual(read_log_entries(self.log), [])

    def test_json_entry_has_timestamp_and_display(self) -> None:
        log_selection("with spaces", self.log)
        entries = read_log_entries(self.log)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].item, "with spaces")
        self.assertIsNotNone(entries[0].timestamp)
        self.assertTrue(entries[0].display.endswith("  with spaces"))

    def test_legacy_entry_keeps_raw_display(self) -> None:
        self.log.write_text(
            "2020-01-01T00:00:00Z - old name\n",
            encoding="utf-8",
        )
        entries = read_log_entries(self.log)
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0].item, "old name")
        self.assertIsNone(entries[0].timestamp)
        self.assertEqual(entries[0].display, "2020-01-01T00:00:00Z - old name")

    def test_blank_and_malformed_lines_are_skipped(self) -> None:
        self.log.write_text("\n[1, 2]\nnot json\n", encoding="utf-8")
        entries = read_log_entries(self.log)
        self.assertEqual([entry.item for entry in entries], ["not json"])


class RemoveLogItemTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "history.jsonl"

    def test_removes_all_entries_for_item(self) -> None:
        for item in ("a", "b", "a", "c"):
            log_selection(item, self.log)
        self.assertEqual(remove_log_item("a", self.log), 2)
        self.assertEqual(get_logged_items(self.log), {"b", "c"})
        self.assertEqual(
            [entry.item for entry in read_log_entries(self.log)], ["b", "c"]
        )

    def test_removes_legacy_entry_by_parsed_item(self) -> None:
        self.log.write_text(
            "2020-01-01T00:00:00Z - legacy name\n"
            '{"ts": "2026-01-01T00:00:00+00:00", "item": "keep"}\n',
            encoding="utf-8",
        )
        self.assertEqual(remove_log_item("legacy name", self.log), 1)
        self.assertEqual(get_logged_items(self.log), {"keep"})

    def test_preserves_unrelated_lines_verbatim(self) -> None:
        content = (
            "2020-01-01T00:00:00Z - old\n"
            '{"ts": "2026-01-02T00:00:00+00:00", "item": "a"}\n'
            "\n"
            "not json\n"
            '{"ts": "2026-01-03T00:00:00+00:00", "item": "b"}\n'
        )
        self.log.write_text(content, encoding="utf-8")
        self.assertEqual(remove_log_item("a", self.log), 1)
        self.assertEqual(
            self.log.read_text(encoding="utf-8"),
            "2020-01-01T00:00:00Z - old\n"
            "\n"
            "not json\n"
            '{"ts": "2026-01-03T00:00:00+00:00", "item": "b"}\n',
        )

    def test_missing_item_is_a_noop(self) -> None:
        log_selection("a", self.log)
        before = self.log.read_bytes()
        self.assertEqual(remove_log_item("missing", self.log), 0)
        self.assertEqual(self.log.read_bytes(), before)

    def test_missing_log_returns_zero(self) -> None:
        self.assertEqual(remove_log_item("a", self.log), 0)
        self.assertFalse(self.log.exists())

    def test_removing_last_entry_leaves_empty_log(self) -> None:
        log_selection("only", self.log)
        self.assertEqual(remove_log_item("only", self.log), 1)
        self.assertEqual(self.log.read_text(encoding="utf-8"), "")
        self.assertEqual(get_logged_items(self.log), set())


class RemoveLogItemsTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "history.jsonl"

    def test_removes_multiple_items_in_one_rewrite(self) -> None:
        for item in ("a", "b", "c", "a"):
            log_selection(item, self.log)
        self.assertEqual(remove_log_items({"a", "c"}, self.log), 3)
        self.assertEqual(get_logged_items(self.log), {"b"})
        self.assertEqual([entry.item for entry in read_log_entries(self.log)], ["b"])

    def test_removes_legacy_entry_by_parsed_item(self) -> None:
        self.log.write_text(
            "2020-01-01T00:00:00Z - legacy name\n"
            '{"ts": "2026-01-01T00:00:00+00:00", "item": "keep"}\n'
            '{"ts": "2026-01-02T00:00:00+00:00", "item": "drop"}\n',
            encoding="utf-8",
        )
        self.assertEqual(remove_log_items({"legacy name", "drop"}, self.log), 2)
        self.assertEqual(get_logged_items(self.log), {"keep"})

    def test_preserves_unrelated_lines_verbatim(self) -> None:
        content = (
            "2020-01-01T00:00:00Z - old\n"
            '{"ts": "2026-01-02T00:00:00+00:00", "item": "a"}\n'
            "\n"
            "not json\n"
            '{"ts": "2026-01-03T00:00:00+00:00", "item": "b"}\n'
        )
        self.log.write_text(content, encoding="utf-8")
        self.assertEqual(remove_log_items({"a"}, self.log), 1)
        self.assertEqual(
            self.log.read_text(encoding="utf-8"),
            "2020-01-01T00:00:00Z - old\n"
            "\n"
            "not json\n"
            '{"ts": "2026-01-03T00:00:00+00:00", "item": "b"}\n',
        )

    def test_empty_items_is_a_noop(self) -> None:
        log_selection("a", self.log)
        before = self.log.read_bytes()
        self.assertEqual(remove_log_items(set(), self.log), 0)
        self.assertEqual(self.log.read_bytes(), before)

    def test_missing_items_are_a_noop(self) -> None:
        log_selection("a", self.log)
        before = self.log.read_bytes()
        self.assertEqual(remove_log_items({"missing", "also-missing"}, self.log), 0)
        self.assertEqual(self.log.read_bytes(), before)

    def test_missing_log_returns_zero(self) -> None:
        self.assertEqual(remove_log_items({"a", "b"}, self.log), 0)
        self.assertFalse(self.log.exists())

    def test_removing_last_entries_leaves_empty_log(self) -> None:
        log_selection("one", self.log)
        log_selection("two", self.log)
        self.assertEqual(remove_log_items({"one", "two"}, self.log), 2)
        self.assertEqual(self.log.read_text(encoding="utf-8"), "")
        self.assertEqual(get_logged_items(self.log), set())


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


class LoadLogTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "history.jsonl"

    def test_missing_file_returns_empties(self) -> None:
        self.assertEqual(load_log(self.log), (set(), []))

    def test_single_read_yields_names_and_display(self) -> None:
        self.log.write_text(
            '{"ts": "2026-01-01T00:00:00+00:00", "item": "new"}\n'
            "2026-01-02T00:00:00+00:00 - old - item\n"
            "\n"
            "[1, 2]\n",
            encoding="utf-8",
        )
        names, display = load_log(self.log)
        self.assertEqual(names, {"new", "old - item"})
        self.assertEqual(
            display,
            [
                "2026-01-01T00:00:00+00:00  new",
                "2026-01-02T00:00:00+00:00 - old - item",
            ],
        )


class MixedHistoryReadTest(unittest.TestCase):
    """One fixture covering every supported line form and duplicates."""

    CONTENT = (
        '{"ts": "2026-01-01T00:00:00+00:00", "item": "current"}\n'
        "2020-01-01T00:00:00Z - legacy - name\n"
        "plain name\n"
        "\n"
        "[1, 2]\n"
        '{"ts": "2026-01-02T00:00:00+00:00", "item": "current"}\n'
    )

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "history.jsonl"

    def test_structured_and_derived_reads_agree(self) -> None:
        self.log.write_text(self.CONTENT, encoding="utf-8")
        entries = read_log_entries(self.log)
        names, display = load_log(self.log)
        logged = get_logged_items(self.log)
        expected_items = ["current", "legacy - name", "plain name", "current"]
        expected_display = [
            "2026-01-01T00:00:00+00:00  current",
            "2020-01-01T00:00:00Z - legacy - name",
            "plain name",
            "2026-01-02T00:00:00+00:00  current",
        ]
        self.assertEqual([entry.item for entry in entries], expected_items)
        self.assertEqual(
            [entry.timestamp for entry in entries],
            ["2026-01-01T00:00:00+00:00", None, None, "2026-01-02T00:00:00+00:00"],
        )
        self.assertEqual([entry.display for entry in entries], expected_display)
        self.assertEqual(display, expected_display)
        self.assertEqual(names, set(expected_items))
        self.assertEqual(logged, names)

    def test_default_read_is_tolerant_but_strict_read_propagates(self) -> None:
        self.log.write_text(self.CONTENT, encoding="utf-8")
        with patch(
            "choosier.storage.Path.read_text",
            side_effect=PermissionError("denied"),
        ):
            self.assertEqual(read_log_entries(self.log), [])
            self.assertEqual(load_log(self.log), (set(), []))
            with self.assertRaises(PermissionError):
                read_log_entries(self.log, ignore_errors=False)
            with self.assertRaises(PermissionError):
                get_logged_items(self.log)


class ArchiveLogTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "history.jsonl"

    def test_moves_log_to_timestamped_backup(self) -> None:
        log_selection("a", self.log)
        backup = archive_log(self.log)
        self.assertIsNotNone(backup)
        assert backup is not None
        self.assertFalse(self.log.exists())
        self.assertTrue(backup.exists())
        self.assertIn("history-", backup.name)
        self.assertTrue(backup.name.endswith(".jsonl.old"))
        self.assertEqual(get_logged_items(backup), {"a"})

    def test_missing_log_returns_none(self) -> None:
        self.assertIsNone(archive_log(self.log))

    def test_unarchivable_path_raises(self) -> None:
        with self.assertRaises(OSError):
            archive_log(Path(self.tmp.name))


class AppendLogEntryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "history.jsonl"

    def test_receipt_matches_the_appended_bytes(self) -> None:
        receipt = append_log_entry("a - b ✓", self.log)
        self.assertIsNotNone(receipt)
        assert receipt is not None
        self.assertEqual(receipt.item, "a - b ✓")
        self.assertNotIn("\n", receipt.entry)
        self.assertNotIn("\r", receipt.entry)
        self.assertEqual(parse_log_line(receipt.entry)[1], "a - b ✓")
        data = self.log.read_bytes()
        self.assertEqual(receipt.digest, hashlib.sha256(data).hexdigest())
        self.assertRegex(receipt.digest, r"^[0-9a-f]{64}$")

    def test_rotation_returns_no_receipt(self) -> None:
        self.log.write_bytes(b"x" * 1_000_000)
        receipt = append_log_entry("a", self.log)
        self.assertIsNone(receipt)
        self.assertFalse(self.log.exists())
        self.assertEqual(len(list(Path(self.tmp.name).glob("history-*.jsonl.old"))), 1)

    def test_log_selection_still_appends_without_a_receipt(self) -> None:
        log_selection("a", self.log)
        self.assertEqual(get_logged_items(self.log), {"a"})


class UndoLogEntryTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "history.jsonl"

    def _append(self, item: str = "a") -> UndoReceipt:
        receipt = append_log_entry(item, self.log)
        assert receipt is not None
        return receipt

    def test_undo_removes_only_the_final_entry(self) -> None:
        first = self._append("a")
        second = self._append("b")
        self.assertEqual(undo_log_entry(second, self.log), "undone")
        self.assertEqual(self.log.read_text(encoding="utf-8"), f"{first.entry}\n")

    def test_same_item_twice_removes_only_the_newest_entry(self) -> None:
        first = self._append("a")
        second = self._append("a")
        self.assertNotEqual(first.digest, second.digest)
        self.assertEqual(undo_log_entry(first, self.log), "changed")
        self.assertEqual(undo_log_entry(second, self.log), "undone")
        self.assertEqual(self.log.read_text(encoding="utf-8"), f"{first.entry}\n")

    def test_external_append_refuses_and_preserves_bytes(self) -> None:
        receipt = self._append("a")
        with open(self.log, "a", encoding="utf-8") as handle:
            handle.write('{"ts": "t", "item": "external"}\n')
        before = self.log.read_bytes()
        self.assertEqual(undo_log_entry(receipt, self.log), "changed")
        self.assertEqual(self.log.read_bytes(), before)

    def test_external_removal_refuses_and_preserves_bytes(self) -> None:
        first = self._append("a")
        second = self._append("b")
        data = self.log.read_bytes()
        prefix = f"{first.entry}\n".encode()
        self.assertTrue(data.startswith(prefix))
        self.log.write_bytes(data[len(prefix) :])
        before = self.log.read_bytes()
        self.assertEqual(undo_log_entry(second, self.log), "changed")
        self.assertEqual(self.log.read_bytes(), before)

    def test_full_rewrite_refuses_and_preserves_bytes(self) -> None:
        receipt = self._append("a")
        self.log.write_text('{"ts": "t", "item": "other"}\n', encoding="utf-8")
        before = self.log.read_bytes()
        self.assertEqual(undo_log_entry(receipt, self.log), "changed")
        self.assertEqual(self.log.read_bytes(), before)

    def test_missing_log_reports_nothing_to_undo(self) -> None:
        receipt = UndoReceipt(item="a", entry='{"item": "a"}', digest="0" * 64)
        self.assertEqual(undo_log_entry(receipt, self.log), "nothing_to_undo")
        self.assertFalse(self.log.exists())

    def test_empty_log_reports_nothing_to_undo(self) -> None:
        receipt = self._append("a")
        self.log.write_bytes(b"")
        self.assertEqual(undo_log_entry(receipt, self.log), "nothing_to_undo")
        self.assertEqual(self.log.read_bytes(), b"")

    def test_missing_parent_is_not_created(self) -> None:
        missing = Path(self.tmp.name) / "missing" / "history.jsonl"
        receipt = UndoReceipt(item="a", entry='{"item": "a"}', digest="0" * 64)
        self.assertEqual(undo_log_entry(receipt, missing), "nothing_to_undo")
        self.assertFalse(missing.parent.exists())

    def test_sixty_three_character_digest_is_refused(self) -> None:
        receipt = self._append("a")
        short = UndoReceipt(receipt.item, receipt.entry, receipt.digest[:63])
        before = self.log.read_bytes()
        self.assertEqual(undo_log_entry(short, self.log), "changed")
        self.assertEqual(self.log.read_bytes(), before)

    def test_uppercase_digest_is_refused(self) -> None:
        receipt = self._append("a")
        upper = UndoReceipt(receipt.item, receipt.entry, receipt.digest.upper())
        before = self.log.read_bytes()
        self.assertEqual(undo_log_entry(upper, self.log), "changed")
        self.assertEqual(self.log.read_bytes(), before)

    def test_missing_line_terminator_is_refused(self) -> None:
        receipt = self._append("a")
        data = self.log.read_bytes()
        unterminated = data.rstrip(b"\n")
        self.log.write_bytes(unterminated)
        crafted = UndoReceipt(
            item=receipt.item,
            entry=receipt.entry,
            digest=hashlib.sha256(unterminated).hexdigest(),
        )
        self.assertEqual(undo_log_entry(crafted, self.log), "changed")
        self.assertEqual(self.log.read_bytes(), unterminated)

    def test_entry_with_a_line_break_is_refused(self) -> None:
        receipt = self._append("a")
        data = self.log.read_bytes()
        crafted = UndoReceipt(
            item=receipt.item,
            entry=f"{receipt.entry}\n",
            digest=hashlib.sha256(data).hexdigest(),
        )
        self.assertEqual(undo_log_entry(crafted, self.log), "changed")
        self.assertEqual(self.log.read_bytes(), data)

    def test_malformed_final_line_is_refused(self) -> None:
        self.log.write_text("[1, 2]\n", encoding="utf-8")
        data = self.log.read_bytes()
        receipt = UndoReceipt(
            item="anything",
            entry="[1, 2]",
            digest=hashlib.sha256(data).hexdigest(),
        )
        self.assertEqual(undo_log_entry(receipt, self.log), "changed")
        self.assertEqual(self.log.read_bytes(), data)

    def test_io_error_propagates(self) -> None:
        receipt = self._append("a")
        with patch(
            "choosier.storage.Path.read_bytes",
            side_effect=PermissionError("denied"),
        ):
            with self.assertRaises(PermissionError):
                undo_log_entry(receipt, self.log)

    def test_concurrent_undo_waits_for_the_history_lock(self) -> None:
        receipt = self._append("a")
        results: list[str] = []

        def run_undo() -> None:
            results.append(undo_log_entry(receipt, self.log))

        thread = threading.Thread(target=run_undo)
        with exclusive_lock(self.log):
            thread.start()
            time.sleep(0.2)
            self.assertTrue(thread.is_alive())
            self.assertEqual(results, [])
        thread.join(timeout=5)
        self.assertFalse(thread.is_alive())
        self.assertEqual(results, ["undone"])


if __name__ == "__main__":
    unittest.main()
