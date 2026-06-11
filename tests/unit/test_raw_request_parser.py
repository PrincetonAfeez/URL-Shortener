"""Tests for the raw request parser. """

import pytest

from sniplink.raw_http.request_parser import (
    BadRequest,
    UriTooLong,
    extract_code,
    parse_http_request,
)


def test_parse_http_request_extracts_request_line_path_query_and_headers():
    request = parse_http_request(
        b"GET /abc123?x=1 HTTP/1.1\r\nHost: localhost\r\nUser-Agent: curl\r\n\r\n"
    )

    assert request.method == "GET"
    assert request.path == "/abc123"
    assert request.query_string == "x=1"
    assert request.headers["host"] == "localhost"
    assert extract_code(request.path) == "abc123"


def test_parse_http_request_rejects_bad_request_line():
    with pytest.raises(BadRequest):
        parse_http_request(b"GET /missing-version\r\n\r\n")


def test_parse_http_request_rejects_empty_bytes():
    """Empty input has no request line — must be a clean 400, not a crash."""

    with pytest.raises(BadRequest):
        parse_http_request(b"")


def test_parse_http_request_rejects_whitespace_only_request_line():
    with pytest.raises(BadRequest):
        parse_http_request(b"   \r\nHost: localhost\r\n\r\n")


def test_parse_http_request_rejects_request_without_http_version_token():
    with pytest.raises(BadRequest):
        parse_http_request(b"GET /demo NOTHTTP\r\nHost: localhost\r\n\r\n")


def test_parse_http_request_rejects_oversized_request_target():
    """The 414 URI Too Long path — bug PR3 in the audit pass."""

    long_target = b"/" + b"a" * 4096
    request_line = b"GET " + long_target + b" HTTP/1.1\r\nHost: localhost\r\n\r\n"

    with pytest.raises(UriTooLong):
        parse_http_request(request_line, max_path_length=2048)


def test_parse_http_request_rejects_malformed_header_line():
    """Header line without a colon must be rejected, not silently dropped."""

    with pytest.raises(BadRequest):
        parse_http_request(
            b"GET /demo HTTP/1.1\r\nHost: localhost\r\nMalformedHeaderLine\r\n\r\n"
        )


def test_extract_code_single_segment_only():
    assert extract_code("/demo") == "demo"
    assert extract_code("/demo/") == "demo"
    assert extract_code("/") is None
    assert extract_code("/demo/extra") is None
