""" Data models for the service. """

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class Link:
    id: int
    short_code: str
    destination_url: str
    redirect_status: int = 302
    created_at: datetime = field(default_factory=utc_now)
    expires_at: datetime | None = None
    disabled_at: datetime | None = None
    deleted_at: datetime | None = None
    max_clicks: int | None = None
    click_count: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Click:
    id: int
    link_id: int
    clicked_at: datetime = field(default_factory=utc_now)
    referrer: str | None = None
    user_agent: str | None = None


@dataclass(slots=True)
class RedirectDecision:
    short_code: str
    destination_url: str
    status_code: int
    link: Link


@dataclass(slots=True)
class HealthCheckResult:
    link_id: int
    checked_at: datetime
    status_code: int | None
    error: str | None
    elapsed_ms: float
    redirect_count: int = 0
