#!/usr/bin/env python3
"""Backward-compatible entrypoint. Prefer `python -m choosier` or `choosier`."""

from choosier.chooser import get_unselected_item
from choosier.cli import main
from choosier.storage import get_logged_items, log_selection

__all__ = ["get_logged_items", "get_unselected_item", "log_selection", "main"]


if __name__ == "__main__":
    raise SystemExit(main())
