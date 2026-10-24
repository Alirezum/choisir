"""FastAPI web UI for choosier (requires the `web` extra).

The JSON API is a thin layer over the same core functions the CLI and
TUI use. When the Vue frontend has been built (`frontend/` with Vite),
`create_app()` also serves the bundle from the colocated
`choosier/web_static/` directory. The server binds to localhost only.
"""

import random
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Literal

import uvicorn
from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field

from choosier.chooser import (
    get_unselected_item,
    list_candidates,
    resolve_log_path,
)
from choosier.launcher import launch_path
from choosier.preview import (
    PREVIEW_MAX_IMAGE_BYTES,
    PreviewVideo,
    image_media_type,
    preview_entry,
    sniff_image_media_type,
    video_matches_content,
    video_media_type,
)
from choosier.storage import (
    LogEntry,
    archive_log,
    log_selection,
    read_log_entries,
    remove_log_item,
    reset_log,
)

DEFAULT_PORT = 8765
PANEL_MAX_LINES = 200
THUMBNAIL_MAX_SIZE = (480, 480)
THUMBNAIL_QUALITY = 84
PREVIEW_MAX_SIZE = (1600, 1600)
PREVIEW_QUALITY = 90
STATIC_DIR = Path(__file__).resolve().parent / "web_static"


class PreviewImageModel(BaseModel):
    """One previewable image inside an archive or a standalone file."""

    index: int | None = None
    name: str
    media_type: str
    size: int


class PreviewVideoModel(BaseModel):
    """One standalone video available for preview."""

    name: str
    media_type: str
    size: int


class PreviewModel(BaseModel):
    """Structured preview of a picked entry."""

    kind: str
    text: str
    truncated: bool = False
    entry_count: int | None = None
    size: int | None = None
    images: list[PreviewImageModel] = Field(default_factory=list)
    image_total: int = 0
    video: PreviewVideoModel | None = None


class DefaultsResponse(BaseModel):
    path: str
    log_file: str


class BrowserEntry(BaseModel):
    name: str
    is_dir: bool


class BrowseResponse(BaseModel):
    path: str
    parent: str | None
    entries: list[BrowserEntry]


class HistoryEntryModel(BaseModel):
    """One history log line with its parsed item for per-item actions."""

    timestamp: str | None
    item: str
    display: str


class StateResponse(BaseModel):
    valid_path: bool
    path: str
    log_file: str
    remaining: list[str]
    remaining_total: int
    history: list[HistoryEntryModel]
    history_total: int


class PickRequest(BaseModel):
    path: str
    log_file: str | None = None
    seed: int | None = None
    dry_run: bool = False
    include_hidden: bool = False
    files_only: bool = False
    dirs_only: bool = False


class PickResponse(BaseModel):
    status: Literal["picked", "empty", "exhausted", "invalid_path"]
    log_file: str
    item: str | None = None
    logged: bool = False
    preview: PreviewModel | None = None


class OpenRequest(BaseModel):
    path: str


class OpenResponse(BaseModel):
    opened: str


class ArchiveResponse(BaseModel):
    log_file: str
    backup: str | None


class ClearResponse(BaseModel):
    log_file: str
    removed: bool


class RemoveHistoryItemResponse(BaseModel):
    log_file: str
    item: str
    removed: int


def _log_path(path: str, log_file: str | None) -> Path:
    return resolve_log_path(Path(path).expanduser(), log_file or "")


def _preview_model(entry: Path) -> PreviewModel:
    preview = preview_entry(entry)
    video: PreviewVideoModel | None = None
    if preview.video is not None:
        video = _video_model(preview.video)
    return PreviewModel(
        kind=preview.kind,
        text=preview.text,
        truncated=preview.truncated,
        entry_count=preview.entry_count,
        size=preview.size,
        images=[
            PreviewImageModel(
                index=image.index,
                name=image.name,
                media_type=image.media_type,
                size=image.size,
            )
            for image in preview.images
        ],
        image_total=preview.image_total,
        video=video,
    )


def _video_model(video: PreviewVideo) -> PreviewVideoModel:
    return PreviewVideoModel(
        name=video.name,
        media_type=video.media_type,
        size=video.size,
    )


def _read_standalone_image(path: Path) -> tuple[bytes, str]:
    """Read a supported image file, bounded by the preview size limit."""
    if image_media_type(path.name) is None:
        raise HTTPException(status_code=415, detail="Not a supported image")
    try:
        size = path.stat().st_size
    except OSError as e:
        raise HTTPException(status_code=404, detail=f"Image is gone: {e}")
    if size > PREVIEW_MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image is too large to preview")
    try:
        with open(path, "rb") as f:
            data = f.read(PREVIEW_MAX_IMAGE_BYTES + 1)
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Cannot read image: {e}")
    if len(data) > PREVIEW_MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image is too large to preview")
    media_type = sniff_image_media_type(data[:32])
    if media_type is None:
        raise HTTPException(status_code=415, detail="Not a supported image")
    return data, media_type


