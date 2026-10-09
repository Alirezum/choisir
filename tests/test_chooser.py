"""Tests for choosier.chooser: filtering, history, seeded picks."""

import random
import tempfile
import unittest
from pathlib import Path

from choosier.chooser import (
    get_unselected_item,
    list_available_items,
    resolve_default_log,
)
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


if __name__ == "__main__":
    unittest.main()
