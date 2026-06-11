"""Service-level proof that ``reserved_prefixes`` is threaded into ``validate_alias``.

``tests/unit/test_validation_reserved.py`` exercises ``validate_alias``
directly. This test pins the wiring one level up: a regression that drops
``reserved_codes=self.reserved_prefixes`` from
``SniplinkService.create_link`` would still pass the unit suite, but would
fail this test.
"""

from __future__ import annotations

import pytest

from sniplink.core import SniplinkService
from sniplink.exceptions import InvalidAlias
from sniplink.storage import SQLiteStorage


def test_service_rejects_alias_in_configured_reserved_prefixes(sqlite_db_path):
    service = SniplinkService(
        SQLiteStorage(sqlite_db_path),
        reserved_codes=("custom-reserved",),
    )
    service.initialize()

    with pytest.raises(InvalidAlias):
        service.create_link("https://example.com", alias="custom-reserved")


def test_service_with_explicit_empty_list_allows_any_alias(sqlite_db_path):
    """Explicit empty ``reserved_prefixes`` means "no reservations" — useful
    for tests that want to use names like ``api`` for their own reasons."""

    service = SniplinkService(
        SQLiteStorage(sqlite_db_path),
        reserved_codes=(),
    )
    service.initialize()

    link = service.create_link("https://example.com", alias="api")
    assert link.short_code == "api"
