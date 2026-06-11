"""HTMX dashboard create flow."""

from __future__ import annotations

import pytest
from django.test import Client


@pytest.mark.usefixtures("_django_db_access")
def test_dashboard_htmx_create_returns_success_partial():
    client = Client(HTTP_HOST="testserver")
    page = client.get("/")
    csrf = page.cookies["csrftoken"].value

    response = client.post(
        "/",
        data={
            "url": "https://example.com",
            "alias": "htmx",
            "strategy": "base62",
            "redirect_status": "302",
        },
        HTTP_HX_REQUEST="true",
        HTTP_X_CSRFTOKEN=csrf,
    )

    assert response.status_code == 201
    assert b"htmx" in response.content
    assert b"https://example.com" in response.content


@pytest.mark.usefixtures("_django_db_access")
def test_api_key_accepts_authorization_bearer_header():
    from django.test import override_settings

    client = Client(HTTP_HOST="testserver")
    with override_settings(SNIPLINK_API_KEY="secret"):
        denied = client.post(
            "/api/links",
            data='{"url":"https://example.com"}',
            content_type="application/json",
        )
        assert denied.status_code == 401

        allowed = client.post(
            "/api/links",
            data='{"url":"https://example.com","alias":"bearer"}',
            content_type="application/json",
            HTTP_AUTHORIZATION="Bearer secret",
        )
        assert allowed.status_code == 201
