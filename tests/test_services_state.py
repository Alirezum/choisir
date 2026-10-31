"""Direct tests for choosier.services.state."""

import json
import tempfile
import unittest
from pathlib import Path

from choosier.services import (
    PANEL_MAX_LINES,
    FailureKind,
    ServiceError,
    build_state,
)


class StateSnapshotTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "target"
        self.target.mkdir()
        self.log = self.target / ".choosier.jsonl"

    def _populate_large(self) -> None:
        for index in range(500):
            (self.target / f"file{index:03d}").touch()
        self.log.write_text(
            "".join(
                json.dumps({"ts": f"t{index}", "item": f"file{index:03d}"}) + "\n"
                for index in range(250)
            ),
            encoding="utf-8",
        )

    def test_invalid_path_precedes_filter_conflict(self) -> None:
        regular_file = self.target / "file"
        regular_file.touch()
        for path in (self.target / "missing", regular_file):
            with self.subTest(path=path.name):
                state = build_state(
                    path,
                    files_only=True,
                    dirs_only=True,
                )
                self.assertFalse(state.valid_path)
                self.assertEqual(state.path, path)
                self.assertEqual(state.log_file, path / ".choosier.jsonl")
                self.assertEqual(state.remaining, ())
                self.assertEqual(state.remaining_total, 0)
                self.assertEqual(state.history, ())
                self.assertEqual(state.history_total, 0)

    def test_conflicting_filters_raise_service_error(self) -> None:
        with self.assertRaises(ServiceError) as caught:
            build_state(self.target, files_only=True, dirs_only=True)
        self.assertEqual(caught.exception.kind, FailureKind.INVALID_INPUT)
        self.assertEqual(
            caught.exception.message,
            "files_only and dirs_only are mutually exclusive",
        )

    def test_hidden_and_type_filters(self) -> None:
        for name in ("a.txt", "b.txt", ".hidden"):
            (self.target / name).touch()
        (self.target / "sub").mkdir()
        default = build_state(self.target, self.log, max_lines=None)
        self.assertEqual(default.remaining, ("a.txt", "b.txt", "sub"))
        self.assertEqual(default.remaining_total, 3)
        files = build_state(self.target, self.log, files_only=True, max_lines=None)
        self.assertEqual(files.remaining, ("a.txt", "b.txt"))
        directories = build_state(self.target, self.log, dirs_only=True, max_lines=None)
        self.assertEqual(directories.remaining, ("sub",))
        hidden = build_state(self.target, self.log, include_hidden=True, max_lines=None)
        self.assertEqual(hidden.remaining, (".hidden", "a.txt", "b.txt", "sub"))
        self.assertEqual(hidden.remaining_total, 4)

    def test_managed_history_and_archive_are_excluded(self) -> None:
        (self.target / "a").touch()
        (self.target / "b").touch()
        self.log.write_text(
            json.dumps({"ts": "t", "item": "a"}) + "\n",
            encoding="utf-8",
        )
        (self.target / ".choosier-20260101T000000Z.jsonl.old").touch()
        state = build_state(self.target, self.log, include_hidden=True, max_lines=None)
        self.assertEqual(state.log_file, self.log)
        self.assertEqual(state.remaining, ("b",))
        self.assertEqual(state.remaining_total, 1)
        self.assertEqual(state.history_total, 1)

    def test_default_cap_keeps_first_remaining_and_last_history(self) -> None:
        self._populate_large()
        state = build_state(self.target, self.log)
        self.assertEqual(state.remaining_total, 250)
        self.assertEqual(len(state.remaining), PANEL_MAX_LINES)
        self.assertEqual(
            state.remaining,
            tuple(f"file{index:03d}" for index in range(250, 450)),
        )
        self.assertEqual(state.history_total, 250)
        self.assertEqual(len(state.history), PANEL_MAX_LINES)
        self.assertEqual(
            [entry.item for entry in state.history],
            [f"file{index:03d}" for index in range(50, 250)],
        )

    def test_max_lines_none_returns_full_tui_shape(self) -> None:
        self._populate_large()
        state = build_state(self.target, self.log, max_lines=None)
        self.assertEqual(state.remaining_total, 250)
        self.assertEqual(
            state.remaining,
            tuple(f"file{index:03d}" for index in range(250, 500)),
        )
        self.assertEqual(state.history_total, 250)
        self.assertEqual(
            [entry.item for entry in state.history],
            [f"file{index:03d}" for index in range(250)],
        )

    def test_empty_and_malformed_history(self) -> None:
        (self.target / "a").touch()
        (self.target / "b").touch()
        missing = build_state(self.target, self.log, max_lines=None)
        self.assertEqual(missing.remaining, ("a", "b"))
        self.assertEqual(missing.history, ())
        self.assertEqual(missing.history_total, 0)
        self.log.write_text(
            '\n[1, 2]\n{"noitem": 1}\nnull\n',
            encoding="utf-8",
        )
        malformed = build_state(self.target, self.log, max_lines=None)
        self.assertEqual(malformed.remaining, ("a", "b"))
        self.assertEqual(malformed.history, ())
        self.assertEqual(malformed.history_total, 0)


if __name__ == "__main__":
    unittest.main()
