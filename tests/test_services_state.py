"""Direct tests for choosier.services.state."""

import json
import tempfile
import unittest
from pathlib import Path

from choosier.filters import FILTER_ENTRY_LIMIT, FilterSelection
from choosier.services import (
    PANEL_MAX_LINES,
    FailureKind,
    ServiceError,
    build_state,
)
from choosier.services.history import HistoryService
from choosier.skip import SkipSelection


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


class FilteredStateTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "target"
        self.target.mkdir()
        self.log = self.target / ".choosier.jsonl"
        for name in ("a.jpg", "B.JPG", "notes.txt", "README"):
            (self.target / name).touch()
        (self.target / "sub").mkdir()

    def test_filter_options_describe_the_folder(self) -> None:
        state = build_state(self.target, self.log, max_lines=None)
        self.assertEqual(
            [(item.key, item.count) for item in state.filter_options.types],
            [("dir", 1), ("file:.jpg", 2), ("file:.txt", 1), ("file:", 1)],
        )
        self.assertEqual(
            [item.name for item in state.filter_options.entries],
            ["B.JPG", "README", "a.jpg", "notes.txt", "sub"],
        )
        self.assertEqual(state.filter_options.entries_total, 5)
        self.assertFalse(state.filter_options.entries_truncated)

    def test_filtered_remaining_and_total(self) -> None:
        selection = FilterSelection(
            excluded_types=frozenset({"file:.txt", "dir"}),
            excluded_entries=frozenset({"B.JPG"}),
        )
        state = build_state(self.target, self.log, selection=selection, max_lines=None)
        self.assertEqual(state.remaining, ("README", "a.jpg"))
        self.assertEqual(state.remaining_total, 2)
        # Option counts still describe the unfiltered folder composition.
        self.assertEqual(
            [(item.key, item.count) for item in state.filter_options.types],
            [("dir", 1), ("file:.jpg", 2), ("file:.txt", 1), ("file:", 1)],
        )

    def test_option_counts_are_before_history_subtraction(self) -> None:
        self.log.write_text(
            '{"ts": "t", "item": "a.jpg"}\n{"ts": "t", "item": "B.JPG"}\n',
            encoding="utf-8",
        )
        state = build_state(self.target, self.log, max_lines=None)
        self.assertEqual(state.remaining, ("README", "notes.txt", "sub"))
        self.assertEqual(state.remaining_total, 3)
        counts = {item.key: item.count for item in state.filter_options.types}
        self.assertEqual(counts["file:.jpg"], 2)
        self.assertEqual(state.filter_options.entries_total, 5)

    def test_known_entry_exclusions_matches_current_candidates(self) -> None:
        selection = FilterSelection(
            excluded_entries=frozenset({"notes.txt", "stale.txt"}),
        )
        state = build_state(self.target, self.log, selection=selection, max_lines=None)
        self.assertEqual(state.known_entry_exclusions, ("notes.txt",))
        # Stale exclusions are ignored when filtering.
        self.assertEqual(
            state.remaining,
            ("B.JPG", "README", "a.jpg", "sub"),
        )

    def test_known_entry_exclusions_survive_the_visible_cap(self) -> None:
        for index in range(FILTER_ENTRY_LIMIT + 10):
            (self.target / f"f{index:05d}").touch()
        outside = f"f{FILTER_ENTRY_LIMIT + 5:05d}"
        selection = FilterSelection(excluded_entries=frozenset({outside}))
        state = build_state(self.target, self.log, selection=selection, max_lines=None)
        self.assertEqual(state.filter_options.entries_total, FILTER_ENTRY_LIMIT + 15)
        self.assertTrue(state.filter_options.entries_truncated)
        self.assertEqual(len(state.filter_options.entries), FILTER_ENTRY_LIMIT)
        self.assertNotIn(outside, [item.name for item in state.filter_options.entries])
        self.assertEqual(state.known_entry_exclusions, (outside,))
        self.assertNotIn(outside, state.remaining)

    def test_invalid_path_has_empty_options_and_known_exclusions(self) -> None:
        selection = FilterSelection(excluded_entries=frozenset({"notes.txt"}))
        state = build_state(
            self.target / "missing",
            self.log,
            selection=selection,
        )
        self.assertFalse(state.valid_path)
        self.assertEqual(state.filter_options.types, ())
        self.assertEqual(state.filter_options.entries, ())
        self.assertEqual(state.filter_options.entries_total, 0)
        self.assertFalse(state.filter_options.entries_truncated)
        self.assertEqual(state.known_entry_exclusions, ())

    def test_no_selection_reports_no_known_exclusions(self) -> None:
        state = build_state(self.target, self.log, max_lines=None)
        self.assertEqual(state.known_entry_exclusions, ())


