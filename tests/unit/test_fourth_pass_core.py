"""Regression tests for the fourth-pass audit fixes."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from sniplink.core import SniplinkService
from sniplink.core.lifecycle import is_active_link
from sniplink.exceptions import CodeDisabled, CodeNotFound, InvalidAlias
from sniplink.models import Link, utc_now
from sniplink.storage import SQLiteStorage


def test_base62_skips_reserved_generated_code(sqlite_db_path):
    codec = MagicMock()
    codec.encode.side_effect = ["api", "safe1"]
    service = SniplinkService(
        SQLiteStorage(sqlite_db_path),
        base62_codec=codec,
        reserved_codes=("api",),
    )
    service.initialize()
    link = service.create_link("https://example.com")
    assert link.short_code == "safe1"


def test_resolve_rejects_reserved_code(sqlite_db_path):
    service = SniplinkService(
        SQLiteStorage(sqlite_db_path),
        reserved_codes=("api",),
    )
    service.initialize()
    with pytest.raises(CodeNotFound):
        service.resolve("api", record_click=False)


def test_disable_link_rejects_already_disabled(sqlite_db_path):
    service = SniplinkService(SQLiteStorage(sqlite_db_path))
    service.initialize()
    service.create_link("https://example.com", alias="off")
    service.disable_link("off")
    with pytest.raises(CodeDisabled):
        service.disable_link("off")


def test_pending_rows_are_not_active():
    link = Link(
        id=1,
        short_code="__pending_abc",
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
    assert not is_active_link(link)


def test_validate_alias_normalizes_to_lowercase():
    from sniplink.core.validation import validate_alias

    assert validate_alias("Demo") == "demo"


def test_validate_future_expiry_rejects_past():
    from datetime import timedelta

    from sniplink.core.validation import validate_future_expiry

    past = utc_now() - timedelta(hours=1)
    with pytest.raises(ValueError, match="future"):
        validate_future_expiry(past)
