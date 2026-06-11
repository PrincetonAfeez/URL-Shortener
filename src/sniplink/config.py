"""Configuration loader.

The CLI, raw HTTP server, WSGI app, and Django settings all read from the same
``sniplink.toml`` file via :func:`load_config`. Each value can be overridden by
the matching ``SNIPLINK_*`` environment variable, which is what tests and CI
use to point at temporary databases without rewriting the TOML file.
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

# Repo-root sniplink.toml — searched at import time so both the CLI and the
# Django settings module find the same file when run from any working
# directory.
_THIS_FILE = Path(__file__).resolve()
DEFAULT_CONFIG_PATH = _THIS_FILE.parents[2] / "sniplink.toml"

DEFAULT_RESERVED_CODES = (
    "api",
    "admin",
    "dashboard",
    "static",
    "favicon.ico",
    "links",
)
DEFAULT_REDACT_KEYS = ("authorization", "x-api-key", "api_key", "secret")
DEFAULT_BASE_ALIASES = (
    # Both port-bearing and port-less variants of the dev hostnames count as
    # "this shortener" for self-reference detection. Without the port-less
    # entries a reverse proxy that strips ports could slip a self-shortened
    # link past validation. Users can add more entries in sniplink.toml.
    "http://127.0.0.1:8000",
    "http://localhost",
    "http://127.0.0.1",
)
DEFAULT_API_MAX_BODY_BYTES = 64 * 1024


@dataclass(frozen=True, slots=True)
class ApiConfig:
    max_body_bytes: int = DEFAULT_API_MAX_BODY_BYTES


@dataclass(frozen=True, slots=True)
class LoggingConfig:
    level: str = "INFO"
    format: str = "json"
    redact_keys: tuple[str, ...] = DEFAULT_REDACT_KEYS


@dataclass(frozen=True, slots=True)
class SniplinkConfig:
    database_path: Path = Path("sniplink.db")
    default_base_url: str = "http://localhost:8000"
    # Extra origins that count as "this shortener" for self-reference
    # detection. The dashboard is typically reachable at both
    # http://localhost:8000 and http://127.0.0.1:8000; without the second
    # entry a self-shortened link via the IP form would slip past validation.
    base_aliases: tuple[str, ...] = DEFAULT_BASE_ALIASES
    default_redirect_status: int = 302
    random_token_length: int = 7
    collision_retry_limit: int = 8
    max_destination_length: int = 2048
    max_request_path_bytes: int = 2048
    raw_http_recv_timeout: float = 5.0
    # Exact short codes blocked on redirect and auto-assignment (not prefixes).
    reserved_codes: tuple[str, ...] = DEFAULT_RESERVED_CODES
    api: ApiConfig = field(default_factory=ApiConfig)
    logging: LoggingConfig = field(default_factory=LoggingConfig)


def _read_toml(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    with path.open("rb") as fh:
        data = tomllib.load(fh)
    return data.get("sniplink", {}) or {}


def _resolve_db_path(raw: str, anchor: Path) -> Path:
    """Resolve ``raw`` against ``anchor`` so CLI and Django find the same DB.

    Relative paths in ``sniplink.toml`` are resolved against the repo root
    (the directory holding the TOML file). Absolute paths are used as-is.
    """

    candidate = Path(raw).expanduser()
    if candidate.is_absolute():
        return candidate
    return (anchor.parent / candidate).resolve()


def _coerce_tuple(value: Any, default: tuple[str, ...]) -> tuple[str, ...]:
    if value is None:
        return default
    if isinstance(value, (list, tuple)):
        return tuple(str(item) for item in value)
    raise TypeError(f"expected list/tuple, got {type(value).__name__}")


def load_config(
    database_path: str | None = None,
    *,
    config_path: Path | None = None,
) -> SniplinkConfig:
    """Resolve config from ``sniplink.toml``, env vars, then defaults.

    The precedence order is *argument* > *env var* > *TOML* > *dataclass
    default*. ``database_path`` keeps backwards compatibility with the CLI's
    ``--db`` flag.
    """

    anchor = config_path or DEFAULT_CONFIG_PATH
    raw = _read_toml(anchor)
    api_raw = raw.get("api", {}) or {}
    log_raw = raw.get("logging", {}) or {}

    resolved_db_raw = (
        database_path
        or os.environ.get("SNIPLINK_DB")
        or raw.get("database_path")
        or "sniplink.db"
    )
    resolved_db = _resolve_db_path(resolved_db_raw, anchor)
    base_url = (
        os.environ.get("SNIPLINK_BASE_URL")
        or raw.get("default_base_url")
        or "http://localhost:8000"
    )
    redirect_status = int(
        os.environ.get("SNIPLINK_REDIRECT_STATUS")
        or raw.get("default_redirect_status")
        or 302
    )
    retry_limit = int(
        os.environ.get("SNIPLINK_COLLISION_RETRIES")
        or raw.get("collision_retry_limit")
        or 8
    )
    api = ApiConfig(
        max_body_bytes=int(
            os.environ.get("SNIPLINK_API_MAX_BODY_BYTES")
            or api_raw.get("max_body_bytes")
            or DEFAULT_API_MAX_BODY_BYTES
        ),
    )
    logging_cfg = LoggingConfig(
        level=os.environ.get("SNIPLINK_LOG_LEVEL") or log_raw.get("level") or "INFO",
        format=os.environ.get("SNIPLINK_LOG_FORMAT") or log_raw.get("format") or "json",
        redact_keys=_coerce_tuple(log_raw.get("redact_keys"), DEFAULT_REDACT_KEYS),
    )

    return SniplinkConfig(
        database_path=resolved_db,
        default_base_url=base_url,
        base_aliases=_coerce_tuple(raw.get("base_aliases"), DEFAULT_BASE_ALIASES),
        default_redirect_status=redirect_status,
        random_token_length=int(raw.get("random_token_length") or 7),
        collision_retry_limit=retry_limit,
        max_destination_length=int(raw.get("max_destination_length") or 2048),
        max_request_path_bytes=int(raw.get("max_request_path_bytes") or 2048),
        raw_http_recv_timeout=float(raw.get("raw_http_recv_timeout") or 5.0),
        reserved_codes=_coerce_tuple(
            raw.get("reserved_codes") or raw.get("reserved_prefixes"),
            DEFAULT_RESERVED_CODES,
        ),
        api=api,
        logging=logging_cfg,
    )
