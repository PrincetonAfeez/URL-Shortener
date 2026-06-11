"""Direct unit tests for ``sniplink.cli.main`` command handlers."""

from __future__ import annotations

import argparse
from datetime import datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest

from sniplink.cli import exit_codes
from sniplink.cli.main import (
    build_parser,
    build_service,
    cmd_check_health,
    cmd_create,
    cmd_delete,
    cmd_disable,
    cmd_expire,
    cmd_init_db,
    cmd_list,
    cmd_resolve,
    cmd_serve_raw,
    cmd_serve_wsgi,
    cmd_stats,
    main,
    parse_datetime,
)
from sniplink.core import SniplinkService
from sniplink.exceptions import AliasTaken, CodeNotFound, CollisionExhausted, LinkGone, StorageError
from sniplink.storage import SQLiteStorage


@pytest.fixture
def service(tmp_path) -> SniplinkService:
    svc = SniplinkService(SQLiteStorage(tmp_path / "cli-unit.db"))
    svc.initialize()
    return svc


def _args(**kwargs) -> argparse.Namespace:
    return argparse.Namespace(**kwargs)


def test_parse_datetime_rejects_empty():
    with pytest.raises(argparse.ArgumentTypeError):
        parse_datetime("")


def test_parse_datetime_adds_utc():
    parsed = parse_datetime("2026-12-31T12:00:00")
    assert parsed.tzinfo == timezone.utc


def test_parse_datetime_rejects_invalid_iso():
    with pytest.raises(argparse.ArgumentTypeError, match="not an ISO"):
        parse_datetime("not-a-date")


def test_build_parser_has_all_subcommands():
    parser = build_parser()
    sub = next(action for action in parser._actions if action.dest == "command")
    assert sub.choices is not None
    assert {
        "init-db",
        "create",
        "resolve",
        "list",
        "stats",
        "disable",
        "delete",
        "expire",
        "serve-raw",
        "serve-wsgi",
        "check-health",
    } <= set(sub.choices.keys())


def test_build_service_uses_config_base_url(tmp_path):
    args = _args(db=str(tmp_path / "cli-unit.db"), base_url=None)
    svc = build_service(args)
    assert svc.base_url


def test_cmd_init_db(capsys, service, tmp_path):
    code = cmd_init_db(_args(db=str(tmp_path / "cli-unit.db")), service)
    out = capsys.readouterr().out
    assert code == exit_codes.SUCCESS
    assert "initialized" in out
    assert "migrate --fake-initial" in out


def test_cmd_create_rejects_invalid_max_clicks(service):
    with pytest.raises(ValueError, match="max_clicks"):
        cmd_create(
            _args(
                url="https://example.com",
                alias="badmc",
                random=False,
                redirect_status=None,
                expires_at=None,
                max_clicks=0,
                json=False,
                base_url=None,
            ),
            service,
        )


def test_cmd_create_json_output(capsys, service):
    code = cmd_create(
        _args(
            url="https://example.com",
            alias="cli",
            random=False,
            redirect_status=None,
            expires_at=None,
            max_clicks=None,
            json=True,
            base_url="http://short.test",
        ),
        service,
    )
    assert code == exit_codes.SUCCESS
    assert '"short_code": "cli"' in capsys.readouterr().out


def test_cmd_create_random_strategy(capsys, service):
    cmd_create(
        _args(
            url="https://example.com",
            alias=None,
            random=True,
            redirect_status=307,
            expires_at=None,
            max_clicks=None,
            json=False,
            base_url=None,
        ),
        service,
    )
    assert "->" in capsys.readouterr().out


def test_cmd_resolve_plain_and_json(capsys, service):
    service.create_link("https://example.com", alias="res")
    cmd_resolve(_args(code="res", json=False), service)
    assert "https://example.com" in capsys.readouterr().out
    cmd_resolve(_args(code="res", json=True), service)
    assert '"destination_url"' in capsys.readouterr().out


