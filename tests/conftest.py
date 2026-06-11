"""Shared pytest fixtures for the sniplink test suite.

Three things this file does:

1. Hands every unit test a fresh ``SQLiteStorage`` pointed at a per-test
   temp file. Each test gets its own DB so they can run in parallel without
   stepping on each other's links.

2. Initializes a file-backed SQLite database for tests marked
   ``concurrency``. The concurrency tests rely on SQLite's
   ``UNIQUE(short_code)`` constraint, not on any particular transaction
   pragma — the writer lock engages automatically when ``INSERT`` runs, and
   the constraint raises ``IntegrityError`` for the loser. See ADR 0004.

3. Provides a ``service`` factory and a pre-initialized ``service`` fixture
   so the integration tests are not all reinventing the same setup
   boilerplate.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest

from sniplink.core import SniplinkService
from sniplink.storage import SQLiteStorage


@pytest.fixture
def sqlite_db_path(tmp_path: Path) -> Path:
    """File-backed SQLite path the storage layer will create on first use."""
    return tmp_path / "sniplink-test.db"


@pytest.fixture
def sqlite_storage(sqlite_db_path: Path) -> SQLiteStorage:
    """Initialized SQLiteStorage instance, ready to use."""
    storage = SQLiteStorage(sqlite_db_path)
    storage.initialize()
    return storage


@pytest.fixture
def service_factory(sqlite_db_path: Path):
    """Build SniplinkService instances bound to the same temp DB.

    Useful for concurrency tests that need multiple service objects (each
    with its own connection) talking to a shared database.
    """

    def _factory(**kwargs) -> SniplinkService:
        storage = SQLiteStorage(sqlite_db_path)
        service = SniplinkService(storage, **kwargs)
        service.initialize()
        return service

    return _factory


@pytest.fixture
def service(service_factory) -> SniplinkService:
    """A single ready-to-use SniplinkService for unit and integration tests."""
    return service_factory()


@pytest.fixture
def concurrent_sqlite_db_path(tmp_path: Path) -> Iterator[Path]:
    """File-backed SQLite database for ``@pytest.mark.concurrency`` tests.

    Calling ``SQLiteStorage.initialize`` sets WAL mode on the file (sticky)
    and creates the schema. The concurrency tests then open their own
    ``SQLiteStorage`` instances against this path and race for the
    ``UNIQUE(short_code)`` constraint — SQLite's writer lock serializes the
    INSERTs and the constraint raises ``IntegrityError`` for whichever
    request loses the race. No extra transaction pragmas are needed; the
    constraint is what makes the race observable.
    """

    path = tmp_path / "concurrent.db"
    SQLiteStorage(path).initialize()
    yield path
