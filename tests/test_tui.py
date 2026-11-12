"""Tests for choosier.tui display helpers and filter widgets."""

import tempfile
import unittest
from pathlib import Path
from typing import cast
from unittest.mock import patch

from rich.text import Text

from choosier.path_memory import MutationResult, PathMemory
from choosier.services import HistoryService, build_state, pick
from choosier.services.state import PANEL_MAX_LINES

try:
    from textual.widgets import (
        Button,
        Checkbox,
        Input,
        OptionList,
        RadioButton,
        RadioSet,
        SelectionList,
        Static,
        TabbedContent,
    )

    from choosier.filters import FilterOptions, FilterSelection
    from choosier.tui import (
        FILTERED_EMPTY_TEXT,
        FILTERED_EXHAUSTED_TEXT,
        ChooserApp,
        filter_notice,
        filter_summary,
        render_panel,
    )

    HAS_TEXTUAL = True
except ImportError:
    HAS_TEXTUAL = False


def _plain(content: object) -> str:
    return content.plain if isinstance(content, Text) else str(content)


def _prompts(selection_list: object) -> list[str]:
    return [
        _plain(option.prompt)
        for option in selection_list.options  # type: ignore[attr-defined]
    ]


@unittest.skipUnless(HAS_TEXTUAL, "ui extra (textual) not installed")
class FilterTextTest(unittest.TestCase):
    def _options(self, *, truncated: bool = False) -> "FilterOptions":
        return FilterOptions(
            types=(),
            entries=(),
            entries_total=5000 if truncated else 0,
            entries_truncated=truncated,
        )

    def test_not_ready_has_no_summary(self) -> None:
        self.assertEqual(
            filter_summary(None, eligible_entries=0, valid_path=False),
            "",
        )

    def test_invalid_path_message_precedes_empty_message(self) -> None:
        self.assertEqual(
            filter_summary(
                self._options(),
                eligible_entries=0,
                valid_path=False,
            ),
            "Choose a valid folder to see filter options.",
        )

    def test_empty_folder_and_pluralization(self) -> None:
        self.assertEqual(
            filter_summary(
                self._options(),
                eligible_entries=0,
                valid_path=True,
            ),
            "No eligible entries to filter.",
        )

    def test_no_filter_and_active_summaries(self) -> None:
        from choosier.filters import CandidateEntry, build_filter_options, type_key_for

        options = build_filter_options(
            [
                CandidateEntry("a.txt", False, type_key_for("a.txt", is_dir=False)),
                CandidateEntry("sub", True, type_key_for("sub", is_dir=True)),
            ]
        )
        self.assertEqual(
            filter_summary(options, eligible_entries=2, valid_path=True),
            "No filter: all 2 types checked; 2 of 2 entries eligible.",
        )
        self.assertEqual(
            filter_summary(
                options,
                eligible_entries=1,
                valid_path=True,
                excluded_types={"file:.txt"},
            ),
            "Filter active: 1 of 2 types checked; 1 of 2 entries eligible.",
        )

    def test_bounded_notice(self) -> None:
        from choosier.filters import FilterEntryOption, FilterTypeOption

        options = FilterOptions(
            types=(FilterTypeOption(key="file:.txt", label=".txt files", count=5000),),
            entries=tuple(
                FilterEntryOption(name=f"file{index}", type_key="file:.txt")
                for index in range(1000)
            ),
            entries_total=5000,
            entries_truncated=True,
        )
        self.assertEqual(filter_notice(self._options()), None)
        notice = filter_notice(options)
        assert notice is not None
        self.assertIn("Showing first 1000 of 5000 entries.", notice)
        self.assertIn(
            "Entries outside this list are unchanged here; type filters still "
            "apply to them.",
            notice,
        )


