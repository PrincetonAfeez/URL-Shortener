"""Tests for HTMX CSRF enforcement on the dashboard form posts.

The dashboard's disable / delete endpoints are *not* @csrf_exempt — they
rely on the middleware + the ``hx-headers`` token injected by ``base.html``
(see ADR 0005). These tests pin that wiring so a regression that drops the
middleware or the template tag fails loudly.
"""

from __future__ import annotations

from django.test import Client


def _create_link(client: Client, alias: str) -> None:
    response = client.post(
        "/api/links",
        data=f'{{"url":"https://example.com","alias":"{alias}"}}',
        content_type="application/json",
    )
    assert response.status_code == 201


def test_dashboard_disable_without_csrf_token_is_rejected():
    enforced = Client(HTTP_HOST="testserver", enforce_csrf_checks=True)
    _create_link(enforced, "csrf-target")

    response = enforced.post("/links/csrf-target/disable")

    assert response.status_code == 403


def test_dashboard_disable_with_csrf_token_succeeds():
    enforced = Client(HTTP_HOST="testserver", enforce_csrf_checks=True)
    _create_link(enforced, "csrf-target")

    # Render the dashboard so the CSRF cookie + token land in the client jar.
    dashboard = enforced.get("/")
    assert dashboard.status_code == 200
    token = dashboard.cookies["csrftoken"].value

    response = enforced.post(
        "/links/csrf-target/disable",
        HTTP_X_CSRFTOKEN=token,
    )

    assert response.status_code in {200, 302}