def test_cmd_list_and_stats(capsys, service):
    service.create_link("https://example.com", alias="listed")
    cmd_list(_args(include_deleted=False), service)
    assert "listed" in capsys.readouterr().out
    cmd_stats(_args(code="listed"), service)
    assert '"click_count"' in capsys.readouterr().out


def test_cmd_disable_delete_expire(capsys, service):
    service.create_link("https://example.com", alias="life")
    cmd_disable(_args(code="life", base_url="http://x"), service)
    capsys.readouterr()
    with pytest.raises(LinkGone):
        service.disable_link("life")
    service.create_link("https://example.org", alias="del")
    cmd_delete(_args(code="del", base_url=None), service)
    service.create_link("https://example.net", alias="exp")
    when = datetime.now(timezone.utc) + timedelta(days=1)
    cmd_expire(_args(code="exp", at=when, base_url=None), service)
    assert capsys.readouterr().out


def test_cmd_expire_defaults_at_to_now(capsys, service):
    service.create_link("https://example.com", alias="now")
    cmd_expire(_args(code="now", at=None, base_url=None), service)
    assert "now" in capsys.readouterr().out


def test_cmd_serve_raw_and_wsgi(monkeypatch, capsys, service, tmp_path):
    monkeypatch.setattr("sniplink.cli.main.RawHTTPServer.serve_forever", lambda self: None)
    monkeypatch.setattr("sniplink.cli.main.make_server", lambda *a, **k: MagicMock(serve_forever=lambda: None))
    cmd_serve_raw(_args(db=str(tmp_path / "cli-unit.db"), host="127.0.0.1", port=9001), service)
    assert "raw HTTP" in capsys.readouterr().out
    cmd_serve_wsgi(_args(db=str(tmp_path / "cli-unit.db"), host="127.0.0.1", port=9101), service)
    assert "WSGI" in capsys.readouterr().out


def test_cmd_check_health(capsys, service):
    service.create_link("https://example.com", alias="health")
    code = cmd_check_health(
        _args(concurrency=2, timeout=1.0, allow_private=False),
        service,
    )
    assert code == exit_codes.SUCCESS
    assert '"link_id"' in capsys.readouterr().out


def test_main_maps_exceptions(tmp_path, capsys):
    db = str(tmp_path / "main.db")
    assert main(["--db", db, "resolve", "missing"]) == exit_codes.NOT_FOUND
    main(["--db", db, "init-db"])
    main(["--db", db, "create", "https://example.com", "--alias", "x"])
    assert main(["--db", db, "create", "https://other.com", "--alias", "x"]) == exit_codes.CONFLICT
    main(["--db", db, "disable", "x"])
    assert main(["--db", db, "disable", "x"]) == exit_codes.GONE
    assert main(["--db", db, "create", "javascript:alert(1)", "--alias", "bad"]) == exit_codes.FAILURE
    assert main(["--db", db, "create", "https://x.com", "--redirect-status", "999"]) == exit_codes.USAGE_ERROR


def test_main_maps_storage_error(tmp_path, monkeypatch, capsys):
    db = str(tmp_path / "store.db")
    monkeypatch.setattr(
        "sniplink.cli.main.build_service",
        lambda *a, **k: (_ for _ in ()).throw(StorageError("db down")),
    )
    assert main(["--db", db, "init-db"]) == exit_codes.FAILURE


def test_main_maps_collision_exhausted(tmp_path, monkeypatch):
    db = str(tmp_path / "col.db")
    service = SniplinkService(SQLiteStorage(db))
    service.initialize()
    monkeypatch.setattr("sniplink.cli.main.build_service", lambda *a, **k: service)
    from unittest.mock import MagicMock

    service.random_codec = MagicMock()
    service.create_link("https://example.com", alias="taken")
    service.random_codec.generate.return_value = "taken"
    assert (
        main(["--db", db, "create", "https://other.com", "--random"])
        == exit_codes.EXHAUSTED
    )