@unittest.skipUnless(HAS_TEXTUAL, "ui extra (textual) not installed")
class RenderPanelTest(unittest.TestCase):
    def test_empty_shows_placeholder(self) -> None:
        self.assertEqual(render_panel([], "(none)"), "(none)")

    def test_names_joined_and_escaped(self) -> None:
        self.assertEqual(render_panel(["a", "b[weird]"], "(none)"), "a\nb\\[weird]")

    def test_long_views_capped_with_count(self) -> None:
        lines = [f"item{i}" for i in range(5)]
        self.assertEqual(
            render_panel(lines, "(none)", max_lines=3),
            "(showing last 3 of 5)\nitem2\nitem3\nitem4",
        )
        self.assertEqual(render_panel(lines, "(none)", max_lines=5), "\n".join(lines))


@unittest.skipUnless(HAS_TEXTUAL, "ui extra (textual) not installed")
class TuiHistoryScenarioTest(unittest.TestCase):
    HISTORY_SIZE = PANEL_MAX_LINES + 50

    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "target"
        self.target.mkdir()
        self.log = self.target / ".choosier.jsonl"
        for index in range(self.HISTORY_SIZE):
            (self.target / f"item{index:03d}").touch()
        history = HistoryService(self.log)
        for index in range(self.HISTORY_SIZE):
            history.append(f"item{index:03d}")

    def test_long_history_panel_renders_the_last_200_lines(self) -> None:
        state = build_state(self.target, self.log, max_lines=None)
        self.assertEqual(state.history_total, self.HISTORY_SIZE)
        self.assertEqual(len(state.history), self.HISTORY_SIZE)
        self.assertEqual(state.remaining, ())
        history_lines = [entry.display for entry in state.history]
        rendered = render_panel(history_lines, "(no history yet)")
        lines = rendered.splitlines()
        self.assertEqual(
            lines[0],
            f"(showing last {PANEL_MAX_LINES} of {self.HISTORY_SIZE})",
        )
        self.assertEqual(lines[1:], history_lines[-PANEL_MAX_LINES:])
        self.assertTrue(history_lines[-1].endswith(f"item{self.HISTORY_SIZE - 1:03d}"))
        self.assertNotIn(history_lines[0], lines[1:])

    def test_archive_and_clear_match_shared_service_outcomes(self) -> None:
        history = HistoryService(self.log)
        backup = history.archive()
        self.assertIsNotNone(backup)
        assert backup is not None
        self.assertTrue(backup.name.endswith(".jsonl.old"))
        self.assertTrue(backup.exists())
        self.assertFalse(self.log.exists())
        state = build_state(self.target, self.log, max_lines=None)
        self.assertEqual(state.history_total, 0)
        self.assertEqual(state.history, ())
        self.assertEqual(
            render_panel(
                [entry.display for entry in state.history],
                "(no history yet)",
            ),
            "(no history yet)",
        )

        history.append("fresh")
        state = build_state(self.target, self.log, max_lines=None)
        self.assertEqual(state.history_total, 1)
        self.assertEqual([entry.item for entry in state.history], ["fresh"])
        self.assertTrue(history.clear())
        self.assertFalse(self.log.exists())
        self.assertFalse(history.clear())
        state = build_state(self.target, self.log, max_lines=None)
        self.assertEqual(state.history_total, 0)
        self.assertEqual(state.history, ())


