"""Targeted tests for remaining uncovered branches."""

from __future__ import annotations

import asyncio
from datetime import timedelta

import pytest

from sniplink.api.errors import status_for_exception
from sniplink.api.validation import parse_api_max_clicks
from sniplink.codecs.base62 import Base62Codec
from sniplink.codecs.random_token import RandomTokenCodec
from sniplink.config import _coerce_tuple, load_config
from sniplink.core.lifecycle import is_active_link, link_display_state
from sniplink.core.validation import normalize_destination_url
from sniplink.exceptions import CodeDeleted, CodeNotFound, InvalidDestinationURL, StorageError
from sniplink.models import Link, utc_now
from sniplink.observability.redaction import redact_mapping, redact_secret
from sniplink.storage.sqlite_store import SQLiteStorage


def test_base62_encode_zero_and_invalid_alphabet():
    codec = Base62Codec()
    assert codec.encode(0) == "0"
    with pytest.raises(ValueError, match="duplicate"):
        Base62Codec(alphabet="aa")
    with pytest.raises(ValueError, match="at least two"):
        Base62Codec(alphabet="a")


def test_random_token_validation_and_not_implemented():
    with pytest.raises(ValueError, match="positive"):
        RandomTokenCodec(length=0)
    with pytest.raises(ValueError, match="duplicate"):
        RandomTokenCodec(alphabet="aa")
    codec = RandomTokenCodec(length=3)
    with pytest.raises(NotImplementedError):
        codec.encode(1)
    with pytest.raises(NotImplementedError):
        codec.decode("abc")


def test_coerce_tuple_rejects_bad_type():
    with pytest.raises(TypeError, match="list/tuple"):
        _coerce_tuple("nope", ("a",))


def test_normalize_destination_url_edge_cases():
    with pytest.raises(InvalidDestinationURL, match="required"):
        normalize_destination_url("   ")
    with pytest.raises(InvalidDestinationURL, match="too long"):
        normalize_destination_url("https://example.com/" + "x" * 3000, max_length=32)
    with pytest.raises(InvalidDestinationURL, match="host"):
        normalize_destination_url("https:///path")
    assert normalize_destination_url("https://EXAMPLE.com:443/path").startswith("https://example.com/")


def test_self_reference_blocks_shortener_origin():
    with pytest.raises(InvalidDestinationURL, match="sniplink"):
        normalize_destination_url(
            "http://localhost:8000/foo",
            base_urls=["http://localhost:8000"],
        )


def test_redact_non_string_sensitive_value():
    payload = redact_mapping({"token": 12345}, redact_keys=["token"])
    assert payload["token"] == "***"


def test_validate_future_expiry_rejects_past():
    from sniplink.core.validation import validate_future_expiry

    past = utc_now() - timedelta(days=1)
    with pytest.raises(ValueError, match="future"):
        validate_future_expiry(past)
    with pytest.raises(ValueError, match="future"):
        validate_future_expiry(utc_now())


def test_self_reference_skips_base_url_without_netloc():
    assert normalize_destination_url(
        "https://example.com",
        base_urls=["http:///"],
    ).startswith("https://example.com/")


def test_self_reference_skips_empty_base_url():
    assert normalize_destination_url(
        "https://example.com",
        base_urls=["", "http://localhost:8000"],
    ).startswith("https://example.com/")


def test_redact_secret_and_nested_mapping():
    assert redact_secret(None) is None
    assert redact_secret("short") == "***"
    assert redact_secret("abcdefghij") == "abcd...ghij"
    payload = redact_mapping(
        {"Authorization": "Bearer secret-token", "nested": {"api_key": "k"}},
        redact_keys=["authorization", "api_key"],
    )
    assert "..." in payload["Authorization"]
    assert payload["nested"]["api_key"] == "***"
    payload_list = redact_mapping({"items": [{"token": "x"}]}, redact_keys=["token"])
    assert payload_list["items"][0]["token"] == "***"


def test_status_for_generic_sniplink_error():
    assert status_for_exception(StorageError("x")) == 500
    assert status_for_exception(RuntimeError("x")) == 500


def test_parse_api_max_clicks_bool_rejected():
    with pytest.raises(ValueError, match="integer"):
        parse_api_max_clicks(True)


def test_link_display_state_all_labels():
    now = utc_now()
    assert link_display_state(Link(1, "a", "https://x", 302, now, deleted_at=now)) == "deleted"
    assert link_display_state(Link(1, "a", "https://x", 302, now, disabled_at=now)) == "disabled"
    assert link_display_state(
        Link(1, "a", "https://x", 302, now, expires_at=now - timedelta(seconds=1))
    ) == "expired"
    assert link_display_state(Link(1, "a", "https://x", 302, now, max_clicks=1, click_count=1)) == "capped"
    assert link_display_state(Link(1, "a", "https://x", 302, now)) == "active"
    assert not is_active_link(Link(1, "__pending_x", "https://x", 302, now))


def test_sqlite_storage_error_paths(tmp_path, monkeypatch):
    storage = SQLiteStorage(tmp_path / "err.db")
    storage.initialize()

    with pytest.raises(ValueError, match="unsupported lifecycle"):
        storage._touch_lifecycle("nope", "bad_column")  # noqa: SLF001

    link = storage.insert_link(
        short_code="gone",
        destination_url="https://example.com",
        redirect_status=302,
    )
    storage.mark_deleted("gone")
    with pytest.raises(CodeDeleted):
        storage.record_click(link.id)

    with pytest.raises(CodeNotFound):
        storage.get_link("missing")

    with pytest.raises(CodeNotFound):
        storage.set_expiry("missing", utc_now() + timedelta(days=1))


def test_sqlite_check_constraint_maps_to_storage_error(tmp_path):
    storage = SQLiteStorage(tmp_path / "int.db")
    storage.initialize()
    with pytest.raises(StorageError):
        storage.insert_link(
            short_code="bad",
            destination_url="https://b.com",
            redirect_status=999,
        )


def test_sqlite_save_health_result(tmp_path):
    storage = SQLiteStorage(tmp_path / "health.db")
    storage.initialize()
    link = storage.insert_link(
        short_code="h",
        destination_url="https://example.com",
        redirect_status=302,
    )
    from sniplink.models import HealthCheckResult

    storage.save_health_result(
        HealthCheckResult(
            link_id=link.id,
            checked_at=utc_now(),
            status_code=200,
            error=None,
            elapsed_ms=1.5,
            redirect_count=0,
        )
    )
