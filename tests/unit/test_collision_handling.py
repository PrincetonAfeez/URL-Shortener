"""Tests for collision handling. """

import pytest

from sniplink.codecs import RandomTokenCodec
from sniplink.core import SniplinkService
from sniplink.exceptions import AliasTaken, CollisionExhausted
from sniplink.storage import SQLiteStorage


class FixedTokenCodec(RandomTokenCodec):
    def __init__(self, tokens):
        self.tokens = iter(tokens)
        self.length = 1
        self.alphabet = "abc"

    def generate(self):
        return next(self.tokens)


def test_alias_conflict_comes_from_unique_constraint(tmp_path):
    service = SniplinkService(SQLiteStorage(tmp_path / "test.db"))
    service.initialize()
    service.create_link("https://example.com", alias="same")

    with pytest.raises(AliasTaken):
        service.create_link("https://example.org", alias="same")


def test_random_token_retries_after_collision(tmp_path):
    service = SniplinkService(
        SQLiteStorage(tmp_path / "test.db"),
        random_codec=FixedTokenCodec(["dup", "ok"]),
    )
    service.initialize()
    service.create_link("https://example.com", alias="dup")

    link = service.create_link("https://example.org", code_strategy="random")

    assert link.short_code == "ok"


def test_random_token_exhausts_retry_budget(tmp_path):
    service = SniplinkService(
        SQLiteStorage(tmp_path / "test.db"),
        random_codec=FixedTokenCodec(["dup", "dup"]),
        collision_retry_limit=2,
    )
    service.initialize()
    service.create_link("https://example.com", alias="dup")

    with pytest.raises(CollisionExhausted):
        service.create_link("https://example.org", code_strategy="random")


def test_base62_collision_hard_deletes_pending_row(tmp_path):
    import sqlite3
    from contextlib import closing

    db_path = tmp_path / "test.db"
    service = SniplinkService(SQLiteStorage(db_path))
    service.initialize()
    service.create_link("https://example.com", alias="1")

    with closing(sqlite3.connect(db_path)) as conn:
        pending = conn.execute(
            "SELECT COUNT(*) FROM links WHERE short_code LIKE '__pending_%'"
        ).fetchone()[0]
    assert pending == 0
