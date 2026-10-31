"""Direct tests for choosier.services.pick."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from choosier.services import FailureKind, ServiceError, pick


class PickTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "target"
        self.target.mkdir()
        self.log = self.target / ".choosier.jsonl"

    def test_seeded_picks_are_repeatable(self) -> None:
        for name in ("a", "b", "c", "d"):
            (self.target / name).touch()
        first = pick(self.target, self.log, seed=7, commit=False)
        second = pick(self.target, self.log, seed=7, commit=False)
        self.assertEqual(first.status, "picked")
        self.assertIsNotNone(first.item)
        self.assertEqual(first.item, second.item)
        self.assertFalse(first.logged)
        self.assertFalse(second.logged)
        self.assertFalse(self.log.exists())

    def test_dry_run_never_logs(self) -> None:
        (self.target / "only").touch()
        outcome = pick(self.target, self.log, seed=1, dry_run=True)
        self.assertEqual(outcome.status, "picked")
        self.assertEqual(outcome.item, "only")
        self.assertFalse(outcome.logged)
        self.assertFalse(self.log.exists())

    def test_commit_false_suppresses_logging(self) -> None:
        for name in ("a", "b"):
            (self.target / name).touch()
        outcome = pick(self.target, self.log, seed=1, commit=False)
        self.assertEqual(outcome.status, "picked")
        self.assertFalse(outcome.logged)
        self.assertFalse(self.log.exists())

    def test_empty_and_exhausted_statuses(self) -> None:
        empty_target = Path(self.tmp.name) / "empty"
        empty_target.mkdir()
        empty = pick(empty_target, empty_target / ".choosier.jsonl", seed=1)
        self.assertEqual(empty.status, "empty")
        self.assertIsNone(empty.item)
        self.assertFalse(empty.logged)

        (self.target / "a").touch()
        (self.target / "b").touch()
        self.log.write_text(
            '{"ts": "t", "item": "a"}\n{"ts": "t", "item": "b"}\n',
            encoding="utf-8",
        )
        exhausted = pick(self.target, self.log, seed=1)
        self.assertEqual(exhausted.status, "exhausted")
        self.assertIsNone(exhausted.item)
        self.assertFalse(exhausted.logged)

    def test_invalid_path_is_a_domain_outcome(self) -> None:
        missing = self.target / "missing"
        outcome = pick(missing, self.log, seed=1)
        self.assertEqual(outcome.status, "invalid_path")
        self.assertIsNone(outcome.item)
        self.assertFalse(outcome.logged)
        self.assertEqual(outcome.log_file, self.log)
        self.assertFalse(self.log.exists())

    def test_conflicting_filters_raise_service_error(self) -> None:
        with self.assertRaises(ServiceError) as caught:
            pick(self.target, self.log, files_only=True, dirs_only=True)
        self.assertEqual(caught.exception.kind, FailureKind.INVALID_INPUT)
        self.assertEqual(
            caught.exception.message,
            "files_only and dirs_only are mutually exclusive",
        )

    def test_write_failure_uses_the_exact_error_prefix(self) -> None:
        for name in ("a", "b"):
            (self.target / name).touch()
        with patch(
            "choosier.storage.log_selection",
            side_effect=OSError("boom"),
        ):
            with self.assertRaises(ServiceError) as caught:
                pick(self.target, self.log, seed=2)
        self.assertEqual(caught.exception.kind, FailureKind.IO_ERROR)
        self.assertEqual(caught.exception.message, "Error writing log: boom")
        self.assertIsInstance(caught.exception.__cause__, OSError)
        self.assertFalse(self.log.exists())

    def test_preview_is_optional(self) -> None:
        (self.target / "note.txt").write_text("hello\nworld\n", encoding="utf-8")
        without = pick(self.target, self.log, seed=1, dry_run=True)
        self.assertIsNone(without.preview)
        with_preview = pick(
            self.target,
            self.log,
            seed=1,
            dry_run=True,
            include_preview=True,
        )
        self.assertIsNotNone(with_preview.preview)
        assert with_preview.preview is not None
        self.assertEqual(with_preview.preview.kind, "text")
        self.assertIn("hello", with_preview.preview.text)

    def test_hidden_and_type_filters(self) -> None:
        hidden_target = Path(self.tmp.name) / "hidden"
        hidden_target.mkdir()
        (hidden_target / ".hidden").touch()
        hidden_log = hidden_target / ".choosier.jsonl"
        self.assertEqual(
            pick(hidden_target, hidden_log, seed=1, commit=False).status,
            "exhausted",
        )
        included = pick(
            hidden_target,
            hidden_log,
            seed=1,
            commit=False,
            include_hidden=True,
        )
        self.assertEqual(included.status, "picked")
        self.assertEqual(included.item, ".hidden")

        typed_target = Path(self.tmp.name) / "typed"
        typed_target.mkdir()
        (typed_target / "file.txt").touch()
        (typed_target / "sub").mkdir()
        typed_log = typed_target / ".choosier.jsonl"
        files = pick(
            typed_target,
            typed_log,
            seed=1,
            commit=False,
            files_only=True,
        )
        dirs = pick(
            typed_target,
            typed_log,
            seed=1,
            commit=False,
            dirs_only=True,
        )
        self.assertEqual(files.item, "file.txt")
        self.assertEqual(dirs.item, "sub")


if __name__ == "__main__":
    unittest.main()
