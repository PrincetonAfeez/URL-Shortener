"""Django redirect adapter parity (ADR 0003)."""

from __future__ import annotations

import pytest
from django.test import Client


@pytest.mark.parametrize("status_code", (301, 302, 307, 308))
@pytest.mark.usefixtures("_django_db_access")
def test_django_redirect_returns_location_and_cache_control(status_code):
    client = Client(HTTP_HOST="testserver")
    client.post(
        "/api/links",
        data=(
            f'{{"url":"https://example.com","alias":"r{status_code}",'
            f'"redirect_status":{status_code}}}'
        ),
        content_type="application/json",
    )

    response = client.get(f"/r{status_code}")
    assert response.status_code == status_code
    assert response["Location"] == "https://example.com/"
    assert response["Cache-Control"] == "no-store"
    assert response.content == b""


@pytest.mark.usefixtures("_django_db_access")
def test_django_head_redirect_does_not_increment_clicks():
    client = Client(HTTP_HOST="testserver")
    client.post(
        "/api/links",
        data='{"url":"https://example.com","alias":"head"}',
        content_type="application/json",
    )

    response = client.head("/head")
    assert response.status_code == 302
    assert response["Location"] == "https://example.com/"

    stats = client.get("/api/links/head/stats")
    assert stats.json()["click_count"] == 0


@pytest.mark.usefixtures("_django_db_access")
def test_django_redirect_returns_410_for_disabled_link():
    client = Client(HTTP_HOST="testserver")
    client.post(
        "/api/links",
        data='{"url":"https://example.com","alias":"gone"}',
        content_type="application/json",
    )
    client.post("/api/links/gone/disable")

    response = client.get("/gone")
    assert response.status_code == 410
