"""Prove clicks are not recorded after a link is disabled (atomic lifecycle gate)."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from sniplink.core import SniplinkService
from sniplink.exceptions import CodeDisabled
from sniplink.storage import SQLiteStorage


@pytest.mark.concurrency
def test_sqlite_disabled_link_rejects_concurrent_clicks(sqlite_db_path):
    service = SniplinkService(SQLiteStorage(sqlite_db_path))
    service.initialize()
    service.create_link("https://example.com", alias="race")
    service.resolve("race")
    service.disable_link("race")
    before = service.storage.get_link("race").click_count

    def attempt(_):
        try:
            SniplinkService(SQLiteStorage(sqlite_db_path)).resolve("race")
            return "ok"
        except CodeDisabled:
            return "gone"

    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(attempt, range(20)))

    assert all(item == "gone" for item in outcomes)
    assert service.storage.get_link("race").click_count == before
