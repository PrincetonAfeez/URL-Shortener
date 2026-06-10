"""Output utilities for the CLI."""

from __future__ import annotations

import json

from sniplink.api.serializers import link_to_dict
from sniplink.core.lifecycle import link_display_state
from sniplink.models import Link


def print_json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True, default=str))


def print_link(link: Link, *, base_url: str, as_json: bool = False) -> None:
    short_url = f"{base_url.rstrip('/')}/{link.short_code}"
    if as_json:
        print_json(link_to_dict(link, short_url=short_url))
        return
    print(f"{link.short_code} -> {link.destination_url}")
    print(f"short_url: {short_url}")
    print(f"status: {link.redirect_status}")
    print(f"clicks: {link.click_count}")


def print_link_table(links: list[Link]) -> None:
    print(f"{'CODE':<12} {'CLICKS':>6} {'STATE':<9} URL")
    for link in links:
        state = link_display_state(link)
        print(f"{link.short_code:<12} {link.click_count:>6} {state:<9} {link.destination_url}")
