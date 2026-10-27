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
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from PIL import Image, ImageOps, UnidentifiedImageError
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import (
    MalformedRangeHeader,
    RangeNotSatisfiable,
)

from choosier.chooser import (
    get_unselected_item,
    list_candidates,
    resolve_log_path,
)
from choosier.launcher import launch_path
from choosier.preview import (
    PREVIEW_MAX_IMAGE_BYTES,
    PreviewKind,
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
    remove_log_items,
    reset_log,
)

DEFAULT_PORT = 8765
PANEL_MAX_LINES = 200
THUMBNAIL_MAX_SIZE = (480, 480)
THUMBNAIL_QUALITY = 84
PREVIEW_MAX_SIZE = (1600, 1600)
PREVIEW_QUALITY = 90
STATIC_DIR = Path(__file__).resolve().parent / "web_static"

ErrorCode = Literal[
    "invalid_request",
    "forbidden",
    "not_found",
    "method_not_allowed",
    "payload_too_large",
    "unsupported_media_type",
    "range_not_satisfiable",
    "validation_error",
    "internal_error",
]

ERROR_STATUS: dict[ErrorCode, int] = {
    "invalid_request": 400,
    "forbidden": 403,
    "not_found": 404,
    "method_not_allowed": 405,
    "payload_too_large": 413,
    "unsupported_media_type": 415,
    "range_not_satisfiable": 416,
    "validation_error": 422,
    "internal_error": 500,
}

_HTTP_ERROR_CODES: dict[int, ErrorCode] = {
    400: "invalid_request",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    413: "payload_too_large",
    415: "unsupported_media_type",
    416: "range_not_satisfiable",
    422: "validation_error",
    500: "internal_error",
}

ErrorDetails = dict[str, object]


class ApiError(Exception):
    """A route failure that serializes through the documented error envelope."""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        details: ErrorDetails | None = None,
        headers: dict[str, str] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details
        self.headers = headers


def _error_body(
    code: ErrorCode,
    message: str,
    details: ErrorDetails | None = None,
) -> dict[str, object]:
    """Build the one JSON error shape; `detail` stays a string for the frontend."""
    error: dict[str, object] = {
        "code": code,
        "message": message,
        "details": details,
    }
    return {"error": error, "detail": message}


def _error_response(
    code: ErrorCode,
    message: str,
    details: ErrorDetails | None = None,
    headers: dict[str, str] | None = None,
    status_code: int | None = None,
) -> JSONResponse:
    """Serialize an API error with the status aligned to its code."""
    return JSONResponse(
        status_code=ERROR_STATUS[code] if status_code is None else status_code,
        content=_error_body(code, message, details),
        headers=headers,
    )


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

    kind: PreviewKind
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


class RemoveHistoryItemsRequest(BaseModel):
    path: str
    log_file: str | None = None
    items: list[str] = Field(min_length=1)


class RemoveHistoryItemsResponse(BaseModel):
    log_file: str
    items: list[str]
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
        raise ApiError("unsupported_media_type", "Not a supported image")
    try:
        size = path.stat().st_size
    except OSError as e:
        raise ApiError("not_found", f"Image is gone: {e}")
    if size > PREVIEW_MAX_IMAGE_BYTES:
        raise ApiError("payload_too_large", "Image is too large to preview")
    try:
        with open(path, "rb") as f:
            data = f.read(PREVIEW_MAX_IMAGE_BYTES + 1)
    except OSError as e:
        raise ApiError("internal_error", f"Cannot read image: {e}")
    if len(data) > PREVIEW_MAX_IMAGE_BYTES:
        raise ApiError("payload_too_large", "Image is too large to preview")
    media_type = sniff_image_media_type(data[:32])
    if media_type is None:
        raise ApiError("unsupported_media_type", "Not a supported image")
    return data, media_type


def _read_archived_image(path: Path, index: int) -> tuple[bytes, str]:
    """Read one image member by position, never by client-supplied name."""
    if not zipfile.is_zipfile(path):
        raise ApiError("invalid_request", "Not a zip archive")
    data = b""
    try:
        with zipfile.ZipFile(path) as archive:
            infos = archive.infolist()
            if index < 0 or index >= len(infos):
                raise ApiError("not_found", "Image not found in archive")
            info = infos[index]
            if info.is_dir() or image_media_type(info.filename) is None:
                raise ApiError("unsupported_media_type", "Not a supported image")
            if info.flag_bits & 0x1:
                raise ApiError(
                    "invalid_request", "Encrypted archive members are not supported"
                )
            if info.file_size > PREVIEW_MAX_IMAGE_BYTES:
                raise ApiError("payload_too_large", "Image is too large to preview")
            with archive.open(info) as member:
                data = member.read(PREVIEW_MAX_IMAGE_BYTES + 1)
    except zipfile.BadZipFile as e:
        raise ApiError("invalid_request", f"Not a valid archive: {e}")
    except (RuntimeError, NotImplementedError) as e:
        raise ApiError("invalid_request", f"Cannot read archive member: {e}")
    except OSError as e:
        raise ApiError("internal_error", f"Cannot read archive: {e}")
    if len(data) > PREVIEW_MAX_IMAGE_BYTES:
        raise ApiError("payload_too_large", "Image is too large to preview")
    media_type = sniff_image_media_type(data[:32])
    if media_type is None:
        raise ApiError("unsupported_media_type", "Not a supported image")
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
        raise ApiError("unsupported_media_type", f"Cannot decode image: {e}")


