"""Django ORM click-path proofs.

True thread fan-out against Django's SQLite backend hits ``database table is
locked`` — that is a Django/SQLite test-harness limitation, not a gap in
``DjangoStorage.record_click``. Thread concurrency is proven on
``SQLiteStorage`` in ``tests/concurrency/``; these tests prove the Django
adapter applies the same conditional UPDATE semantics sequentially.
"""

from __future__ import annotations

import pytest

from sniplink.core import SniplinkService
from sniplink.exceptions import CodeDisabled, CodeExpired
from links.storage_adapter import DjangoStorage


@pytest.mark.usefixtures("_django_db_access")
def test_django_click_counter_and_click_rows_stay_in_sync():
    service = SniplinkService(DjangoStorage())
    service.initialize()
    service.create_link("https://example.com", alias="djcounter")

    for _ in range(25):
        SniplinkService(DjangoStorage()).resolve("djcounter")

    final = service.storage.get_link("djcounter")
    assert final.click_count == 25
    assert service.storage.stats("djcounter")["recorded_clicks"] == 25


@pytest.mark.usefixtures("_django_db_access")
def test_django_max_clicks_gate():
    service = SniplinkService(DjangoStorage())
    service.initialize()
    service.create_link("https://example.com", alias="djcapped", max_clicks=3)

    outcomes = []
    for _ in range(8):
        try:
            SniplinkService(DjangoStorage()).resolve("djcapped")
            outcomes.append("ok")
        except CodeExpired:
            outcomes.append("expired")

    assert outcomes.count("ok") == 3
    assert outcomes.count("expired") == 5
    assert service.storage.get_link("djcapped").click_count == 3


@pytest.mark.usefixtures("_django_db_access")
def test_django_disabled_link_rejects_further_clicks():
    service = SniplinkService(DjangoStorage())
    service.initialize()
    service.create_link("https://example.com", alias="djoff")
    service.resolve("djoff")
    service.disable_link("djoff")
    before = service.storage.get_link("djoff").click_count

    for _ in range(6):
        with pytest.raises(CodeDisabled):
            SniplinkService(DjangoStorage()).resolve("djoff")

    assert service.storage.get_link("djoff").click_count == before
