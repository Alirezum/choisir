#!/usr/bin/env python3
import json
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_LOG_NAME = "selected_items.jsonl"


def _parse_log_line(line: str) -> str | None:
    line = line.strip()
    if not line:
        return None
    try:
        obj = json.loads(line)
    except json.JSONDecodeError:
        pass
    else:
        if isinstance(obj, dict) and isinstance(obj.get("item"), str):
            return obj["item"]
        return None
    if " - " in line:
        return line.split(" - ", 1)[1]
    return line


def get_logged_items(log_file: str | Path = DEFAULT_LOG_NAME) -> set[str]:
    log_path = Path(log_file).expanduser()
    if not log_path.exists():
        return set()
    with open(log_path, encoding="utf-8") as f:
        items = set()
        for line in f:
            item = _parse_log_line(line)
            if item is None:
                continue
            items.add(item)
        return items


def log_selection(item: str, log_file: str | Path = DEFAULT_LOG_NAME) -> None:
    log_path = Path(log_file).expanduser()
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            ts = datetime.now(UTC).isoformat()
            f.write(json.dumps({"ts": ts, "item": item}, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"Error writing log: {e}", file=sys.stderr)
        sys.exit(1)
    _maybe_rotate_log(log_path)


def _maybe_rotate_log(log_file: str | Path = DEFAULT_LOG_NAME) -> None:
    log_path = Path(log_file).expanduser()
    try:
        if log_path.stat().st_size > 1_000_000:
            log_path.rename(str(log_path) + ".old")
    except OSError:
        pass


def get_unselected_item(
    directory: str | Path, log_file: str | Path = DEFAULT_LOG_NAME
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
            print(f"Added in {DEFAULT_LOG_NAME} with timestamp.\n")
