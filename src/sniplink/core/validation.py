""" Validation functions. """

from __future__ import annotations

import re
from collections.abc import Iterable
from datetime import datetime
from urllib.parse import SplitResult, urlsplit, urlunsplit

from sniplink.config import DEFAULT_RESERVED_CODES
from sniplink.exceptions import InvalidAlias, InvalidDestinationURL

ALLOWED_SCHEMES = {"http", "https"}
MAX_DESTINATION_LENGTH = 2048
ALIAS_RE = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
# Fallback when callers omit ``reserved_codes`` (see ``config.DEFAULT_RESERVED_CODES``).
_FALLBACK_RESERVED = frozenset(code.lower() for code in DEFAULT_RESERVED_CODES)


def normalize_destination_url(
    url: str,
    *,
    base_urls: Iterable[str] | None = None,
    max_length: int = MAX_DESTINATION_LENGTH,
) -> str:
    if not url or not url.strip():
        raise InvalidDestinationURL("destination URL is required")
    url = url.strip()
    if len(url) > max_length:
        raise InvalidDestinationURL("destination URL is too long")

    parsed = urlsplit(url)
    if parsed.scheme.lower() not in ALLOWED_SCHEMES:
        raise InvalidDestinationURL("only http and https URLs are allowed")
    if not parsed.netloc:
        raise InvalidDestinationURL("destination URL must include a host")

    normalized = _normalize_split(parsed)
    _reject_self_reference(normalized, base_urls or [])
    # Drop fragment (intentional — shorteners don't preserve client-side
    # anchors) and userinfo (no leaking creds through a public redirect).
    return urlunsplit(normalized)


def validate_max_clicks(max_clicks: int | None) -> int | None:
    """Return ``max_clicks`` when valid, or raise ``ValueError``."""

    if max_clicks is not None and max_clicks < 1:
        raise ValueError("max_clicks: must be at least 1 when set")
    return max_clicks


def validate_alias(alias: str, *, reserved_codes: Iterable[str] | None = None) -> str:
    """Return ``alias`` normalized, or raise ``InvalidAlias``.

    ``reserved_codes`` defaults to :data:`DEFAULT_RESERVED_CODES`. The
    service injects the configured list (``config.reserved_codes``) so the
    TOML is the runtime source of truth.
    """

    reserved = (
        frozenset(code.lower() for code in reserved_codes)
        if reserved_codes is not None
        else _FALLBACK_RESERVED
    )
    alias = alias.strip()
    if not ALIAS_RE.fullmatch(alias):
        raise InvalidAlias("aliases may contain letters, digits, hyphen, or underscore")
    if alias.lower() in reserved:
        raise InvalidAlias(f"reserved short code: {alias}")
    if alias.startswith("__pending_"):
        raise InvalidAlias("alias prefix is reserved")
    return alias.lower()


def is_reserved_code(code: str, *, reserved_codes: Iterable[str]) -> bool:
    blocked = frozenset(item.lower() for item in reserved_codes)
    return code.lower() in blocked


def validate_future_expiry(expires_at: datetime | None) -> datetime | None:
    """Reject expiry timestamps already in the past."""

    if expires_at is None:
        return None
    from sniplink.models import utc_now

    if expires_at <= utc_now():
        raise ValueError("expires_at: must be in the future when set")
    return expires_at


def _normalize_split(parsed) -> SplitResult:
    scheme = parsed.scheme.lower()
    host = parsed.hostname.lower() if parsed.hostname else ""
    port = parsed.port
    if port and not ((scheme == "http" and port == 80) or (scheme == "https" and port == 443)):
        host = f"{host}:{port}"
    path = parsed.path or "/"
    # Replaces userinfo and fragment with empty strings — intentional, see
    # the docstring on normalize_destination_url.
    return SplitResult(scheme, host, path, parsed.query, "")


def _reject_self_reference(destination: SplitResult, base_urls: Iterable[str]) -> None:
    for base_url in base_urls:
        if not base_url:
            continue
        base = urlsplit(base_url)
        if not base.netloc:
            continue
        same_scheme = destination.scheme == base.scheme.lower()
        same_host = destination.netloc.lower() == base.netloc.lower()
        if same_scheme and same_host:
            raise InvalidDestinationURL("destination may not point back to sniplink")
