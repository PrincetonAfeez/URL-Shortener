"""Tests for the raw socket redirect. """

import socket
import threading
import time

from sniplink.core import SniplinkService
from sniplink.raw_http import RawHTTPServer
from sniplink.storage import SQLiteStorage


def test_raw_socket_server_returns_redirect_headers(tmp_path):
    service = SniplinkService(SQLiteStorage(tmp_path / "test.db"))
    service.initialize()
    service.create_link("https://example.com", alias="demo")
    server = RawHTTPServer(service, host="127.0.0.1", port=0)
    ready = threading.Event()
    thread = threading.Thread(
        target=lambda: server.serve_once(ready=ready), daemon=True
    )
    thread.start()
    # The thread signals readiness after bind() + listen() — no busy-wait
    # on server.port. See bug #11 in the fourth-pass review.
    assert ready.wait(timeout=5), "raw HTTP server failed to bind in time"
    time.sleep(0.05)

    with socket.create_connection(("127.0.0.1", server.port), timeout=5) as client:
        client.sendall(b"GET /demo HTTP/1.1\r\nHost: localhost\r\n\r\n")
        response = client.recv(4096)

    thread.join(timeout=2)
    assert b"HTTP/1.1 302 Found\r\n" in response
    assert b"Location: https://example.com/\r\n" in response
    assert b"Content-Length: 0\r\n" in response
