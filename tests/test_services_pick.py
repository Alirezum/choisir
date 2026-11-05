"""Direct tests for choosier.services.pick."""

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from choosier.filters import FilterSelection
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


class FilteredPickTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "target"
        self.target.mkdir()
        self.log = self.target / ".choosier.jsonl"
        for name in ("a.jpg", "B.JPG", "notes.txt", "README"):
            (self.target / name).touch()
        (self.target / "sub").mkdir()

    def test_filtered_empty_has_no_side_effects(self) -> None:
        selection = FilterSelection(
            excluded_types=frozenset({"file:.txt", "file:", "dir"}),
            excluded_entries=frozenset({"a.jpg", "B.JPG"}),
        )
        outcome = pick(self.target, self.log, seed=1, selection=selection)
        self.assertEqual(outcome.status, "filtered_empty")
        self.assertIsNone(outcome.item)
        self.assertFalse(outcome.logged)
        self.assertFalse(self.log.exists())

    def test_filtered_exhausted_keeps_other_entries_untouched(self) -> None:
        selection = FilterSelection(
            excluded_types=frozenset({"file:.txt", "file:", "dir"}),
        )
        first = pick(self.target, self.log, seed=1, selection=selection)
        self.assertEqual(first.status, "picked")
        self.assertIn(first.item, {"a.jpg", "B.JPG"})
        second = pick(self.target, self.log, seed=2, selection=selection)
        self.assertEqual(second.status, "picked")
        self.assertIsNotNone(first.item)
        self.assertIsNotNone(second.item)
        self.assertNotEqual(first.item, second.item)
        third = pick(self.target, self.log, seed=3, selection=selection)
        self.assertEqual(third.status, "filtered_exhausted")
        self.assertIsNone(third.item)
        self.assertFalse(third.logged)
        self.assertEqual(
            self.log.read_text(encoding="utf-8").count("\n"),
            2,
        )

    def test_exhausted_when_filters_remove_nothing(self) -> None:
        self.log.write_text(
            "".join(
                f'{{"ts": "t", "item": "{name}"}}\n'
                for name in ("a.jpg", "B.JPG", "notes.txt", "README", "sub")
            ),
            encoding="utf-8",
        )
        outcome = pick(self.target, self.log, seed=1)
        self.assertEqual(outcome.status, "exhausted")
        self.assertFalse(outcome.logged)

    def test_hidden_only_folder_stays_exhausted(self) -> None:
        hidden_target = Path(self.tmp.name) / "hidden"
        hidden_target.mkdir()
        (hidden_target / ".hidden").touch()
        outcome = pick(
            hidden_target,
            hidden_target / ".choosier.jsonl",
            seed=1,
            selection=FilterSelection(excluded_types=frozenset({"dir"})),
        )
        self.assertEqual(outcome.status, "exhausted")

    def test_invalid_path_precedes_filtered_outcomes(self) -> None:
        outcome = pick(
            self.target / "missing",
            self.log,
            seed=1,
            selection=FilterSelection(excluded_types=frozenset({"dir"})),
        )
        self.assertEqual(outcome.status, "invalid_path")
        self.assertFalse(self.log.exists())

    def test_dry_run_filtered_pick_does_not_log(self) -> None:
        selection = FilterSelection(excluded_entries=frozenset({"notes.txt"}))
        outcome = pick(self.target, self.log, seed=1, dry_run=True, selection=selection)
        self.assertEqual(outcome.status, "picked")
        self.assertIn(outcome.item, {"a.jpg", "B.JPG", "README", "sub"})
        self.assertFalse(outcome.logged)
        self.assertFalse(self.log.exists())

    def test_type_and_entry_exclusions_intersect(self) -> None:
        selection = FilterSelection(
            excluded_types=frozenset({"file:.txt", "file:.jpg", "dir"}),
            excluded_entries=frozenset({"README"}),
        )
        outcome = pick(self.target, self.log, seed=1, selection=selection)
        self.assertEqual(outcome.status, "filtered_empty")

        only_jpg = FilterSelection(
            excluded_types=frozenset({"file:.txt", "file:", "dir"}),
            excluded_entries=frozenset({"B.JPG"}),
        )
        picked = pick(self.target, self.log, seed=1, selection=only_jpg)
        self.assertEqual(picked.status, "picked")
        self.assertEqual(picked.item, "a.jpg")

    def test_sc004_one_hundred_seeded_entry_picks(self) -> None:
        selection = FilterSelection(
            excluded_entries=frozenset({"notes.txt", "README", "sub"}),
        )
        allowed = {"a.jpg", "B.JPG"}
        for seed in range(100):
            outcome = pick(
                self.target,
                self.log,
                seed=seed,
                dry_run=True,
                selection=selection,
            )
            self.assertEqual(outcome.status, "picked")
            self.assertIn(outcome.item, allowed)
        self.assertFalse(self.log.exists())


if __name__ == "__main__":
    unittest.main()
