"""Terminal UI for choosier (requires the `ui` extra)."""

from collections.abc import Collection
from pathlib import Path

from rich.markup import escape
from rich.text import Text
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    DirectoryTree,
    Footer,
    Header,
    Input,
    OptionList,
    RadioButton,
    RadioSet,
    SelectionList,
    Static,
    TabbedContent,
    TabPane,
)
from textual.widgets.selection_list import Selection

from choosier.chooser import parse_seed, resolve_log_path
from choosier.filters import FilterOptions, FilterSelection
from choosier.path_memory import PathMemory
from choosier.preview import preview_entry
from choosier.services import (
    FailureKind,
    HistoryService,
    ServiceError,
    build_state,
    open_entry,
    pick,
)
from choosier.services.state import PANEL_MAX_LINES

NO_CHOICE_TEXT = "No choice yet — enter a directory and press Pick."
MODE_LABELS = ("all", "files", "dirs")
FILTERED_EMPTY_TEXT = "Filters exclude every entry. Clear filters or adjust selections."
FILTERED_EXHAUSTED_TEXT = (
    "All entries matching the filters have been selected. "
    "Clear filters or reset history."
)


def _plural(count: int, singular: str, plural_form: str) -> str:
    return f"{count} {singular if count == 1 else plural_form}"


def filter_summary(
    options: FilterOptions | None,
    *,
    eligible_entries: int,
    valid_path: bool,
    excluded_types: Collection[str] = (),
    excluded_entries: Collection[str] = (),
) -> str:
    """The exact summary text shared with the web filter panel."""
    if options is None:
        return ""
    if not valid_path:
        return "Choose a valid folder to see filter options."
    types_count = len(options.types)
    if types_count == 0:
        return "No eligible entries to filter."
    type_keys = {item.key for item in options.types}
    checked = len(type_keys - set(excluded_types))
    prefix = (
        f"Filter active: {checked} of {_plural(types_count, 'type', 'types')} checked"
        if excluded_types or excluded_entries
        else f"No filter: all {_plural(types_count, 'type', 'types')} checked"
    )
    eligible = max(0, eligible_entries)
    entries = _plural(options.entries_total, "entry", "entries")
    return f"{prefix}; {eligible} of {entries} eligible."


def filter_notice(options: FilterOptions | None) -> str | None:
    """The bounded-entry notice, or None when every entry is visible."""
    if options is None or not options.entries_truncated:
        return None
    return (
        f"Showing first {len(options.entries)} of {options.entries_total} entries. "
        "Select all and Clear selection apply to these visible entries. "
        "Entries outside this list are unchanged here; type filters still apply "
        "to them."
    )


def render_panel(
    lines: list[str], empty_text: str, max_lines: int = PANEL_MAX_LINES
) -> str:
    """Render view lines, markup-escaped so filenames display literally.

    Long views are capped to the newest entries with a count header.
    """
    if not lines:
        return empty_text
    if len(lines) > max_lines:
        shown = lines[-max_lines:]
        header = f"(showing last {max_lines} of {len(lines)})\n"
    else:
        shown = lines
        header = ""
    return header + "\n".join(escape(line) for line in shown)


