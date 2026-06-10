# sniplink

`sniplink` is a Python URL-shortener capstone focused on HTTP, TCP sockets,
redirect semantics, WSGI, Django, SQLite, APIs, and asyncio.

The architecture is intentionally layered:

```text
CLI / raw socket HTTP / WSGI / Django + HTMX / JSON API / async tools
    -> core service
        -> storage interface
            -> SQLite or Django ORM adapter
```

**One engine, multiple front ends.** The CLI, raw socket server, WSGI app,
Django views, and JSON API are independent adapters over the same
framework-free core. The raw socket server and the WSGI app are parallel
demonstrations of the same redirect behavior; Django sits on top of WSGI as
the higher-level framework form of the same request/response idea.

## Quick Start

```powershell
python -m pip install -e .[dev] -c requirements-lock.txt
sniplink init-db
sniplink create https://example.com
sniplink list
sniplink serve-raw --port 9000
```

`requirements-lock.txt` pins the dev environment so a fresh clone installs
the exact set the test suite was verified against. Drop the `-c` flag to use
the looser ranges from `pyproject.toml`.

In another terminal:

```powershell
curl -v http://localhost:9000/1
```

## Django Web UI

```powershell
python web/manage.py migrate
python web/manage.py runserver 127.0.0.1:8000
```

Open `http://127.0.0.1:8000/`.

The Django app uses a `DjangoStorage` adapter that implements the same storage
contract as the SQLite CLI/raw server path. The core service does not import
Django. Both adapters read and write the **same tables** (`links`, `clicks`,
`health_check_results`) inside `sniplink.toml#database_path`.

| You started with | Then run |
| ---------------- | -------- |
| `python web/manage.py migrate` | `sniplink` CLI commands as usual |
| `sniplink init-db` | `python web/manage.py migrate --fake-initial` |

Migration `0002` reconciles legacy `links_*` shadow tables from older checkouts.

## JSON API

```powershell
curl -i -X POST http://127.0.0.1:8000/api/links `
  -H "Content-Type: application/json" `
  -d "{\"url\":\"https://example.com\",\"alias\":\"demo\"}"

curl -i http://127.0.0.1:8000/api/links/demo
curl -i http://127.0.0.1:8000/api/links/demo/stats
curl -i -X POST http://127.0.0.1:8000/api/links/demo/disable
curl -i -X POST http://127.0.0.1:8000/api/links/demo/expire `
  -H "Content-Type: application/json" `
  -d "{}"
curl -i -X DELETE http://127.0.0.1:8000/api/links/demo
```

Set `SNIPLINK_API_KEY` in the environment to require `X-API-Key` (or
`Authorization: Bearer …`) on JSON API calls.

## CLI

```powershell
sniplink --version
sniplink create https://example.com --alias demo
sniplink resolve demo
sniplink stats demo
sniplink delete demo
sniplink check-health --concurrency 10 --timeout 5
sniplink serve-wsgi --port 9100
```

Use `--db path\to\sniplink.db` on commands when you want an isolated database.

### Exit codes

The CLI exits with one of the following codes — scripts can branch on them:

| Code | Meaning                                                                  |
| ---- | ------------------------------------------------------------------------ |
| 0    | Success                                                                  |
| 1    | Generic runtime failure (`SniplinkError` not covered by a more specific code) |
| 2    | Usage error (invalid flag value, unsupported `--redirect-status`, etc.)  |
| 4    | Short code not found                                                     |
| 5    | Short code is gone (expired, disabled, or soft-deleted)                  |
| 6    | Alias conflict (a vanity alias was already taken)                        |

Defined in `src/sniplink/cli/exit_codes.py` and raised in `cli/main.py`.

## Configuration

`sniplink.toml` is the single source of truth for engine behavior. Both the
CLI (`sniplink.config.load_config`) and the Django app
(`sniplink_web.settings`) read from it, so the two front ends never disagree
about the database path, redirect defaults, or limits.

Override any field at runtime with the matching environment variable:

| TOML key                                 | Env var                       |
| ---------------------------------------- | ----------------------------- |
| `sniplink.database_path`                 | `SNIPLINK_DB`                 |
| `sniplink.default_base_url`              | `SNIPLINK_BASE_URL`           |
| `sniplink.default_redirect_status`       | `SNIPLINK_REDIRECT_STATUS`    |
| `sniplink.collision_retry_limit`         | `SNIPLINK_COLLISION_RETRIES`  |
| `sniplink.api.max_body_bytes`            | `SNIPLINK_API_MAX_BODY_BYTES` |
| `sniplink.logging.level`                 | `SNIPLINK_LOG_LEVEL`          |
| `sniplink.logging.format`                | `SNIPLINK_LOG_FORMAT`         |
| _(optional API auth)_                    | `SNIPLINK_API_KEY`            |

## Protocol Proof Points

