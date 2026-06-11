"""Storage migrations. """

from __future__ import annotations

from pathlib import Path

from sniplink.storage.sqlite_store import SQLiteStorage


def initialize_sqlite(path: str | Path) -> None:
    SQLiteStorage(path).initialize()
