"""Tests for the 404.html / 410.html templates served by redirect_link."""

from __future__ import annotations

from django.test import Client


def test_unknown_code_renders_404_template():
    client = Client(HTTP_HOST="testserver")

    response = client.get("/never-existed")

    assert response.status_code == 404
    assert b"404 Not Found" in response.content
    assert b"never-existed" in response.content


def test_deleted_code_renders_410_template():
    client = Client(HTTP_HOST="testserver")
    create = client.post(
        "/api/links",
        data='{"url":"https://example.com","alias":"gone-soon"}',
        content_type="application/json",
    )
    assert create.status_code == 201

    delete = client.delete("/api/links/gone-soon")
    assert delete.status_code == 204

    response = client.get("/gone-soon")

    assert response.status_code == 410
    assert b"410 Gone" in response.content
    assert b"gone-soon" in response.content