@unittest.skipUnless(HAS_TEXTUAL, "ui extra (textual) not installed")
class TuiFilterScenarioTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.target = Path(self.tmp.name) / "target"
        self.target.mkdir()
        self.log = self.target / ".choosier.jsonl"

    def _touch(self, *names: str) -> None:
        for name in names:
            if name.endswith("/"):
                (self.target / name[:-1]).mkdir()
            else:
                (self.target / name).touch()

    def _summary(self, app: "ChooserApp") -> str:
        return _plain(app.query_one("#filter-summary", Static).content)

    def _remaining(self, app: "ChooserApp") -> str:
        return _plain(app.query_one("#remaining", Static).content)

    async def test_types_prompts_summary_and_filtered_remaining(self) -> None:
        self._touch("a.txt", "b.TXT", "c.jpg", "README", "sub/")
        app = ChooserApp(str(self.target))
        with patch("choosier.tui.build_state", wraps=build_state) as build_mock:
            async with app.run_test() as pilot:
                await pilot.pause()
                type_list = app.query_one("#type-filter", SelectionList)
                self.assertEqual(
                    _prompts(type_list),
                    [
                        "Folders (1)",
                        ".jpg files (1)",
                        ".txt files (2)",
                        "Files without an extension (1)",
                    ],
                )
                self.assertEqual(set(type_list.selected), app._visible_type_keys())
                self.assertEqual(
                    self._summary(app),
                    "No filter: all 4 types checked; 5 of 5 entries eligible.",
                )

                type_list.toggle("file:.txt")
                await pilot.pause()

                self.assertEqual(app._excluded_types, {"file:.txt"})
                self.assertEqual(self._remaining(app), "README\nc.jpg\nsub")
                self.assertEqual(
                    self._summary(app),
                    "Filter active: 3 of 4 types checked; 3 of 5 entries eligible.",
                )
                selections = [
                    call.kwargs["selection"]
                    for call in build_mock.call_args_list
                    if "selection" in call.kwargs
                ]
                self.assertIn(
                    FilterSelection(excluded_types=frozenset({"file:.txt"})),
                    selections,
                )

                with patch("choosier.tui.pick", wraps=pick) as pick_mock:
                    app.query_one("#dry-run", Checkbox).value = True
                    app.do_pick()
                    await pilot.pause()
                    self.assertIn(
                        FilterSelection(excluded_types=frozenset({"file:.txt"})),
                        [pick_mock.call_args.kwargs["selection"]],
                    )
                self.assertIn(
                    _plain(app.query_one("#choice", Static).content),
                    {"README", "c.jpg", "sub"},
                )

    async def test_hidden_and_mode_changes_rebuild_type_options(self) -> None:
        self._touch("a.txt", ".hidden.txt", "sub/")
        app = ChooserApp(str(self.target))
        async with app.run_test() as pilot:
            await pilot.pause()
            type_list = app.query_one("#type-filter", SelectionList)
            self.assertEqual(_prompts(type_list), ["Folders (1)", ".txt files (1)"])

            app.query_one("#include-hidden", Checkbox).value = True
            await pilot.pause()
            self.assertEqual(
                _prompts(type_list),
                ["Folders (1)", ".txt files (2)"],
            )

            radios = app.query_one("#mode", RadioSet).query(RadioButton)
            radios[1].value = True
            await pilot.pause()
            self.assertEqual(_prompts(type_list), [".txt files (2)"])

            radios[2].value = True
            await pilot.pause()
            self.assertEqual(_prompts(type_list), ["Folders (1)"])

    async def test_path_and_log_changes_reset_type_exclusions(self) -> None:
        self._touch("a.txt", "b.jpg")
        app = ChooserApp(str(self.target))
        async with app.run_test() as pilot:
            await pilot.pause()
            type_list = app.query_one("#type-filter", SelectionList)
            type_list.toggle("file:.txt")
            await pilot.pause()
            self.assertEqual(app._excluded_types, {"file:.txt"})

            log_input = app.query_one("#log-input", Input)
            log_input.value = str(self.target / "custom.jsonl")
            await pilot.pause()
            self.assertEqual(app._excluded_types, set())
            self.assertEqual(app._excluded_entries, set())
            self.assertEqual(self._summary(app), "")

            app._refresh_panels()
            await pilot.pause()
            self.assertEqual(
                self._summary(app),
                "No filter: all 2 types checked; 2 of 2 entries eligible.",
            )
            type_list.toggle("file:.txt")
            await pilot.pause()

            path_input = app.query_one("#path-input", Input)
            path_input.value = str(self.target / "missing")
            await pilot.pause()
            self.assertEqual(app._excluded_types, set())
            self.assertEqual(self._summary(app), "")
            app._refresh_panels()
            await pilot.pause()
            self.assertEqual(
                self._summary(app),
                "Choose a valid folder to see filter options.",
            )

    async def test_options_tab_activation_rebuilds_the_lists(self) -> None:
        self._touch("a.txt")
        app = ChooserApp(str(self.target))
        async with app.run_test() as pilot:
            await pilot.pause()
            self._touch("new.md")
            app.query_one(TabbedContent).active = "options-tab"
            await pilot.pause()
            self.assertIn("new.md", app._visible_entry_names())
            type_list = app.query_one("#type-filter", SelectionList)
            self.assertEqual(_prompts(type_list), [".md files (1)", ".txt files (1)"])

    async def test_filtered_empty_and_exhausted_messages(self) -> None:
        self._touch("a.txt")
        app = ChooserApp(str(self.target))
        async with app.run_test() as pilot:
            await pilot.pause()
            app.query_one("#type-filter", SelectionList).toggle("file:.txt")
            await pilot.pause()
            app.do_pick()
            await pilot.pause()
            self.assertEqual(
                _plain(app.query_one("#status", Static).content), FILTERED_EMPTY_TEXT
            )
            self.assertFalse(self.log.exists())

        other = Path(self.tmp.name) / "exhausted"
        other.mkdir()
        for name in ("x.txt", "y.txt", "z.jpg"):
            (other / name).touch()
        app = ChooserApp(str(other))
        async with app.run_test() as pilot:
            await pilot.pause()
            type_list = app.query_one("#type-filter", SelectionList)
            type_list.toggle("file:.jpg")
            await pilot.pause()
            app.do_pick()
            await pilot.pause()
            app.do_pick()
            await pilot.pause()
            app.do_pick()
            await pilot.pause()
            self.assertEqual(
                _plain(app.query_one("#status", Static).content),
                FILTERED_EXHAUSTED_TEXT,
            )
            log = other / ".choosier.jsonl"
            self.assertEqual(log.read_text(encoding="utf-8").count("\n"), 2)

    async def test_entry_prompts_include_names_and_type_labels_literally(self) -> None:
        self._touch("[draft] notes.txt", "odd.[x]", "sub/")
        app = ChooserApp(str(self.target))
        async with app.run_test() as pilot:
            await pilot.pause()
            type_list = app.query_one("#type-filter", SelectionList)
            entry_list = app.query_one("#entry-filter", SelectionList)
            self.assertIn(".[x] files (1)", _prompts(type_list))
            self.assertEqual(
                _prompts(entry_list),
                [
                    "[draft] notes.txt   .txt files",
                    "odd.[x]   .[x] files",
                    "sub   Folders",
                ],
            )

    async def test_entry_and_type_exclusions_intersect_and_restore(self) -> None:
        self._touch("a.txt", "b.txt", "c.jpg", "sub/")
        app = ChooserApp(str(self.target))
        with patch("choosier.tui.build_state", wraps=build_state) as build_mock:
            async with app.run_test() as pilot:
                await pilot.pause()
                entry_list = app.query_one("#entry-filter", SelectionList)
                entry_list.toggle("b.txt")
                await pilot.pause()
                app.query_one("#type-filter", SelectionList).toggle("file:.jpg")
                await pilot.pause()

                self.assertEqual(app._excluded_entries, {"b.txt"})
                self.assertEqual(app._excluded_types, {"file:.jpg"})
                expected = FilterSelection(
                    excluded_types=frozenset({"file:.jpg"}),
                    excluded_entries=frozenset({"b.txt"}),
                )
                selections = [
                    call.kwargs["selection"]
                    for call in build_mock.call_args_list
                    if "selection" in call.kwargs
                ]
                self.assertIn(expected, selections)
                self.assertEqual(self._remaining(app), "a.txt\nsub")

                entry_list.toggle("b.txt")
                await pilot.pause()
                self.assertEqual(app._excluded_entries, set())
                self.assertEqual(self._remaining(app), "a.txt\nb.txt\nsub")

                with patch("choosier.tui.pick", wraps=pick) as pick_mock:
                    app.query_one("#dry-run", Checkbox).value = True
                    app.do_pick()
                    await pilot.pause()
                    self.assertEqual(
                        pick_mock.call_args.kwargs["selection"],
                        FilterSelection(excluded_types=frozenset({"file:.jpg"})),
                    )
                    self.assertIn(
                        _plain(app.query_one("#choice", Static).content),
                        {"a.txt", "b.txt", "sub"},
                    )

    async def test_logged_entry_stays_out_after_rechecking(self) -> None:
        self._touch("a.txt", "b.txt")
        HistoryService(self.log).append("b.txt")
        app = ChooserApp(str(self.target))
        async with app.run_test() as pilot:
            await pilot.pause()
            entry_list = app.query_one("#entry-filter", SelectionList)
            entry_list.toggle("b.txt")
            await pilot.pause()
            entry_list.toggle("b.txt")
            await pilot.pause()
            self.assertEqual(app._excluded_entries, set())
            self.assertEqual(self._remaining(app), "a.txt")

    async def test_entry_actions_preserve_names_outside_the_visible_cap(self) -> None:
        for index in range(1005):
            (self.target / f"f{index:05d}.txt").touch()
        outside = "f01004.txt"
        app = ChooserApp(str(self.target))
        async with app.run_test() as pilot:
            await pilot.pause()
            options = app._filter_options
            assert options is not None
            self.assertEqual(options.entries_total, 1005)
            self.assertEqual(len(options.entries), 1000)

            app._excluded_entries.add(outside)
            app._refresh_panels()
            await pilot.pause()
            self.assertIn(outside, app._known_entry_exclusions)
            self.assertIn(outside, app._excluded_entries)

            entry_list = app.query_one("#entry-filter", SelectionList)
            entry_list.toggle("f00000.txt")
            await pilot.pause()
            self.assertIn(outside, app._excluded_entries)
            self.assertIn("f00000.txt", app._excluded_entries)

            app.query_one("#entries-none", Button).press()
            await pilot.pause()
            self.assertIn(outside, app._excluded_entries)
            self.assertEqual(len(app._excluded_entries), 1001)

            app.query_one("#entries-all", Button).press()
            await pilot.pause()
            self.assertEqual(app._excluded_entries, {outside})

            notice = app.query_one("#filter-notice", Static)
            self.assertTrue(notice.display)
            self.assertIn("Showing first 1000 of 1005 entries.", _plain(notice.content))
            self.assertIn(
                "Entries outside this list are unchanged here; type filters still "
                "apply to them.",
                _plain(notice.content),
            )
            self.assertEqual(
                self._summary(app),
                "Filter active: 1 of 1 type checked; 1004 of 1005 entries eligible.",
            )

    async def test_clear_filters_resets_both_sets_and_lists(self) -> None:
        self._touch("a.txt", "b.jpg", "sub/")
        app = ChooserApp(str(self.target))
        async with app.run_test() as pilot:
            await pilot.pause()
            app.query_one("#type-filter", SelectionList).toggle("dir")
            app.query_one("#entry-filter", SelectionList).toggle("b.jpg")
            await pilot.pause()
            self.assertTrue(app._excluded_types)
            self.assertTrue(app._excluded_entries)
            clear = app.query_one("#clear-filters", Button)
            self.assertFalse(clear.disabled)

            clear.press()
            await pilot.pause()
            self.assertEqual(app._excluded_types, set())
            self.assertEqual(app._excluded_entries, set())
            self.assertEqual(
                set(app.query_one("#type-filter", SelectionList).selected),
                app._visible_type_keys(),
            )
            options = app._filter_options
            assert options is not None
            self.assertEqual(
                set(app.query_one("#entry-filter", SelectionList).selected),
                {item.name for item in options.entries},
            )
            self.assertTrue(clear.disabled)
            self.assertEqual(
                self._summary(app),
                "No filter: all 3 types checked; 3 of 3 entries eligible.",
            )

    async def test_summary_is_history_aware_and_invalid_path_is_distinct(self) -> None:
        self._touch("a.txt", "b.txt", "sub/")
        HistoryService(self.log).append("a.txt")
        app = ChooserApp(str(self.target))
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertEqual(
                self._summary(app),
                "No filter: all 2 types checked; 2 of 3 entries eligible.",
            )

            app.query_one("#path-input", Input).value = str(self.target / "missing")
            app._refresh_panels()
            await pilot.pause()
            self.assertEqual(
                self._summary(app),
                "Choose a valid folder to see filter options.",
            )
            self.assertEqual(
                _plain(app.query_one("#remaining", Static).content), "(none)"
            )
            self.assertFalse(app.query_one("#filter-notice", Static).display)

    async def test_current_choice_survives_path_and_log_changes(self) -> None:
        self._touch("only.txt")
        app = ChooserApp(str(self.target))
        async with app.run_test() as pilot:
            await pilot.pause()
            app.do_pick()
            await pilot.pause()
            self.assertEqual(app._current_choice, self.target / "only.txt")

            path_input = app.query_one("#path-input", Input)
            path_input.value = str(self.target / "next")
            app.query_one("#log-input", Input).value = "custom.jsonl"
            await pilot.pause()
            self.assertEqual(app._current_choice, self.target / "only.txt")

    async def test_filter_controls_are_keyboard_focusable_and_labelled(self) -> None:
        self._touch("a.txt", "sub/")
        app = ChooserApp(str(self.target))
        async with app.run_test() as pilot:
            await pilot.pause()
            for widget_id in (
                "#types-all",
                "#types-none",
                "#entries-all",
                "#entries-none",
                "#type-filter",
                "#entry-filter",
                "#clear-filters",
            ):
                self.assertTrue(
                    app.query_one(widget_id).can_focus,
                    widget_id,
                )
            labels = [
                _plain(cast(Static, widget).content)
                for widget in app.query(".filter-label")
            ]
            self.assertEqual(labels, ["Types", "Entries"])
            self.assertEqual(
                _plain(app.query_one("#types-all", Button).label),
                "All types",
            )
            self.assertEqual(
                _plain(app.query_one("#entries-none", Button).label),
                "No entries",
            )


