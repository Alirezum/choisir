"""Terminal UI for choosier (requires the `ui` extra)."""

import random
from pathlib import Path

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
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
)

from choosier.chooser import get_unselected_item, resolve_default_log
from choosier.storage import log_selection

NO_CHOICE_TEXT = "No choice yet — enter a directory and press Pick."
MODE_LABELS = ("all", "files", "dirs")


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
    #options {
        height: auto;
    }
    """

    BINDINGS = [("q", "quit", "Quit")]

    def __init__(self, initial_path: str = "", log_file: str | None = None) -> None:
        super().__init__()
        self._initial_path = initial_path
        self._initial_log = log_file or ""

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
        with Vertical(id="options"):
            yield Input(
                value=self._initial_log,
                placeholder="Log file (empty = <directory>/.choosier.jsonl)",
                id="log-input",
            )
            yield Input(placeholder="Seed (empty = random)", id="seed-input")
            with Horizontal():
                yield Checkbox("Dry run (don't log)", id="dry-run")
                yield Checkbox("Include hidden", id="include-hidden")
            yield RadioSet(
                RadioButton("Files and dirs", value=True),
                RadioButton("Files only"),
                RadioButton("Dirs only"),
                id="mode",
            )
        yield Footer()

    @property
    def _target(self) -> Path:
        return Path(self.query_one("#path-input", Input).value).expanduser()

    def _mode(self) -> str:
        return MODE_LABELS[self.query_one("#mode", RadioSet).pressed_index]

    def _set_status(self, message: str) -> None:
        self.query_one("#status", Static).update(message)

    def _show_choice(self, message: str) -> None:
        self.query_one("#choice", Static).update(message)

    def on_button_pressed(self, event: Button.Pressed) -> None:
        if event.button.id == "pick":
            self.do_pick()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id in ("path-input", "seed-input", "log-input"):
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
        try:
            seed = parse_seed(self.query_one("#seed-input", Input).value)
        except ValueError:
            self._set_status("Invalid seed (must be an integer).")
            return
        log_path = resolve_log_path(target, self.query_one("#log-input", Input).value)
        dry_run = self.query_one("#dry-run", Checkbox).value
        mode = self._mode()
        rng = random.Random(seed) if seed is not None else None
        random_item = get_unselected_item(
            target,
            log_path,
            include_hidden=self.query_one("#include-hidden", Checkbox).value,
            files_only=mode == "files",
            dirs_only=mode == "dirs",
            rng=rng,
        )
        if random_item is None:
            if any(target.iterdir()):
                self._set_status("All choices have been selected. Delete log to reset.")
            else:
                self._set_status("Path Empty.")
            return
        if dry_run:
            self._show_choice(random_item)
            self._set_status("Dry run: selection not logged.")
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
