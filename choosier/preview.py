"""Structured previews for picked entries (no UI dependencies)."""

import zipfile
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

PREVIEW_MAX_LINES = 10
PREVIEW_MAX_BYTES = 8_192
PREVIEW_MAX_COUNT = 1_000
PREVIEW_MAX_IMAGES = 12
PREVIEW_MAX_IMAGE_BYTES = 20_000_000
PREVIEW_MAX_ARCHIVE_ENTRIES = 10_000

PreviewKind = Literal[
    "text",
    "directory",
    "binary",
    "empty",
    "gone",
    "unreadable",
    "archive",
    "image",
]

IMAGE_MEDIA_TYPES = {
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".gif": "image/gif",
    ".webp": "image/webp",
    ".bmp": "image/bmp",
}
ARCHIVE_SUFFIXES = frozenset({".zip", ".cbz"})


@dataclass(frozen=True)
class PreviewImage:
    """One image available for preview.

    `index` is the member position inside a zip archive; it is None for
    standalone image files. Serving code reads members by index, never by
    a client-supplied name, which avoids path traversal.
    """

    index: int | None
    name: str
    media_type: str
    size: int


@dataclass(frozen=True)
class Preview:
    """Short display data for a picked entry.

    `text` is the human-readable rendering; `entry_count` and `size`
    carry the structured values behind it. `truncated` marks previews
    that were capped by the line/byte/entry limits. `images` carries the
    bounded list of previewable images and `image_total` the full count.
    """

    kind: PreviewKind
    text: str
    truncated: bool = False
    entry_count: int | None = None
    size: int | None = None
    images: tuple[PreviewImage, ...] = ()
    image_total: int = 0


def image_media_type(name: str) -> str | None:
    """Map a filename to a supported image media type."""
    return IMAGE_MEDIA_TYPES.get(Path(name).suffix.lower())


def sniff_image_media_type(head: bytes) -> str | None:
    """Detect a supported image media type from its leading bytes."""
    if head.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    if head.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if head.startswith((b"GIF87a", b"GIF89a")):
        return "image/gif"
    if len(head) >= 12 and head[:4] == b"RIFF" and head[8:12] == b"WEBP":
        return "image/webp"
    if head.startswith(b"BM"):
        return "image/bmp"
    return None


def _format_size(size: int) -> str:
    if size < 1_000:
        return f"{size} B"
    if size < 1_000_000:
        return f"{size / 1_000:.1f} KB"
    return f"{size / 1_000_000:.1f} MB"


def _plural(count: int, singular: str, plural: str | None = None) -> str:
    word = singular if count == 1 else (plural or f"{singular}s")
    return f"{count} {word}"


def _preview_archive(entry: Path, max_images: int) -> Preview:
    """Preview a zip/cbz archive without extracting anything to disk."""
    try:
        with zipfile.ZipFile(entry) as archive:
            infos = archive.infolist()
    except (OSError, zipfile.BadZipFile) as e:
        return Preview(kind="unreadable", text=f"(unreadable: {e})")

    scanned = infos[:PREVIEW_MAX_ARCHIVE_ENTRIES]
    images: list[PreviewImage] = []
    image_total = 0
    other_entries = 0
    skipped = 0
    for index, info in enumerate(scanned):
        if info.is_dir():
            continue
        name = info.filename
        if name.startswith("__MACOSX/") or Path(name).name.startswith("."):
            continue
        media_type = image_media_type(name)
        if media_type is None:
            other_entries += 1
            continue
        image_total += 1
        if info.flag_bits & 0x1 or info.file_size > PREVIEW_MAX_IMAGE_BYTES:
            skipped += 1
            continue
        if len(images) < max_images:
            images.append(
                PreviewImage(
                    index=index,
                    name=name,
                    media_type=media_type,
                    size=info.file_size,
                )
            )

    if image_total == 0:
        summary = _plural(len(infos), "entry", "entries")
    else:
        summary = _plural(image_total, "image")
        if other_entries:
            summary += f", {_plural(other_entries, 'other entry', 'other entries')}"
    if skipped:
        summary += f" ({skipped} skipped: too large or encrypted)"
    text = f"<zip archive: {summary}>"
    if images and len(images) < image_total:
        text += f"\n(showing first {len(images)} of {image_total} images)"

    try:
        size = entry.stat().st_size
    except OSError:
        size = None
    return Preview(
        kind="archive",
        text=text,
        truncated=len(images) < image_total or len(infos) > len(scanned),
        entry_count=len(infos),
        size=size,
        images=tuple(images),
        image_total=image_total,
    )


def _preview_image(entry: Path, head: bytes) -> Preview | None:
    """Preview a standalone image file, or None when the bytes do not match."""
    media_type = sniff_image_media_type(head)
    expected = image_media_type(entry.name)
    if media_type is None or media_type != expected:
        return None
    try:
        size = entry.stat().st_size
    except OSError:
        size = len(head)
    if size > PREVIEW_MAX_IMAGE_BYTES:
        return Preview(
            kind="image",
            text=(
                f"<image: {media_type}, {_format_size(size)} (too large to preview)>"
            ),
            size=size,
            image_total=1,
        )
    image = PreviewImage(
        index=None,
        name=entry.name,
        media_type=media_type,
        size=size,
    )
    return Preview(
        kind="image",
        text=f"<image: {media_type}, {_format_size(size)}>",
        size=size,
        images=(image,),
        image_total=1,
    )


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
        suffix = entry.suffix.lower()
        if suffix in ARCHIVE_SUFFIXES and zipfile.is_zipfile(entry):
            return _preview_archive(entry, max_images=PREVIEW_MAX_IMAGES)
        try:
            with open(entry, "rb") as f:
                chunk = f.read(max_bytes + 1)
        except OSError as e:
            return Preview(kind="unreadable", text=f"(unreadable: {e})")
        truncated = len(chunk) > max_bytes
        head = chunk[:max_bytes]
        if suffix in IMAGE_MEDIA_TYPES:
            image_preview = _preview_image(entry, head[:32])
            if image_preview is not None:
                return image_preview
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
