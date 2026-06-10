"""CLI module."""

from __future__ import annotations

import argparse
import asyncio
from datetime import datetime, timezone
from wsgiref.simple_server import make_server

from sniplink import __version__
from sniplink.async_tools import AsyncHealthChecker
from sniplink.cli import exit_codes
from sniplink.cli.output import print_json, print_link, print_link_table
from sniplink.config import SniplinkConfig, load_config
from sniplink.core import SniplinkService
from sniplink.core.factory import build_sniplink_service
from sniplink.exceptions import (
    AliasTaken,
    CodeNotFound,
    CollisionExhausted,
    LinkGone,
    SniplinkError,
)
from sniplink.observability import configure_logging
from sniplink.raw_http import RawHTTPServer
from sniplink.storage import SQLiteStorage
from sniplink.wsgi_app import make_app


def build_service(args: argparse.Namespace, config: SniplinkConfig | None = None) -> SniplinkService:
    if config is None:
        config = load_config(args.db)
    storage = SQLiteStorage(config.database_path)
    service = build_sniplink_service(
        storage,
        config,
        base_url=args.base_url or config.default_base_url,
    )
    service.initialize()
    return service


def _render_base_url(args: argparse.Namespace, service: SniplinkService) -> str:
    return args.base_url or service.base_url


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    config = load_config(getattr(args, "db", None))
    configure_logging(
        args.log_level or config.logging.level,
        format=config.logging.format,
        redact_keys=config.logging.redact_keys,
    )

    try:
        service = build_service(args, config=config)
        return args.func(args, service)
    except AliasTaken as exc:
        print(f"conflict: {exc}")
        return exit_codes.CONFLICT
    except CollisionExhausted as exc:
        print(f"exhausted: {exc}")
        return exit_codes.EXHAUSTED
    except CodeNotFound as exc:
        print(f"not found: {exc}")
        return exit_codes.NOT_FOUND
    except LinkGone as exc:
        print(f"gone: {exc}")
        return exit_codes.GONE
    except ValueError as exc:
        # service.create_link raises ValueError for unsupported
        # redirect_status or unknown code_strategy. Surface it as a usage
        # error instead of a Python traceback (bug #3 in the fourth-pass
        # review).
        print(f"invalid argument: {exc}")
        return exit_codes.USAGE_ERROR
    except SniplinkError as exc:
        print(f"error: {exc}")
        return exit_codes.FAILURE


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sniplink")
    parser.add_argument(
        "--version",
        action="version",
        version=f"sniplink {__version__}",
    )
    parser.add_argument("--db", help="SQLite database path (overrides sniplink.toml)")
    parser.add_argument(
        "--base-url",
        default=None,
        help="base URL used to render short_url (defaults to sniplink.toml)",
    )
    parser.add_argument(
        "--log-level",
        default=None,
        help="logging level (defaults to sniplink.toml#logging.level)",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    init_db = sub.add_parser("init-db", help="initialize the SQLite database")
    init_db.set_defaults(func=cmd_init_db)

    create = sub.add_parser("create", help="create a short link")
    create.add_argument("url")
    create.add_argument("--alias")
    create.add_argument("--random", action="store_true", help="use random token codec")
    # Default left as None so the service uses
    # sniplink.toml#default_redirect_status. Passing 302 here would shadow
    # the config knob — see bug #4 in the third-pass review.
    create.add_argument("--redirect-status", type=int, default=None)
    create.add_argument("--expires-at", type=parse_datetime)
    create.add_argument("--max-clicks", type=int)
    create.add_argument("--json", action="store_true")
    _add_base_url_arg(create)
    create.set_defaults(func=cmd_create)

    resolve = sub.add_parser("resolve", help="resolve a short code without counting a click")
    resolve.add_argument("code")
    resolve.add_argument("--json", action="store_true")
    resolve.set_defaults(func=cmd_resolve)

    list_cmd = sub.add_parser("list", help="list links")
    list_cmd.add_argument("--include-deleted", action="store_true")
    list_cmd.set_defaults(func=cmd_list)

    stats = sub.add_parser("stats", help="show stats")
    stats.add_argument("code")
    stats.set_defaults(func=cmd_stats)

    disable = sub.add_parser("disable", help="disable a link")
    disable.add_argument("code")
    _add_base_url_arg(disable)
    disable.set_defaults(func=cmd_disable)

    delete = sub.add_parser("delete", help="soft-delete a link")
    delete.add_argument("code")
    _add_base_url_arg(delete)
    delete.set_defaults(func=cmd_delete)

    expire = sub.add_parser("expire", help="set link expiry")
    expire.add_argument("code")
    _add_base_url_arg(expire)
    # default=None and resolve to "now" inside cmd_expire — capturing
    # datetime.now() here freezes the value at parser-build-time
    # (bug #6 in the fourth-pass review).
    expire.add_argument("--at", type=parse_datetime, default=None)
    expire.set_defaults(func=cmd_expire)

    raw = sub.add_parser("serve-raw", help="run the raw socket redirect server")
    raw.add_argument("--host", default="127.0.0.1")
    raw.add_argument("--port", type=int, default=9000)
    raw.set_defaults(func=cmd_serve_raw)

    wsgi = sub.add_parser("serve-wsgi", help="run the hand-written WSGI app")
    wsgi.add_argument("--host", default="127.0.0.1")
    wsgi.add_argument("--port", type=int, default=9100)
    wsgi.set_defaults(func=cmd_serve_wsgi)

    health = sub.add_parser("check-health", help="check stored destination URLs concurrently")
    health.add_argument("--concurrency", type=int, default=10)
    health.add_argument("--timeout", type=float, default=5.0)
    health.add_argument("--allow-private", action="store_true")
    health.set_defaults(func=cmd_check_health)
    return parser


def _add_base_url_arg(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--base-url",
        default=None,
        help="base URL used to render short_url (defaults to sniplink.toml)",
    )


def parse_datetime(value: str) -> datetime:
    if not value:
        raise argparse.ArgumentTypeError(
            "expected an ISO 8601 timestamp, got an empty string"
        )
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            f"not an ISO 8601 timestamp: {value!r}"
        ) from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def cmd_init_db(args: argparse.Namespace, service: SniplinkService) -> int:
    config = load_config(getattr(args, "db", None))
    print(f"initialized {config.database_path}")
    print(
        "Django dashboard on this file: python web/manage.py migrate --fake-initial"
    )
    return exit_codes.SUCCESS


