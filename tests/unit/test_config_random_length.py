"""Config-driven random token length reaches the service."""

from __future__ import annotations

from sniplink.codecs import RandomTokenCodec
from sniplink.config import SniplinkConfig
from sniplink.core.factory import build_sniplink_service
from sniplink.storage import SQLiteStorage


def test_build_service_honors_random_token_length(tmp_path):
    config = SniplinkConfig(
        database_path=tmp_path / "cfg.db",
        random_token_length=12,
    )
    service = build_sniplink_service(SQLiteStorage(config.database_path), config)
    assert isinstance(service.random_codec, RandomTokenCodec)
    assert service.random_codec.length == 12
