"""Tests for the API body-size cap (HTTP 413 + JSON envelope)."""

from __future__ import annotations

import json

from django.conf import settings
from django.test import Client


def test_api_create_rejects_body_larger_than_cap():
    cap = settings.SNIPLINK_API_MAX_BODY_BYTES
    # Build a JSON payload whose serialized length exceeds the cap.
    huge_metadata = {"filler": "x" * (cap + 1024)}
    payload = json.dumps({"url": "https://example.com", "metadata": huge_metadata})
    assert len(payload.encode("utf-8")) > cap

    client = Client(HTTP_HOST="testserver")
    response = client.post("/api/links", data=payload, content_type="application/json")

    assert response.status_code == 413
    body = response.json()
    assert body == {
        "error": {
            "type": "PayloadTooLarge",
            "message": "request body exceeds configured limit",
        }
    }


def test_api_create_accepts_body_just_under_cap():
    cap = settings.SNIPLINK_API_MAX_BODY_BYTES
    # Pad the description so we land near (but under) the cap.
    filler_bytes = max(0, cap - 256)  # 256-byte runway for surrounding JSON
    payload = json.dumps(
        {
            "url": "https://example.com",
            "alias": "ok",
            "metadata": {"filler": "x" * filler_bytes},
        }
    )
    assert len(payload.encode("utf-8")) <= cap

    client = Client(HTTP_HOST="testserver")
    response = client.post("/api/links", data=payload, content_type="application/json")

    assert response.status_code == 201
