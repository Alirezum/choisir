"""Command-line entrypoint."""

import sys
from pathlib import Path

from choosier.chooser import get_unselected_item, resolve_default_log
from choosier.storage import log_selection


def main(argv: list[str] | None = None) -> int:
    """Run the chooser. Returns a process exit code."""
    args = list(sys.argv[1:] if argv is None else argv)
    if args:
        dir_path = args[0]
    else:
        dir_path = input("Enter Path: ")

    target = Path(dir_path).expanduser()
    if not target.is_dir():
        print("Invalid Path.", file=sys.stderr)
        return 1
    log_path = resolve_default_log(target)
    random_item = get_unselected_item(target, log_path)
    if random_item is None:
        if any(target.iterdir()):
            print("All choices have been selected. Delete log to reset.")
        else:
            print("Path Empty.")
    else:
        print(f"The choice: {random_item}")
        try:
            log_selection(random_item, log_path)
        except OSError as e:
            print(f"Error writing log: {e}", file=sys.stderr)
            return 1
        print(f"Added in {log_path} with timestamp.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
