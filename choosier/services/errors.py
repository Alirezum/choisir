"""Interface-neutral service failures."""

from enum import StrEnum


class FailureKind(StrEnum):
    """Failure categories shared by every adapter."""

    INVALID_INPUT = "invalid_input"
    FORBIDDEN = "forbidden"
    NOT_FOUND = "not_found"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"
    RANGE_NOT_SATISFIABLE = "range_not_satisfiable"
    IO_ERROR = "io_error"


class ServiceError(Exception):
    """A business failure with no HTTP or UI coupling."""

    def __init__(
        self,
        kind: FailureKind,
        message: str,
        details: dict[str, object] | None = None,
    ) -> None:
        super().__init__(message)
        self.kind = kind
        self.message = message
        self.details = details
