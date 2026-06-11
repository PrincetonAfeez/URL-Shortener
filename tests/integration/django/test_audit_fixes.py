"""Regression tests for the audit-fix batch."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest
from django.test import Client, override_settings


@pytest.mark.usefixtures("_django_db_access")
def test_api_disable_and_expire_endpoints():
    client = Client(HTTP_HOST="testserver")
    created = client.post(
        "/api/links",
        data='{"url":"https://example.com","alias":"lifecycle"}',
        content_type="application/json",
    )
    assert created.status_code == 201

    disabled = client.post("/api/links/lifecycle/disable")
    assert disabled.status_code == 200
    assert disabled.json()["disabled_at"] is not None

    expired = client.post(
        "/api/links/lifecycle/expire",
        data="{}",
        content_type="application/json",
    )
    assert expired.status_code == 200
    assert expired.json()["expires_at"] is not None


@pytest.mark.usefixtures("_django_db_access")
def test_api_detail_returns_410_for_disabled_link():
    client = Client(HTTP_HOST="testserver")
    client.post(
        "/api/links",
        data='{"url":"https://example.com","alias":"off"}',
        content_type="application/json",
    )
    client.post("/api/links/off/disable")

    detail = client.get("/api/links/off")
    assert detail.status_code == 410


@pytest.mark.usefixtures("_django_db_access")
def test_reserved_code_redirect_returns_404():
    client = Client(HTTP_HOST="testserver")
    response = client.get("/api")
    assert response.status_code == 404


@pytest.mark.usefixtures("_django_db_access")
@override_settings(SNIPLINK_API_KEY="secret")
def test_api_key_required_when_configured():
    client = Client(HTTP_HOST="testserver")
    denied = client.post(
        "/api/links",
        data='{"url":"https://example.com"}',
        content_type="application/json",
    )
    assert denied.status_code == 401

    allowed = client.post(
        "/api/links",
        data='{"url":"https://example.com","alias":"authed"}',
        content_type="application/json",
        HTTP_X_API_KEY="secret",
    )
    assert allowed.status_code == 201


@pytest.mark.usefixtures("_django_db_access")
def test_stats_panel_returns_410_for_disabled_link():
    client = Client(HTTP_HOST="testserver")
    client.post(
        "/api/links",
        data='{"url":"https://example.com","alias":"nostat"}',
        content_type="application/json",
    )
    client.post("/api/links/nostat/disable")

    response = client.get("/links/nostat/stats")
    assert response.status_code == 410


@pytest.mark.usefixtures("_django_db_access")
def test_api_disable_on_gone_link_returns_410():
    client = Client(HTTP_HOST="testserver")
    client.post(
        "/api/links",
        data='{"url":"https://example.com","alias":"twice"}',
        content_type="application/json",
    )
    client.post("/api/links/twice/disable")

    again = client.post("/api/links/twice/disable")
    assert again.status_code == 410


@pytest.mark.usefixtures("_django_db_access")
def test_api_stats_returns_410_for_disabled_link():
    client = Client(HTTP_HOST="testserver")
    client.post(
        "/api/links",
        data='{"url":"https://example.com","alias":"nostats"}',
        content_type="application/json",
    )
    client.post("/api/links/nostats/disable")

    response = client.get("/api/links/nostats/stats")
    assert response.status_code == 410


@pytest.mark.usefixtures("_django_db_access")
def test_api_rejects_bad_max_clicks_and_metadata():
    client = Client(HTTP_HOST="testserver")
    for payload in (
        '{"url":"https://example.com","max_clicks":-1}',
        '{"url":"https://example.com","max_clicks":0}',
    ):
        bad_clicks = client.post(
            "/api/links",
            data=payload,
            content_type="application/json",
        )
        assert bad_clicks.status_code == 400

    bad_meta = client.post(
        "/api/links",
        data='{"url":"https://example.com","metadata":[]}',
        content_type="application/json",
    )
    assert bad_meta.status_code == 400


def test_django_models_use_canonical_table_names():
    from links import models

    assert models.Link._meta.db_table == "links"
    assert models.Click._meta.db_table == "clicks"
    assert models.HealthCheckResult._meta.db_table == "health_check_results"


def test_cli_writes_canonical_links_table(tmp_path):
    db_path = tmp_path / "shared.db"
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(["src", "web", env.get("PYTHONPATH", "")])
    repo = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))

    subprocess.run(
        [sys.executable, "-m", "sniplink", "--db", str(db_path), "init-db"],
        check=True,
        cwd=repo,
        env=env,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "sniplink",
            "--db",
            str(db_path),
            "create",
            "https://example.com",
            "--alias",
            "shared",
        ],
        check=True,
        cwd=repo,
        env=env,
    )

    import sqlite3

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "links" in tables
        assert "links_link" not in tables
        (code,) = conn.execute("SELECT short_code FROM links").fetchone()
        assert code == "shared"
