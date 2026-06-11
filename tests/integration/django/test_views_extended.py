"""Extended Django view coverage: HTMX errors, API expire, method guards."""

from __future__ import annotations

import json

import pytest
from django.test import Client, override_settings


def _csrf(client: Client) -> str:
    return client.get("/").cookies["csrftoken"].value


@pytest.mark.usefixtures("_django_db_access")
def test_dashboard_htmx_create_error_partial():
    client = Client(HTTP_HOST="testserver")
    csrf = _csrf(client)
    response = client.post(
        "/",
        data={"url": "javascript:alert(1)", "strategy": "base62"},
        HTTP_HX_REQUEST="true",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert response.status_code == 200
    assert b"error" in response.content.lower()


@pytest.mark.usefixtures("_django_db_access")
def test_disable_htmx_404_and_410():
    client = Client(HTTP_HOST="testserver")
    csrf = _csrf(client)
    missing = client.post(
        "/links/missing/disable",
        HTTP_HX_REQUEST="true",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert missing.status_code == 404

    create = client.post(
        "/",
        data={"url": "https://example.com", "alias": "gone", "strategy": "base62"},
        HTTP_HX_REQUEST="true",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert create.status_code == 201
    csrf = _csrf(client)
    client.post(
        "/links/gone/disable",
        HTTP_HX_REQUEST="true",
        HTTP_X_CSRFTOKEN=csrf,
    )
    again = client.post(
        "/links/gone/disable",
        HTTP_HX_REQUEST="true",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert again.status_code == 410


@pytest.mark.usefixtures("_django_db_access")
def test_delete_htmx_404():
    client = Client(HTTP_HOST="testserver")
    csrf = _csrf(client)
    response = client.post(
        "/links/nope/delete",
        HTTP_HX_REQUEST="true",
        HTTP_X_CSRFTOKEN=csrf,
    )
    assert response.status_code == 404


@pytest.mark.usefixtures("_django_db_access")
def test_stats_panel_requires_auth_when_not_htmx():
    client = Client(HTTP_HOST="testserver")
    with override_settings(SNIPLINK_API_KEY="secret"):
        denied = client.get("/links/any/stats")
        assert denied.status_code == 401
        allowed = client.get(
            "/links/any/stats",
            HTTP_AUTHORIZATION="Bearer secret",
        )
        assert allowed.status_code == 404


@pytest.mark.usefixtures("_django_db_access")
def test_api_expire_and_method_guards():
    client = Client(HTTP_HOST="testserver")
    created = client.post(
        "/api/links",
        data=json.dumps({"url": "https://example.com", "alias": "expapi"}),
        content_type="application/json",
    )
    assert created.status_code == 201

    wrong = client.get("/api/links/expapi/expire")
    assert wrong.status_code == 405

    expired = client.post(
        "/api/links/expapi/expire",
        data=json.dumps({"expires_at": "2020-01-01T00:00:00Z"}),
        content_type="application/json",
    )
    assert expired.status_code == 200

    detail_get = client.get("/api/links/expapi")
    assert detail_get.status_code == 410


@pytest.mark.usefixtures("_django_db_access")
def test_redirect_rejects_post():
    client = Client(HTTP_HOST="testserver")
    response = client.post("/demo")
    assert response.status_code == 405


@pytest.mark.usefixtures("_django_db_access")
def test_dashboard_rejects_put():
    client = Client(HTTP_HOST="testserver")
    response = client.put("/")
    assert response.status_code == 405
