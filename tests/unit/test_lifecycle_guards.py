"""Unit tests for ``ensure_can_disable`` / ``ensure_can_expire``."""

from __future__ import annotations

from datetime import timedelta

import pytest

from sniplink.core.lifecycle import ensure_can_disable, ensure_can_expire
from sniplink.exceptions import CodeDeleted, CodeDisabled
from sniplink.models import Link, utc_now


def _link(**kwargs) -> Link:
    defaults = dict(
        id=1,
        short_code="demo",
        destination_url="https://example.com",
        redirect_status=302,
        created_at=utc_now(),
        expires_at=None,
        disabled_at=None,
        deleted_at=None,
        max_clicks=None,
        click_count=0,
        metadata={},
    )
    defaults.update(kwargs)
    return Link(**defaults)


def test_ensure_can_disable_rejects_deleted():
    with pytest.raises(CodeDeleted):
        ensure_can_disable(_link(deleted_at=utc_now()))


def test_ensure_can_disable_rejects_already_disabled():
    with pytest.raises(CodeDisabled):
        ensure_can_disable(_link(disabled_at=utc_now()))


def test_ensure_can_expire_rejects_deleted():
    with pytest.raises(CodeDeleted):
        ensure_can_expire(_link(deleted_at=utc_now() - timedelta(hours=1)))


def test_ensure_can_expire_allows_disabled_link():
    ensure_can_expire(_link(disabled_at=utc_now()))
