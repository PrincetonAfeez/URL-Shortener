"""Django JSON API behavior — status codes, conflict, delete, stats."""

from __future__ import annotations

from django.test import Client


def test_django_api_create_conflict_stats_and_delete():
    client = Client(HTTP_HOST="testserver")

    response = client.post(
        "/api/links",
        data='{"url":"https://example.com","alias":"demo"}',
        content_type="application/json",
    )
    assert response.status_code == 201
    assert response["Location"].endswith("/demo")

    conflict = client.post(
        "/api/links",
        data='{"url":"https://example.org","alias":"demo"}',
        content_type="application/json",
    )
    assert conflict.status_code == 409

    stats = client.get("/api/links/demo/stats")
    assert stats.status_code == 200
    assert stats.json()["short_code"] == "demo"

    deleted = client.delete("/api/links/demo")
    assert deleted.status_code == 204