@unittest.skipUnless(HAS_TEXTUAL, "ui extra (textual) not installed")
class TuiPathMemoryScenarioTest(unittest.IsolatedAsyncioTestCase):
    def setUp(self) -> None:
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.target = self.root / "target"
        self.target.mkdir()
        (self.target / "a.txt").touch()
        self.memory = PathMemory()

    def _folder(self, name: str, *files: str) -> Path:
        folder = self.root / name
        folder.mkdir()
        for file_name in files:
            (folder / file_name).touch()
        return folder

    def _input(self, app: "ChooserApp") -> str:
        return app.query_one("#path-input", Input).value

    def _status(self, app: "ChooserApp") -> str:
        return _plain(app.query_one("#status", Static).content)

    def _remaining(self, app: "ChooserApp") -> str:
        return _plain(app.query_one("#remaining", Static).content)

    def _recent_paths(self, app: "ChooserApp") -> list[str]:
        recent_list = app.query_one("#recent-paths", OptionList)
        return [_plain(option.prompt) for option in recent_list.options]

    async def test_empty_launch_restores_the_remembered_folder(self) -> None:
        self.memory.record(self.target)
        app = ChooserApp("")
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertEqual(self._input(app), str(self.target.resolve()))
            self.assertIn("a.txt", self._remaining(app))
            self.assertIsNone(app._current_choice)
            self.assertEqual(app._excluded_types, set())
            self.assertEqual(app._excluded_entries, set())

    async def test_explicit_path_wins_even_when_invalid(self) -> None:
        self.memory.record(self.target)
        missing = str(self.root / "missing")
        app = ChooserApp(missing)
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertEqual(self._input(app), missing)
            app.do_pick()
            await pilot.pause()
            self.assertEqual(self._status(app), "Invalid Path.")
            self.assertEqual(
                self.memory.snapshot().recent,
                (str(self.target.resolve()),),
            )

    async def test_stale_recent_falls_back_and_is_pruned(self) -> None:
        stale = self._folder("stale")
        self.memory.record(self.target)
        self.memory.record(stale)
        stale.rmdir()
        app = ChooserApp("")
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertEqual(self._input(app), str(self.target.resolve()))
            self.assertIn("unavailable", self._status(app))
            self.assertEqual(
                self.memory.snapshot().recent,
                (str(self.target.resolve()),),
            )

    async def test_first_run_stays_empty(self) -> None:
        app = ChooserApp("")
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertEqual(self._input(app), "")
            self.assertEqual(self._status(app), "")
            self.assertFalse(self.memory.file.exists())

    async def test_successful_and_dry_run_picks_record(self) -> None:
        app = ChooserApp(str(self.target))
        async with app.run_test() as pilot:
            await pilot.pause()
            app.do_pick()
            await pilot.pause()
            self.assertIn("Logged in", self._status(app))
            self.assertEqual(
                self.memory.snapshot().recent,
                (str(self.target.resolve()),),
            )

        other = self._folder("other", "b.txt")
        app = ChooserApp(str(other))
        async with app.run_test() as pilot:
            await pilot.pause()
            app.query_one("#dry-run", Checkbox).value = True
            app.do_pick()
            await pilot.pause()
            self.assertIn("Dry run", self._status(app))
            self.assertEqual(
                self.memory.snapshot().recent[0],
                str(other.resolve()),
            )
            self.assertFalse((other / ".choosier.jsonl").exists())

    async def test_empty_exhausted_and_invalid_picks_do_not_record(self) -> None:
        empty = self._folder("empty")
        app = ChooserApp(str(empty))
        async with app.run_test() as pilot:
            await pilot.pause()
            app.do_pick()
            await pilot.pause()
            self.assertEqual(self._status(app), "Path Empty.")
            self.assertEqual(self.memory.snapshot().recent, ())

        exhausted = self._folder("exhausted", "only.txt")
        HistoryService(exhausted / ".choosier.jsonl").append("only.txt")
        app = ChooserApp(str(exhausted))
        async with app.run_test() as pilot:
            await pilot.pause()
            app.do_pick()
            await pilot.pause()
            self.assertIn("All choices have been selected", self._status(app))
            self.assertEqual(self.memory.snapshot().recent, ())

        app = ChooserApp(str(self.root / "missing"))
        async with app.run_test() as pilot:
            await pilot.pause()
            app.do_pick()
            await pilot.pause()
            self.assertEqual(self._status(app), "Invalid Path.")
            self.assertEqual(self.memory.snapshot().recent, ())

    async def test_record_notice_is_shown_without_losing_the_pick(self) -> None:
        notice = MutationResult(False, False, "Could not remember this folder.")
        app = ChooserApp(str(self.target))
        with patch("choosier.tui.PathMemory.record", return_value=notice):
            async with app.run_test() as pilot:
                await pilot.pause()
                app.do_pick()
                await pilot.pause()
                status = self._status(app)
                self.assertIn("Logged in", status)
                self.assertIn("Could not remember this folder.", status)
                self.assertIsNotNone(app._current_choice)

    async def test_recent_list_shows_valid_paths_newest_first(self) -> None:
        first = self._folder("first", "a.txt")
        second = self._folder("second", "b.txt")
        self.memory.record(first)
        self.memory.record(second)
        app = ChooserApp(str(self.target))
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertEqual(
                self._recent_paths(app),
                [str(second.resolve()), str(first.resolve())],
            )
            self.assertTrue(app.query_one("#recent-paths", OptionList).can_focus)
            self.assertFalse(app.query_one("#recent-use", Button).disabled)

    async def test_recent_list_omits_stale_entries(self) -> None:
        stale = self._folder("stale")
        self.memory.record(self.target)
        self.memory.record(stale)
        stale.rmdir()
        app = ChooserApp(str(self.target))
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertEqual(
                self._recent_paths(app),
                [str(self.target.resolve())],
            )
            self.assertIn(
                "unavailable",
                _plain(app.query_one("#recent-warning", Static).content),
            )
            self.assertEqual(
                self.memory.snapshot().recent,
                (str(self.target.resolve()),),
            )

    async def test_use_sets_the_path_input_and_refreshes_panels(self) -> None:
        other = self._folder("other", "b.txt")
        self.memory.record(self.target)
        self.memory.record(other)
        app = ChooserApp(str(self.target))
        async with app.run_test() as pilot:
            await pilot.pause()
            app.query_one("#recent-paths", OptionList).highlighted = 1
            app.query_one("#recent-use", Button).press()
            await pilot.pause()
            self.assertEqual(self._input(app), str(self.target.resolve()))
            self.assertIn("a.txt", self._remaining(app))
            self.assertIn(
                f"Using {self.target.resolve()}",
                self._status(app),
            )

    async def test_recent_controls_are_keyboard_reachable(self) -> None:
        other = self._folder("other", "b.txt")
        self.memory.record(other)
        self.memory.record(self.target)
        app = ChooserApp(str(self.target))
        async with app.run_test() as pilot:
            await pilot.pause()
            app.query_one("#tabs", TabbedContent).active = "options-tab"
            await pilot.pause()
            recent_list = app.query_one("#recent-paths", OptionList)
            self.assertTrue(recent_list.can_focus)
            recent_list.focus()
            await pilot.pause()
            self.assertIs(app.focused, recent_list)
            await pilot.press("down")
            await pilot.press("down")
            await pilot.pause()
            self.assertEqual(recent_list.highlighted, 1)

            use_button = app.query_one("#recent-use", Button)
            self.assertTrue(use_button.can_focus)
            use_button.focus()
            await pilot.pause()
            self.assertIs(app.focused, use_button)

    async def test_recent_list_refreshes_after_a_successful_pick(self) -> None:
        other = self._folder("other", "b.txt")
        self.memory.record(self.target)
        app = ChooserApp(str(self.target))
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertEqual(
                self._recent_paths(app),
                [str(self.target.resolve())],
            )
            app.query_one("#path-input", Input).value = str(other)
            app.do_pick()
            await pilot.pause()
            self.assertEqual(
                self._recent_paths(app),
                [str(other.resolve()), str(self.target.resolve())],
            )

    async def test_restore_does_not_restore_session_state(self) -> None:
        HistoryService(self.target / ".choosier.jsonl").append("a.txt")
        self.memory.record(self.target)
        app = ChooserApp("")
        async with app.run_test() as pilot:
            await pilot.pause()
            self.assertEqual(self._input(app), str(self.target.resolve()))
            self.assertIsNone(app._current_choice)
            self.assertEqual(app._excluded_types, set())
            self.assertEqual(app._excluded_entries, set())
            self.assertNotIn("a.txt", self._remaining(app))
            history = _plain(app.query_one("#history", Static).content)
            self.assertIn("a.txt", history)


if __name__ == "__main__":
    unittest.main()