class StateSkipTest(unittest.TestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "target"
        self.target.mkdir()
        self.log = self.target / ".choosier.jsonl"
        for name in ("alpha.txt", "beta.txt", "gamma", "sub"):
            if name == "sub":
                (self.target / name).mkdir()
            else:
                (self.target / name).touch()
        self.history = HistoryService(self.log)

    def test_skip_leaves_remaining_and_reports_skipped(self) -> None:
        state = build_state(
            self.target,
            self.log,
            max_lines=None,
            skips=SkipSelection(frozenset({"beta.txt"})),
        )
        self.assertEqual(
            state.remaining, ("alpha.txt", "gamma", "sub")
        )
        self.assertEqual(state.remaining_total, 3)
        self.assertEqual(state.skipped, ("beta.txt",))
        self.assertEqual(state.skipped_total, 1)
        self.assertEqual(state.skipped_present, ("beta.txt",))
        self.assertFalse(state.all_skipped)

    def test_logged_skip_is_hidden_but_still_present(self) -> None:
        self.history.append("beta.txt")
        state = build_state(
            self.target,
            self.log,
            max_lines=None,
            skips=SkipSelection(frozenset({"beta.txt"})),
        )
        self.assertEqual(state.skipped, ())
        self.assertEqual(state.skipped_total, 0)
        self.assertEqual(state.skipped_present, ("beta.txt",))
        self.assertNotIn("beta.txt", state.remaining)

    def test_removing_history_makes_the_skip_displayable_again(self) -> None:
        self.history.append("beta.txt")
        skipped = SkipSelection(frozenset({"beta.txt"}))
        before = build_state(self.target, self.log, skips=skipped)
        self.assertEqual(before.skipped, ())
        self.history.remove("beta.txt")
        after = build_state(self.target, self.log, skips=skipped)
        self.assertEqual(after.skipped, ("beta.txt",))
        self.assertNotIn("beta.txt", after.remaining)

    def test_deleted_or_renamed_entry_is_pruned_from_both_lists(self) -> None:
        (self.target / "alpha.txt").rename(self.target / "renamed.txt")
        state = build_state(
            self.target,
            self.log,
            max_lines=None,
            skips=SkipSelection(frozenset({"alpha.txt"})),
        )
        self.assertEqual(state.skipped, ())
        self.assertEqual(state.skipped_present, ())
        self.assertNotIn("alpha.txt", state.remaining)
        self.assertIn("renamed.txt", state.remaining)

    def test_filter_hidden_skip_stays_listed(self) -> None:
        selection = FilterSelection(excluded_entries=frozenset({"beta.txt"}))
        state = build_state(
            self.target,
            self.log,
            selection=selection,
            skips=SkipSelection(frozenset({"beta.txt"})),
        )
        self.assertNotIn("beta.txt", state.remaining)
        self.assertEqual(state.skipped, ("beta.txt",))
        self.assertEqual(state.skipped_present, ("beta.txt",))

    def test_option_hidden_skip_stays_listed(self) -> None:
        (self.target / ".hidden").touch()
        state = build_state(
            self.target,
            self.log,
            include_hidden=False,
            files_only=True,
            skips=SkipSelection(frozenset({".hidden"})),
        )
        self.assertEqual(state.skipped, (".hidden",))
        self.assertEqual(state.skipped_present, (".hidden",))
        self.assertNotIn(".hidden", state.remaining)

    def test_all_skipped_only_when_every_eligible_entry_is_skipped(self) -> None:
        names = ("alpha.txt", "beta.txt", "gamma")
        state = build_state(
            self.target,
            self.log,
            files_only=True,
            skips=SkipSelection(frozenset(names)),
        )
        self.assertTrue(state.all_skipped)
        self.assertEqual(state.remaining, ())
        self.assertEqual(state.remaining_total, 0)
        self.assertEqual(state.skipped, ("alpha.txt", "beta.txt", "gamma"))

        partial = build_state(
            self.target,
            self.log,
            files_only=True,
            skips=SkipSelection(frozenset({"alpha.txt"})),
        )
        self.assertFalse(partial.all_skipped)

    def test_all_skipped_excludes_logged_entries(self) -> None:
        self.history.append("alpha.txt")
        state = build_state(
            self.target,
            self.log,
            files_only=True,
            skips=SkipSelection(frozenset({"alpha.txt", "beta.txt", "gamma"})),
        )
        self.assertTrue(state.all_skipped)
        self.assertEqual(state.skipped, ("beta.txt", "gamma"))

    def test_skipped_list_is_not_truncated_by_panel_limit(self) -> None:
        names = [f"entry-{index:03d}" for index in range(5)]
        for name in names:
            (self.target / name).touch()
        state = build_state(
            self.target,
            self.log,
            max_lines=1,
            skips=SkipSelection(frozenset(names)),
        )
        self.assertEqual(len(state.remaining), 1)
        self.assertEqual(state.remaining_total, 4)
        self.assertEqual(state.skipped, tuple(sorted(names)))
        self.assertEqual(state.skipped_total, 5)

    def test_empty_skips_leave_the_existing_result_unchanged(self) -> None:
        baseline = build_state(self.target, self.log, max_lines=None)
        explicit = build_state(
            self.target,
            self.log,
            max_lines=None,
            skips=SkipSelection(),
        )
        self.assertEqual(baseline, explicit)
        self.assertEqual(baseline.skipped, ())
        self.assertFalse(baseline.all_skipped)

    def test_invalid_path_has_empty_skip_fields(self) -> None:
        state = build_state(
            self.target / "missing",
            self.log,
            skips=SkipSelection(frozenset({"alpha.txt"})),
        )
        self.assertFalse(state.valid_path)
        self.assertEqual(state.skipped, ())
        self.assertEqual(state.skipped_total, 0)
        self.assertEqual(state.skipped_present, ())
        self.assertFalse(state.all_skipped)


if __name__ == "__main__":
    unittest.main()
