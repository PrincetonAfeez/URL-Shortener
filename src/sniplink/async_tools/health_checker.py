"""Async link health checker — concurrent HEAD requests via stdlib asyncio.

This module is the project's asyncio teaching point. It uses
``asyncio.open_connection`` directly (rather than ``aiohttp``) so the wire
remains visible: every check builds a HEAD request, sends it, reads the
status line and headers, and tears the connection down.

Timing scope
------------
:class:`AsyncHealthChecker` records *total* elapsed milliseconds per check
via :class:`sniplink.async_tools.timing.Timer`. It does **not** break the
budget down into DNS, TCP connect, TLS handshake, and TTFB phases — that
would require a custom ``SSLContext`` plus per-state instrumentation, which
is documented in ADR 0006 as a stretch follow-up rather than half-implemented
here.

Safety
------
The checker refuses private, loopback, and link-local destinations by
default. Pass ``allow_private=True`` (or the CLI ``--allow-private`` flag)
when running against a test server on ``127.0.0.1`` during the demo.
"""

from __future__ import annotations

import asyncio
import contextlib
import ipaddress
import logging
import socket
from collections.abc import Iterable
from datetime import timezone
from urllib.parse import urljoin, urlsplit

from sniplink.async_tools.timing import Timer
from sniplink.exceptions import RedirectLimitExceeded
from sniplink.models import HealthCheckResult, Link, utc_now
from sniplink.storage.base import Storage

LOG = logging.getLogger(__name__)


class AsyncHealthChecker:
    def __init__(
        self,
        *,
        concurrency: int = 10,
        timeout: float = 5.0,
        max_redirects: int = 3,
        allow_private: bool = False,
    ) -> None:
        if concurrency <= 0:
            raise ValueError("concurrency must be positive")
        self.concurrency = concurrency
        self.timeout = timeout
        self.max_redirects = max_redirects
        self.allow_private = allow_private

    async def check_links(
        self,
        links: Iterable[Link],
        *,
        storage: Storage | None = None,
    ) -> list[HealthCheckResult]:
        semaphore = asyncio.Semaphore(self.concurrency)

        async def checked(link: Link) -> HealthCheckResult:
            async with semaphore:
                result = await self.check_link(link)
                if storage is not None:
                    try:
                        await asyncio.to_thread(storage.save_health_result, result)
                    except Exception:  # noqa: BLE001 - don't abort the batch.
                        LOG.exception(
                            "failed to persist health-check result for link %s",
                            link.id,
                        )
                return result

        return await asyncio.gather(*(checked(link) for link in links))

    async def check_link(self, link: Link) -> HealthCheckResult:
        with Timer() as timer:
            checked_at = utc_now().astimezone(timezone.utc)
            try:
                status_code, redirect_count = await asyncio.wait_for(
                    self._follow_head(link.destination_url),
                    timeout=self.timeout,
                )
                error = None
            except Exception as exc:  # noqa: BLE001 - CLI should report failure text.
                status_code = None
                redirect_count = 0
                error = exc.__class__.__name__ + ": " + str(exc)

        return HealthCheckResult(
            link_id=link.id,
            checked_at=checked_at,
            status_code=status_code,
            error=error,
            elapsed_ms=timer.elapsed_ms,
            redirect_count=redirect_count,
        )

    async def _follow_head(self, url: str) -> tuple[int, int]:
        current = url
        redirects = 0
        for _ in range(self.max_redirects + 1):
            status, headers = await self._head(current)
            if status in {301, 302, 303, 307, 308}:
                location = headers.get("location")
                if not location:
                    # RFC 9110: a 3xx without Location is malformed. Surface
                    # it as an explicit error instead of pretending it was a
                    # successful terminal response (bug #9 in the review).
                    raise ValueError(f"{status} response missing Location header")
                redirects += 1
                current = urljoin(current, location)
                continue
            return status, redirects
        raise RedirectLimitExceeded(
            f"exceeded {self.max_redirects} redirects starting from {url}"
        )

    async def _head(self, url: str) -> tuple[int, dict[str, str]]:
        parsed = urlsplit(url)
        if parsed.scheme not in {"http", "https"}:
            raise ValueError("only http and https URLs can be checked")
        if not parsed.hostname:
            raise ValueError("URL must include a host")
        if not self.allow_private:
            await self._reject_private_host(parsed.hostname)

        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        ssl = parsed.scheme == "https"
        path = parsed.path or "/"
        if parsed.query:
            path += "?" + parsed.query

        # Build the Host header from hostname (+ optional :port) instead of
        # parsed.netloc. parsed.netloc includes any user:password@ prefix,
        # which would leak credentials to a remote host — bug #8 in the
        # second-pass code review.
        host_header = parsed.hostname
        if parsed.port is not None:
            host_header = f"{parsed.hostname}:{parsed.port}"

        reader, writer = await asyncio.open_connection(parsed.hostname, port, ssl=ssl)
        try:
            request = (
                f"HEAD {path} HTTP/1.1\r\n"
                f"Host: {host_header}\r\n"
                "User-Agent: sniplink-health-checker/0.1\r\n"
                "Connection: close\r\n\r\n"
            )
            writer.write(request.encode("ascii"))
            await writer.drain()
            raw = await reader.readuntil(b"\r\n\r\n")
        finally:
            # Always close the writer, even if readuntil raised mid-stream —
            # otherwise the socket leaks until GC. wait_closed itself can
            # raise once the peer is gone; that's expected during teardown
            # and not actionable.
            writer.close()
            with contextlib.suppress(Exception):
                await writer.wait_closed()

        head = raw.decode("iso-8859-1")
        lines = head.split("\r\n")
        status_parts = lines[0].split()
        if len(status_parts) < 2 or not status_parts[1].isdigit():
            raise ValueError("malformed HTTP status line")
        headers: dict[str, str] = {}
        for line in lines[1:]:
            if ":" in line:
                name, value = line.split(":", 1)
                headers[name.strip().lower()] = value.strip()
        return int(status_parts[1]), headers

    async def _reject_private_host(self, hostname: str) -> None:
        infos = await asyncio.to_thread(socket.getaddrinfo, hostname, None)
        for info in infos:
            address = info[4][0]
            ip = ipaddress.ip_address(address)
            if ip.is_private or ip.is_loopback or ip.is_link_local:
                raise ValueError("private/internal hosts are not checked by default")
