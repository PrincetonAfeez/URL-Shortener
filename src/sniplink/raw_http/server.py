"""Raw HTTP server. """

from __future__ import annotations

import logging
import socket
import threading
import time
from collections.abc import Iterable

from sniplink.core.service import SniplinkService
from sniplink.exceptions import CodeNotFound, LinkGone, SniplinkError
from sniplink.observability import log_redirect_decision
from sniplink.raw_http.request_parser import (
    BadRequest,
    UriTooLong,
    extract_code,
    parse_http_request,
)
from sniplink.raw_http.response_writer import error_response, redirect_response

LOG = logging.getLogger(__name__)


class RawHTTPServer:
    """Tiny single-threaded HTTP server used to demonstrate redirect over TCP.

    Production-aimed hardening from the code reviews:

    * Each accepted client has ``client.settimeout(recv_timeout)`` so a slow
      or dead client cannot block the accept loop indefinitely.
    * The server socket is held on ``self._server`` and closed from
      :meth:`shutdown`, which unblocks :meth:`serve_forever`'s blocking
      ``accept()`` call.
    * Paths whose first segment matches ``reserved_prefixes`` short-circuit
      to 404 so the resolver is never asked about ``api``/``admin``/etc.
    * Both the per-client block in :meth:`serve_forever` and
      :meth:`handle_request_bytes` wrap their work in ``try / except
      Exception`` so one bad request can no longer crash the server.
    """

    def __init__(
        self,
        service: SniplinkService,
        *,
        host: str = "127.0.0.1",
        port: int = 9000,
        recv_limit: int = 8192,
        recv_timeout: float = 5.0,
        reserved_codes: Iterable[str] = (),
        max_path_length: int = 2048,
    ) -> None:
        self.service = service
        self.host = host
        self.port = port
        self.recv_limit = recv_limit
        self.recv_timeout = recv_timeout
        self.reserved_codes = frozenset(p.lower() for p in reserved_codes)
        self.max_path_length = max_path_length
        self._stop = threading.Event()
        self._server: socket.socket | None = None

    def serve_forever(self) -> None:
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self._server.bind((self.host, self.port))
            self._server.listen()
            while not self._stop.is_set():
                try:
                    client, address = self._server.accept()
                except OSError:
                    # shutdown() closed the server socket — exit cleanly.
                    break
                try:
                    with client:
                        client.settimeout(self.recv_timeout)
                        LOG.info("accepted connection from %s:%s", *address)
                        raw = self._recv_headers(client)
                        response = self.handle_request_bytes(raw)
                        client.sendall(response)
                except Exception:  # noqa: BLE001 - keep the server alive.
                    LOG.exception("unhandled error serving raw client %s:%s", *address)
        finally:
            if self._server is not None:
                try:
                    self._server.close()
                finally:
                    self._server = None

    def serve_once(self, *, ready: threading.Event | None = None) -> None:
        """Handle exactly one connection then return.

        ``ready`` is an optional :class:`threading.Event` that is set after
        :meth:`socket.bind` + :meth:`socket.listen` return. Tests can
        ``thread.start()`` then ``ready.wait(timeout=2)`` instead of
        busy-polling ``server.port`` — bug #11 in the fourth-pass review.
        """

        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as server:
            server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            server.bind((self.host, self.port))
            self.port = server.getsockname()[1]
            server.listen(1)
            if ready is not None:
                ready.set()
            client, address = server.accept()
            with client:
                client.settimeout(self.recv_timeout)
                LOG.info("accepted connection from %s:%s", *address)
                raw = self._recv_headers(client)
                client.sendall(self.handle_request_bytes(raw))

    def shutdown(self) -> None:
        """Stop the accept loop. Safe to call from another thread."""

        self._stop.set()
        server = self._server
        if server is None:
            return
        try:
            server.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        try:
            server.close()
        except OSError:
            pass

    def _recv_headers(self, client: socket.socket) -> bytes:
        chunks: list[bytes] = []
        total = 0
        try:
            while total < self.recv_limit:
                chunk = client.recv(1024)
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
                if b"\r\n\r\n" in chunk or b"\r\n\r\n" in b"".join(chunks):
                    break
        except TimeoutError:
            # Slow / dead client. Return whatever we have so handle_request
            # can map it to a 400 Bad Request.
            pass
        return b"".join(chunks)

    def handle_request_bytes(self, raw: bytes) -> bytes:
        method = "GET"
        code: str | None = None
        try:
            request = parse_http_request(raw, max_path_length=self.max_path_length)
            method = request.method
            LOG.info(
                "request line parsed method=%s path=%s version=%s",
                request.method,
                request.path,
                request.http_version,
            )
            if request.method not in {"GET", "HEAD"}:
                return error_response(
                    405,
                    "only GET and HEAD are supported",
                    method=request.method,
                    allow="GET, HEAD",
                )
            code = extract_code(request.path)
            if code is None:
                return error_response(404, "short code required", method=request.method)
            if code.lower() in self.reserved_codes:
                return error_response(404, "reserved short code", method=request.method)
            started = time.perf_counter()
            decision = self.service.resolve(
                code,
                record_click=request.method == "GET",
                referrer=request.headers.get("referer"),
                user_agent=request.headers.get("user-agent"),
            )
            lookup_ms = (time.perf_counter() - started) * 1000.0
            log_redirect_decision(
                "raw_http",
                short_code=code,
                status_code=decision.status_code,
                destination_url=decision.destination_url,
                lookup_ms=lookup_ms,
                result="found",
            )
            return redirect_response(
                location=decision.destination_url,
                status_code=decision.status_code,
                method=request.method,
            )
        except BadRequest as exc:
            return error_response(400, str(exc), method=method)
        except UriTooLong as exc:
            return error_response(414, str(exc), method=method)
        except CodeNotFound:
            log_redirect_decision(
                "raw_http",
                short_code=code or "",
                status_code=404,
                destination_url=None,
                lookup_ms=0.0,
                result="not_found",
            )
            return error_response(404, "short code not found", method=method)
        except LinkGone:
            log_redirect_decision(
                "raw_http",
                short_code=code or "",
                status_code=410,
                destination_url=None,
                lookup_ms=0.0,
                result="gone",
            )
            return error_response(410, "short code is gone", method=method)
        except SniplinkError as exc:
            return error_response(500, str(exc), method=method)
        except Exception:  # noqa: BLE001 - last-resort handler keeps server up.
            LOG.exception("unexpected error in handle_request_bytes")
            return error_response(500, "internal server error", method=method)
