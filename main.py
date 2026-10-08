#!/usr/bin/env python3
import random
import sys
from datetime import UTC, datetime
from pathlib import Path


def get_logged_items(log_file: str | Path = "selected_items.txt") -> set[str]:
    log_path = Path(log_file).expanduser()
    if not log_path.exists():
        return set()
    with open(log_path, encoding="utf-8") as f:
        items = set()
        for line in f:
            line = line.strip()
            if not line:
                continue
            if " - " in line:
                item = line.split(" - ", 1)[1]
            else:
                item = line
            items.add(item)
        return items


def log_selection(item: str, log_file: str | Path = "selected_items.txt") -> None:
    log_path = Path(log_file).expanduser()
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            ts = datetime.now(UTC).isoformat()
            f.write(f"{ts} - {item}\n")
    except OSError as e:
        print(f"Error writing log: {e}", file=sys.stderr)
        sys.exit(1)
    _maybe_rotate_log(log_path)


def _maybe_rotate_log(log_file: str | Path = "selected_items.txt") -> None:
    log_path = Path(log_file).expanduser()
    try:
        if log_path.stat().st_size > 1_000_000:
            log_path.rename(str(log_path) + ".old")
    except OSError:
        pass


def get_unselected_item(
    directory: str | Path, log_file: str | Path = "selected_items.txt"
) -> str | None:
    dir_path = Path(directory).expanduser()
    all_items = {p.name for p in dir_path.iterdir()}
    if not all_items:
        return None

    logged_items = get_logged_items(log_file)
    available_items = list(all_items - logged_items)

    if not available_items:
        return None
    return random.choice(available_items)


if __name__ == "__main__":
    if len(sys.argv) > 1:
        dir_path = sys.argv[1]
    else:
        dir_path = input("Enter Path: ")

    target = Path(dir_path).expanduser()
    if not target.is_dir():
        print("Invalid Path.", file=sys.stderr)
        sys.exit(1)
    else:
        random_item = get_unselected_item(target)
        if random_item is None:
            all_items = [p.name for p in target.iterdir()]
            if not all_items:
                print("Path Empty.")
            else:
                print("All choices have been selected. Delete log to reset.")
        else:
            print(f"The choice: {random_item}")
            log_selection(random_item)
            print("Added in selected_items.txt with timestamp.\n")
