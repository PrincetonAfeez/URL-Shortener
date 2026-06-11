"""Hardening checks for ``AsyncHealthChecker._head``.

Bug #8 — the Host header was built from ``urlsplit(url).netloc`` which
includes the ``user:password@`` prefix. The fix builds it from
``parsed.hostname`` (+ optional ``:port``). This test points the checker at
a destination URL that *embeds* credentials and asserts the bytes that hit
the wire do not contain them.

Bug #7 — exceeding the redirect-hop budget now raises
``RedirectLimitExceeded`` (a subclass of ``HealthCheckError``) instead of
``TimeoutError``. The error type ends up in ``HealthCheckResult.error`` so
operators can tell a timeout from a loop.
"""

from __future__ import annotations

import asyncio

import pytest

from sniplink.async_tools import AsyncHealthChecker
from sniplink.exceptions import RedirectLimitExceeded
from sniplink.models import Link, utc_now


def test_head_host_header_does_not_include_userinfo():
    received: list[bytes] = []

    async def echo_request(reader, writer):
        received.append(await reader.readuntil(b"\r\n\r\n"))
        writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def run():
        server = await asyncio.start_server(echo_request, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        link = Link(
            id=1,
            short_code="leaky",
            # Userinfo (alice:secret@) is part of the URL — credentials must
            # not appear in the Host header sent to the destination.
            destination_url=f"http://alice:secret@127.0.0.1:{port}/x",
            created_at=utc_now(),
        )
        checker = AsyncHealthChecker(concurrency=1, timeout=2, allow_private=True)
        await checker.check_links([link])
        server.close()
        await server.wait_closed()

    asyncio.run(run())

    assert received, "destination server never received a request"
    request_bytes = received[0]
    assert b"alice" not in request_bytes
    assert b"secret" not in request_bytes
    assert f"Host: 127.0.0.1".encode() in request_bytes


def test_redirect_limit_exceeded_surfaces_as_named_error():
    """Loop a server at itself; the checker should raise RedirectLimitExceeded."""

    async def loop_back(reader, writer):
        await reader.readuntil(b"\r\n\r\n")
        # Always tell the client to follow another redirect — the checker
        # must give up after ``max_redirects + 1`` hops.
        port = writer.get_extra_info("sockname")[1]
        writer.write(
            f"HTTP/1.1 302 Found\r\n"
            f"Location: http://127.0.0.1:{port}/next\r\n"
            f"Content-Length: 0\r\n"
            f"Connection: close\r\n\r\n".encode()
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def run():
        server = await asyncio.start_server(loop_back, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        link = Link(
            id=1,
            short_code="loop",
            destination_url=f"http://127.0.0.1:{port}/",
            created_at=utc_now(),
        )
        checker = AsyncHealthChecker(
            concurrency=1, timeout=5, max_redirects=2, allow_private=True
        )
        results = await checker.check_links([link])
        server.close()
        await server.wait_closed()
        return results

    [result] = asyncio.run(run())

    assert result.status_code is None
    assert result.error is not None
    assert RedirectLimitExceeded.__name__ in result.error


def test_health_checker_rejects_private_host_by_default():
    link = Link(
        id=1,
        short_code="local",
        destination_url="http://127.0.0.1:9/",
        created_at=utc_now(),
    )
    checker = AsyncHealthChecker(concurrency=1, timeout=1, allow_private=False)

    async def run():
        return await checker.check_links([link])

    [result] = asyncio.run(run())
    assert result.status_code is None
    assert result.error is not None
    assert "private" in result.error.lower() or "loopback" in result.error.lower()
