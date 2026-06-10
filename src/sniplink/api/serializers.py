"""Serializers for the API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sniplink.models import Link


def _iso(value: datetime | None) -> str | None:
    return value.isoformat() if value else None


def link_to_dict(link: Link, *, short_url: str | None = None) -> dict[str, Any]:
    payload = {
        "id": link.id,
        "short_code": link.short_code,
        "destination_url": link.destination_url,
        "redirect_status": link.redirect_status,
        "created_at": _iso(link.created_at),
        "expires_at": _iso(link.expires_at),
        "disabled_at": _iso(link.disabled_at),
        "deleted_at": _iso(link.deleted_at),
        "max_clicks": link.max_clicks,
        "click_count": link.click_count,
        "metadata": link.metadata,
    }
    if short_url:
        payload["short_url"] = short_url
    return payload
