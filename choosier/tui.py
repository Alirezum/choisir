"""Terminal UI for choosier (requires the `ui` extra)."""

import json
import random
from pathlib import Path

from rich.markup import escape
from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.screen import ModalScreen
from textual.widgets import (
    Button,
    Checkbox,
    DirectoryTree,
    Footer,
    Header,
    Input,
    RadioButton,
    RadioSet,
    Static,
    TabbedContent,
    TabPane,
)

from choosier.chooser import (
    get_unselected_item,
    list_available_items,
    resolve_default_log,
)
from choosier.storage import log_selection, reset_log

NO_CHOICE_TEXT = "No choice yet — enter a directory and press Pick."
MODE_LABELS = ("all", "files", "dirs")
PREVIEW_MAX_LINES = 10
PREVIEW_MAX_BYTES = 8_192


def parse_seed(text: str) -> int | None:
    """Parse a seed input; blank means random. Raises ValueError if invalid."""
    stripped = text.strip()
    if not stripped:
        return None
    return int(stripped)


def resolve_log_path(target: Path, override: str) -> Path:
    """Effective history log: explicit override or colocated default."""
    if override.strip():
        return Path(override).expanduser()
    return resolve_default_log(target)


def read_history(log_path: Path) -> list[str]:
    """Display lines for the history view (oldest first)."""
    try:
        raw_lines = log_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    lines: list[str] = []
    for raw in raw_lines:
        line = raw.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
        except json.JSONDecodeError:
            lines.append(line)
            continue
        if isinstance(obj, dict) and isinstance(obj.get("item"), str):
            lines.append(f"{obj.get('ts', '?')}  {obj['item']}")
    return lines


def render_panel(lines: list[str], empty_text: str) -> str:
    """Render view lines, markup-escaped so filenames display literally."""
    if not lines:
        return empty_text
    return "\n".join(escape(line) for line in lines)


def preview_entry(
    entry: Path,
    max_lines: int = PREVIEW_MAX_LINES,
    max_bytes: int = PREVIEW_MAX_BYTES,
) -> str:
    """Short display text for a picked entry (never reads much)."""
    try:
        if not entry.exists():
            return "(gone)"
        if entry.is_dir():
            try:
                count = sum(1 for _ in entry.iterdir())
            except OSError:
                return "<directory>"
            noun = "entry" if count == 1 else "entries"
            return f"<directory with {count} {noun}>"
        try:
            with open(entry, "rb") as f:
                chunk = f.read(max_bytes + 1)
        except OSError as e:
            return f"(unreadable: {e})"
        truncated = len(chunk) > max_bytes
        head = chunk[:max_bytes]
        if b"\x00" in head:
            size = f"{max_bytes}+" if truncated else str(len(head))
            return f"<binary file, {size} bytes>"
        lines = head.decode("utf-8", errors="replace").splitlines()
        if not lines:
            return "(empty file)"
        shown = lines[:max_lines]
        out = "\n".join(shown)
        if len(lines) > max_lines or truncated:
            out += "\n… (truncated)"
        return out
    except OSError as e:
        return f"(unreadable: {e})"


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
            yield Static(self._message)
            with Horizontal():
                yield Button("Yes, delete", id="yes", variant="error")
                yield Button("Cancel", id="no", variant="primary")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "yes")


