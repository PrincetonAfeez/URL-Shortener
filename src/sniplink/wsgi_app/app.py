"""WSGI application. """

from __future__ import annotations

import time
from collections.abc import Callable, Iterable

from sniplink.core.service import SniplinkService
from sniplink.exceptions import CodeNotFound, LinkGone
from sniplink.observability import log_redirect_decision
from sniplink.raw_http.request_parser import extract_code, path_too_long
from sniplink.raw_http.response_writer import REASONS

StartResponse = Callable[[str, list[tuple[str, str]]], None]


def make_app(
    service: SniplinkService,
    *,
    reserved_codes: Iterable[str] = (),
    max_path_length: int = 2048,
):
    """Build the hand-written WSGI redirect app.

    ``reserved_codes`` parity with :class:`sniplink.raw_http.server.RawHTTPServer`
    — paths whose code matches a reserved prefix short-circuit to 404 so the
    WSGI adapter does not disagree with the raw socket server about whether
    ``/api`` resolves as a short code (bug #4 in the fourth-pass review).
    """

    reserved = frozenset(p.lower() for p in reserved_codes)

    def app(environ: dict, start_response: StartResponse) -> Iterable[bytes]:
        method = environ.get("REQUEST_METHOD", "GET").upper()
        path = environ.get("PATH_INFO", "/")

        if method not in {"GET", "HEAD"}:
            return _respond(
                start_response,
                405,
                method,
                b"method not allowed\n",
                extra_headers=[("Allow", "GET, HEAD")],
            )
        if path_too_long(path, max_path_length=max_path_length):
            return _respond(start_response, 414, method, b"request target is too long\n")

        code = extract_code(path)
        if code is None:
            return _respond(start_response, 404, method, b"short code required\n")
        if code.lower() in reserved:
            return _respond(start_response, 404, method, b"reserved short code\n")

        try:
            started = time.perf_counter()
            decision = service.resolve(
                code,
                record_click=method == "GET",
                referrer=environ.get("HTTP_REFERER"),
                user_agent=environ.get("HTTP_USER_AGENT"),
            )
            lookup_ms = (time.perf_counter() - started) * 1000.0
        except CodeNotFound:
            log_redirect_decision(
                "wsgi",
                short_code=code,
                status_code=404,
                destination_url=None,
                lookup_ms=0.0,
                result="not_found",
            )
            return _respond(start_response, 404, method, b"short code not found\n")
        except LinkGone:
            log_redirect_decision(
                "wsgi",
                short_code=code,
                status_code=410,
                destination_url=None,
                lookup_ms=0.0,
                result="gone",
            )
            return _respond(start_response, 410, method, b"short code is gone\n")

        log_redirect_decision(
            "wsgi",
            short_code=code,
            status_code=decision.status_code,
            destination_url=decision.destination_url,
            lookup_ms=lookup_ms,
            result="found",
        )
        start_response(
            f"{decision.status_code} {REASONS[decision.status_code]}",
            [
                ("Location", decision.destination_url),
                ("Cache-Control", "no-store"),
                ("Content-Length", "0"),
            ],
        )
        return [b""]

    return app


def _respond(
    start_response: StartResponse,
    status_code: int,
    method: str,
    body: bytes,
    *,
    extra_headers: list[tuple[str, str]] | None = None,
) -> list[bytes]:
    headers = [
        ("Content-Type", "text/plain; charset=utf-8"),
        ("Cache-Control", "no-store"),
        ("Content-Length", str(len(body))),
    ]
    if extra_headers:
        headers.extend(extra_headers)
    start_response(f"{status_code} {REASONS[status_code]}", headers)
    return [b""] if method == "HEAD" else [body]
