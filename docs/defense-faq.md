# Defense FAQ

Short answers for common evaluator questions.

## Why SQLite instead of PostgreSQL?

The capstone thesis is **HTTP protocol mastery** and **adapter layering**, not
database administration. SQLite proves WAL concurrency, `UNIQUE`-driven
collision handling, and a shared file between CLI and Django. Production would
move to Postgres with the same `Storage` contract.

## Why WSGI instead of ASGI?

To make the synchronous `environ` / `start_response` / byte-iterable boundary
visible. Django still runs on WSGI here; asyncio is reserved for outbound
health checks (ADR 0005, ADR 0006).

## How can two threads create the same vanity alias?

They cannot both succeed. The second `INSERT` or `UPDATE` hits
`UNIQUE(short_code)` and raises `AliasTaken`; the service retries with a new
candidate up to `collision_retry_limit`. See ADR 0004 and
`tests/concurrency/test_concurrent_code_creation.py`.

## What happens when `max_clicks` is exhausted mid-request?

`record_click` runs a **single conditional UPDATE** — if the cap is already
reached, `rowcount == 0` and the caller gets `CodeExpired` before a click row
is inserted. Concurrent threads cannot both pass a check-then-write pattern.

## What happens if a link is disabled during concurrent GETs?

The atomic UPDATE in `record_click` requires `disabled_at IS NULL`. After
disable, all further counted redirects fail with `CodeDisabled`. See
`tests/concurrency/test_disable_click_race.py`.

## CLI-first vs Django-first bootstrap?

Both paths converge on tables `links`, `clicks`, `health_check_results` in
`sniplink.toml#database_path`. CLI-first needs `migrate --fake-initial` so
Django adopts existing tables. See README and migration `0002`.

## Why is `302` the default redirect?

`302 Found` is the conventional tracked redirect for shorteners — intermediaries
and browsers treat it as temporary. `301`/`308` are available per link but
risk aggressive caching (ADR 0003).

## Why `Cache-Control: no-store` on redirects?

Click analytics would be wrong if a browser or CDN cached the redirect response.
We prefer honest counting over microsecond lookup savings (ADR 0007).

## Why `Connection: close` on the raw socket server?

The demo server handles one request per connection and exits — keeping the
implementation small and easy to compare with WSGI and Django.
