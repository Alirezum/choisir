"""Directory browsing for every interface."""

from pathlib import Path

from choosier.services.errors import FailureKind, ServiceError
from choosier.services.models import BrowseEntry, BrowseListing


def browse_directory(path: str | Path) -> BrowseListing:
    """List one directory, directories first, then case-insensitive name."""
    directory = Path(path).expanduser()
    if not directory.is_dir():
        raise ServiceError(FailureKind.NOT_FOUND, "Not a directory")
    try:
        children = sorted(
            directory.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())
        )
    except OSError as e:
        raise ServiceError(FailureKind.FORBIDDEN, f"Cannot list: {e}") from e
    parent = directory.parent if directory.parent != directory else None
    return BrowseListing(
        path=directory,
        parent=parent,
        entries=tuple(
            BrowseEntry(name=child.name, is_dir=child.is_dir()) for child in children
        ),
    )
