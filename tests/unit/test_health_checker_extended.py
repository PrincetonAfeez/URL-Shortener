"""Extended coverage for :class:`sniplink.async_tools.health_checker.AsyncHealthChecker`."""

from __future__ import annotations

import asyncio
from unittest.mock import MagicMock

import pytest

from sniplink.async_tools import AsyncHealthChecker
from sniplink.exceptions import RedirectLimitExceeded
from sniplink.models import Link, utc_now


def test_health_checker_rejects_non_positive_concurrency():
    with pytest.raises(ValueError, match="positive"):
        AsyncHealthChecker(concurrency=0)


def test_health_checker_rejects_non_http_scheme():
    checker = AsyncHealthChecker(allow_private=True)
    link = Link(1, "x", "ftp://example.com", 302, utc_now())

    async def run():
        return await checker.check_link(link)

    result = asyncio.run(run())
    assert result.error is not None
    assert "only http and https" in result.error


def test_health_checker_rejects_missing_host():
    checker = AsyncHealthChecker(allow_private=True)
    link = Link(1, "x", "https:///path", 302, utc_now())
    result = asyncio.run(checker.check_link(link))
    assert "host" in (result.error or "").lower()


def test_health_checker_follows_redirect_without_location():
    async def handler(reader, writer):
        await reader.readuntil(b"\r\n\r\n")
        writer.write(b"HTTP/1.1 302 Found\r\nConnection: close\r\n\r\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def run():
        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        link = Link(1, "x", f"http://127.0.0.1:{port}/", 302, utc_now())
        checker = AsyncHealthChecker(concurrency=1, timeout=2, allow_private=True)
        result = await checker.check_link(link)
        server.close()
        await server.wait_closed()
        return result

    result = asyncio.run(run())
    assert result.error is not None
    assert "Location" in result.error


def test_health_checker_http_with_query_string():
    async def handler(reader, writer):
        await reader.readuntil(b"\r\n\r\n")
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def run():
        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        link = Link(
            1,
            "x",
            f"http://127.0.0.1:{port}/path?x=1",
            302,
            utc_now(),
        )
        checker = AsyncHealthChecker(concurrency=1, timeout=2, allow_private=True)
        result = await checker.check_link(link)
        server.close()
        await server.wait_closed()
        return result

    result = asyncio.run(run())
    assert result.status_code == 200


def test_health_checker_malformed_status_line():
    async def handler(reader, writer):
        await reader.readuntil(b"\r\n\r\n")
        writer.write(b"NOT HTTP\r\n\r\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def run():
        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        link = Link(1, "x", f"http://127.0.0.1:{port}/", 302, utc_now())
        checker = AsyncHealthChecker(concurrency=1, timeout=2, allow_private=True)
        result = await checker.check_link(link)
        server.close()
        await server.wait_closed()
        return result

    result = asyncio.run(run())
    assert "malformed HTTP status line" in (result.error or "")


def test_health_checker_redirect_limit_exceeded():
    async def handler(reader, writer):
        await reader.readuntil(b"\r\n\r\n")
        writer.write(
            b"HTTP/1.1 302 Found\r\n"
            b"Location: /loop\r\n"
            b"Connection: close\r\n\r\n"
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def run():
        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        link = Link(1, "x", f"http://127.0.0.1:{port}/loop", 302, utc_now())
        checker = AsyncHealthChecker(
            concurrency=1,
            timeout=2,
            max_redirects=1,
            allow_private=True,
        )
        result = await checker.check_link(link)
        server.close()
        await server.wait_closed()
        return result

    result = asyncio.run(run())
    assert result.error is not None
    assert "RedirectLimitExceeded" in result.error


def test_health_checker_persist_failure_does_not_abort_batch():
    storage = MagicMock()
    storage.save_health_result.side_effect = RuntimeError("disk full")
    link = Link(1, "x", "https://example.com", 302, utc_now())
    checker = AsyncHealthChecker(concurrency=1, timeout=1, allow_private=False)
    results = asyncio.run(checker.check_links([link], storage=storage))
    assert len(results) == 1
    storage.save_health_result.assert_called_once()


def test_health_checker_rejects_private_host_by_default():
    checker = AsyncHealthChecker(allow_private=False)

    async def run():
        await checker._reject_private_host("127.0.0.1")  # noqa: SLF001

    with pytest.raises(ValueError, match="private"):
        asyncio.run(run())
