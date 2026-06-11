"""Tests for the WSGI redirect. """

from sniplink.core import SniplinkService
from sniplink.storage import SQLiteStorage
from sniplink.wsgi_app import make_app


def test_wsgi_redirect_uses_start_response_and_location(tmp_path):
    service = SniplinkService(SQLiteStorage(tmp_path / "test.db"))
    service.initialize()
    service.create_link("https://example.com", alias="demo")
    app = make_app(service)
    captured = {}

    def start_response(status, headers):
        captured["status"] = status
        captured["headers"] = dict(headers)

    body = list(
        app(
            {
                "REQUEST_METHOD": "GET",
                "PATH_INFO": "/demo",
                "QUERY_STRING": "",
                "HTTP_USER_AGENT": "pytest",
            },
            start_response,
        )
    )

    assert captured["status"] == "302 Found"
    assert captured["headers"]["Location"] == "https://example.com/"
    assert body == [b""]
