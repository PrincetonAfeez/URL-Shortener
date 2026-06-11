"""Tests for the path too long. """

from sniplink.raw_http.request_parser import path_too_long


def test_path_too_long_respects_limit():
    assert not path_too_long("/demo", max_path_length=32)
    assert path_too_long("/" + ("x" * 40), max_path_length=32)
