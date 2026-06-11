"""Additional SQLiteStorage coverage."""

from __future__ import annotations

import pytest

from sniplink.core import SniplinkService
from sniplink.exceptions import CodeNotFound
from sniplink.storage import SQLiteStorage


def test_cleanup_stale_pending_links(tmp_path):
    storage = SQLiteStorage(tmp_path / "pending.db")
    storage.initialize()
    pending = storage.insert_pending_link(
        destination_url="https://example.com",
        redirect_status=302,
    )
    import sqlite3

    with sqlite3.connect(tmp_path / "pending.db") as conn:
        conn.execute(
            "UPDATE links SET created_at = '2000-01-01T00:00:00+00:00' WHERE id = ?",
            (pending.id,),
        )
        conn.commit()
    removed = storage.cleanup_stale_pending_links(max_age_hours=24)
    assert removed >= 1
    with pytest.raises(CodeNotFound):
        storage.get_link_by_id(pending.id)


def test_delete_pending_link_rejects_finalized_rows(tmp_path):
    storage = SQLiteStorage(tmp_path / "guard.db")
    storage.initialize()
    link = storage.insert_link(
        short_code="final",
        destination_url="https://example.com",
        redirect_status=302,
    )
    with pytest.raises(CodeNotFound):
        storage.delete_pending_link(link.id)


def test_stats_normalizes_last_clicked_at(tmp_path):
    service = SniplinkService(SQLiteStorage(tmp_path / "stats.db"))
    service.initialize()
    service.create_link("https://example.com", alias="stat")
    service.resolve("stat")
    payload = service.stats("stat")
    assert payload["last_clicked_at"] is not None
    assert "T" in payload["last_clicked_at"]
