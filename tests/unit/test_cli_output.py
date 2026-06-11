"""Tests for ``sniplink.cli.output``."""

from __future__ import annotations

from sniplink.cli.output import print_json, print_link, print_link_table
from sniplink.models import Link, utc_now


def _link(**kwargs) -> Link:
    defaults = dict(
        id=1,
        short_code="demo",
        destination_url="https://example.com",
        redirect_status=302,
        created_at=utc_now(),
        expires_at=None,
        disabled_at=None,
        deleted_at=None,
        max_clicks=None,
        click_count=3,
        metadata={},
    )
    defaults.update(kwargs)
    return Link(**defaults)


def test_print_json(capsys):
    print_json({"a": 1})
    assert '"a": 1' in capsys.readouterr().out


def test_print_link_text_and_json(capsys):
    print_link(_link(), base_url="http://short.test", as_json=False)
    text = capsys.readouterr().out
    assert "demo -> https://example.com" in text
    assert "short_url: http://short.test/demo" in text
    print_link(_link(), base_url="http://short.test/", as_json=True)
    assert '"short_code": "demo"' in capsys.readouterr().out


def test_print_link_table(capsys):
    print_link_table([_link(), _link(short_code="two", click_count=0)])
    out = capsys.readouterr().out
    assert "CODE" in out
    assert "demo" in out
    assert "two" in out