class ConfirmScreen(ModalScreen[bool]):
    """Yes/no confirmation dialog."""

    CSS = """
    ConfirmScreen {
        align: center middle;
    }
    #confirm-box {
        width: 60;
        height: auto;
        border: solid red;
        padding: 1 2;
    }
    """

    def __init__(self, message: str) -> None:
        super().__init__()
        self._message = message

    def compose(self) -> ComposeResult:
        with Vertical(id="confirm-box"):
            yield Static(escape(self._message))
            with Horizontal():
                yield Button("Yes, delete", id="yes", variant="error")
                yield Button("Cancel", id="no", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


class ChooserApp(App[None]):
    """Interactive directory picker with persistent history."""

    CSS = """
    #choice {
        height: 3;
        content-align: center middle;
        text-style: bold;
        border: solid green;
    }
    #status {
        height: 3;
    }
    #main {
        height: 1fr;
    }
    #left {
        width: 1fr;
        height: 100%;
    }
    #preview-wrap {
        height: 1fr;
        min-height: 4;
        overflow-y: auto;
    }
    #checks {
        height: 3;
    }
    #actions {
        height: 3;
    }
    #tabs {
        width: 1fr;
        height: 100%;
    }
    #options-body {
        height: 1fr;
    }
    .filter-label,
    .recent-label {
        margin-top: 1;
        color: #dde4e2;
        text-style: bold;
    }
    #filter-summary {
        height: auto;
        margin-top: 1;
        color: #98a4a7;
    }
    #type-actions,
    #entry-actions {
        height: 3;
    }
    #type-filter,
    #entry-filter {
        height: 10;
        border: solid #2a343a;
    }
    #filter-notice,
    #recent-warning {
        height: auto;
        margin-top: 1;
        padding: 0 1;
        background: #0a0f12;
        color: #d9a23a;
    }
    #recent-paths {
        height: 8;
        border: solid #2a343a;
    }
    #recent-empty {
        height: auto;
        color: #98a4a7;
    }
    #recent-actions {
        height: 3;
    }
    #clear-filters {
        margin-top: 1;
        width: auto;
    }
    """

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+n", "pick", "Pick"),
    ]

    def __init__(self, initial_path: str = "", log_file: str | None = None) -> None:
        super().__init__()
        self._initial_path = initial_path
        self._initial_log = log_file or ""
        self._current_choice: Path | None = None
        self._excluded_types: set[str] = set()
        self._excluded_entries: set[str] = set()
        self._filter_options: FilterOptions | None = None
        self._known_entry_exclusions: set[str] = set()
        self._filter_scope: tuple[Path, Path] | None = None
        self._syncing_filters = False
        self._last_remaining_total = 0
        self._last_valid_path = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(
            value=self._initial_path,
            placeholder="Directory path",
            id="path-input",
        )
        with Horizontal(id="main"):
            with Vertical(id="left"):
                yield Static(NO_CHOICE_TEXT, id="choice")
                with Vertical(id="preview-wrap"):
                    yield Static("(preview appears here)", id="preview")
                with Horizontal(id="actions"):
                    yield Button("Pick", id="pick", variant="primary")
                    yield Button("Open", id="open")
                yield Static("", id="status")
            with TabbedContent(id="tabs"):
                with TabPane("Browse", id="browse-tab"):
                    yield DirectoryTree(Path.home(), id="browser")
                with TabPane("Remaining", id="remaining-tab"):
                    yield Static("(none)", id="remaining")
                with TabPane("History", id="history-tab"):
                    yield Static("(no history yet)", id="history")
                    yield Button("Archive history", id="archive")
                    yield Button("Clear history", id="clear", variant="error")
                with TabPane("Options", id="options-tab"):
                    with VerticalScroll(id="options-body"):
                        yield Static("Recent folders", classes="recent-label")
                        yield Static(
                            "No remembered folders yet.",
                            id="recent-empty",
                        )
                        yield OptionList(id="recent-paths")
                        with Horizontal(id="recent-actions"):
                            yield Button(
                                "Use",
                                id="recent-use",
                                disabled=True,
                            )
                            yield Button(
                                "Remove",
                                id="recent-remove",
                                disabled=True,
                            )
                            yield Button(
                                "Clear recent",
                                id="recent-clear",
                                disabled=True,
                            )
                        yield Static("", id="recent-warning")
                        yield Input(
                            value=self._initial_log,
                            placeholder=(
                                "Log file (empty = <directory>/.choosier.jsonl)"
                            ),
                            id="log-input",
                        )
                        yield Input(
                            placeholder="Seed (empty = random)", id="seed-input"
                        )
                        with Horizontal(id="checks"):
                            yield Checkbox("Dry run (don't log)", id="dry-run")
                            yield Checkbox("Include hidden", id="include-hidden")
                        yield RadioSet(
                            RadioButton("Files and dirs", value=True),
                            RadioButton("Files only"),
                            RadioButton("Dirs only"),
                            id="mode",
                        )
                        yield Static("", id="filter-summary")
                        yield Static("Types", classes="filter-label")
                        with Horizontal(id="type-actions"):
                            yield Button("All types", id="types-all")
                            yield Button("No types", id="types-none")
                        yield SelectionList(id="type-filter", disabled=True)
                        yield Static("Entries", classes="filter-label")
                        with Horizontal(id="entry-actions"):
                            yield Button("All entries", id="entries-all")
                            yield Button("No entries", id="entries-none")
                        yield SelectionList(id="entry-filter", disabled=True)
                        yield Static("", id="filter-notice")
                        yield Button("Clear filters", id="clear-filters", disabled=True)
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#open", Button).disabled = True
        self.query_one("#pick", Button).focus()
        self._apply_startup_memory()
        self._refresh_recent_paths()
        self._refresh_panels()

    def _apply_startup_memory(self) -> None:
        """Fill an empty launch path from the first valid remembered folder."""
        if self._initial_path:
            return
        resolution = PathMemory().startup(Path(""))
        if resolution.source == "recent":
            self.query_one("#path-input", Input).value = str(resolution.path)
        if resolution.warning:
            self._set_status(resolution.warning)

    def action_pick(self) -> None:
        """Pick action, also bound to ctrl+n (ctrl+p is the palette)."""
        self.do_pick()

    @property
    def _target(self) -> Path:
        return Path(self.query_one("#path-input", Input).value).expanduser()

    def _current_log_path(self) -> Path:
        return resolve_log_path(self._target, self.query_one("#log-input", Input).value)

    def _picker_flags(self) -> dict[str, bool]:
        mode = MODE_LABELS[self.query_one("#mode", RadioSet).pressed_index]
        return {
            "include_hidden": self.query_one("#include-hidden", Checkbox).value,
            "files_only": mode == "files",
            "dirs_only": mode == "dirs",
        }

    def _set_status(self, message: str) -> None:
        self.query_one("#status", Static).update(escape(message))

    def _show_choice(self, message: str) -> None:
        self.query_one("#choice", Static).update(message)
        self.query_one("#open", Button).disabled = False

    def _update_preview(self) -> None:
        if self._current_choice is None:
            text = "(preview appears here)"
        else:
            text = preview_entry(self._current_choice).text
        self.query_one("#preview", Static).update(escape(text))

    def _sync_filter_scope(self) -> bool:
        """Reset exclusions when the folder or log target changes."""
        scope = (self._target, self._current_log_path())
        if self._filter_scope == scope:
            return False
        self._filter_scope = scope
        self._excluded_types.clear()
        self._excluded_entries.clear()
        self._filter_options = None
        self._known_entry_exclusions.clear()
        return True

    def _filter_selection(self) -> FilterSelection:
        return FilterSelection(
            excluded_types=frozenset(self._excluded_types),
            excluded_entries=frozenset(self._excluded_entries),
        )

    def _clear_filter_lists(self) -> None:
        self._syncing_filters = True
        try:
            for widget_id in ("#type-filter", "#entry-filter"):
                widget = self.query_one(widget_id, SelectionList)
                widget.clear_options()
                widget.disabled = True
        finally:
            self._syncing_filters = False

    def _rebuild_filter_lists(self) -> None:
        options = self._filter_options
        labels = {item.key: item.label for item in options.types} if options else {}
        type_list = self.query_one("#type-filter", SelectionList)
        entry_list = self.query_one("#entry-filter", SelectionList)
        self._syncing_filters = True
        try:
            type_list.clear_options()
            entry_list.clear_options()
            if options is not None:
                type_list.add_options(
                    Selection(
                        Text(f"{item.label} ({item.count})"),
                        item.key,
                        item.key not in self._excluded_types,
                    )
                    for item in options.types
                )
                entry_list.add_options(
                    Selection(
                        Text(
                            f"{item.name}   {labels.get(item.type_key, item.type_key)}"
                        ),
                        item.name,
                        item.name not in self._excluded_entries,
                    )
                    for item in options.entries
                )
            type_list.disabled = not (options and options.types)
            entry_list.disabled = not (options and options.entries)
        finally:
            self._syncing_filters = False

    def _update_filter_widgets(self) -> None:
        options = self._filter_options
        self.query_one("#filter-summary", Static).update(
            escape(
                filter_summary(
                    options,
                    eligible_entries=self._last_remaining_total,
                    valid_path=self._last_valid_path,
                    excluded_types=self._excluded_types,
                    excluded_entries=self._excluded_entries,
                )
            )
        )
        notice = filter_notice(options)
        notice_widget = self.query_one("#filter-notice", Static)
        notice_widget.display = notice is not None
        if notice is not None:
            notice_widget.update(escape(notice))
        active = bool(self._excluded_types or self._excluded_entries)
        self.query_one("#clear-filters", Button).disabled = not active
        add_types = bool(options and options.types)
        add_entries = bool(options and options.entries)
        for widget_id, enabled in (
            ("#types-all", add_types),
            ("#types-none", add_types),
            ("#entries-all", add_entries),
            ("#entries-none", add_entries),
        ):
            self.query_one(widget_id, Button).disabled = not enabled

    def _refresh_panels(self, rebuild_filters: bool = True) -> None:
        self._sync_filter_scope()
        snapshot = build_state(
            self._target,
            self._current_log_path(),
            max_lines=None,
            selection=self._filter_selection(),
            **self._picker_flags(),
        )
        self._filter_options = snapshot.filter_options
        self._known_entry_exclusions = set(snapshot.known_entry_exclusions)
        self._last_remaining_total = snapshot.remaining_total
        self._last_valid_path = snapshot.valid_path
        present_types = {item.key for item in snapshot.filter_options.types}
        self._excluded_types &= present_types
        self._excluded_entries &= self._known_entry_exclusions
        self.query_one("#remaining", Static).update(
            render_panel(list(snapshot.remaining), "(none)")
        )
        self.query_one("#history", Static).update(
            render_panel(
                [entry.display for entry in snapshot.history],
                "(no history yet)",
            )
        )
        self.query_one("#filter-summary", Static).update(
            escape(
                filter_summary(
                    snapshot.filter_options,
                    eligible_entries=snapshot.remaining_total,
                    valid_path=snapshot.valid_path,
                    excluded_types=self._excluded_types,
                    excluded_entries=self._excluded_entries,
                )
            )
        )
        notice = filter_notice(snapshot.filter_options)
        notice_widget = self.query_one("#filter-notice", Static)
        notice_widget.display = notice is not None
        if notice is not None:
            notice_widget.update(escape(notice))
        self.query_one("#clear-filters", Button).disabled = not (
            self._excluded_types or self._excluded_entries
        )
        add_types = bool(snapshot.filter_options.types)
        add_entries = bool(snapshot.filter_options.entries)
        for widget_id, enabled in (
            ("#types-all", add_types),
            ("#types-none", add_types),
            ("#entries-all", add_entries),
            ("#entries-none", add_entries),
        ):
            self.query_one(widget_id, Button).disabled = not enabled
        if rebuild_filters:
            self._rebuild_filter_lists()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "pick":
            self.do_pick()
        elif event.button.id == "open":
            self._open_current()
        elif event.button.id == "archive":
            self._archive_history()
        elif event.button.id == "clear":
            self._ask_clear()
        elif event.button.id == "types-all":
            self._select_all_types()
        elif event.button.id == "types-none":
            self._clear_all_types()
        elif event.button.id == "entries-all":
            self._select_all_entries()
        elif event.button.id == "entries-none":
            self._clear_all_entries()
        elif event.button.id == "clear-filters":
            self._clear_filters_all()
        elif event.button.id == "recent-use":
            self._use_recent_path()
        elif event.button.id == "recent-remove":
            self._remove_recent_path()
        elif event.button.id == "recent-clear":
            self._clear_recent_paths()

    def _refresh_recent_paths(self) -> None:
        """Rebuild the recent-folder list without touching the active path."""
        snapshot = PathMemory().snapshot()
        recent_list = self.query_one("#recent-paths", OptionList)
        recent_list.clear_options()
        recent_list.add_options(snapshot.recent)
        recent_list.disabled = not snapshot.recent
        self.query_one("#recent-empty", Static).display = not snapshot.recent
        empty = not snapshot.recent
        self.query_one("#recent-use", Button).disabled = empty
        self.query_one("#recent-remove", Button).disabled = empty
        self.query_one("#recent-clear", Button).disabled = empty
        warning_widget = self.query_one("#recent-warning", Static)
        warning_widget.display = snapshot.warning is not None
        if snapshot.warning is not None:
            warning_widget.update(escape(snapshot.warning))

    def _highlighted_recent_path(self) -> str | None:
        """Return the highlighted remembered folder, if any."""
        recent_list = self.query_one("#recent-paths", OptionList)
        if recent_list.option_count == 0:
            return None
        index = recent_list.highlighted
        if index is None:
            index = 0
        prompt = recent_list.get_option_at_index(index).prompt
        return prompt.plain if isinstance(prompt, Text) else str(prompt)

    def _use_recent_path(self) -> None:
        """Activate the highlighted remembered folder in the path input."""
        path = self._highlighted_recent_path()
        if path is None:
            self._set_status("No remembered folders yet.")
            return
        self.query_one("#path-input", Input).value = path
        self._set_status(f"Using {path}.")
        self._refresh_panels()
        self._refresh_recent_paths()

    def _remove_recent_path(self) -> None:
        """Forget the highlighted remembered folder, leaving the input alone."""
        path = self._highlighted_recent_path()
        if path is None:
            self._set_status("No remembered folders yet.")
            return
        result = PathMemory().remove(path)
        if not result.ok:
            self._set_status(result.notice or "Could not update remembered folders.")
            return
        self._set_status(
            f"Removed {path} from remembered folders."
            if result.changed
            else f"{path} is not a remembered folder."
        )
        self._refresh_recent_paths()

    def _clear_recent_paths(self) -> None:
        """Forget all remembered folders, leaving the input alone."""
        result = PathMemory().clear()
        if not result.ok:
            self._set_status(result.notice or "Could not update remembered folders.")
            return
        self._set_status(
            "Cleared all remembered folders."
            if result.changed
            else "No remembered folders to clear."
        )
        self._refresh_recent_paths()

    def _visible_type_keys(self) -> set[str]:
        options = self._filter_options
        return {item.key for item in options.types} if options else set()

    def _visible_entry_names(self) -> set[str]:
        options = self._filter_options
        return {item.name for item in options.entries} if options else set()

    def _select_all_types(self) -> None:
        type_list = self.query_one("#type-filter", SelectionList)
        self._syncing_filters = True
        try:
            type_list.select_all()
        finally:
            self._syncing_filters = False
        self._excluded_types.clear()
        self._refresh_panels(rebuild_filters=False)

    def _clear_all_types(self) -> None:
        type_list = self.query_one("#type-filter", SelectionList)
        self._syncing_filters = True
        try:
            type_list.deselect_all()
        finally:
            self._syncing_filters = False
        self._excluded_types = self._visible_type_keys()
        self._refresh_panels(rebuild_filters=False)

    def _select_all_entries(self) -> None:
        entry_list = self.query_one("#entry-filter", SelectionList)
        self._syncing_filters = True
        try:
            entry_list.select_all()
        finally:
            self._syncing_filters = False
        self._excluded_entries -= self._visible_entry_names()
        self._refresh_panels(rebuild_filters=False)

    def _clear_all_entries(self) -> None:
        entry_list = self.query_one("#entry-filter", SelectionList)
        self._syncing_filters = True
        try:
            entry_list.deselect_all()
        finally:
            self._syncing_filters = False
        self._excluded_entries |= self._visible_entry_names()
        self._refresh_panels(rebuild_filters=False)

    def _clear_filters_all(self) -> None:
        self._syncing_filters = True
        try:
            self.query_one("#type-filter", SelectionList).select_all()
            self.query_one("#entry-filter", SelectionList).select_all()
        finally:
            self._syncing_filters = False
        self._excluded_types.clear()
        self._excluded_entries.clear()
        self._refresh_panels(rebuild_filters=False)

    def on_selection_list_selected_changed(
        self, event: SelectionList.SelectedChanged[str]
    ) -> None:
        if self._syncing_filters:
            return
        widget_id = event.selection_list.id
        if widget_id == "type-filter":
            next_excluded = self._visible_type_keys() - set(
                event.selection_list.selected
            )
            if next_excluded == self._excluded_types:
                return
            self._excluded_types = next_excluded
        elif widget_id == "entry-filter":
            visible = self._visible_entry_names()
            kept = self._excluded_entries - visible
            next_entries = kept | (visible - set(event.selection_list.selected))
            if next_entries == self._excluded_entries:
                return
            self._excluded_entries = next_entries
        else:
            return
        self._refresh_panels(rebuild_filters=False)

    def on_checkbox_changed(self, event: Checkbox.Changed) -> None:
        if event.checkbox.id == "include-hidden":
            self._refresh_panels(rebuild_filters=True)

    def on_radio_set_changed(self, event: RadioSet.Changed) -> None:
        if event.radio_set.id == "mode":
            self._refresh_panels(rebuild_filters=True)

    def on_input_changed(self, event: Input.Changed) -> None:
        if event.input.id not in ("path-input", "log-input"):
            return
        if self._sync_filter_scope():
            self._clear_filter_lists()
            self._update_filter_widgets()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id in ("path-input", "seed-input", "log-input"):
            self.do_pick()

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        self.query_one("#path-input", Input).value = str(event.path)
        self._set_status(f"Directory: {event.path}")
        self._refresh_panels()

    def on_tabbed_content_tab_activated(
        self, event: TabbedContent.TabActivated
    ) -> None:
        if event.pane.id in (
            "browse-tab",
            "remaining-tab",
            "history-tab",
            "options-tab",
        ):
            self._refresh_panels()

    def _archive_history(self) -> None:
        """Move the history log to a timestamped backup (no confirm needed)."""
        target = self._target
        if not target.is_dir():
            self._set_status("Invalid Path.")
            return
        log_path = self._current_log_path()
        try:
            backup = HistoryService(log_path).archive()
        except ServiceError as e:
            self._set_status(e.message)
            return
        if backup is None:
            self._set_status(f"No log at {log_path}.")
        else:
            self._set_status(f"Archived to {backup.name}.")
        self._refresh_panels()

    def _ask_clear(self) -> None:
        target = self._target
        if not target.is_dir():
            self._set_status("Invalid Path.")
            return
        log_path = self._current_log_path()
        self.push_screen(
            ConfirmScreen(f"Clear all history?\n{log_path}"),
            self._do_clear,
        )

    def _do_clear(self, confirmed: bool | None) -> None:
        if not confirmed:
            self._set_status("Clear cancelled.")
            return
        target = self._target
        if not target.is_dir():
            self._set_status("Invalid Path.")
            return
        log_path = self._current_log_path()
        try:
            removed = HistoryService(log_path).clear()
        except ServiceError as e:
            self._set_status(e.message)
            return
        if removed:
            self._set_status(f"Removed {log_path}.")
        else:
            self._set_status(f"No log at {log_path}.")
        self._refresh_panels()

    def _open_current(self) -> None:
        """Open the current choice with the OS default handler."""
        if self._current_choice is None:
            self._set_status("Pick something first.")
            return
        try:
            open_entry(self._current_choice)
        except ServiceError as e:
            if e.kind is FailureKind.NOT_FOUND:
                self._set_status(f"Gone: {self._current_choice.name}")
            else:
                self._set_status(e.message)
            return
        self._set_status(f"Opened {self._current_choice.name}.")

    def do_pick(self) -> None:
        """Pick one unselected entry, log it, and display the result."""
        self._sync_filter_scope()
        target = self._target
        if not target.is_dir():
            self._set_status("Invalid Path.")
            self._refresh_panels()
            return
        browser = self.query_one("#browser", DirectoryTree)
        if browser.path != target:
            browser.path = target
        try:
            seed = parse_seed(self.query_one("#seed-input", Input).value)
        except ValueError:
            self._set_status("Invalid seed (must be an integer).")
            return
        log_path = self._current_log_path()
        dry_run = self.query_one("#dry-run", Checkbox).value
        try:
            outcome = pick(
                target,
                log_path,
                seed=seed,
                dry_run=dry_run,
                selection=self._filter_selection(),
                **self._picker_flags(),
            )
        except ServiceError as e:
            self._set_status(e.message)
            return
        if outcome.status == "invalid_path":
            self._set_status("Invalid Path.")
            self._refresh_panels()
            return
        if outcome.item is None:
            if outcome.status == "filtered_empty":
                self._set_status(FILTERED_EMPTY_TEXT)
            elif outcome.status == "filtered_exhausted":
                self._set_status(FILTERED_EXHAUSTED_TEXT)
            elif outcome.status == "exhausted":
                self._set_status("All choices have been selected. Delete log to reset.")
            else:
                self._set_status("Path Empty.")
            self._refresh_panels()
            return
        if dry_run:
            self._finish_pick(target, outcome.item, "Dry run: selection not logged.")
            return
        self._finish_pick(target, outcome.item, f"Logged in {log_path}.")

    def _finish_pick(self, target: Path, item: str, message: str) -> None:
        """Display a successful pick, update preview, and refresh panels."""
        memory_notice = PathMemory().record(target).notice
        self._show_choice(item)
        self._current_choice = target / item
        self._update_preview()
        if memory_notice is None:
            self._set_status(message)
        else:
            self._set_status(f"{message} {memory_notice}")
        self._refresh_panels()
        self._refresh_recent_paths()


def run(initial_path: str = "", log_file: str | None = None) -> int:
    """Launch the TUI. Returns a process exit code."""
    ChooserApp(initial_path=initial_path, log_file=log_file).run()
    return 0
