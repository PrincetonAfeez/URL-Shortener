"""Tests for the WSGI errors. """


from sniplink.core import SniplinkService
from sniplink.storage import SQLiteStorage
from sniplink.wsgi_app import make_app


def test_wsgi_reserved_prefix_returns_404(tmp_path):
    service = SniplinkService(
        SQLiteStorage(tmp_path / "wsgi.db"),
        reserved_codes=("api",),
    )
    service.initialize()
    service.create_link("https://example.com", alias="real")
    app = make_app(service, reserved_codes=("api",))
    captured: dict = {}

    def start_response(status, headers):
        captured["status"] = status

    body = list(
        app(
            {"REQUEST_METHOD": "GET", "PATH_INFO": "/api"},
            start_response,
        )
    )
    assert captured["status"] == "404 Not Found"
    assert body == [b"reserved short code\n"]


def test_wsgi_method_not_allowed(tmp_path):
    service = SniplinkService(SQLiteStorage(tmp_path / "wsgi.db"))
    service.initialize()
    app = make_app(service)
    captured: dict = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    list(app({"REQUEST_METHOD": "POST", "PATH_INFO": "/x"}, start_response))
    assert captured["status"] == "405 Method Not Allowed"
    assert captured["headers"]["Allow"] == "GET, HEAD"
    assert captured.get("headers", {}).get("Allow") == "GET, HEAD"


def test_wsgi_rejects_overlong_path(tmp_path):
    service = SniplinkService(SQLiteStorage(tmp_path / "wsgi.db"))
    service.initialize()
    app = make_app(service, max_path_length=16)
    captured: dict = {}

    def start_response(status, headers):
        captured["status"] = status

    long_path = "/" + ("a" * 32)
    list(app({"REQUEST_METHOD": "GET", "PATH_INFO": long_path}, start_response))
    assert captured["status"] == "414 URI Too Long"
