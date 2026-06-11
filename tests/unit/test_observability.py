"""Tests for the JSON logger and the credential-redaction helpers."""

from __future__ import annotations

import io
import json
import logging

import pytest

from sniplink.observability import (
    JSONFormatter,
    configure_logging,
    log_redirect_decision,
    redact_mapping,
    redact_secret,
)


def _capture_log(level: str = "INFO") -> tuple[logging.Logger, io.StringIO]:
    buffer = io.StringIO()
    handler = logging.StreamHandler(buffer)
    handler.setFormatter(JSONFormatter(redact_keys=["authorization", "x-api-key"]))
    logger = logging.getLogger(f"sniplink.test.{id(buffer)}")
    logger.handlers = [handler]
    logger.setLevel(level)
    logger.propagate = False
    return logger, buffer


def test_json_formatter_emits_valid_json_object():
    logger, buffer = _capture_log()
    logger.info("hello world", extra={"safe": "value"})

    record = json.loads(buffer.getvalue().strip())
    assert record["level"] == "INFO"
    assert record["message"] == "hello world"
    assert record["extra"] == {"safe": "value"}
    assert "timestamp" in record


def test_json_formatter_masks_authorization_in_extra():
    logger, buffer = _capture_log()
    logger.info(
        "auth_event",
        extra={"authorization": "Bearer abcdefghijklmnop", "safe": "ok"},
    )

    record = json.loads(buffer.getvalue().strip())
    assert record["extra"]["authorization"] == "Bear...mnop"
    assert record["extra"]["safe"] == "ok"


def test_json_formatter_includes_exception_when_present():
    logger, buffer = _capture_log()
    try:
        raise ValueError("boom")
    except ValueError:
        logger.exception("failed")

    record = json.loads(buffer.getvalue().strip())
    assert "ValueError" in record["exception"]


def test_redact_secret_masks_middle_keeps_ends():
    assert redact_secret("Bearer abcdefghijklmnop") == "Bear...mnop"
    assert redact_secret("short") == "***"
    assert redact_secret(None) is None


def test_redact_mapping_walks_nested_structures():
    payload = {
        "Authorization": "Bearer abcdefghijklmnop",
        "nested": {"api_key": "abcdefghijklmnop", "safe": 1},
        "list": [{"secret": "abcdefghijklmnop"}, "ok"],
    }
    out = redact_mapping(payload)

    assert out["Authorization"].endswith("mnop")
    assert out["nested"]["api_key"].endswith("mnop")
    assert out["nested"]["safe"] == 1
    assert out["list"][0]["secret"].endswith("mnop")
    assert out["list"][1] == "ok"


def test_configure_logging_replaces_existing_handlers():
    configure_logging("DEBUG", format="json", redact_keys=["authorization"])
    before = list(logging.getLogger().handlers)
    configure_logging("DEBUG", format="plain")
    after = list(logging.getLogger().handlers)

    assert len(before) == 1
    assert len(after) == 1
    assert before[0] is not after[0]


def test_log_redirect_decision_emits_structured_extra(caplog: pytest.LogCaptureFixture):
    with caplog.at_level(logging.INFO, logger="sniplink.redirect"):
        log_redirect_decision(
            "raw_http",
            short_code="abc123",
            status_code=302,
            destination_url="https://example.com/",
            lookup_ms=12.3456,
            result="found",
        )

    record = caplog.records[-1]
    assert record.message == "redirect_served"
    assert record.adapter == "raw_http"
    assert record.short_code == "abc123"
    assert record.status_code == 302
    assert record.destination_url == "https://example.com/"
    assert record.lookup_ms == 12.346
    assert record.result == "found"
