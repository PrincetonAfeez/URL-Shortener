"""Tests for ``sniplink.api.serializers.link_to_dict``."""

from __future__ import annotations

from datetime import datetime, timezone

from sniplink.api import link_to_dict
from sniplink.models import Link


def test_link_to_dict_includes_all_documented_fields():
    created_at = datetime(2026, 1, 2, 3, 4, 5, tzinfo=timezone.utc)
    link = Link(
        id=42,
        short_code="demo",
        destination_url="https://example.com/",
        redirect_status=302,
        created_at=created_at,
        expires_at=None,
        disabled_at=None,
        deleted_at=None,
        max_clicks=10,
        click_count=3,
        metadata={"campaign": "alpha"},
    )

    payload = link_to_dict(link, short_url="http://short.test/demo")

    assert payload == {
        "id": 42,
        "short_code": "demo",
        "destination_url": "https://example.com/",
        "redirect_status": 302,
        "created_at": "2026-01-02T03:04:05+00:00",
        "expires_at": None,
        "disabled_at": None,
        "deleted_at": None,
        "max_clicks": 10,
        "click_count": 3,
        "metadata": {"campaign": "alpha"},
        "short_url": "http://short.test/demo",
    }


def test_link_to_dict_omits_short_url_when_not_supplied():
    link = Link(id=1, short_code="x", destination_url="https://example.com/")
    payload = link_to_dict(link)

    assert "short_url" not in payload
    assert payload["short_code"] == "x"
