"""Storage base protocol. """

from __future__ import annotations

from datetime import datetime
from typing import Any, Protocol

from sniplink.models import HealthCheckResult, Link


class Storage(Protocol):
    def initialize(self) -> None:
        """Create or migrate the backing store."""

    def insert_link(
        self,
        *,
        short_code: str,
        destination_url: str,
        redirect_status: int,
        expires_at: datetime | None = None,
        max_clicks: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Link:
        """Insert a link using the supplied short code."""

    def insert_pending_link(
        self,
        *,
        destination_url: str,
        redirect_status: int,
        expires_at: datetime | None = None,
        max_clicks: int | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> Link:
        """Insert a link before a sequential code is known."""

    def update_short_code(self, link_id: int, short_code: str) -> Link:
        """Assign a final short code to an existing link."""

    def delete_pending_link(self, link_id: int) -> None:
        """Hard-delete a pending row that lost a code collision."""

    def get_link(self, short_code: str) -> Link:
        """Return a link by short code, including inactive links."""

    def get_link_by_id(self, link_id: int) -> Link:
        """Return a link by database ID."""

    def list_links(self, include_deleted: bool = False) -> list[Link]:
        """List stored links."""

    def mark_disabled(self, short_code: str) -> Link:
        """Mark a link disabled."""

    def mark_deleted(self, short_code: str) -> Link:
        """Soft-delete a link."""

    def set_expiry(self, short_code: str, expires_at: datetime) -> Link:
        """Set an expiry timestamp."""

    def record_click(
        self,
        link_id: int,
        *,
        referrer: str | None = None,
        user_agent: str | None = None,
    ) -> Link:
        """Record a click and increment the aggregate counter.

        Implementations must perform the increment via a conditional
        ``UPDATE`` so the ``max_clicks`` gate is atomic: if the link has
        already hit its quota, the update affects zero rows and the call
        raises :class:`sniplink.exceptions.CodeExpired` instead of inserting
        a stray click row. See ADR 0004 and bug #1 in the code review.
        """

    def stats(self, short_code: str) -> dict[str, Any]:
        """Return basic analytics for a link."""

    def save_health_result(self, result: HealthCheckResult) -> None:
        """Persist one health-check result."""
