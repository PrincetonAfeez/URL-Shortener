"""Tests for the link display state. """

from datetime import timedelta

from sniplink.core.lifecycle import link_display_state
from sniplink.models import Link, utc_now


def test_link_display_state_labels():
    now = utc_now()
    assert link_display_state(Link(id=1, short_code="a", destination_url="https://x")) == "active"
    assert (
        link_display_state(
            Link(
                id=1,
                short_code="a",
                destination_url="https://x",
                disabled_at=now,
            )
        )
        == "disabled"
    )
    assert (
        link_display_state(
            Link(
                id=1,
                short_code="a",
                destination_url="https://x",
                expires_at=now - timedelta(seconds=1),
            )
        )
        == "expired"
    )
    assert (
        link_display_state(
            Link(
                id=1,
                short_code="a",
                destination_url="https://x",
                max_clicks=1,
                click_count=1,
            )
        )
        == "capped"
    )
