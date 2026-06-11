"""Service implementation. """

from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime
from typing import Any, Literal

from sniplink.codecs import Base62Codec, RandomTokenCodec
from sniplink.core.lifecycle import (
    ensure_click_quota_available,
    ensure_can_disable,
    ensure_can_expire,
    ensure_link_available,
    is_active_link,
)
from sniplink.core.validation import (
    is_reserved_code,
    normalize_destination_url,
    validate_alias,
    validate_future_expiry,
    validate_max_clicks,
)
from sniplink.exceptions import AliasTaken, CodeNotFound, CollisionExhausted
from sniplink.models import Link, RedirectDecision
from sniplink.storage.base import Storage

CodeStrategy = Literal["base62", "random"]
SUPPORTED_REDIRECTS = {301, 302, 307, 308}


class SniplinkService:
    """Engine — the framework-free core every adapter depends on.

    All defaults come from :class:`sniplink.config.SniplinkConfig`. The
    service does not call :func:`load_config` itself so unit tests can pass
    their own values without writing a TOML file.
    """

    def __init__(
        self,
        storage: Storage,
        *,
        base_url: str = "http://localhost:8000",
        base_aliases: Sequence[str] = (),
        default_redirect_status: int = 302,
        reserved_codes: Sequence[str] = (),
        base62_codec: Base62Codec | None = None,
        random_codec: RandomTokenCodec | None = None,
        collision_retry_limit: int = 8,
        max_destination_length: int = 2048,
    ) -> None:
        if default_redirect_status not in SUPPORTED_REDIRECTS:
            raise ValueError(f"unsupported default redirect status: {default_redirect_status}")
        self.storage = storage
        self.base_url = base_url
        self.base_aliases = tuple(base_aliases)
        self.default_redirect_status = default_redirect_status
        self.reserved_codes = tuple(reserved_codes)
        self.base62_codec = base62_codec or Base62Codec()
        self.random_codec = random_codec or RandomTokenCodec()
        self.collision_retry_limit = collision_retry_limit
        self.max_destination_length = max_destination_length

    def initialize(self) -> None:
        self.storage.initialize()
        if hasattr(self.storage, "cleanup_stale_pending_links"):
            self.storage.cleanup_stale_pending_links()

    def create_link(
        self,
        destination_url: str,
        *,
        alias: str | None = None,
        code_strategy: CodeStrategy = "base62",
        redirect_status: int | None = None,
        expires_at: datetime | None = None,
        max_clicks: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Link:
        if redirect_status is None:
            redirect_status = self.default_redirect_status
        if redirect_status not in SUPPORTED_REDIRECTS:
            raise ValueError(f"unsupported redirect status: {redirect_status}")
        validate_max_clicks(max_clicks)
        expires_at = validate_future_expiry(expires_at)
        normalized_url = normalize_destination_url(
            destination_url,
            base_urls=self._self_reference_origins(),
            max_length=self.max_destination_length,
        )

        if alias is not None:
            return self.storage.insert_link(
                short_code=validate_alias(alias, reserved_codes=self.reserved_codes),
                destination_url=normalized_url,
                redirect_status=redirect_status,
                expires_at=expires_at,
                max_clicks=max_clicks,
                metadata=metadata,
            )

        if code_strategy == "random":
            return self._create_random(
                normalized_url,
                redirect_status=redirect_status,
                expires_at=expires_at,
                max_clicks=max_clicks,
                metadata=metadata,
            )
        if code_strategy == "base62":
            return self._create_base62(
                normalized_url,
                redirect_status=redirect_status,
                expires_at=expires_at,
                max_clicks=max_clicks,
                metadata=metadata,
            )
        raise ValueError(f"unknown code strategy: {code_strategy}")

    def _create_base62(
        self,
        destination_url: str,
        *,
        redirect_status: int,
        expires_at: datetime | None,
        max_clicks: int | None,
        metadata: dict[str, Any] | None,
    ) -> Link:
        for _ in range(self.collision_retry_limit):
            pending = self.storage.insert_pending_link(
                destination_url=destination_url,
                redirect_status=redirect_status,
                expires_at=expires_at,
                max_clicks=max_clicks,
                metadata=metadata,
            )
            candidate = self.base62_codec.encode(pending.id)
            if is_reserved_code(candidate, reserved_codes=self.reserved_codes):
                self.storage.delete_pending_link(pending.id)
                continue
            try:
                return self.storage.update_short_code(pending.id, candidate)
            except AliasTaken:
                self.storage.delete_pending_link(pending.id)
            except CodeNotFound:
                try:
                    self.storage.delete_pending_link(pending.id)
                except CodeNotFound:
                    pass
                continue
        raise CollisionExhausted("base62 code collided with existing aliases too often")

    def _create_random(
        self,
        destination_url: str,
        *,
        redirect_status: int,
        expires_at: datetime | None,
        max_clicks: int | None,
        metadata: dict[str, Any] | None,
    ) -> Link:
        for _ in range(self.collision_retry_limit):
            candidate = self.random_codec.generate()
            if is_reserved_code(candidate, reserved_codes=self.reserved_codes):
                continue
            try:
                return self.storage.insert_link(
                    short_code=candidate,
                    destination_url=destination_url,
                    redirect_status=redirect_status,
                    expires_at=expires_at,
                    max_clicks=max_clicks,
                    metadata=metadata,
                )
            except AliasTaken:
                continue
        raise CollisionExhausted("random token collision retry limit exhausted")

    def resolve(
        self,
        short_code: str,
        *,
        record_click: bool = True,
        referrer: str | None = None,
        user_agent: str | None = None,
    ) -> RedirectDecision:
        if is_reserved_code(short_code, reserved_codes=self.reserved_codes):
            raise CodeNotFound(f"reserved short code: {short_code}")
        link = self.storage.get_link(short_code)
        ensure_link_available(link)
        if not record_click:
            ensure_click_quota_available(link)
        if record_click:
            # storage.record_click also performs the atomic max_clicks gate
            # — see bug #1 in the code review. It raises CodeExpired if the
            # link has already exhausted its quota.
            link = self.storage.record_click(
                link.id,
                referrer=referrer,
                user_agent=user_agent,
            )
        return RedirectDecision(
            short_code=link.short_code,
            destination_url=link.destination_url,
            status_code=link.redirect_status,
            link=link,
        )

    def fetch_link(self, short_code: str) -> Link:
        """Return a link record without applying redirect lifecycle gates."""

        return self.storage.get_link(short_code)

    def disable_link(self, short_code: str) -> Link:
        ensure_can_disable(self.storage.get_link(short_code))
        return self.storage.mark_disabled(short_code)

    def delete_link(self, short_code: str) -> Link:
        return self.storage.mark_deleted(short_code)

    def expire_link(self, short_code: str, when: datetime) -> Link:
        ensure_can_expire(self.storage.get_link(short_code))
        return self.storage.set_expiry(short_code, when)

    def list_links(self, include_deleted: bool = False) -> list[Link]:
        return self.storage.list_links(include_deleted=include_deleted)

    def list_active_links(self) -> list[Link]:
        return [link for link in self.list_links() if is_active_link(link)]

    def stats(self, short_code: str) -> dict[str, Any]:
        return self.storage.stats(short_code)

    def _self_reference_origins(self) -> list[str]:
        # The deployment is typically reachable at both 127.0.0.1 and
        # localhost — config.base_aliases names the extras so a self-shortened
        # link via the IP form still fails validation.
        return [self.base_url, *self.base_aliases]
