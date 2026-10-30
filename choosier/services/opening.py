"""Opening entries with the OS default program."""

from pathlib import Path

from choosier import launcher
from choosier.services.errors import FailureKind, ServiceError
from choosier.services.models import OpenOutcome


def open_entry(path: str | Path) -> OpenOutcome:
    """Open one entry through the platform launcher."""
    entry = Path(path).expanduser()
    if not entry.exists():
        raise ServiceError(FailureKind.NOT_FOUND, "Entry is gone")
    try:
        launcher.launch_path(entry)
    except OSError as e:
        raise ServiceError(FailureKind.IO_ERROR, f"Cannot open: {e}") from e
    return OpenOutcome(name=entry.name)
