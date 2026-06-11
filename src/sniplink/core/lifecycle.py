"""Lifecycle predicates checked before serving a redirect.

The ``max_clicks`` cap for counted redirects is enforced atomically inside
``record_click``. For ``HEAD`` / resolve-without-click paths,
:func:`ensure_click_quota_available` performs the same read-only gate.
"""

from __future__ import annotations

from sniplink.exceptions import CodeDeleted, CodeDisabled, CodeExpired
from sniplink.models import Link, utc_now


def ensure_can_disable(link: Link) -> None:
    """Gate ``disable_link`` — reject deleted or already-disabled records."""

    if link.deleted_at is not None:
        raise CodeDeleted(f"short code was deleted: {link.short_code}")
    if link.disabled_at is not None:
        raise CodeDisabled(f"short code is disabled: {link.short_code}")


def ensure_can_expire(link: Link) -> None:
    """Gate ``expire_link`` — reject deleted records only."""

    if link.deleted_at is not None:
        raise CodeDeleted(f"short code was deleted: {link.short_code}")


def ensure_link_available(link: Link) -> None:
    now = utc_now()
    if link.deleted_at is not None:
        raise CodeDeleted(f"short code was deleted: {link.short_code}")
    if link.disabled_at is not None:
        raise CodeDisabled(f"short code is disabled: {link.short_code}")
    if link.expires_at is not None and link.expires_at <= now:
        raise CodeExpired(f"short code is expired: {link.short_code}")


def ensure_click_quota_available(link: Link) -> None:
    """Raise ``CodeExpired`` when a link has exhausted its click budget."""

    if link.max_clicks is not None and link.click_count >= link.max_clicks:
        raise CodeExpired(f"short code reached max_clicks: {link.short_code}")


def link_display_state(link: Link) -> str:
    """Return a dashboard-friendly lifecycle label for ``link``."""

    now = utc_now()
    if link.deleted_at is not None:
        return "deleted"
    if link.disabled_at is not None:
        return "disabled"
    if link.expires_at is not None and link.expires_at <= now:
        return "expired"
    if link.max_clicks is not None and link.click_count >= link.max_clicks:
        return "capped"
    return "active"


def is_active_link(link: Link) -> bool:
    if link.short_code.startswith("__pending_"):
        return False
    return link_display_state(link) == "active"