def cmd_create(args: argparse.Namespace, service: SniplinkService) -> int:
    if args.max_clicks is not None and args.max_clicks < 1:
        raise ValueError("max_clicks: must be at least 1 when set")
    link = service.create_link(
        args.url,
        alias=args.alias,
        code_strategy="random" if args.random else "base62",
        redirect_status=args.redirect_status,
        expires_at=args.expires_at,
        max_clicks=args.max_clicks,
    )
    print_link(link, base_url=_render_base_url(args, service), as_json=args.json)
    return exit_codes.SUCCESS


def cmd_resolve(args: argparse.Namespace, service: SniplinkService) -> int:
    decision = service.resolve(args.code, record_click=False)
    payload = {
        "short_code": decision.short_code,
        "destination_url": decision.destination_url,
        "status_code": decision.status_code,
    }
    print_json(payload) if args.json else print(decision.destination_url)
    return exit_codes.SUCCESS


def cmd_list(args: argparse.Namespace, service: SniplinkService) -> int:
    print_link_table(service.list_links(include_deleted=args.include_deleted))
    return exit_codes.SUCCESS


def cmd_stats(args: argparse.Namespace, service: SniplinkService) -> int:
    service.resolve(args.code, record_click=False)
    print_json(service.stats(args.code))
    return exit_codes.SUCCESS


def cmd_disable(args: argparse.Namespace, service: SniplinkService) -> int:
    print_link(service.disable_link(args.code), base_url=_render_base_url(args, service))
    return exit_codes.SUCCESS


def cmd_delete(args: argparse.Namespace, service: SniplinkService) -> int:
    print_link(service.delete_link(args.code), base_url=_render_base_url(args, service))
    return exit_codes.SUCCESS


def cmd_expire(args: argparse.Namespace, service: SniplinkService) -> int:
    when = args.at if args.at is not None else datetime.now(timezone.utc)
    print_link(service.expire_link(args.code, when), base_url=_render_base_url(args, service))
    return exit_codes.SUCCESS


def cmd_serve_raw(args: argparse.Namespace, service: SniplinkService) -> int:
    config = load_config(getattr(args, "db", None))
    print(f"raw HTTP server listening on http://{args.host}:{args.port}")
    RawHTTPServer(
        service,
        host=args.host,
        port=args.port,
        recv_timeout=config.raw_http_recv_timeout,
        reserved_codes=config.reserved_codes,
        max_path_length=config.max_request_path_bytes,
    ).serve_forever()
    return exit_codes.SUCCESS


def cmd_serve_wsgi(args: argparse.Namespace, service: SniplinkService) -> int:
    config = load_config(getattr(args, "db", None))
    app = make_app(
        service,
        reserved_codes=config.reserved_codes,
        max_path_length=config.max_request_path_bytes,
    )
    print(f"WSGI server listening on http://{args.host}:{args.port}")
    print(
        "NOTE: wsgiref.simple_server is single-threaded and development-only; "
        "it is here to demonstrate the WSGI interface, not for production use."
    )
    with make_server(args.host, args.port, app) as server:
        server.serve_forever()
    return exit_codes.SUCCESS


def cmd_check_health(args: argparse.Namespace, service: SniplinkService) -> int:
    checker = AsyncHealthChecker(
        concurrency=args.concurrency,
        timeout=args.timeout,
        allow_private=args.allow_private,
    )
    results = asyncio.run(
        checker.check_links(service.list_active_links(), storage=service.storage)
    )
    print_json(
        [
            {
                "link_id": result.link_id,
                "status_code": result.status_code,
                "error": result.error,
                "elapsed_ms": round(result.elapsed_ms, 2),
                "redirect_count": result.redirect_count,
            }
            for result in results
        ]
    )
    return exit_codes.SUCCESS


if __name__ == "__main__":
    raise SystemExit(main())
