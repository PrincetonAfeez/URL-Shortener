"""Tests for the reserved-prefix gate in ``validate_alias``."""

from __future__ import annotations

import pytest

from sniplink.core.validation import (
    DEFAULT_RESERVED_CODES,
    normalize_destination_url,
    validate_alias,
)
from sniplink.exceptions import InvalidAlias, InvalidDestinationURL


@pytest.mark.parametrize("reserved", sorted(DEFAULT_RESERVED_CODES))
def test_validate_alias_rejects_each_default_reserved_code(reserved: str):
    with pytest.raises(InvalidAlias):
        validate_alias(reserved)


def test_validate_alias_accepts_custom_reserved_list_and_ignores_defaults():
    # The caller passes their own list — the defaults no longer apply.
    assert validate_alias("api", reserved_codes={"custom"}) == "api"
    with pytest.raises(InvalidAlias):
        validate_alias("custom", reserved_codes={"custom"})


def test_validate_alias_rejects_pending_prefix():
    with pytest.raises(InvalidAlias):
        validate_alias("__pending_anything")


def test_validate_alias_rejects_malformed_characters():
    with pytest.raises(InvalidAlias):
        validate_alias("has space")
    with pytest.raises(InvalidAlias):
        validate_alias("with!bang")
    with pytest.raises(InvalidAlias):
        validate_alias("contains/slash")


def test_normalize_destination_url_rejects_unsafe_schemes():
    with pytest.raises(InvalidDestinationURL):
        normalize_destination_url("javascript:alert(1)")
    with pytest.raises(InvalidDestinationURL):
        normalize_destination_url("data:text/html,<script>")
    with pytest.raises(InvalidDestinationURL):
        normalize_destination_url("file:///etc/passwd")


def test_normalize_destination_url_rejects_self_reference_via_any_alias():
    aliases = ["http://localhost:8000", "http://127.0.0.1:8000"]
    with pytest.raises(InvalidDestinationURL):
        normalize_destination_url("http://127.0.0.1:8000/abc", base_urls=aliases)
    with pytest.raises(InvalidDestinationURL):
        normalize_destination_url("http://localhost:8000/xyz", base_urls=aliases)