def _read_archived_image(path: Path, index: int) -> tuple[bytes, str]:
    """Read one image member by position, never by client-supplied name."""
    if not zipfile.is_zipfile(path):
        raise HTTPException(status_code=400, detail="Not a zip archive")
    data = b""
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if index < 0 or index >= len(infos):
                raise HTTPException(
                    status_code=404, detail="Image not found in archive"
                )
            info = infos[index]
            if info.is_dir() or image_media_type(info.filename) is None:
                raise HTTPException(status_code=415, detail="Not a supported image")
            if info.flag_bits & 0x1:
                raise HTTPException(
                    status_code=400,
                    detail="Encrypted archive members are not supported",
                )
            if info.file_size > PREVIEW_MAX_IMAGE_BYTES:
                raise HTTPException(
                    status_code=413, detail="Image is too large to preview"
                )
            with archive.open(info) as member:
                data = member.read(PREVIEW_MAX_IMAGE_BYTES + 1)
    except zipfile.BadZipFile as e:
        raise HTTPException(status_code=400, detail=f"Not a valid archive: {e}")
    except (RuntimeError, NotImplementedError) as e:
        raise HTTPException(status_code=400, detail=f"Cannot read archive member: {e}")
    except OSError as e:
        raise HTTPException(status_code=500, detail=f"Cannot read archive: {e}")
    if len(data) > PREVIEW_MAX_IMAGE_BYTES:
        raise HTTPException(status_code=413, detail="Image is too large to preview")
    media_type = sniff_image_media_type(data[:32])
    if media_type is None:
        raise HTTPException(status_code=415, detail="Not a supported image")
    return data, media_type


