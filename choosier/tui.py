"""Terminal UI for choosier (requires the `ui` extra)."""

import os
import random
import subprocess
import sys
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
    list_candidates,
    resolve_default_log,
)
from choosier.storage import (
    archive_log,
    log_selection,
    parse_log_line,
    reset_log,
)

NO_CHOICE_TEXT = "No choice yet — enter a directory and press Pick."
MODE_LABELS = ("all", "files", "dirs")
PREVIEW_MAX_LINES = 10
PREVIEW_MAX_BYTES = 8_192
PREVIEW_MAX_COUNT = 1_000
PANEL_MAX_LINES = 200


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
    return load_log(log_path)[1]


def load_log(log_path: Path) -> tuple[set[str], list[str]]:
    """Read a history log once: (logged names, history display lines)."""
    try:
        raw_lines = log_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return set(), []
    names: set[str] = set()
    display: list[str] = []
    for raw in raw_lines:
        stripped = raw.strip()
        if not stripped:
            continue
        ts, item = parse_log_line(stripped)
        if item is None:
            continue
        names.add(item)
        display.append(f"{ts}  {item}" if ts is not None else stripped)
    return names, display


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


def launch_path(entry: Path) -> None:
    """Open an entry with the OS default handler (non-blocking).

    Raises:
        OSError: If no handler is available or launching fails.
    """
    if sys.platform == "win32":
        os.startfile(str(entry))
        return
    if sys.platform == "darwin":
        cmd = ["open", str(entry)]
    else:
        cmd = ["xdg-open", str(entry)]
    try:
        subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    except FileNotFoundError as e:
        raise OSError(f"No program available to open files ({cmd[0]})") from e


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
                count = 0
                for _ in entry.iterdir():
                    count += 1
                    if count > PREVIEW_MAX_COUNT:
                        return f"<directory with {PREVIEW_MAX_COUNT}+ entries>"
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
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#open", Button).disabled = True
        self.query_one("#pick", Button).focus()
        self._refresh_panels()

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
            text = preview_entry(self._current_choice)
        self.query_one("#preview", Static).update(escape(text))

    def _refresh_panels(self) -> None:
        target = self._target
        if target.is_dir():
            log_path = self._current_log_path()
            flags = self._picker_flags()
            try:
                candidates = list_candidates(target, log_path, **flags)
            except FileNotFoundError:
                candidates = set()
            logged, history = load_log(log_path)
            remaining = sorted(candidates - logged)
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
        elif event.button.id == "open":
            self._open_current()
        elif event.button.id == "archive":
            self._archive_history()
        elif event.button.id == "clear":
            self._ask_clear()

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
        if event.pane.id in ("browse-tab", "remaining-tab", "history-tab"):
            self._refresh_panels()

    def _archive_history(self) -> None:
        """Move the history log to a timestamped backup (no confirm needed)."""
        target = self._target
        if not target.is_dir():
            self._set_status("Invalid Path.")
            return
        log_path = self._current_log_path()
        try:
            backup = archive_log(log_path)
        except OSError as e:
            self._set_status(f"Error archiving log: {e}")
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
            removed = reset_log(log_path)
        except OSError as e:
            self._set_status(f"Error resetting log: {e}")
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
        if not self._current_choice.exists():
            self._set_status(f"Gone: {self._current_choice.name}")
            return
        try:
            launch_path(self._current_choice)
        except OSError as e:
            self._set_status(f"Cannot open: {e}")
            return
        self._set_status(f"Opened {self._current_choice.name}.")

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
