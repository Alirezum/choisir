"""Interface-independent application services for choosier."""

from choosier.services.browse import browse_directory
from choosier.services.errors import FailureKind, ServiceError
from choosier.services.history import HistoryService
from choosier.services.models import (
    BrowseEntry,
    BrowseListing,
    HistorySnapshot,
    OpenOutcome,
    PickOutcome,
    StateSnapshot,
)
from choosier.services.opening import open_entry
from choosier.services.pick import pick
from choosier.services.state import PANEL_MAX_LINES, build_state

__all__ = [
    "FailureKind",
    "ServiceError",
    "HistoryService",
    "PANEL_MAX_LINES",
    "BrowseEntry",
    "BrowseListing",
    "HistorySnapshot",
    "StateSnapshot",
    "PickOutcome",
    "OpenOutcome",
    "browse_directory",
    "build_state",
    "pick",
    "open_entry",
]