def create_app(initial_path: str = "", log_file: str | None = None) -> FastAPI:
    """Build the web app; initial values seed the defaults endpoint."""
    app = FastAPI(title="choosier")

    @app.exception_handler(ApiError)
    async def api_error_handler(
        _request: Request,
        exc: ApiError,
    ) -> JSONResponse:
        return _error_response(
            exc.code,
            exc.message,
            details=exc.details,
            headers=exc.headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_exception_handler(
        _request: Request,
        exc: StarletteHTTPException,
    ) -> JSONResponse:
        code = _HTTP_ERROR_CODES.get(exc.status_code)
        if code is None:
            return _error_response("internal_error", "Internal server error")
        if isinstance(exc.detail, str):
            message = exc.detail
        elif code == "validation_error":
            message = "Request validation failed"
        else:
            message = "Request failed"
        headers = dict(exc.headers) if exc.headers is not None else None
        return _error_response(
            code,
            message,
            headers=headers,
            status_code=exc.status_code,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        _request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        issues: list[dict[str, object]] = []
        first_location = "request"
        first_message = "Invalid request"
        for index, error in enumerate(exc.errors()):
            location = [str(part) for part in error.get("loc", ())]
            message = str(error.get("msg", "Invalid value"))
            issue_type = str(error.get("type", "value_error"))
            issues.append(
                {
                    "location": location,
                    "message": message,
                    "type": issue_type,
                }
            )
            if index == 0:
                first_location = ".".join(location) or "request"
                first_message = message
        if not issues:
            issues.append(
                {
                    "location": ["request"],
                    "message": "Invalid request",
                    "type": "value_error",
                }
            )
        return _error_response(
            "validation_error",
            f"Request validation failed: {first_location}: {first_message}",
            details={"issues": issues},
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(
        _request: Request,
        _exc: Exception,
    ) -> JSONResponse:
        return _error_response("internal_error", "Internal server error")

    @app.get("/api/defaults")
    def defaults() -> DefaultsResponse:
        return DefaultsResponse(path=initial_path, log_file=log_file or "")

    @app.get("/api/browse")
    def browse(path: str) -> BrowseResponse:
        """List one directory for the folder browser (dirs first)."""
        directory = Path(path).expanduser()
        if not directory.is_dir():
            raise ApiError("not_found", "Not a directory")
        try:
            children = sorted(
                directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
            )
        except OSError as e:
            raise ApiError("forbidden", f"Cannot list: {e}")
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
            raise ApiError(
                "invalid_request", "files_only and dirs_only are mutually exclusive"
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
            raise ApiError(
                "invalid_request", "files_only and dirs_only are mutually exclusive"
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
                raise ApiError("internal_error", f"Error writing log: {e}")
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
            raise ApiError("not_found", "Image is gone")
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
    def video(path: str, request: Request) -> FileResponse:
        """Stream a standalone video with byte-range support."""
        entry = Path(path).expanduser()
        if not entry.is_file():
            raise ApiError("not_found", "Video is gone")
        media_type = video_media_type(entry.name)
        if media_type is None:
            raise ApiError("unsupported_media_type", "Not a supported video")
        try:
            with open(entry, "rb") as handle:
                head = handle.read(32)
            stat_result = entry.stat()
        except OSError as e:
            raise ApiError("internal_error", f"Cannot read video: {e}")
        if not video_matches_content(entry.name, head):
            raise ApiError("unsupported_media_type", "Not a supported video")
        response = FileResponse(
            path=entry,
            media_type=media_type,
            stat_result=stat_result,
            headers={
                "Cache-Control": "no-store",
                "X-Content-Type-Options": "nosniff",
            },
            content_disposition_type="inline",
        )
        range_header = request.headers.get("range")
        if range_header is not None:
            if_range = request.headers.get("if-range")
            if if_range is None or response._should_use_range(if_range):
                try:
                    FileResponse._parse_range_header(range_header, stat_result.st_size)
                except MalformedRangeHeader as exc:
                    raise ApiError("invalid_request", exc.content)
                except RangeNotSatisfiable as exc:
                    raise ApiError(
                        "range_not_satisfiable",
                        "Requested range not satisfiable",
                        headers={"Content-Range": f"bytes */{exc.max_size}"},
                    )
        return response

    @app.post("/api/open")
    def open_entry(request: OpenRequest) -> OpenResponse:
        """Open an entry with the OS default program."""
        entry = Path(request.path).expanduser()
        if not entry.exists():
            raise ApiError("not_found", "Entry is gone")
        try:
            launch_path(entry)
        except OSError as e:
            raise ApiError("internal_error", f"Cannot open: {e}")
        return OpenResponse(opened=entry.name)

    @app.post("/api/history/archive")
    def archive(path: str, log_file: str | None = None) -> ArchiveResponse:
        log_path = _log_path(path, log_file)
        try:
            backup = archive_log(log_path)
        except OSError as e:
            raise ApiError("internal_error", f"Error archiving log: {e}")
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
            raise ApiError("internal_error", f"Error resetting log: {e}")
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
            raise ApiError("internal_error", f"Error removing history item: {e}")
        return RemoveHistoryItemResponse(
            log_file=str(log_path), item=item, removed=removed
        )

    @app.post("/api/history/remove")
    def remove_history_items(
        request: RemoveHistoryItemsRequest,
    ) -> RemoveHistoryItemsResponse:
        """Delete every log entry for all selected items in one rewrite."""
        log_path = _log_path(request.path, request.log_file)
        try:
            removed = remove_log_items(request.items, log_path)
        except OSError as e:
            raise ApiError("internal_error", f"Error removing history items: {e}")
        return RemoveHistoryItemsResponse(
            log_file=str(log_path), items=request.items, removed=removed
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