def _make_thumbnail(
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
        raise HTTPException(status_code=415, detail=f"Cannot decode image: {e}")


def create_app(initial_path: str = "", log_file: str | None = None) -> FastAPI:
    """Build the web app; initial values seed the defaults endpoint."""
    app = FastAPI(title="choosier")

    @app.get("/api/defaults")
    def defaults() -> DefaultsResponse:
        return DefaultsResponse(path=initial_path, log_file=log_file or "")

    @app.get("/api/browse")
    def browse(path: str) -> BrowseResponse:
        """List one directory for the folder browser (dirs first)."""
        directory = Path(path).expanduser()
        if not directory.is_dir():
            raise HTTPException(status_code=404, detail="Not a directory")
        try:
            children = sorted(
                directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except OSError as e:
            raise HTTPException(status_code=403, detail=f"Cannot list: {e}")
        parent = directory.parent if directory.parent != directory else None
        return BrowseResponse(
            path=str(directory),
            parent=str(parent) if parent is not None else None,
            entries=[
                BrowserEntry(name=child.name, is_dir=child.is_dir())
                for child in children
            ],
        )

    @app.get("/api/state")
    def state(
        path: str,
        log_file: str | None = None,
        include_hidden: bool = False,
        files_only: bool = False,
        dirs_only: bool = False,
    ) -> StateResponse:
        """Remaining picks and history for the current target and filters."""
        target = Path(path).expanduser()
        log_path = _log_path(path, log_file)
        if not target.is_dir():
            return StateResponse(
                valid_path=False,
                path=str(target),
                log_file=str(log_path),
                remaining=[],
                remaining_total=0,
                history=[],
                history_total=0,
            )
        if files_only and dirs_only:
            raise HTTPException(
                status_code=400,
                detail="files_only and dirs_only are mutually exclusive",
            )
        try:
            candidates = list_candidates(
                target,
                log_path,
                include_hidden=include_hidden,
                files_only=files_only,
                dirs_only=dirs_only,
            )
        except FileNotFoundError:
            candidates = set()
        entries: list[LogEntry] = read_log_entries(log_path)
        logged = {entry.item for entry in entries}
        remaining = sorted(candidates - logged)
        return StateResponse(
            valid_path=True,
            path=str(target),
            log_file=str(log_path),
            remaining=remaining[:PANEL_MAX_LINES],
            remaining_total=len(remaining),
            history=[
                HistoryEntryModel(
                    timestamp=entry.timestamp,
                    item=entry.item,
                    display=entry.display,
                )
                for entry in entries[-PANEL_MAX_LINES:]
            ],
            history_total=len(entries),
        )

    @app.post("/api/pick")
    def pick(request: PickRequest) -> PickResponse:
        """Pick one unselected entry, mirroring the CLI/TUI states."""
        target = Path(request.path).expanduser()
        log_path = _log_path(request.path, request.log_file)
        if not target.is_dir():
            return PickResponse(status="invalid_path", log_file=str(log_path))
        rng = random.Random(request.seed) if request.seed is not None else None
        try:
            item = get_unselected_item(
                target,
                log_path,
                include_hidden=request.include_hidden,
                files_only=request.files_only,
                dirs_only=request.dirs_only,
                rng=rng,
            )
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail="files_only and dirs_only are mutually exclusive",
            )
        if item is None:
            status: Literal["empty", "exhausted"] = (
                "exhausted" if any(target.iterdir()) else "empty"
            )
            return PickResponse(status=status, log_file=str(log_path))
        logged = False
        if not request.dry_run:
            try:
                log_selection(item, log_path)
            except OSError as e:
                raise HTTPException(status_code=500, detail=f"Error writing log: {e}")
            logged = True
        return PickResponse(
            status="picked",
            log_file=str(log_path),
            item=item,
            logged=logged,
            preview=_preview_model(target / item),
        )

    @app.get("/api/preview")
    def preview(path: str) -> PreviewModel:
        """Structured preview for an entry path."""
        return _preview_model(Path(path).expanduser())

    @app.get("/api/image")
    def image(
        path: str,
        index: int | None = None,
        variant: Literal["thumb", "preview"] | None = None,
    ) -> Response:
        """Serve a standalone image or one image member of a zip archive.

        `variant=thumb` downscales for the contact-sheet grid;
        `variant=preview` produces a larger, high-quality WebP for a
        single-image preview. Omit it for the original image bytes.
        """
        entry = Path(path).expanduser()
        if not entry.is_file():
            raise HTTPException(status_code=404, detail="Image is gone")
        if index is None:
            data, media_type = _read_standalone_image(entry)
        else:
            data, media_type = _read_archived_image(entry, index)
        if variant == "thumb":
            data = _make_thumbnail(data)
            media_type = "image/webp"
        elif variant == "preview":
            data = _make_thumbnail(
                data,
                max_size=PREVIEW_MAX_SIZE,
                quality=PREVIEW_QUALITY,
            )
            media_type = "image/webp"
        return Response(
            content=data,
            media_type=media_type,
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
        )

    @app.get("/api/video")
    def video(path: str) -> FileResponse:
        """Stream a standalone video with byte-range support."""
        entry = Path(path).expanduser()
        if not entry.is_file():
            raise HTTPException(status_code=404, detail="Video is gone")
        media_type = video_media_type(entry.name)
        if media_type is None:
            raise HTTPException(status_code=415, detail="Not a supported video")
        try:
            with open(entry, "rb") as handle:
                head = handle.read(32)
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Cannot read video: {e}")
        if not video_matches_content(entry.name, head):
            raise HTTPException(status_code=415, detail="Not a supported video")
        return FileResponse(
            path=entry,
            media_type=media_type,
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
            content_disposition_type="inline",
        )

    @app.post("/api/open")
    def open_entry(request: OpenRequest) -> OpenResponse:
        """Open an entry with the OS default program."""
        entry = Path(request.path).expanduser()
        if not entry.exists():
            raise HTTPException(status_code=404, detail="Entry is gone")
        try:
            launch_path(entry)
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Cannot open: {e}")
        return OpenResponse(opened=entry.name)

    @app.post("/api/history/archive")
    def archive(path: str, log_file: str | None = None) -> ArchiveResponse:
        log_path = _log_path(path, log_file)
        try:
            backup = archive_log(log_path)
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Error archiving log: {e}")
        return ArchiveResponse(
            log_file=str(log_path),
            backup=backup.name if backup is not None else None,
        )

    @app.delete("/api/history")
    def clear(path: str, log_file: str | None = None) -> ClearResponse:
        log_path = _log_path(path, log_file)
        try:
            removed = reset_log(log_path)
        except OSError as e:
            raise HTTPException(status_code=500, detail=f"Error resetting log: {e}")
        return ClearResponse(log_file=str(log_path), removed=removed)

    @app.delete("/api/history/item")
    def remove_history_item(
        path: str, item: str, log_file: str | None = None
    ) -> RemoveHistoryItemResponse:
        """Delete every log entry for `item`, leaving other entries alone."""
        log_path = _log_path(path, log_file)
        try:
            removed = remove_log_item(item, log_path)
        except OSError as e:
            raise HTTPException(
                status_code=500, detail=f"Error removing history item: {e}"
            )
        return RemoveHistoryItemResponse(
            log_file=str(log_path), item=item, removed=removed
        )

    if STATIC_DIR.is_dir():
        app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="spa")

    return app


def run(
    initial_path: str = "",
    log_file: str | None = None,
    port: int = DEFAULT_PORT,
) -> int:
    """Serve the web UI on localhost. Returns a process exit code."""
    app = create_app(initial_path=initial_path, log_file=log_file)
    print(f"choosier web UI on http://127.0.0.1:{port} (ctrl+c to stop)")
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="warning")
    return 0
