"""Shared test isolation: never read or write the developer's path memory."""

import pytest


@pytest.fixture(autouse=True)
def isolated_path_memory(tmp_path, monkeypatch):
    """Point every test at a unique temporary path-memory file."""
    monkeypatch.setenv(
        "CHOOSIER_PATH_MEMORY_FILE",
        str(tmp_path / "path-memory.json"),
    )