- Raw socket server calls `socket()`, `bind()`, `listen()`, `accept()`,
  `recv()`, `sendall()`, and deliberately closes the connection.
- Redirects are manually serialized with status line, `Location`,
  `Cache-Control`, `Content-Length`, and `Connection`.
- `GET` and `HEAD` are supported; `HEAD` sends headers with no body.
- Unknown codes return `404 Not Found`.
- Expired, disabled, and deleted links return `410 Gone`.
- API create returns `201 Created` with a `Location` header.
- Alias conflicts return `409 Conflict`.
- API bodies over `sniplink.api.max_body_bytes` get `413 Payload Too Large`.
- Random token creation relies on the database `UNIQUE` constraint and bounded
  retry logic.
- Async health checking performs concurrent outbound network I/O with timeouts
  and a concurrency cap.

## Reserved Short Codes

The redirect path refuses to assign or look up codes that match the reserved
prefix list in `sniplink.toml` (default: `api`, `admin`, `dashboard`, `static`,
`favicon.ico`). This stops a vanity alias from shadowing the JSON API or
dashboard route.

## Tests

```powershell
python -m pytest
```

Coverage targets:

- `sniplink.core`: aim for **≥ 85%** (framework-free engine, easiest to test).
- Everything else: **≥ 70%**.
- The aggregate floor enforced by `pyproject.toml` is **60%** today and grows
  toward 80% as milestones 4–9 land — see `docs/planning/timeline.md`.

`pytest-asyncio` is in the `dev` extras and is required for the
`asyncio_mode = "auto"` pytest setting. Without it, the suite still runs but
emits an "Unknown config option" warning (suppressed via `filterwarnings`).

The concurrency tests use SQLite WAL plus `BEGIN IMMEDIATE` so two threads
actually race for the `UNIQUE(short_code)` constraint instead of being silently
serialized by the default writer lock. See ADR 0004.

## Design Choices Worth Calling Out

- **WSGI on purpose.** Django can run through ASGI in modern deployments. This
  capstone intentionally demonstrates WSGI so the synchronous
  request/response boundary is visible. See ADR 0005.
- **Asyncio lives in the health-checker.** The redirect path is synchronous;
  asyncio handles concurrent outbound network I/O instead of being forced into
  the WSGI request path. See ADR 0006.
- **No application cache.** A redirect-lookup cache adds invalidation
  questions for every lifecycle transition. We send `Cache-Control: no-store`
  on tracked redirects instead. If a cache is added later, it must be
  single-process (the `manage.py runserver` case); a multi-worker Gunicorn
  deployment would fragment an in-process LRU and require Redis-class
  infrastructure. See ADR 0007.
- **No CORS configuration.** The dashboard and the JSON API share an origin
  (`http://127.0.0.1:8000`). Cross-origin scripted access is intentionally out
  of scope.
- **CSV import, bulk importer, idempotent dedup, QR codes, geo breakdown,
  caching, API-key auth, rate limiting** — all stretch goals. They live in
  `docs/planning/timeline.md` so they cannot quietly inflate the core scope.

## Privacy Posture

By default `sniplink` stores `User-Agent` and `Referer` on each click row
because the analytics demo needs them. It does **not** store client IP
addresses. The health checker refuses to probe private, loopback, or
link-local destinations unless `--allow-private` is passed for local testing.
The `observability.redaction` module strips `Authorization`, API-key, and
secret-shaped header values out of logs.

## Implementation Caveats (worth knowing during the defense)

- **`wsgiref.simple_server`** powers `sniplink serve-wsgi`. It is single-
  threaded and explicitly development-only per the stdlib docs. The point is
  to show the WSGI interface, not to run production traffic.
- **TLS timing.** The async health checker uses `asyncio.open_connection` with
  `ssl=True` for `https://` destinations and records total elapsed time. It
  does not break the budget down into DNS / connect / TLS handshake / TTFB
  phases — that needs a custom `SSLContext` and is documented as a future
  upgrade in ADR 0006.
- **User-Agent parsing.** The dashboard and CLI display raw User-Agent
  strings. No browser/OS family parsing is implemented; the capstone keeps that
  out of scope rather than ship a brittle 20-line classifier. See ADR 0006 for
  the scope decision.
- **HTMX + CSRF.** The Django views are session-less and use HTMX. Form posts
  send `X-CSRFToken` via the `hx-headers` directive in the base template; the
  middleware is enabled in `sniplink_web.settings`. JSON API endpoints are
  `@csrf_exempt` because the capstone has no session login.

## Documentation

- [Protocol evidence](docs/protocol-evidence.md)
- [Demo script](docs/demo-script.md)
- [Production reflection](docs/production-reflection.md)
- [Milestone timeline](docs/planning/timeline.md)
- Architecture decision records live in [docs/adr](docs/adr).
