"""Concurrency proofs for ``record_click``.

ADR 0004 says the click counter is incremented atomically. These tests fan
N clicks across a thread pool and assert two invariants:

1. ``link.click_count == N`` (the aggregate counter advances exactly N
   times, with no lost updates from a check-then-write race).
2. ``len(clicks) == N`` (every increment paired with exactly one click row,
   so the integer counter and the per-event table stay in sync).

A third test verifies the atomic ``max_clicks`` gate: when ``max_clicks`` is
set, no concurrent request can push ``click_count`` past the cap, and the
overrun attempts surface as ``CodeExpired`` instead of silently incrementing.
"""

from __future__ import annotations

import sqlite3
from concurrent.futures import ThreadPoolExecutor
from contextlib import closing

import pytest

from sniplink.core import SniplinkService
from sniplink.exceptions import CodeExpired
from sniplink.storage import SQLiteStorage


@pytest.mark.concurrency
def test_concurrent_clicks_keep_counter_and_click_rows_in_sync(sqlite_db_path):
    service = SniplinkService(SQLiteStorage(sqlite_db_path))
    service.initialize()
    link = service.create_link("https://example.com", alias="counter")

    def click(_):
        SniplinkService(SQLiteStorage(sqlite_db_path)).resolve("counter")

    with ThreadPoolExecutor(max_workers=8) as pool:
        list(pool.map(click, range(40)))

    final = service.storage.get_link("counter")
    assert final.click_count == 40

    with closing(sqlite3.connect(sqlite_db_path)) as conn, conn:
        (rows,) = conn.execute(
            "SELECT COUNT(*) FROM clicks WHERE link_id = ?", (link.id,)
        ).fetchone()
    assert rows == 40


@pytest.mark.concurrency
def test_concurrent_clicks_cannot_bust_max_clicks(sqlite_db_path):
    service = SniplinkService(SQLiteStorage(sqlite_db_path))
    service.initialize()
    service.create_link("https://example.com", alias="capped", max_clicks=5)

    def attempt(_) -> str:
        try:
            SniplinkService(SQLiteStorage(sqlite_db_path)).resolve("capped")
        except CodeExpired:
            return "expired"
        return "ok"

    # Returning the outcome from each thread avoids the lost-update race a
    # nonlocal ``+= 1`` counter would otherwise have under the GIL (bug #6
    # in the third-pass review).
    with ThreadPoolExecutor(max_workers=8) as pool:
        outcomes = list(pool.map(attempt, range(20)))

    final = service.storage.get_link("capped")
    assert outcomes.count("ok") == 5
    assert outcomes.count("expired") == 15
    assert final.click_count == 5
