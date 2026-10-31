"""Direct tests for choosier.services.history: one history access path."""

import json
import tempfile
import unittest
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from choosier import storage
from choosier.services import FailureKind, HistoryService, ServiceError

FIXED = datetime(2026, 1, 2, 3, 4, 5, tzinfo=UTC)
MIXED = (
    '{"ts": "2026-01-01T00:00:00+00:00", "item": "current"}\n'
    "2020-01-01T00:00:00Z - legacy - name\n"
    "plain name\n"
    "\n"
    "[1, 2]\n"
    '{"ts": "2026-01-02T00:00:00+00:00", "item": "current"}\n'
)
EXPECTED_ITEMS = ("current", "legacy - name", "plain name", "current")
EXPECTED_DISPLAY = (
    "2026-01-01T00:00:00+00:00  current",
    "2020-01-01T00:00:00Z - legacy - name",
    "plain name",
    "2026-01-02T00:00:00+00:00  current",
)


class HistorySnapshotTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "history.jsonl"

    def test_snapshot_reads_history_once_and_derives_views(self) -> None:
        self.log.write_text(MIXED, encoding="utf-8")
        service = HistoryService(self.log)
        with patch(
            "choosier.storage.read_log_entries", wraps=storage.read_log_entries
        ) as read:
            snapshot = service.snapshot()
        read.assert_called_once_with(self.log, ignore_errors=True)
        self.assertEqual(
            tuple(entry.item for entry in snapshot.entries), EXPECTED_ITEMS
        )
        self.assertEqual(
            tuple(entry.timestamp for entry in snapshot.entries),
            (
                "2026-01-01T00:00:00+00:00",
                None,
                None,
                "2026-01-02T00:00:00+00:00",
            ),
        )
        self.assertEqual(snapshot.display, EXPECTED_DISPLAY)
        self.assertEqual(
            snapshot.logged,
            frozenset({"current", "legacy - name", "plain name"}),
        )

    def test_missing_history_derives_empty_views(self) -> None:
        service = HistoryService(self.log)
        snapshot = service.snapshot()
        self.assertEqual(snapshot.entries, ())
        self.assertEqual(snapshot.logged, frozenset())
        self.assertEqual(snapshot.display, ())
        self.assertEqual(service.read_entries(), ())
        self.assertEqual(service.logged_items(), set())
        self.assertEqual(service.display_lines(), [])

    def test_tolerant_read_ignores_io_errors(self) -> None:
        service = HistoryService(self.log)
        with patch(
            "choosier.storage.Path.read_text",
            side_effect=PermissionError("denied"),
        ):
            snapshot = service.snapshot()
        self.assertEqual(snapshot.entries, ())
        self.assertEqual(snapshot.logged, frozenset())
        self.assertEqual(snapshot.display, ())

    def test_strict_read_propagates_io_errors(self) -> None:
        service = HistoryService(self.log)
        with patch(
            "choosier.storage.Path.read_text",
            side_effect=PermissionError("denied"),
        ):
            with self.assertRaises(PermissionError):
                service.snapshot(ignore_errors=False)

    def test_strict_flag_reaches_the_storage_seam(self) -> None:
        service = HistoryService(self.log)
        with patch("choosier.storage.read_log_entries", return_value=[]) as read:
            service.snapshot(ignore_errors=False)
        read.assert_called_once_with(self.log, ignore_errors=False)


class HistoryAppendTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "history.jsonl"

    def test_append_writes_one_current_jsonl_line(self) -> None:
        with patch("choosier.storage.datetime") as mock_datetime:
            mock_datetime.now.return_value = FIXED
            HistoryService(self.log).append("a - b ✓")
        content = self.log.read_text(encoding="utf-8")
        self.assertTrue(content.endswith("\n"))
        lines = content.splitlines()
        self.assertEqual(len(lines), 1)
        self.assertEqual(
            json.loads(lines[0]),
            {"ts": FIXED.isoformat(), "item": "a - b ✓"},
        )

    def test_append_creates_missing_history(self) -> None:
        HistoryService(self.log).append("fresh")
        entries = HistoryService(self.log).read_entries()
        self.assertEqual([entry.item for entry in entries], ["fresh"])
        self.assertEqual(HistoryService(self.log).logged_items(), {"fresh"})


class HistoryRemovalTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.log = self.directory / "history.jsonl"

    def test_remove_deletes_every_duplicate_entry(self) -> None:
        keep = '{"ts": "2026-01-03T00:00:00+00:00", "item": "keep"}\n'
        self.log.write_text(
            '{"ts": "2026-01-01T00:00:00+00:00", "item": "dup"}\n'
            "2020-01-01T00:00:00Z - dup\n"
            "plain dup\n"
            '{"ts": "2026-01-02T00:00:00+00:00", "item": "dup"}\n' + keep,
            encoding="utf-8",
        )
        removed = HistoryService(self.log).remove("dup")
        self.assertEqual(removed, 3)
        self.assertEqual(
            self.log.read_text(encoding="utf-8"),
            "plain dup\n" + keep,
        )

    def test_remove_many_rewrites_once_and_keeps_unrelated_lines(self) -> None:
        kept = (
            "2020-01-01T00:00:00Z - old\n"
            "\n"
            "not json\n"
            '{"ts": "2026-01-03T00:00:00+00:00", "item": "b"}\n'
        )
        self.log.write_text(
            "2020-01-01T00:00:00Z - old\n"
            '{"ts": "2026-01-02T00:00:00+00:00", "item": "a"}\n'
            "\n"
            "not json\n"
            '{"ts": "2026-01-03T00:00:00+00:00", "item": "b"}\n'
            '{"ts": "2026-01-04T00:00:00+00:00", "item": "a"}\n',
            encoding="utf-8",
        )
        with patch(
            "choosier.storage._rewrite_log", wraps=storage._rewrite_log
        ) as rewrite:
            removed = HistoryService(self.log).remove_many(["a", "missing"])
        self.assertEqual(removed, 2)
        self.assertEqual(rewrite.call_count, 1)
        self.assertEqual(self.log.read_text(encoding="utf-8"), kept)
        self.assertEqual(list(self.directory.glob(".*.tmp")), [])

    def test_empty_batch_does_not_rewrite(self) -> None:
        self.log.write_text(MIXED, encoding="utf-8")
        before = self.log.read_bytes()
        with patch(
            "choosier.storage._rewrite_log", wraps=storage._rewrite_log
        ) as rewrite:
            removed = HistoryService(self.log).remove_many([])
        self.assertEqual(removed, 0)
        rewrite.assert_not_called()
        self.assertEqual(self.log.read_bytes(), before)

    def test_missing_history_removals_return_zero(self) -> None:
        service = HistoryService(self.log)
        self.assertEqual(service.remove("missing"), 0)
        self.assertEqual(service.remove_many(["missing"]), 0)
        self.assertFalse(self.log.exists())


class HistoryArchiveClearTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.directory = Path(self.tmp.name)
        self.log = self.directory / "history.jsonl"

    def test_archive_moves_history_to_timestamped_backup(self) -> None:
        self.log.write_text(MIXED, encoding="utf-8")
        with patch("choosier.storage.datetime") as mock_datetime:
            mock_datetime.now.return_value = FIXED
            backup = HistoryService(self.log).archive()
        self.assertEqual(
            backup,
            self.directory / "history-20260102T030405Z.jsonl.old",
        )
        assert backup is not None
        self.assertTrue(backup.exists())
        self.assertEqual(backup.read_text(encoding="utf-8"), MIXED)
        self.assertFalse(self.log.exists())

    def test_archive_missing_history_returns_none(self) -> None:
        self.assertIsNone(HistoryService(self.log).archive())

    def test_clear_reports_whether_history_existed(self) -> None:
        service = HistoryService(self.log)
        self.assertFalse(service.clear())
        self.log.write_text(MIXED, encoding="utf-8")
        self.assertTrue(service.clear())
        self.assertFalse(self.log.exists())
        self.assertFalse(service.clear())


class HistoryServiceErrorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.log = Path(self.tmp.name) / "history.jsonl"

    def test_storage_oserrors_are_wrapped_with_exact_messages(self) -> None:
        service = HistoryService(self.log)
        cases: tuple[tuple[str, Callable[[HistoryService], object], str, str], ...] = (
            (
                "append",
                lambda target: target.append("item"),
                "choosier.storage.log_selection",
                "Error writing log: boom",
            ),
            (
                "remove",
                lambda target: target.remove("item"),
                "choosier.storage.remove_log_item",
                "Error removing history item: boom",
            ),
            (
                "remove_many",
                lambda target: target.remove_many(["item"]),
                "choosier.storage.remove_log_items",
                "Error removing history items: boom",
            ),
            (
                "archive",
                lambda target: target.archive(),
                "choosier.storage.archive_log",
                "Error archiving log: boom",
            ),
            (
                "clear",
                lambda target: target.clear(),
                "choosier.storage.reset_log",
                "Error resetting log: boom",
            ),
        )
        for operation, action, seam, message in cases:
            with self.subTest(operation=operation):
                with patch(seam, side_effect=OSError("boom")):
                    with self.assertRaises(ServiceError) as caught:
                        action(service)
                self.assertEqual(caught.exception.kind, FailureKind.IO_ERROR)
                self.assertEqual(caught.exception.message, message)
                self.assertEqual(str(caught.exception), message)
                self.assertIsInstance(caught.exception.__cause__, OSError)


if __name__ == "__main__":
    unittest.main()
