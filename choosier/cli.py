"""Command-line interface.

Exit codes: 0 on success, 1 on runtime errors (invalid path, unwritable
log), 3 when the directory is empty, 4 when every choice was already
selected. Code 2 is reserved for argparse usage errors.
"""

import argparse
import random
import sys
from collections.abc import Sequence
from pathlib import Path

from choosier.chooser import (
    get_unselected_item,
    list_available_items,
    resolve_default_log,
)
from choosier.storage import log_selection, reset_log

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
    if args.files_only and args.dirs_only:
        parser.error("--files-only and --dirs-only are mutually exclusive")

    raw_path = args.path if args.path is not None else input("Enter Path: ")
    target = Path(raw_path).expanduser()
    if not target.is_dir():
        print("Invalid Path.", file=sys.stderr)
        return 1
    log_path = (
        Path(args.log_file).expanduser()
        if args.log_file is not None
        else resolve_default_log(target)
    )

    if args.reset:
        try:
            removed = reset_log(log_path)
        except OSError as e:
            print(f"Error resetting log: {e}", file=sys.stderr)
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
    rng = random.Random(args.seed) if args.seed is not None else None

    if args.list:
        remaining = list_available_items(target, log_path, **picker_args)
        for name in remaining:
            print(name)
        if remaining:
            return 0
        return _exhausted_exit(target)

    random_item = get_unselected_item(target, log_path, rng=rng, **picker_args)
    if random_item is None:
        return _exhausted_exit(target)
    print(f"The choice: {random_item}")
    if args.dry_run:
        print("Dry run: selection not logged.")
        return 0
    try:
        log_selection(random_item, log_path)
    except OSError as e:
        print(f"Error writing log: {e}", file=sys.stderr)
        return 1
    print(f"Added in {log_path} with timestamp.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
