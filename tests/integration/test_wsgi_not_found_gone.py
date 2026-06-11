"""WSGI 404/410 branches and HEAD body omission."""

from sniplink.core import SniplinkService
from sniplink.storage import SQLiteStorage
from sniplink.wsgi_app import make_app


def _run(app, environ):
    captured: dict = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    body = list(app(environ, start_response))
    return captured, body


def test_wsgi_not_found(tmp_path):
    service = SniplinkService(SQLiteStorage(tmp_path / "wsgi.db"))
    service.initialize()
    app = make_app(service)
    captured, body = _run(app, {"REQUEST_METHOD": "GET", "PATH_INFO": "/missing"})
    assert captured["status"] == "404 Not Found"
    assert body == [b"short code not found\n"]


def test_wsgi_gone_for_disabled_link(tmp_path):
    service = SniplinkService(SQLiteStorage(tmp_path / "wsgi.db"))
    service.initialize()
    service.create_link("https://example.com", alias="gone")
    service.disable_link("gone")
    app = make_app(service)
    captured, body = _run(app, {"REQUEST_METHOD": "GET", "PATH_INFO": "/gone"})
    assert captured["status"] == "410 Gone"
    assert body == [b"short code is gone\n"]


def test_wsgi_short_code_required(tmp_path):
    service = SniplinkService(SQLiteStorage(tmp_path / "wsgi.db"))
    service.initialize()
    app = make_app(service)
    captured, body = _run(app, {"REQUEST_METHOD": "GET", "PATH_INFO": "/"})
    assert captured["status"] == "404 Not Found"
    assert body == [b"short code required\n"]


def test_wsgi_head_returns_empty_body(tmp_path):
    service = SniplinkService(SQLiteStorage(tmp_path / "wsgi.db"))
    service.initialize()
    service.create_link("https://example.com", alias="head")
    app = make_app(service)
    captured, body = _run(
        app,
        {"REQUEST_METHOD": "HEAD", "PATH_INFO": "/head"},
    )
    assert captured["status"].startswith("302")
    assert body == [b""]
