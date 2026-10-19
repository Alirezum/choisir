"""Structured previews for picked entries (no UI dependencies)."""

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PREVIEW_MAX_LINES = 10
PREVIEW_MAX_BYTES = 8_192
PREVIEW_MAX_COUNT = 1_000

PreviewKind = Literal["text", "directory", "binary", "empty", "gone", "unreadable"]


@dataclass(frozen=True)
class Preview:
    """Short display data for a picked entry.

    `text` is the human-readable rendering; `entry_count` and `size`
    carry the structured values behind it. `truncated` marks previews
    that were capped by the line/byte/entry limits.
    """

    kind: PreviewKind
    text: str
    truncated: bool = False
    entry_count: int | None = None
    size: int | None = None


def preview_entry(
    entry: Path,
    max_lines: int = PREVIEW_MAX_LINES,
    max_bytes: int = PREVIEW_MAX_BYTES,
) -> Preview:
    """Short preview of a picked entry (never reads much)."""
    try:
        if not entry.exists():
            return Preview(kind="gone", text="(gone)")
        if entry.is_dir():
            try:
                count = 0
                for _ in entry.iterdir():
                    count += 1
                    if count > PREVIEW_MAX_COUNT:
                        return Preview(
                            kind="directory",
                            text=f"<directory with {PREVIEW_MAX_COUNT}+ entries>",
                            truncated=True,
                        )
            except OSError:
                return Preview(kind="directory", text="<directory>")
            noun = "entry" if count == 1 else "entries"
            return Preview(
                kind="directory",
                text=f"<directory with {count} {noun}>",
                entry_count=count,
            )
        try:
            with open(entry, "rb") as f:
                chunk = f.read(max_bytes + 1)
        except OSError as e:
            return Preview(kind="unreadable", text=f"(unreadable: {e})")
        truncated = len(chunk) > max_bytes
        head = chunk[:max_bytes]
        if b"\x00" in head:
            size = f"{max_bytes}+" if truncated else str(len(head))
            return Preview(
                kind="binary",
                text=f"<binary file, {size} bytes>",
                truncated=truncated,
                size=len(head),
            )
        lines = head.decode("utf-8", errors="replace").splitlines()
        if not lines:
            return Preview(kind="empty", text="(empty file)")
        shown = lines[:max_lines]
        out = "\n".join(shown)
        cut = len(lines) > max_lines or truncated
        if cut:
            out += "\n… (truncated)"
        return Preview(kind="text", text=out, truncated=cut)
    except OSError as e:
        return Preview(kind="unreadable", text=f"(unreadable: {e})")
