"""Tests for the raw HTTP server. """

from sniplink.core import SniplinkService
from sniplink.raw_http import RawHTTPServer
from sniplink.storage import SQLiteStorage


def test_raw_server_rejects_overlong_path(tmp_path):
    service = SniplinkService(SQLiteStorage(tmp_path / "raw.db"))
    service.initialize()
    server = RawHTTPServer(service, max_path_length=32)
    long_target = "/" + ("a" * 40)
    raw = f"GET {long_target} HTTP/1.1\r\nHost: localhost\r\n\r\n".encode()
    response = server.handle_request_bytes(raw)
    assert b"414" in response


def test_raw_server_rejects_post(tmp_path):
    service = SniplinkService(SQLiteStorage(tmp_path / "raw.db"))
    service.initialize()
    server = RawHTTPServer(service)
    raw = b"POST /demo HTTP/1.1\r\nHost: localhost\r\n\r\n"
    response = server.handle_request_bytes(raw)
    assert b"405" in response
    assert b"Allow: GET, HEAD" in response
