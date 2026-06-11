"""Tests for the API validation. """

from __future__ import annotations

import pytest

from sniplink.api.validation import (
    parse_api_max_clicks,
    parse_api_metadata,
    parse_api_redirect_status,
)


def test_parse_api_max_clicks_accepts_valid_integer():
    assert parse_api_max_clicks(5) == 5
    assert parse_api_max_clicks(None) is None


def test_parse_api_max_clicks_rejects_invalid_values():
    with pytest.raises(ValueError, match="at least 1"):
        parse_api_max_clicks(0)
    with pytest.raises(ValueError, match="at least 1"):
        parse_api_max_clicks(-1)
    with pytest.raises(ValueError, match="integer"):
        parse_api_max_clicks("3")


def test_parse_api_redirect_status_rejects_invalid_values():
    assert parse_api_redirect_status(302) == 302
    assert parse_api_redirect_status(None) is None
    with pytest.raises(ValueError, match="integer"):
        parse_api_redirect_status({})
    with pytest.raises(ValueError, match="integer"):
        parse_api_redirect_status(True)


def test_parse_api_metadata_requires_object():
    assert parse_api_metadata(None) == {}
    assert parse_api_metadata({"k": 1}) == {"k": 1}
    with pytest.raises(ValueError, match="JSON object"):
        parse_api_metadata(["not", "a", "dict"])
