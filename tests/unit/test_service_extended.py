"""Additional SniplinkService coverage: metadata, origins, base62 races."""

from __future__ import annotations

import pytest

from sniplink.core import SniplinkService
from sniplink.models import utc_now
from sniplink.exceptions import CodeNotFound, InvalidDestinationURL
from sniplink.storage import SQLiteStorage


def test_create_link_with_metadata(tmp_path):
    service = SniplinkService(SQLiteStorage(tmp_path / "meta.db"))
    service.initialize()
    link = service.create_link(
        "https://example.com",
        alias="meta",
        metadata={"campaign": "spring"},
    )
    assert link.metadata == {"campaign": "spring"}


def test_self_reference_blocks_base_url_and_aliases(tmp_path):
    service = SniplinkService(
        SQLiteStorage(tmp_path / "self.db"),
        base_url="http://short.test",
        base_aliases=("http://127.0.0.1:8000",),
    )
    service.initialize()
    with pytest.raises(InvalidDestinationURL, match="sniplink"):
        service.create_link("http://short.test/foo")
    with pytest.raises(InvalidDestinationURL, match="sniplink"):
        service.create_link("http://127.0.0.1:8000/bar")


def test_base62_update_short_code_code_not_found_retries(tmp_path, monkeypatch):
    from sniplink.exceptions import CollisionExhausted

    storage = SQLiteStorage(tmp_path / "nf.db")
    service = SniplinkService(storage, collision_retry_limit=2)
    service.initialize()

    def flaky_update(link_id: int, short_code: str):
        try:
            storage.delete_pending_link(link_id)
        except CodeNotFound:
            pass
        raise CodeNotFound(f"link id not found: {link_id}")

    monkeypatch.setattr(storage, "update_short_code", flaky_update)
    with pytest.raises(CollisionExhausted):
        service.create_link("https://example.com")


def test_random_skips_reserved_generated_codes(tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    reserved_codec = MagicMock()
    reserved_codec.generate.side_effect = ["api", "ok"]
    service = SniplinkService(
        SQLiteStorage(tmp_path / "res.db"),
        reserved_codes=("api",),
        random_codec=reserved_codec,
    )
    service.initialize()
    link = service.create_link("https://example.com", code_strategy="random")
    assert link.short_code == "ok"


def test_base62_alias_taken_on_update_retries(tmp_path, monkeypatch):
    from sniplink.exceptions import AliasTaken

    storage = SQLiteStorage(tmp_path / "alias.db")
    service = SniplinkService(storage, collision_retry_limit=3)
    service.initialize()
    service.create_link("https://example.com", alias="taken")

    real_update = storage.update_short_code
    calls = {"n": 0}

    def collide_once(link_id: int, short_code: str):
        calls["n"] += 1
        if calls["n"] == 1:
            raise AliasTaken("short code already exists: x")
        return real_update(link_id, short_code)

    monkeypatch.setattr(storage, "update_short_code", collide_once)
    link = service.create_link("https://example.org")
    assert link.short_code


def test_initialize_cleans_stale_pending_links(tmp_path):
    storage = SQLiteStorage(tmp_path / "pending.db")
    storage.initialize()
    pending = storage.insert_pending_link(
        destination_url="https://example.com",
        redirect_status=302,
    )
    with storage._connect() as conn:  # noqa: SLF001
        conn.execute(
            "UPDATE links SET created_at = ? WHERE id = ?",
            ("2000-01-01T00:00:00+00:00", pending.id),
        )
    service = SniplinkService(storage)
    service.initialize()
    with pytest.raises(CodeNotFound):
        storage.get_link_by_id(pending.id)


def test_create_link_rejects_past_expiry(tmp_path):
    from datetime import timedelta

    service = SniplinkService(SQLiteStorage(tmp_path / "exp.db"))
    service.initialize()
    with pytest.raises(ValueError, match="future"):
        service.create_link(
            "https://example.com",
            alias="past",
            expires_at=utc_now() - timedelta(days=1),
        )


def test_initialize_without_pending_cleanup_hook(tmp_path):
    from sniplink.storage.base import Storage

    class MinimalStorage(Storage):
        def initialize(self) -> None:
            return None

        def insert_link(self, **kwargs):
            raise NotImplementedError

    service = SniplinkService(MinimalStorage())  # type: ignore[arg-type]
    service.initialize()


def test_fetch_link_returns_without_lifecycle_gate(tmp_path):
    service = SniplinkService(SQLiteStorage(tmp_path / "fetch.db"))
    service.initialize()
    service.create_link("https://example.com", alias="raw")
    service.disable_link("raw")
    link = service.fetch_link("raw")
    assert link.disabled_at is not None
