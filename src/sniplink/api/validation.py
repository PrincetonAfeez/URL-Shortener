"""Validation for the API."""

from __future__ import annotations

from typing import Any


def parse_api_max_clicks(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"max_clicks: expected an integer, got {value!r}")
    if value < 1:
        raise ValueError("max_clicks: must be at least 1 when set")
    return value


def parse_api_redirect_status(value: Any) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"redirect_status: expected an integer, got {value!r}")
    return value


def parse_api_metadata(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("metadata: expected a JSON object")
    return value
