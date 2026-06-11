"""Cover remaining SniplinkService branches."""

from __future__ import annotations

import pytest

from sniplink.core import SniplinkService
from sniplink.exceptions import CollisionExhausted
from sniplink.storage import SQLiteStorage


def test_unsupported_default_redirect_status_rejected(tmp_path):
    with pytest.raises(ValueError, match="unsupported default"):
        SniplinkService(SQLiteStorage(tmp_path / "x.db"), default_redirect_status=999)


def test_unknown_code_strategy_raises(tmp_path):
    service = SniplinkService(SQLiteStorage(tmp_path / "x.db"))
    service.initialize()
    with pytest.raises(ValueError, match="unknown code strategy"):
        service.create_link("https://example.com", code_strategy="nope")  # type: ignore[arg-type]


def test_collision_exhausted_when_codec_always_collides(tmp_path, monkeypatch):
    from unittest.mock import MagicMock

    service = SniplinkService(
        SQLiteStorage(tmp_path / "col.db"),
        collision_retry_limit=2,
        random_codec=MagicMock(),
    )
    service.initialize()
    service.create_link("https://example.com", alias="taken")
    service.random_codec.generate.return_value = "taken"
    with pytest.raises(CollisionExhausted):
        service.create_link("https://example.com", code_strategy="random")