class ChooserApp(App[None]):
    """Interactive directory picker with persistent history."""

    CSS = """
    #choice {
        height: 5;
        content-align: center middle;
        text-style: bold;
        border: solid green;
    }
    #status {
        height: 3;
    }
    #preview-wrap {
        height: 10;
        overflow-y: auto;
    }
    #browser {
        height: 10;
    }
    #options {
        height: auto;
    }
    #checks {
        height: 3;
    }
    #tabs {
        height: 10;
    }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, initial_path: str = "", log_file: str | None = None) -> None:
        super().__init__()
        self._initial_path = initial_path
        self._initial_log = log_file or ""
        self._current_choice: Path | None = None

    def compose(self) -> ComposeResult:
        yield Header()
        yield Input(
            value=self._initial_path,
            placeholder="Directory path",
            id="path-input",
        )
        with Horizontal():
            with Vertical():
                yield Static(NO_CHOICE_TEXT, id="choice")
                with Vertical(id="preview-wrap"):
                    yield Static("(preview appears here)", id="preview")
                yield Button("Pick", id="pick", variant="primary")
                yield Static("", id="status")
            yield DirectoryTree(Path.home(), id="browser")
        with Vertical(id="options"):
            yield Input(
                value=self._initial_log,
                placeholder="Log file (empty = <directory>/.choosier.jsonl)",
                id="log-input",
            )
            yield Input(placeholder="Seed (empty = random)", id="seed-input")
            with Horizontal(id="checks"):
                yield Checkbox("Dry run (don't log)", id="dry-run")
                yield Checkbox("Include hidden", id="include-hidden")
            yield RadioSet(
                RadioButton("Files and dirs", value=True),
                RadioButton("Files only"),
                RadioButton("Dirs only"),
                id="mode",
            )
        with TabbedContent(id="tabs"):
            with TabPane("Remaining", id="remaining-tab"):
                yield Static("(none)", id="remaining")
            with TabPane("History", id="history-tab"):
                yield Static("(no history yet)", id="history")
                yield Button("Reset history", id="reset", variant="error")
        yield Footer()

    def on_mount(self) -> None:
        self._refresh_panels()

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
        self.query_one("#status", Static).update(message)

    def _show_choice(self, message: str) -> None:
        self.query_one("#choice", Static).update(message)

    def _update_preview(self) -> None:
        if self._current_choice is None:
            text = "(preview appears here)"
        else:
            text = preview_entry(self._current_choice)
        self.query_one("#preview", Static).update(escape(text))

    def _refresh_panels(self) -> None:
        target = self._target
        if target.is_dir():
            log_path = self._current_log_path()
            remaining = list_available_items(target, log_path, **self._picker_flags())
            history = read_history(log_path)
        else:
            remaining = []
            history = []
        self.query_one("#remaining", Static).update(render_panel(remaining, "(none)"))
        self.query_one("#history", Static).update(
            render_panel(history, "(no history yet)")
        )

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "pick":
            self.do_pick()
        elif event.button.id == "reset":
            self._ask_reset()

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
        self._refresh_panels()

    def _ask_reset(self) -> None:
        target = self._target
        if not target.is_dir():
            self._set_status("Invalid Path.")
            return
        log_path = self._current_log_path()
        self.push_screen(
            ConfirmScreen(f"Delete history log?\n{log_path}"),
            self._do_reset,
        )

    def _do_reset(self, confirmed: bool | None) -> None:
        if not confirmed:
            self._set_status("Reset cancelled.")
            return
        target = self._target
        if not target.is_dir():
            self._set_status("Invalid Path.")
            return
        log_path = self._current_log_path()
        try:
            removed = reset_log(log_path)
        except OSError as e:
            self._set_status(f"Error resetting log: {e}")
            return
        if removed:
            self._set_status(f"Removed {log_path}.")
        else:
            self._set_status(f"No log at {log_path}.")
        self._refresh_panels()

    def do_pick(self) -> None:
        """Pick one unselected entry, log it, and display the result."""
        target = self._target
        if not target.is_dir():
            self._set_status("Invalid Path.")
            self._refresh_panels()
            return
        try:
            seed = parse_seed(self.query_one("#seed-input", Input).value)
        except ValueError:
            self._set_status("Invalid seed (must be an integer).")
            return
        log_path = self._current_log_path()
        dry_run = self.query_one("#dry-run", Checkbox).value
        rng = random.Random(seed) if seed is not None else None
        random_item = get_unselected_item(
            target, log_path, rng=rng, **self._picker_flags()
        )
        if random_item is None:
            if any(target.iterdir()):
                self._set_status("All choices have been selected. Delete log to reset.")
            else:
                self._set_status("Path Empty.")
            self._refresh_panels()
            return
        if dry_run:
            self._show_choice(random_item)
            self._current_choice = target / random_item
            self._update_preview()
            self._set_status("Dry run: selection not logged.")
            self._refresh_panels()
            return
        try:
            log_selection(random_item, log_path)
        except OSError as e:
            self._set_status(f"Error writing log: {e}")
            return
        self._show_choice(random_item)
        self._current_choice = target / random_item
        self._update_preview()
        self._set_status(f"Logged in {log_path}.")
        self._refresh_panels()


def run(initial_path: str = "", log_file: str | None = None) -> int:
    """Launch the TUI. Returns a process exit code."""
    ChooserApp(initial_path=initial_path, log_file=log_file).run()
    return 0
