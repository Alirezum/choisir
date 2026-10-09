"""Terminal UI for choosier (requires the `ui` extra)."""

from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import (
    Button,
    DirectoryTree,
    Footer,
    Header,
    Input,
    Static,
)

from choosier.chooser import get_unselected_item, resolve_default_log
from choosier.storage import log_selection

NO_CHOICE_TEXT = "No choice yet — enter a directory and press Pick."


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
    #browser {
        height: 1fr;
    }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, initial_path: str = "", log_file: str | None = None) -> None:
        super().__init__()
        self._initial_path = initial_path
        self._log_file_override = log_file

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
                yield Button("Pick", id="pick", variant="primary")
                yield Static("", id="status")
            yield DirectoryTree(Path.home(), id="browser")
        yield Footer()

    @property
    def _target(self) -> Path:
        return Path(self.query_one("#path-input", Input).value).expanduser()

    def _log_path(self, target: Path) -> Path:
        if self._log_file_override is not None:
            return Path(self._log_file_override).expanduser()
        return resolve_default_log(target)

    def _set_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def _show_choice(self, message: str) -> None:
        self.query_one("#choice", Static).update(message)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "pick":
            self.do_pick()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id == "path-input":
            self.do_pick()

    def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        self.query_one("#path-input", Input).value = str(event.path)
        self._set_status(f"Directory: {event.path}")

    def do_pick(self) -> None:
        """Pick one unselected entry, log it, and display the result."""
        target = self._target
        if not target.is_dir():
            self._set_status("Invalid Path.")
            return
        log_path = self._log_path(target)
        random_item = get_unselected_item(target, log_path)
        if random_item is None:
            if any(target.iterdir()):
                self._set_status("All choices have been selected. Delete log to reset.")
            else:
                self._set_status("Path Empty.")
            return
        try:
            log_selection(random_item, log_path)
        except OSError as e:
            self._set_status(f"Error writing log: {e}")
            return
        self._show_choice(random_item)
        self._set_status(f"Logged in {log_path}.")


def run(initial_path: str = "", log_file: str | None = None) -> int:
    """Launch the TUI. Returns a process exit code."""
    ChooserApp(initial_path=initial_path, log_file=log_file).run()
    return 0
