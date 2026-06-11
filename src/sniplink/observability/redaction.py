"""Credential redaction helpers used by the logger and the API request log.

The capstone deliberately keeps this module tiny: a fixed list of suspicious
key names (Authorization, X-API-Key, etc.) gets masked, and a token-shaped
string can be partially revealed for debugging without leaking the secret.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Any

DEFAULT_REDACTED_KEYS: tuple[str, ...] = (
    "authorization",
    "x-api-key",
    "api_key",
    "api-key",
    "secret",
    "password",
    "token",
)


def redact_secret(value: str | None) -> str | None:
    """Mask the middle of a credential, keeping the first/last 4 chars."""

    if value is None:
        return None
    if len(value) <= 8:
        return "***"
    return value[:4] + "..." + value[-4:]


def redact_mapping(
    payload: Mapping[str, Any],
    redact_keys: Iterable[str] = (),
) -> dict[str, Any]:
    """Return a copy of ``payload`` with sensitive values masked.

    Key comparison is case-insensitive. Nested mappings are walked
    recursively. Lists are walked element-wise (mapping members get the same
    treatment, others are passed through).
    """

    keys = {key.lower() for key in (redact_keys or DEFAULT_REDACTED_KEYS)}
    return {key: _redact_value(key, value, keys) for key, value in payload.items()}


def _redact_value(key: str, value: Any, keys: set[str]) -> Any:
    if key.lower() in keys:
        if isinstance(value, str):
            return redact_secret(value)
        return "***"
    if isinstance(value, Mapping):
        return redact_mapping(value, keys)
    if isinstance(value, list):
        return [_redact_value(key, item, keys) for item in value]
    return value
