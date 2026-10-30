"""Image and video payload handling for the web adapter.

Pillow is imported only here, keeping the shared services stdlib-only.
"""

import os
import zipfile
from dataclasses import dataclass
from io import BytesIO
from pathlib import Path

from PIL import Image, ImageOps, UnidentifiedImageError

from choosier import preview
from choosier.services.errors import FailureKind, ServiceError

THUMBNAIL_MAX_SIZE = (480, 480)
THUMBNAIL_QUALITY = 84
PREVIEW_MAX_SIZE = (1600, 1600)
PREVIEW_QUALITY = 90


@dataclass(frozen=True)
class ImagePayload:
    """Validated image bytes and their sniffed media type."""

    data: bytes
    media_type: str


@dataclass(frozen=True)
class VideoFile:
    """A validated video file ready for streaming."""

    path: Path
    media_type: str
    stat_result: os.stat_result


def read_image(path: Path, index: int | None = None) -> ImagePayload:
    """Read a standalone image or one image member of a zip archive."""
    if not path.is_file():
        raise ServiceError(FailureKind.NOT_FOUND, "Image is gone")
    if index is None:
        data, media_type = _read_standalone_image(path)
    else:
        data, media_type = _read_archived_image(path, index)
    return ImagePayload(data=data, media_type=media_type)


def _read_standalone_image(path: Path) -> tuple[bytes, str]:
    """Read a supported image file, bounded by the preview size limit."""
    if preview.image_media_type(path.name) is None:
        raise ServiceError(FailureKind.UNSUPPORTED_MEDIA_TYPE, "Not a supported image")
    try:
        size = path.stat().st_size
    except OSError as e:
        raise ServiceError(FailureKind.NOT_FOUND, f"Image is gone: {e}") from e
    if size > preview.PREVIEW_MAX_IMAGE_BYTES:
        raise ServiceError(
            FailureKind.PAYLOAD_TOO_LARGE, "Image is too large to preview"
        )
    try:
        with open(path, "rb") as f:
            data = f.read(preview.PREVIEW_MAX_IMAGE_BYTES + 1)
    except OSError as e:
        raise ServiceError(FailureKind.IO_ERROR, f"Cannot read image: {e}") from e
    if len(data) > preview.PREVIEW_MAX_IMAGE_BYTES:
        raise ServiceError(
            FailureKind.PAYLOAD_TOO_LARGE, "Image is too large to preview"
        )
    media_type = preview.sniff_image_media_type(data[:32])
    if media_type is None:
        raise ServiceError(FailureKind.UNSUPPORTED_MEDIA_TYPE, "Not a supported image")
    return data, media_type


def _read_archived_image(path: Path, index: int) -> tuple[bytes, str]:
    """Read one image member by position, never by client-supplied name."""
    if not zipfile.is_zipfile(path):
        raise ServiceError(FailureKind.INVALID_INPUT, "Not a zip archive")
    data = b""
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if index < 0 or index >= len(infos):
                raise ServiceError(FailureKind.NOT_FOUND, "Image not found in archive")
            info = infos[index]
            if info.is_dir() or preview.image_media_type(info.filename) is None:
                raise ServiceError(
                    FailureKind.UNSUPPORTED_MEDIA_TYPE, "Not a supported image"
                )
            if info.flag_bits & 0x1:
                raise ServiceError(
                    FailureKind.INVALID_INPUT,
                    "Encrypted archive members are not supported",
                )
            if info.file_size > preview.PREVIEW_MAX_IMAGE_BYTES:
                raise ServiceError(
                    FailureKind.PAYLOAD_TOO_LARGE, "Image is too large to preview"
                )
            with archive.open(info) as member:
                data = member.read(preview.PREVIEW_MAX_IMAGE_BYTES + 1)
    except zipfile.BadZipFile as e:
        raise ServiceError(
            FailureKind.INVALID_INPUT, f"Not a valid archive: {e}"
        ) from e
    except (RuntimeError, NotImplementedError) as e:
        raise ServiceError(
            FailureKind.INVALID_INPUT, f"Cannot read archive member: {e}"
        ) from e
    except OSError as e:
        raise ServiceError(FailureKind.IO_ERROR, f"Cannot read archive: {e}") from e
    if len(data) > preview.PREVIEW_MAX_IMAGE_BYTES:
        raise ServiceError(
            FailureKind.PAYLOAD_TOO_LARGE, "Image is too large to preview"
        )
    media_type = preview.sniff_image_media_type(data[:32])
    if media_type is None:
        raise ServiceError(FailureKind.UNSUPPORTED_MEDIA_TYPE, "Not a supported image")
    return data, media_type


def make_thumbnail(
    data: bytes,
    max_size: tuple[int, int] = THUMBNAIL_MAX_SIZE,
    quality: int = THUMBNAIL_QUALITY,
) -> bytes:
    """Downscale image bytes to a WebP rendition for the web UI."""
    try:
        with Image.open(BytesIO(data)) as source:
            image = ImageOps.exif_transpose(source)
            image.thumbnail(max_size, Image.Resampling.LANCZOS)
            if image.mode not in ("RGB", "RGBA"):
                image = image.convert("RGBA")
            output = BytesIO()
            image.save(output, format="WEBP", quality=quality)
            return output.getvalue()
    except (UnidentifiedImageError, Image.DecompressionBombError, OSError) as e:
        raise ServiceError(
            FailureKind.UNSUPPORTED_MEDIA_TYPE, f"Cannot decode image: {e}"
        ) from e


def read_video(path: Path) -> VideoFile:
    """Validate a standalone video file for byte-range streaming."""
    if not path.is_file():
        raise ServiceError(FailureKind.NOT_FOUND, "Video is gone")
    media_type = preview.video_media_type(path.name)
    if media_type is None:
        raise ServiceError(FailureKind.UNSUPPORTED_MEDIA_TYPE, "Not a supported video")
    try:
        with open(path, "rb") as handle:
            head = handle.read(32)
        stat_result = path.stat()
    except OSError as e:
        raise ServiceError(FailureKind.IO_ERROR, f"Cannot read video: {e}") from e
    if not preview.video_matches_content(path.name, head):
        raise ServiceError(FailureKind.UNSUPPORTED_MEDIA_TYPE, "Not a supported video")
    return VideoFile(path=path, media_type=media_type, stat_result=stat_result)
