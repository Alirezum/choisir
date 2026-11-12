"""FastAPI web UI for choosier (requires the `web` extra).

The JSON API is a thin layer over the same core functions the CLI and
TUI use. When the Vue frontend has been built (`frontend/` with Vite),
`create_app()` also serves the bundle from the colocated
`choosier/web_static/` directory. The server binds to localhost only.
"""

from pathlib import Path
from typing import Literal

import uvicorn
from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, field_validator
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.responses import (
    MalformedRangeHeader,
    RangeNotSatisfiable,
)

from choosier import services, web_media
from choosier.chooser import resolve_log_path
from choosier.filters import (
    FilterOptions,
    FilterSelection,
    FilterValidationError,
    normalize_exclusions,
)
from choosier.path_memory import PathMemory
from choosier.preview import (
    Preview,
    PreviewKind,
    PreviewVideo,
    preview_entry,
)

DEFAULT_PORT = 8765
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

SERVICE_ERROR_CODES: dict[services.FailureKind, ErrorCode] = {
    services.FailureKind.INVALID_INPUT: "invalid_request",
    services.FailureKind.FORBIDDEN: "forbidden",
    services.FailureKind.NOT_FOUND: "not_found",
    services.FailureKind.PAYLOAD_TOO_LARGE: "payload_too_large",
    services.FailureKind.UNSUPPORTED_MEDIA_TYPE: "unsupported_media_type",
    services.FailureKind.RANGE_NOT_SATISFIABLE: "range_not_satisfiable",
    services.FailureKind.IO_ERROR: "internal_error",
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
    path_warning: str | None


class PathMemoryResponse(BaseModel):
    recent: list[str]
    warning: str | None


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


class FilterTypeOptionModel(BaseModel):
    """One selectable file type with its base-candidate count."""

    key: str
    label: str
    count: int


class FilterEntryOptionModel(BaseModel):
    """One selectable visible entry and its type key."""

    name: str
    type_key: str


class FilterOptionsModel(BaseModel):
    """The complete type list and bounded entry list for one folder."""

    types: list[FilterTypeOptionModel]
    entries: list[FilterEntryOptionModel]
    entries_total: int
    entries_truncated: bool


class FilterExclusionsRequest(BaseModel):
    """Optional type/entry exclusions shared by state and pick requests."""

    excluded_types: list[str] = Field(default_factory=list)
    excluded_entries: list[str] = Field(default_factory=list)

    @field_validator("excluded_types")
    @classmethod
    def _normalize_types(cls, value: list[str]) -> list[str]:
        try:
            selection = normalize_exclusions(value, [])
        except FilterValidationError as exc:
            raise ValueError(str(exc)) from exc
        return sorted(selection.excluded_types)

    @field_validator("excluded_entries")
    @classmethod
    def _normalize_entries(cls, value: list[str]) -> list[str]:
        try:
            selection = normalize_exclusions([], value)
        except FilterValidationError as exc:
            raise ValueError(str(exc)) from exc
        return sorted(selection.excluded_entries)

    @property
    def filter_selection(self) -> FilterSelection:
        """Already-validated values as the service-layer selection object."""
        return normalize_exclusions(self.excluded_types, self.excluded_entries)


class StateRequest(FilterExclusionsRequest):
    path: str
    log_file: str | None = None
    include_hidden: bool = False
    files_only: bool = False
    dirs_only: bool = False


class FilteredStateResponse(StateResponse):
    filter_options: FilterOptionsModel
    known_entry_exclusions: list[str]


class PickRequest(FilterExclusionsRequest):
    path: str
    log_file: str | None = None
    seed: int | None = None
    dry_run: bool = False
    include_hidden: bool = False
    files_only: bool = False
    dirs_only: bool = False


class PickResponse(BaseModel):
    status: Literal[
        "picked",
        "empty",
        "exhausted",
        "invalid_path",
        "filtered_empty",
        "filtered_exhausted",
    ]
    log_file: str
    item: str | None = None
    logged: bool = False
    preview: PreviewModel | None = None
    path_memory_notice: str | None


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


def _preview_model(preview: Preview) -> PreviewModel:
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


def _filter_options_model(options: FilterOptions) -> FilterOptionsModel:
    return FilterOptionsModel(
        types=[
            FilterTypeOptionModel(
                key=item.key,
                label=item.label,
                count=item.count,
            )
            for item in options.types
        ],
        entries=[
            FilterEntryOptionModel(name=item.name, type_key=item.type_key)
            for item in options.entries
        ],
        entries_total=options.entries_total,
        entries_truncated=options.entries_truncated,
    )


def _history_models(snapshot: services.StateSnapshot) -> list[HistoryEntryModel]:
    return [
        HistoryEntryModel(
            timestamp=entry.timestamp,
            item=entry.item,
            display=entry.display,
        )
        for entry in snapshot.history
    ]


def create_app(initial_path: str = "", log_file: str | None = None) -> FastAPI:
    """Build the web app; initial values seed the defaults endpoint."""
    app = FastAPI(title="choosier")
    memory = PathMemory()
    startup_path = initial_path
    path_warning: str | None = None
    if not initial_path:
        resolution = memory.startup(Path.cwd())
        startup_path = str(resolution.path)
        path_warning = resolution.warning

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

    @app.exception_handler(services.ServiceError)
    async def service_error_handler(
        _request: Request,
        exc: services.ServiceError,
    ) -> JSONResponse:
        return _error_response(
            SERVICE_ERROR_CODES[exc.kind],
            exc.message,
            details=exc.details,
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
        return DefaultsResponse(
            path=startup_path,
            log_file=log_file or "",
            path_warning=path_warning,
        )

    @app.get("/api/paths")
    def paths() -> PathMemoryResponse:
        snapshot = memory.snapshot()
        return PathMemoryResponse(
            recent=list(snapshot.recent),
            warning=snapshot.warning,
        )

    @app.get("/api/browse")
    def browse(path: str) -> BrowseResponse:
        """List one directory for the folder browser (dirs first)."""
        listing = services.browse_directory(path)
        return BrowseResponse(
            path=str(listing.path),
            parent=str(listing.parent) if listing.parent is not None else None,
            entries=[
                BrowserEntry(name=entry.name, is_dir=entry.is_dir)
                for entry in listing.entries
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
        snapshot = services.build_state(
            path,
            log_file,
            include_hidden=include_hidden,
            files_only=files_only,
            dirs_only=dirs_only,
        )
        return StateResponse(
            valid_path=snapshot.valid_path,
            path=str(snapshot.path),
            log_file=str(snapshot.log_file),
            remaining=list(snapshot.remaining),
            remaining_total=snapshot.remaining_total,
            history=_history_models(snapshot),
            history_total=snapshot.history_total,
        )

    @app.post("/api/state")
    def state_filtered(request: StateRequest) -> FilteredStateResponse:
        """Remaining picks, history, and filter options for this selection."""
        snapshot = services.build_state(
            request.path,
            request.log_file,
            include_hidden=request.include_hidden,
            files_only=request.files_only,
            dirs_only=request.dirs_only,
            selection=request.filter_selection,
        )
        return FilteredStateResponse(
            valid_path=snapshot.valid_path,
            path=str(snapshot.path),
            log_file=str(snapshot.log_file),
            remaining=list(snapshot.remaining),
            remaining_total=snapshot.remaining_total,
            history=_history_models(snapshot),
            history_total=snapshot.history_total,
            filter_options=_filter_options_model(snapshot.filter_options),
            known_entry_exclusions=list(snapshot.known_entry_exclusions),
        )

    @app.post("/api/pick")
    def pick(request: PickRequest) -> PickResponse:
        """Pick one unselected entry, mirroring the CLI/TUI states."""
        outcome = services.pick(
            request.path,
            request.log_file,
            seed=request.seed,
            dry_run=request.dry_run,
            include_hidden=request.include_hidden,
            files_only=request.files_only,
            dirs_only=request.dirs_only,
            selection=request.filter_selection,
            include_preview=True,
        )
        memory_notice: str | None = None
        if outcome.status == "picked":
            memory_notice = memory.record(request.path).notice
        return PickResponse(
            status=outcome.status,
            log_file=str(outcome.log_file),
            item=outcome.item,
            logged=outcome.logged,
            preview=_preview_model(outcome.preview) if outcome.preview else None,
            path_memory_notice=memory_notice,
        )

    @app.get("/api/preview")
    def preview(path: str) -> PreviewModel:
        """Structured preview for an entry path."""
        return _preview_model(preview_entry(Path(path).expanduser()))

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
        payload = web_media.read_image(entry, index)
        data = payload.data
        media_type = payload.media_type
        if variant == "thumb":
            data = web_media.make_thumbnail(data)
            media_type = "image/webp"
        elif variant == "preview":
            data = web_media.make_thumbnail(
                data,
                max_size=web_media.PREVIEW_MAX_SIZE,
                quality=web_media.PREVIEW_QUALITY,
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
        video_file = web_media.read_video(entry)
        response = FileResponse(
            path=video_file.path,
            media_type=video_file.media_type,
            stat_result=video_file.stat_result,
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
                    FileResponse._parse_range_header(
                        range_header, video_file.stat_result.st_size
                    )
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
        outcome = services.open_entry(request.path)
        return OpenResponse(opened=outcome.name)

    @app.post("/api/history/archive")
    def archive(path: str, log_file: str | None = None) -> ArchiveResponse:
        log_path = _log_path(path, log_file)
        backup = services.HistoryService(log_path).archive()
        return ArchiveResponse(
            log_file=str(log_path),
            backup=backup.name if backup is not None else None,
        )

    @app.delete("/api/history")
    def clear(path: str, log_file: str | None = None) -> ClearResponse:
        log_path = _log_path(path, log_file)
        removed = services.HistoryService(log_path).clear()
        return ClearResponse(log_file=str(log_path), removed=removed)

    @app.delete("/api/history/item")
    def remove_history_item(
        path: str, item: str, log_file: str | None = None
    ) -> RemoveHistoryItemResponse:
        """Delete every log entry for `item`, leaving other entries alone."""
        log_path = _log_path(path, log_file)
        removed = services.HistoryService(log_path).remove(item)
        return RemoveHistoryItemResponse(
            log_file=str(log_path), item=item, removed=removed
        )

    @app.post("/api/history/remove")
    def remove_history_items(
        request: RemoveHistoryItemsRequest,
    ) -> RemoveHistoryItemsResponse:
        """Delete every log entry for all selected items in one rewrite."""
        log_path = _log_path(request.path, request.log_file)
        removed = services.HistoryService(log_path).remove_many(request.items)
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
