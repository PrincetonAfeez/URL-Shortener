"""Raw HTTP server edge paths: reserved codes, recv timeout, client errors."""

from __future__ import annotations

import socket
import threading
import time
import pytest

from sniplink.core import SniplinkService
from sniplink.raw_http import RawHTTPServer
from sniplink.storage import SQLiteStorage


def _server(tmp_path, **kwargs) -> tuple[RawHTTPServer, SniplinkService]:
    service = SniplinkService(SQLiteStorage(tmp_path / "raw-full.db"))
    service.initialize()
    return RawHTTPServer(service, host="127.0.0.1", port=0, **kwargs), service


def test_raw_server_reserved_code_short_circuit(tmp_path):
    server, service = _server(tmp_path, reserved_codes=("admin",))
    service.create_link("https://example.com", alias="admin")
    raw = b"GET /admin HTTP/1.1\r\nHost: localhost\r\n\r\n"
    response = server.handle_request_bytes(raw)
    assert b"404" in response
    assert b"reserved" in response


def test_raw_server_empty_request_returns_400(tmp_path):
    server, _ = _server(tmp_path)
    response = server.handle_request_bytes(b"")
    assert b"400" in response


def test_raw_server_serve_forever_survives_client_exception(tmp_path, monkeypatch):
    server, service = _server(tmp_path)
    service.create_link("https://example.com", alias="ok")

    def bad_recv(_client):
        raise OSError("boom")

    monkeypatch.setattr(server, "_recv_headers", bad_recv)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    time.sleep(0.05)
    try:
        with socket.create_connection(("127.0.0.1", server.port), timeout=2) as client:
            client.sendall(b"GET /ok HTTP/1.1\r\nHost: localhost\r\n\r\n")
            client.recv(1024)
    except OSError:
        pass
    server.shutdown()
    thread.join(timeout=3)
    assert not thread.is_alive()


def test_raw_server_shutdown_when_not_started(tmp_path):
    server, _ = _server(tmp_path)
    server.shutdown()


def test_raw_server_recv_timeout_in_serve_once(tmp_path, monkeypatch):
    server, service = _server(tmp_path, recv_timeout=0.01)
    service.create_link("https://example.com", alias="slow")

    class TimeoutClient:
        def settimeout(self, _t):
            return None

        def recv(self, _n: int) -> bytes:
            time.sleep(0.05)
            raise TimeoutError("timed out")

        def sendall(self, _data: bytes) -> None:
            return None

        def __enter__(self):
            return self

        def __exit__(self, *args):
            return False

    monkeypatch.setattr(
        "sniplink.raw_http.server.socket.socket.accept",
        lambda self: (TimeoutClient(), ("127.0.0.1", 12345)),
    )
    ready = threading.Event()
    thread = threading.Thread(
        target=lambda: server.serve_once(ready=ready),
        daemon=True,
    )
    thread.start()
    assert ready.wait(timeout=3)
    thread.join(timeout=3)
    assert not thread.is_alive()


def test_raw_server_missing_short_code_path(tmp_path):
    server, _ = _server(tmp_path)
    raw = b"GET / HTTP/1.1\r\nHost: localhost\r\n\r\n"
    response = server.handle_request_bytes(raw)
    assert b"short code required" in response
