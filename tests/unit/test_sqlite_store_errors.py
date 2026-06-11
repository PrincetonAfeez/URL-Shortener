"""SQLite storage error and edge-case coverage."""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import timedelta

import pytest

from sniplink.exceptions import AliasTaken, CodeExpired, CodeNotFound, StorageError
from sniplink.models import utc_now
from sniplink.storage.sqlite_store import SQLiteStorage, _dt_from_db, _dt_to_db, _is_unique_constraint


def test_dt_helpers_normalize_naive_and_none():
    assert _dt_to_db(None) is None
    naive = utc_now().replace(tzinfo=None)
    assert _dt_to_db(naive).endswith("+00:00")
    assert _dt_from_db(None) is None
    assert _dt_from_db("2026-01-01T00:00:00").tzinfo is not None


def test_is_unique_constraint_fallback_message():
    exc = sqlite3.IntegrityError("UNIQUE constraint failed: links.short_code")
    assert _is_unique_constraint(exc) is True
    assert _is_unique_constraint(sqlite3.IntegrityError("CHECK failed")) is False


def test_update_short_code_alias_taken_and_missing(tmp_path):
    storage = SQLiteStorage(tmp_path / "upd.db")
    storage.initialize()
    first = storage.insert_link(
        short_code="one",
        destination_url="https://one.com",
        redirect_status=302,
    )
    storage.insert_link(
        short_code="two",
        destination_url="https://two.com",
        redirect_status=302,
    )
    with pytest.raises(AliasTaken):
        storage.update_short_code(first.id, "two")
    with pytest.raises(CodeNotFound):
        storage.update_short_code(9999, "nope")


def test_insert_link_generic_sqlite_error_maps_to_storage_error(tmp_path, monkeypatch):
    storage = SQLiteStorage(tmp_path / "sqlerr.db")
    storage.initialize()

    @contextmanager
    def failing_connect(self):
        raise sqlite3.OperationalError("disk I/O error")
        yield  # pragma: no cover

    monkeypatch.setattr(SQLiteStorage, "_connect", failing_connect)
    with pytest.raises(StorageError):
        storage.insert_link(
            short_code="x",
            destination_url="https://x.com",
            redirect_status=302,
        )


def test_record_click_disabled_link_raises_code_disabled(tmp_path):
    storage = SQLiteStorage(tmp_path / "disclick.db")
    storage.initialize()
    link = storage.insert_link(
        short_code="off",
        destination_url="https://example.com",
        redirect_status=302,
    )
    storage.mark_disabled("off")
    from sniplink.exceptions import CodeDisabled

    with pytest.raises(CodeDisabled):
        storage.record_click(link.id)


def test_record_click_raises_code_expired_at_cap(tmp_path):
    storage = SQLiteStorage(tmp_path / "cap.db")
    storage.initialize()
    link = storage.insert_link(
        short_code="cap",
        destination_url="https://example.com",
        redirect_status=302,
        max_clicks=1,
    )
    storage.record_click(link.id)
    with pytest.raises(CodeExpired):
        storage.record_click(link.id)


def test_mark_disabled_missing_code(tmp_path):
    storage = SQLiteStorage(tmp_path / "dis.db")
    storage.initialize()
    with pytest.raises(CodeNotFound):
        storage.mark_disabled("missing")


def test_delete_pending_link_missing(tmp_path):
    storage = SQLiteStorage(tmp_path / "pend.db")
    storage.initialize()
    with pytest.raises(CodeNotFound):
        storage.delete_pending_link(999)


def test_initialize_creates_parent_directory(tmp_path):
    db = tmp_path / "nested" / "dir" / "db.sqlite3"
    SQLiteStorage(db).initialize()
    assert db.exists()
