"""Extended coverage for :class:`sniplink.raw_http.server.RawHTTPServer`."""

from __future__ import annotations

import socket
import threading
import time

import pytest

from sniplink.core import SniplinkService
from sniplink.exceptions import StorageError
from sniplink.raw_http import RawHTTPServer
from sniplink.storage import SQLiteStorage


def _server(tmp_path) -> tuple[RawHTTPServer, SniplinkService]:
    service = SniplinkService(SQLiteStorage(tmp_path / "raw.db"))
    service.initialize()
    return RawHTTPServer(service, host="127.0.0.1", port=0), service


def test_raw_server_head_does_not_record_click(tmp_path):
    server, service = _server(tmp_path)
    service.create_link("https://example.com", alias="head")
    raw = b"HEAD /head HTTP/1.1\r\nHost: localhost\r\n\r\n"
    response = server.handle_request_bytes(raw)
    assert b"HTTP/1.1 302" in response
    assert b"\r\n\r\n" in response
    body = response.split(b"\r\n\r\n", 1)[1]
    assert body == b""
    assert service.stats("head")["click_count"] == 0


def test_raw_server_returns_410_for_disabled_link(tmp_path):
    server, service = _server(tmp_path)
    service.create_link("https://example.com", alias="gone")
    service.disable_link("gone")
    raw = b"GET /gone HTTP/1.1\r\nHost: localhost\r\n\r\n"
    response = server.handle_request_bytes(raw)
    assert b"410" in response


def test_raw_server_returns_404_for_missing_code(tmp_path):
    server, _ = _server(tmp_path)
    raw = b"GET /missing HTTP/1.1\r\nHost: localhost\r\n\r\n"
    response = server.handle_request_bytes(raw)
    assert b"404" in response


def test_raw_server_returns_400_for_malformed_request(tmp_path):
    server, _ = _server(tmp_path)
    response = server.handle_request_bytes(b"NOT HTTP\r\n\r\n")
    assert b"400" in response


def test_raw_server_returns_500_for_unexpected_service_error(tmp_path, monkeypatch):
    server, service = _server(tmp_path)
    service.create_link("https://example.com", alias="boom")

    def boom(*args, **kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr(service, "resolve", boom)
    server.service = service
    raw = b"GET /boom HTTP/1.1\r\nHost: localhost\r\n\r\n"
    response = server.handle_request_bytes(raw)
    assert b"500" in response


def test_raw_server_maps_sniplink_error_to_500(tmp_path, monkeypatch):
    server, service = _server(tmp_path)
    service.create_link("https://example.com", alias="store")

    def fail(*args, **kwargs):
        raise StorageError("db down")

    monkeypatch.setattr(service, "resolve", fail)
    server.service = service
    raw = b"GET /store HTTP/1.1\r\nHost: localhost\r\n\r\n"
    response = server.handle_request_bytes(raw)
    assert b"500" in response


def test_raw_server_serve_once_accepts_connection(tmp_path):
    server, service = _server(tmp_path)
    service.create_link("https://example.com", alias="once")
    ready = threading.Event()
    thread = threading.Thread(
        target=lambda: server.serve_once(ready=ready), daemon=True
    )
    thread.start()
    assert ready.wait(timeout=3)
    time.sleep(0.05)
    with socket.create_connection(("127.0.0.1", server.port), timeout=3) as client:
        client.sendall(b"GET /once HTTP/1.1\r\nHost: localhost\r\n\r\n")
        response = client.recv(4096)
    thread.join(timeout=3)
    assert b"302" in response


def test_raw_server_shutdown_unblocks_serve_forever(tmp_path):
    server, _ = _server(tmp_path)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.05)
    server.shutdown()
    thread.join(timeout=3)
    assert not thread.is_alive()
