""" Service factory. """

from __future__ import annotations

from sniplink.codecs import RandomTokenCodec
from sniplink.config import SniplinkConfig
from sniplink.core.service import SniplinkService
from sniplink.storage.base import Storage


def build_sniplink_service(
    storage: Storage,
    config: SniplinkConfig,
    *,
    base_url: str | None = None,
) -> SniplinkService:
    """Construct a :class:`SniplinkService` with config-driven defaults."""

    return SniplinkService(
        storage,
        base_url=base_url or config.default_base_url,
        base_aliases=config.base_aliases,
        default_redirect_status=config.default_redirect_status,
        reserved_codes=config.reserved_codes,
        random_codec=RandomTokenCodec(length=config.random_token_length),
        collision_retry_limit=config.collision_retry_limit,
        max_destination_length=config.max_destination_length,
    )
