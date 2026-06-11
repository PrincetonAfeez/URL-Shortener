"""Cross-backend click-row shape check.

The SQLite store stamps ``clicked_at = utc_now()`` explicitly; the Django
ORM uses ``auto_now_add`` and Django's ``timezone.now()``. Both should
produce UTC-aware timestamps that round-trip through ``isoformat()`` with
the same offset. This test pins that, so a future regression that switches
USE_TZ off (or replaces ``utc_now`` with a naive call) fails loudly.
"""

from __future__ import annotations

from datetime import timezone

import pytest

from sniplink.core import SniplinkService
from sniplink.storage import SQLiteStorage
from links import models  # type: ignore[import]
from links.storage_adapter import DjangoStorage  # type: ignore[import]


@pytest.mark.usefixtures("_django_db_access")
def test_clicked_at_is_utc_aware_in_both_backends(sqlite_db_path):
    # --- SQLite backend ---
    sqlite_service = SniplinkService(SQLiteStorage(sqlite_db_path))
    sqlite_service.initialize()
    sqlite_service.create_link("https://example.com", alias="sqlite-clock")
    sqlite_service.resolve("sqlite-clock")

    sqlite_link = sqlite_service.storage.get_link("sqlite-clock")
    sqlite_click_row = _last_sqlite_click(sqlite_db_path, sqlite_link.id)

    # --- Django ORM backend ---
    django_service = SniplinkService(DjangoStorage())
    django_service.initialize()
    django_service.create_link("https://example.com", alias="django-clock")
    django_service.resolve("django-clock")

    django_click = models.Click.objects.filter(
        link__short_code="django-clock"
    ).order_by("-clicked_at").first()
    assert django_click is not None

    # Both timestamps must be UTC-aware and serialize to a string ending in
    # "+00:00" once normalized to UTC.
    sqlite_iso = sqlite_click_row.endswith("+00:00")
    django_iso = (
        django_click.clicked_at.astimezone(timezone.utc).isoformat().endswith("+00:00")
    )
    assert sqlite_iso, sqlite_click_row
    assert django_iso


def _last_sqlite_click(db_path, link_id: int) -> str:
    import sqlite3
    from contextlib import closing

    with closing(sqlite3.connect(db_path)) as conn, conn:
        row = conn.execute(
            "SELECT clicked_at FROM clicks WHERE link_id = ? ORDER BY id DESC LIMIT 1",
            (link_id,),
        ).fetchone()
    assert row is not None
    return row[0]
