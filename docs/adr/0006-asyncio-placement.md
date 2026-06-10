# ADR 0006: Asyncio Placement

## Status

Accepted (2026-06-09).

## Decision

Use asyncio for the link health-checker only. Keep the WSGI request path
synchronous. The health-checker uses `asyncio.open_connection` to issue
concurrent HEAD requests against stored destinations, with a per-run
concurrency cap and total timeout. Bulk URL-import via local API calls (the
"asyncio fan-out of `POST /api/links`" idea from the original plan) is
explicitly **not** part of the build.

## Context

asyncio is the wrong tool inside a redirect handler. A redirect is one
database lookup plus one HTTP response — there is no I/O to overlap, so
async-ifying it just trades sync code clarity for cooperative-scheduler
complexity.

asyncio **is** the right tool for the health checker, which fans out N
outbound TCP connections against unrelated hosts and must do them
concurrently or take N × timeout seconds. The implementation lives in
`sniplink.async_tools.health_checker.AsyncHealthChecker` and exposes:

- a concurrency `Semaphore`
- per-request `asyncio.wait_for` total timeout
- redirect-hop limit
- a private-host guard (refuses RFC1918 / loopback / link-local destinations
  unless `--allow-private` is passed for local testing)

### Why the bulk importer was dropped

The original plan suggested an async bulk importer that fired many
`POST /api/links` calls concurrently into the local server. That is not a
real concurrency demonstration — the calls would be in-process HTTP
round-trips and a CSV-driven `service.create_link` loop is faster and
simpler. The health checker keeps the asyncio teaching point because the
outbound work is genuinely parallelizable. CSV import is listed under stretch
scope and would call the service directly, not the API.

### TLS-timing scope

`asyncio.open_connection(..., ssl=True)` handles the TLS handshake
internally. The capstone records *total* elapsed time per check; it does not
break the budget down into DNS / connect / TLS handshake / TTFB phases.
Phase-level timing would require a custom `SSLContext` and per-state
instrumentation, which is documented as a stretch follow-up rather than
half-implemented. The `Timer` context manager in `async_tools/timing.py`
captures the total.

## Consequences

- The WSGI app stays one screen of code and is easy to read for the defense
  panel.
- The health checker is testable without a network: an `asyncio.start_server`
  fixture in `tests/integration/test_async_health_checker.py` returns a
  synthetic `204` so the concurrency machinery is exercised hermetically.
- Adding async to the redirect path later would require switching the WSGI
  app to an ASGI app, which is documented in the production reflection.

## Cancellation behavior

The health checker exposes three points where cancellation matters; each is
intentional and worth knowing during the defense:

- **Per-link timeout** — `asyncio.wait_for(self._follow_head(...), timeout=self.timeout)`
  raises `TimeoutError` after the budget. The `except Exception` in
  `check_link` catches it and the result records
  `error = "TimeoutError: "` so an operator can tell timeouts apart from
  refused connections in the JSON output.
- **In-flight HEAD cleanup** — `_head` wraps the read in `try / finally`
  that always calls `writer.close()` and suppresses any
  `wait_closed` failure. If the task running it is cancelled (Ctrl+C in the
  CLI, scheduler-driven cancellation in the future), the writer still closes
  rather than leaking a socket until GC.
- **Whole-batch cancellation** — `sniplink check-health` calls
  `asyncio.run(checker.check_links(...))`. A SIGINT during that call
  surfaces as `KeyboardInterrupt`; `asyncio.run` cancels every outstanding
  `check_link` coroutine, the `finally` blocks fire, and the CLI exits via
  the standard `KeyboardInterrupt` flow. No partial results are persisted
  for the cancelled checks.

The raw socket server has its own cancellation contract: `RawHTTPServer.shutdown()`
closes the server socket from another thread so `accept()` unblocks and
`serve_forever` exits cleanly. That's documented in
`src/sniplink/raw_http/server.py` and isn't async — it's the threading
side of the same "in-flight work has a defined teardown" rule.

## Alternatives considered

- **`aiohttp`** for the health checker. Cleaner code, but it hides the very
  socket lifecycle we want to demonstrate. `asyncio.open_connection` keeps
  the wire visible.
- **Threads instead of asyncio**. Workable, but every outbound check needs a
  thread, which scales worse than a semaphore-bounded coroutine pool.
