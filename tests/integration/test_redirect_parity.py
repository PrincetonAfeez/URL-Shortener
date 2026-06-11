"""Adapter redirect parity tests (ADR 0003)."""

from __future__ import annotations

import socket
import threading
import time

import pytest

from sniplink.core import SniplinkService
from sniplink.raw_http import RawHTTPServer
from sniplink.storage import SQLiteStorage
from sniplink.wsgi_app import make_app

REDIRECT_STATUSES = (301, 302, 307, 308)


@pytest.mark.parametrize("status_code", REDIRECT_STATUSES)
def test_wsgi_redirect_status_and_cache_control(tmp_path, status_code):
    service = SniplinkService(SQLiteStorage(tmp_path / "wsgi.db"))
    service.initialize()
    service.create_link(
        "https://example.com",
        alias="code",
        redirect_status=status_code,
    )
    app = make_app(service)
    captured: dict = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    list(
        app(
            {"REQUEST_METHOD": "GET", "PATH_INFO": "/code", "HTTP_USER_AGENT": "pytest"},
            start_response,
        )
    )
    assert captured["status"].startswith(str(status_code))
    assert captured["headers"]["Location"] == "https://example.com/"
    assert captured["headers"]["Cache-Control"] == "no-store"


def test_wsgi_head_redirect_has_no_body(tmp_path):
    service = SniplinkService(SQLiteStorage(tmp_path / "head.db"))
    service.initialize()
    service.create_link("https://example.com", alias="head")
    app = make_app(service)
    captured: dict = {}

    def start_response(status, headers):
        captured["status"] = status

    body = list(
        app({"REQUEST_METHOD": "HEAD", "PATH_INFO": "/head"}, start_response)
    )
    assert captured["status"] == "302 Found"
    assert body == [b""]
    assert service.stats("head")["click_count"] == 0


def test_wsgi_returns_410_for_disabled_link(tmp_path):
    service = SniplinkService(SQLiteStorage(tmp_path / "gone.db"))
    service.initialize()
    service.create_link("https://example.com", alias="gone")
    service.disable_link("gone")
    app = make_app(service)
    captured: dict = {}

    def start_response(status, headers):
        captured["status"] = status

    list(app({"REQUEST_METHOD": "GET", "PATH_INFO": "/gone"}, start_response))
    assert captured["status"] == "410 Gone"


def test_raw_socket_returns_404_for_unknown_code(tmp_path):
    service = SniplinkService(SQLiteStorage(tmp_path / "raw.db"))
    service.initialize()
    server = RawHTTPServer(service, host="127.0.0.1", port=0)
    ready = threading.Event()
    thread = threading.Thread(
        target=lambda: server.serve_once(ready=ready), daemon=True
    )
    thread.start()
    assert ready.wait(timeout=5)
    time.sleep(0.05)

    with socket.create_connection(("127.0.0.1", server.port), timeout=5) as client:
        client.sendall(b"GET /missing HTTP/1.1\r\nHost: localhost\r\n\r\n")
        response = client.recv(4096)

    thread.join(timeout=2)
    assert b"HTTP/1.1 404" in response
