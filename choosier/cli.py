"""Command-line interface.

Exit codes: 0 on success, 1 on runtime errors (invalid path, unwritable
log), 3 when the directory is empty, 4 when every choice was already
selected. Code 2 is reserved for argparse usage errors.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path

from choosier.chooser import resolve_log_path
from choosier.services import HistoryService, ServiceError, build_state, pick

EMPTY_EXIT = 3
EXHAUSTED_EXIT = 4


def build_parser() -> argparse.ArgumentParser:
    """Create the argument parser for the chooser CLI."""
    parser = argparse.ArgumentParser(
        prog="choosier",
        description=(
            "Pick a random unselected file or directory. "
            "Selections persist in a JSONL history log."
        ),
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Directory to choose from (prompts when omitted).",
    )
    parser.add_argument(
        "--log-file",
        default=None,
        help="History log path (default: <path>/.choosier.jsonl).",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Delete the history log and exit without picking.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Pick without recording the selection.",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Seed for deterministic picks.",
    )
    parser.add_argument(
        "--include-hidden",
        action="store_true",
        help="Consider dotfiles as choices.",
    )
    parser.add_argument(
        "--files-only",
        action="store_true",
        help="Only pick files.",
    )
    parser.add_argument(
        "--dirs-only",
        action="store_true",
        help="Only pick directories.",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List remaining picks instead of choosing.",
    )
    ui_group = parser.add_mutually_exclusive_group()
    ui_group.add_argument(
        "--ui",
        action="store_true",
        help="Launch the interactive terminal UI.",
    )
    ui_group.add_argument(
        "--web",
        action="store_true",
        help="Launch the local web UI.",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Port for --web (default: 8765).",
    )
    return parser


def _exhausted_exit(target: Path) -> int:
    if not any(target.iterdir()):
        print("Path Empty.")
        return EMPTY_EXIT
    print("All choices have been selected. Delete log to reset.")
    return EXHAUSTED_EXIT


def main(argv: Sequence[str] | None = None) -> int:
    """Run the chooser. Returns a process exit code."""
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.ui:
        try:
            from choosier.tui import run
        except ImportError:
            print(
                "The UI needs the 'ui' extra: pip install 'choosier[ui]'.",
                file=sys.stderr,
            )
            return 1
        return run(
            initial_path=args.path or "",
            log_file=args.log_file,
        )
    if args.web:
        try:
            from choosier.web import DEFAULT_PORT
            from choosier.web import run as run_web
        except ImportError:
            print(
                "The web UI needs the 'web' extra: pip install 'choosier[web]'.",
                file=sys.stderr,
            )
            return 1
        return run_web(
            initial_path=args.path if args.path is not None else str(Path.cwd()),
            log_file=args.log_file,
            port=DEFAULT_PORT if args.port is None else args.port,
        )
    if args.files_only and args.dirs_only:
        parser.error("--files-only and --dirs-only are mutually exclusive")

    raw_path = args.path if args.path is not None else input("Enter Path: ")
    target = Path(raw_path).expanduser()
    if not target.is_dir():
        print("Invalid Path.", file=sys.stderr)
        return 1
    log_path = resolve_log_path(target, args.log_file or "")
    history = HistoryService(log_path)

    if args.reset:
        try:
            removed = history.clear()
        except ServiceError as e:
            print(e.message, file=sys.stderr)
            return 1
        if removed:
            print(f"Removed {log_path}.")
        else:
            print(f"No log at {log_path}.")
        return 0

    picker_args = {
        "include_hidden": args.include_hidden,
        "files_only": args.files_only,
        "dirs_only": args.dirs_only,
    }

    if args.list:
        remaining = build_state(
            target, log_path, max_lines=None, **picker_args
        ).remaining
        for name in remaining:
            print(name)
        if remaining:
            return 0
        return _exhausted_exit(target)

    outcome = pick(
        target,
        log_path,
        seed=args.seed,
        dry_run=args.dry_run,
        commit=False,
        **picker_args,
    )
    if outcome.item is None:
        return _exhausted_exit(target)
    print(f"The choice: {outcome.item}")
    if args.dry_run:
        print("Dry run: selection not logged.")
        return 0
    try:
        history.append(outcome.item)
    except ServiceError as e:
        print(e.message, file=sys.stderr)
        return 1
    print(f"Added in {log_path} with timestamp.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
