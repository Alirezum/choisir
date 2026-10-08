#!/usr/bin/env python3
import fnmatch
import json
import random
import sys
from datetime import UTC, datetime
from pathlib import Path

DEFAULT_LOG_FILENAME = ".choosier.jsonl"
LOG_ROTATE_BYTES = 1_000_000


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


def get_logged_items(log_file: str | Path = DEFAULT_LOG_FILENAME) -> set[str]:
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


def log_selection(item: str, log_file: str | Path = DEFAULT_LOG_FILENAME) -> None:
    log_path = Path(log_file).expanduser()
    try:
        with open(log_path, "a", encoding="utf-8") as f:
            ts = datetime.now(UTC).isoformat()
            f.write(json.dumps({"ts": ts, "item": item}, ensure_ascii=False) + "\n")
    except OSError as e:
        print(f"Error writing log: {e}", file=sys.stderr)
        sys.exit(1)
    _maybe_rotate_log(log_path)


def _maybe_rotate_log(log_file: str | Path = DEFAULT_LOG_FILENAME) -> None:
    log_path = Path(log_file).expanduser()
    try:
        if log_path.stat().st_size <= LOG_ROTATE_BYTES:
            return
    except OSError:
        return
    stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    backup = log_path.with_name(f"{log_path.stem}-{stamp}{log_path.suffix}.old")
    counter = 1
    while backup.exists():
        counter += 1
        backup = log_path.with_name(
            f"{log_path.stem}-{stamp}_{counter}{log_path.suffix}.old"
        )
    try:
        log_path.rename(backup)
    except OSError:
        pass


def resolve_default_log(directory: str | Path) -> Path:
    """Default history file colocated with the target directory.

    Colocating (instead of CWD-relative) keeps history stable when the
    tool is run from different working directories. The dot-prefix keeps
    it out of default listings.
    """
    return Path(directory).expanduser() / DEFAULT_LOG_FILENAME


def _is_managed_file(name: str, log_path: Path) -> bool:
    if name == log_path.name:
        return True
    return fnmatch.fnmatch(name, f"{log_path.stem}-*{log_path.suffix}.old")


def get_unselected_item(
    directory: str | Path,
    log_file: str | Path | None = None,
    *,
    include_hidden: bool = False,
    files_only: bool = False,
    dirs_only: bool = False,
) -> str | None:
    if files_only and dirs_only:
        raise ValueError("files_only and dirs_only are mutually exclusive")
    dir_path = Path(directory).expanduser()
    log_path = (
        Path(log_file).expanduser()
        if log_file is not None
        else resolve_default_log(dir_path)
    )

    try:
        entries = list(dir_path.iterdir())
    except FileNotFoundError:
        return None
    if not entries:
        return None

    candidates: set[str] = set()
    for entry in entries:
        name = entry.name
        if not include_hidden and name.startswith("."):
            continue
        if _is_managed_file(name, log_path):
            continue
        if files_only and not entry.is_file():
            continue
        if dirs_only and not entry.is_dir():
            continue
        candidates.add(name)
    if not candidates:
        return None

    logged_items = get_logged_items(log_path)
    available_items = list(candidates - logged_items)

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
        log_path = resolve_default_log(target)
        random_item = get_unselected_item(target, log_path)
        if random_item is None:
            all_items = [p.name for p in target.iterdir()]
            if not all_items:
                print("Path Empty.")
            else:
                print("All choices have been selected. Delete log to reset.")
        else:
            print(f"The choice: {random_item}")
            log_selection(random_item, log_path)
            print(f"Added in {log_path} with timestamp.\n")
