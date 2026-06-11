"""Tests for the async health checker. """

import asyncio

from sniplink.async_tools import AsyncHealthChecker
from sniplink.models import Link, utc_now


def test_async_health_checker_records_status_code():
    async def handler(reader, writer):
        await reader.readuntil(b"\r\n\r\n")
        writer.write(
            b"HTTP/1.1 204 No Content\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
        )
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def run():
        server = await asyncio.start_server(handler, "127.0.0.1", 0)
        port = server.sockets[0].getsockname()[1]
        link = Link(
            id=1,
            short_code="local",
            destination_url=f"http://127.0.0.1:{port}/health",
            created_at=utc_now(),
        )
        checker = AsyncHealthChecker(concurrency=1, timeout=2, allow_private=True)
        results = await checker.check_links([link])
        server.close()
        await server.wait_closed()
        return results

    results = asyncio.run(run())

    assert results[0].status_code == 204
    assert results[0].error is None
