"""Tests for choosier.chooser: filtering, history, seeded picks."""

import random
import tempfile
import unittest
from pathlib import Path

from choosier.chooser import (
    get_unselected_item,
    list_available_items,
    parse_seed,
    resolve_default_log,
    resolve_log_path,
    scan_candidates,
)
from choosier.filters import FilterSelection
from choosier.storage import log_selection


class ChooserTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "target"
        self.target.mkdir()
        self.log = self.target / "history.jsonl"

    def _populate(
        self,
        files: int = 0,
        dirs: int = 0,
        hidden: int = 0,
    ) -> None:
        for i in range(files):
            (self.target / f"file{i}").touch()
        for i in range(dirs):
            (self.target / f"dir{i}").mkdir()
        for i in range(hidden):
            (self.target / f".hidden{i}").touch()

    def test_empty_directory_returns_none(self) -> None:
        self.assertIsNone(get_unselected_item(self.target, self.log))

    def test_missing_directory_returns_none(self) -> None:
        self.assertIsNone(get_unselected_item(self.target / "nope", self.log))
        self.assertEqual(list_available_items(self.target / "nope"), [])

    def test_picks_only_unlogged_items(self) -> None:
        self._populate(files=2)
        log_selection("file0", self.log)
        for _ in range(20):
            self.assertEqual(get_unselected_item(self.target, self.log), "file1")

    def test_exhausted_returns_none(self) -> None:
        self._populate(files=1)
        log_selection("file0", self.log)
        self.assertIsNone(get_unselected_item(self.target, self.log))
        self.assertEqual(list_available_items(self.target, self.log), [])

    def test_hidden_excluded_by_default(self) -> None:
        self._populate(files=1, hidden=1)
        seen = {get_unselected_item(self.target, self.log) for _ in range(20)}
        self.assertEqual(seen, {"file0"})

    def test_hidden_included_when_asked(self) -> None:
        self._populate(files=1, hidden=1)
        seen = {
            get_unselected_item(self.target, self.log, include_hidden=True)
            for _ in range(30)
        }
        self.assertEqual(seen, {"file0", ".hidden0"})

    def test_active_log_and_backups_never_picked(self) -> None:
        self._populate(files=1)
        log_selection("x", self.log)
        (self.target / "history-20260101T000000Z.jsonl.old").touch()
        seen = {
            get_unselected_item(self.target, self.log, include_hidden=True)
            for _ in range(30)
        }
        self.assertEqual(seen, {"file0"})

    def test_files_only_and_dirs_only(self) -> None:
        self._populate(files=1, dirs=1)
        for _ in range(20):
            self.assertEqual(
                get_unselected_item(self.target, self.log, files_only=True),
                "file0",
            )
            self.assertEqual(
                get_unselected_item(self.target, self.log, dirs_only=True),
                "dir0",
            )

    def test_files_and_dirs_together_raise(self) -> None:
        self._populate(files=1)
        with self.assertRaises(ValueError):
            get_unselected_item(self.target, self.log, files_only=True, dirs_only=True)

    def test_seeded_rng_is_deterministic(self) -> None:
        self._populate(files=3)
        first = get_unselected_item(self.target, self.log, rng=random.Random(42))
        second = get_unselected_item(self.target, self.log, rng=random.Random(42))
        self.assertEqual(first, second)

    def test_available_items_are_sorted(self) -> None:
        self._populate(files=3)
        self.assertEqual(
            list_available_items(self.target, self.log),
            ["file0", "file1", "file2"],
        )

    def test_default_log_is_colocated_with_target(self) -> None:
        self._populate(files=1)
        log_path = resolve_default_log(self.target)
        self.assertEqual(log_path, self.target / ".choosier.jsonl")
        self.assertEqual(get_unselected_item(self.target), "file0")
        # picking alone writes nothing; history lives next to the target
        self.assertFalse(log_path.exists())


class CandidateScanTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "target"
        self.target.mkdir()
        self.log = self.target / "history.jsonl"

    def test_scan_applies_existing_rules_once(self) -> None:
        (self.target / "a.txt").touch()
        (self.target / "b").touch()
        (self.target / "sub").mkdir()
        (self.target / ".hidden").touch()
        (self.target / "history.jsonl").touch()
        (self.target / "history-20260101T000000Z.jsonl.old").touch()

        default = scan_candidates(self.target, self.log)
        self.assertTrue(default.valid_path)
        self.assertTrue(default.has_children)
        self.assertEqual(
            [(entry.name, entry.is_dir, entry.type_key) for entry in default.entries],
            [
                ("a.txt", False, "file:.txt"),
                ("b", False, "file:"),
                ("sub", True, "dir"),
            ],
        )

        hidden = scan_candidates(self.target, self.log, include_hidden=True)
        self.assertEqual(
            [entry.name for entry in hidden.entries],
            [".hidden", "a.txt", "b", "sub"],
        )
        files = scan_candidates(self.target, self.log, files_only=True)
        self.assertEqual([entry.name for entry in files.entries], ["a.txt", "b"])
        dirs = scan_candidates(self.target, self.log, dirs_only=True)
        self.assertEqual([entry.name for entry in dirs.entries], ["sub"])

    def test_scan_reports_children_before_option_filtering(self) -> None:
        (self.target / ".hidden").touch()
        hidden_only = scan_candidates(self.target, self.log)
        self.assertTrue(hidden_only.valid_path)
        self.assertTrue(hidden_only.has_children)
        self.assertEqual(hidden_only.entries, ())

    def test_scan_of_empty_folder(self) -> None:
        scan = scan_candidates(self.target, self.log)
        self.assertTrue(scan.valid_path)
        self.assertFalse(scan.has_children)
        self.assertEqual(scan.entries, ())

    def test_scan_of_invalid_path(self) -> None:
        missing = self.target / "missing"
        scan = scan_candidates(missing, self.log)
        self.assertFalse(scan.valid_path)
        self.assertFalse(scan.has_children)
        self.assertEqual(scan.entries, ())

    def test_scan_rejects_conflicting_options(self) -> None:
        with self.assertRaises(ValueError):
            scan_candidates(self.target, self.log, files_only=True, dirs_only=True)


class FilteredSelectionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "target"
        self.target.mkdir()
        self.log = self.target / "history.jsonl"
        for name in ("a.jpg", "B.JPG", "notes.txt", "README"):
            (self.target / name).touch()
        (self.target / "sub").mkdir()

    def test_list_available_items_applies_type_exclusions(self) -> None:
        selection = FilterSelection(excluded_types=frozenset({"file:.txt", "dir"}))
        self.assertEqual(
            list_available_items(self.target, self.log, selection=selection),
            ["B.JPG", "README", "a.jpg"],
        )

    def test_list_available_items_applies_entry_exclusions(self) -> None:
        selection = FilterSelection(excluded_entries=frozenset({"notes.txt", "sub"}))
        self.assertEqual(
            list_available_items(self.target, self.log, selection=selection),
            ["B.JPG", "README", "a.jpg"],
        )

    def test_history_is_subtracted_after_filtering(self) -> None:
        log_selection("a.jpg", self.log)
        selection = FilterSelection(excluded_types=frozenset({"file:.txt", "dir"}))
        self.assertEqual(
            list_available_items(self.target, self.log, selection=selection),
            ["B.JPG", "README"],
        )

    def test_get_unselected_item_respects_filters_and_seed(self) -> None:
        selection = FilterSelection(excluded_types=frozenset({"file:.txt", "dir"}))
        for seed in range(20):
            item = get_unselected_item(
                self.target,
                self.log,
                selection=selection,
                rng=random.Random(seed),
            )
            self.assertIn(item, {"a.jpg", "B.JPG", "README"})

    def test_same_seed_same_filtered_pick(self) -> None:
        selection = FilterSelection(excluded_entries=frozenset({"notes.txt"}))
        first = get_unselected_item(
            self.target, self.log, selection=selection, rng=random.Random(9)
        )
        second = get_unselected_item(
            self.target, self.log, selection=selection, rng=random.Random(9)
        )
        self.assertEqual(first, second)

    def test_no_filter_behavior_is_unchanged(self) -> None:
        self.assertEqual(get_unselected_item(self.target / "missing", self.log), None)
        self.assertEqual(list_available_items(self.target / "missing"), [])

    def test_sc001_one_hundred_seeded_type_picks(self) -> None:
        for name in ("one.txt", "two.txt", "three.md"):
            (self.target / name).touch()
        unchecked = frozenset({"file:.txt", "file:.md", "dir"})
        selection = FilterSelection(excluded_types=unchecked)
        allowed = {"B.JPG", "README", "a.jpg"}
        for seed in range(100):
            item = get_unselected_item(
                self.target,
                self.log,
                selection=selection,
                rng=random.Random(seed),
            )
            self.assertIsNotNone(item)
            self.assertIn(item, allowed)


class ParseSeedTest(unittest.TestCase):
    def test_blank_means_random(self) -> None:
        self.assertIsNone(parse_seed(""))
        self.assertIsNone(parse_seed("   "))

    def test_valid_integer(self) -> None:
        self.assertEqual(parse_seed("7"), 7)
        self.assertEqual(parse_seed("  42 "), 42)

    def test_invalid_raises(self) -> None:
        for bad in ["abc", "1.5", "12a"]:
            with self.assertRaises(ValueError, msg=bad):
                parse_seed(bad)


class ResolveLogPathTest(unittest.TestCase):
    def test_blank_uses_colocated_default(self) -> None:
        self.assertEqual(
            resolve_log_path(Path("/target"), ""),
            Path("/target/.choosier.jsonl"),
        )
        self.assertEqual(
            resolve_log_path(Path("/target"), "   "),
            Path("/target/.choosier.jsonl"),
        )

    def test_explicit_override(self) -> None:
        self.assertEqual(
            resolve_log_path(Path("/target"), "/elsewhere/history.jsonl"),
            Path("/elsewhere/history.jsonl"),
        )


if __name__ == "__main__":
    unittest.main()
