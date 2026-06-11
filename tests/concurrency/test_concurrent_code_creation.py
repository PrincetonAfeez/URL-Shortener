"""Concurrency tests for the UNIQUE(short_code) constraint and retry path.

These tests exist to prove ADR 0004: the database constraint, not application
logic, decides who wins a collision. Each test is marked ``concurrency`` so
the suite can be filtered with ``pytest -m concurrency``.

The ``concurrent_sqlite_db_path`` fixture (see ``tests/conftest.py``)
initializes a file-backed SQLite database in WAL mode. The race itself comes
from SQLite's writer lock + the ``UNIQUE`` constraint — when two threads
attempt the same ``short_code``, one wins the lock and commits; the loser
hits ``IntegrityError``, which the storage layer maps to ``AliasTaken``.
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

import pytest

from sniplink.codecs import RandomTokenCodec
from sniplink.core import SniplinkService
from sniplink.exceptions import AliasTaken
from sniplink.storage import SQLiteStorage


@pytest.mark.concurrency
def test_concurrent_base62_creation_produces_unique_codes(sqlite_db_path):
    service = SniplinkService(SQLiteStorage(sqlite_db_path))
    service.initialize()

    def create(index):
        return service.create_link(f"https://example.com/{index}").short_code

    with ThreadPoolExecutor(max_workers=8) as executor:
        codes = list(executor.map(create, range(40)))

    assert len(codes) == len(set(codes))


@pytest.mark.concurrency
def test_same_alias_from_many_threads_resolves_to_one_winner(concurrent_sqlite_db_path):
    """Many threads race for the same alias. Exactly one wins; the rest see AliasTaken.

    This is the IntegrityError path from ADR 0004 — it does not fire in the
    base62 test above because each thread gets a unique auto-increment ID.
    Forcing the same alias makes the UNIQUE constraint do the work.
    """

    def attempt(index: int) -> str | None:
        service = SniplinkService(SQLiteStorage(concurrent_sqlite_db_path))
        try:
            return service.create_link(
                f"https://example.com/{index}", alias="shared"
            ).short_code
        except AliasTaken:
            return None

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(attempt, range(12)))

    winners = [code for code in results if code is not None]
    losers = [code for code in results if code is None]

    assert len(winners) == 1
    assert winners[0] == "shared"
    assert len(losers) == 11


class _AlwaysCollidesCodec(RandomTokenCodec):
    """Generates the same token until it has run out of pre-canned values.

    Used to force the random-token retry path under concurrency without
    relying on chance.
    """

    def __init__(self, sequence):
        self._sequence = iter(sequence)
        self.length = 1
        self.alphabet = "abc"

    def generate(self) -> str:
        return next(self._sequence)


@pytest.mark.concurrency
def test_random_token_retry_under_concurrency(concurrent_sqlite_db_path):
    """Two threads + a codec that hands out 'dup' then 'a','b','c','d',....

    The first thread to insert wins 'dup'. The second thread's first attempt
    collides, catches AliasTaken, retries with 'a' (or whichever token is
    next), and succeeds. Both threads return a link rather than blowing up.
    """

    tokens = ["dup", "dup", "a", "b", "c", "d"]

    def attempt(index: int) -> str:
        codec = _AlwaysCollidesCodec(list(tokens))
        service = SniplinkService(
            SQLiteStorage(concurrent_sqlite_db_path),
            random_codec=codec,
            collision_retry_limit=len(tokens),
        )
        return service.create_link(
            f"https://example.com/{index}",
            code_strategy="random",
        ).short_code

    with ThreadPoolExecutor(max_workers=2) as executor:
        codes = list(executor.map(attempt, range(2)))

    assert len(codes) == 2
    assert len(set(codes)) == 2
