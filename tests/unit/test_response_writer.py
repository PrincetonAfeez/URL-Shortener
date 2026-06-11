"""Tests for the response writer. """

from sniplink.raw_http.response_writer import build_response, redirect_response


def test_redirect_response_contains_protocol_headers():
    response = redirect_response(location="https://example.com", status_code=302)

    assert b"HTTP/1.1 302 Found\r\n" in response
    assert b"Location: https://example.com\r\n" in response
    assert b"Cache-Control: no-store\r\n" in response
    assert b"Content-Length: 0\r\n" in response


def test_head_response_has_no_body_but_keeps_content_length():
    response = build_response(404, body=b"not found", method="HEAD")

    assert response.endswith(b"\r\n\r\n")
    assert b"Content-Length: 9\r\n" in response
    assert b"not found" not in response
