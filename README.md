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

**Contributors / full test run** (pinned dev toolchain):

```powershell
python -m pip install -r requirements.txt
python -m pip install -e ".[dev]" -c requirements-lock.txt
```

**Runtime only** (CLI + engine, no dev tools):

```powershell
python -m pip install -r requirements.txt
python -m pip install -e .
```

Then:

```powershell
sniplink init-db
sniplink create https://example.com
sniplink list
sniplink serve-raw --port 9000
```

| File | Purpose |
| ---- | ------- |
| `requirements.txt` | Runtime deps (`django`); loose ranges matching `pyproject.toml` |
| `requirements-lock.txt` | Pinned versions for reproducible dev/CI installs (`-c` constraints) |
| `pyproject.toml` | Package metadata, pytest/coverage/ruff/mypy config |

In another terminal:

```powershell
curl -v http://localhost:9000/1
```

## Django Web UI

If you already ran **Quick Start** (`sniplink init-db`) on the default
`sniplink.db`, use `--fake-initial` so Django adopts the existing tables:

```powershell
python web/manage.py migrate --fake-initial
python web/manage.py runserver 127.0.0.1:8000
```

Greenfield Django-first setup (no prior `init-db`):

```powershell
python web/manage.py migrate
python web/manage.py runserver 127.0.0.1:8000
```

Open `http://127.0.0.1:8000/`.

## Container smoke run

This container is a **repeatable local/demo runtime**, not a production
deployment. It uses Django's development `runserver` (same caveats as above)
and a fresh SQLite file inside the container on each run unless you mount a
volume at the database path.

```powershell
docker build -t sniplink .
docker run --rm -p 8000:8000 `
  -e SNIPLINK_DJANGO_DEBUG=false `
  -e SNIPLINK_SECRET_KEY=change-me `
  -e SNIPLINK_API_KEY=demo-key `
  sniplink
```

The image runs `migrate` before `runserver` so the dashboard is usable on first
boot. Then open `http://127.0.0.1:8000/`.

CI runs `docker build` and a lightweight HTTP smoke check on every push/PR
(`.github/workflows/ci.yml`, job `docker-smoke`).

For a persistent database across container restarts, mount the configured path
(from `sniplink.toml`, default `sniplink.db`):

```powershell
docker run --rm -p 8000:8000 `
  -v "${PWD}/data:/app/data" `
  -e SNIPLINK_DB=/app/data/sniplink.db `
  -e SNIPLINK_DJANGO_DEBUG=false `
  -e SNIPLINK_SECRET_KEY=change-me `
  sniplink
```

See `docs/production-reflection.md` for what would change in a real deployment
(Gunicorn/uvicorn, Postgres, TLS termination, rate limits, and so on).

The Django app uses a `DjangoStorage` adapter that implements the same storage
contract as the SQLite CLI/raw server path. The core service does not import
Django. Both adapters read and write the **same tables** (`links`, `clicks`,
`health_check_results`) inside `sniplink.toml#database_path`.

| You started with | Then run |
| ---------------- | -------- |
| `python web/manage.py migrate` | `sniplink` CLI commands as usual |
| `sniplink init-db` | `python web/manage.py migrate --fake-initial` |

Migration `0002` reconciles legacy `links_*` shadow tables from older checkouts.
Migration `0003` renames Django index names for CLI-first bootstrap.
Migration `0004` aligns composite click indexes and drops redundant `short_code` indexes.
Migration `0005` normalizes `metadata` for CLI-first shared databases.

### API lifecycle semantics

- `POST /api/links/{code}/disable` — **strict**: a second call on an already-disabled link returns `410 Gone`.
- `DELETE /api/links/{code}` — **idempotent**: repeat delete returns `204 No Content`.

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
| 7    | Code-assignment retry budget exhausted (`CollisionExhausted`)          |

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
| `sniplink.reserved_codes`                | _(TOML only; legacy `reserved_prefixes` accepted)_ |
| `sniplink.base_aliases`                  | _(TOML only)_                 |
| `sniplink.random_token_length`           | _(TOML only)_                 |
| `sniplink.max_destination_length`        | _(TOML only)_                 |
| `sniplink.max_request_path_bytes`        | _(TOML only)_                 |
| `sniplink.raw_http_recv_timeout`         | _(TOML only)_                 |
| `sniplink.logging.redact_keys`           | _(TOML only)_                 |
| `sniplink.api.max_body_bytes`            | `SNIPLINK_API_MAX_BODY_BYTES` |
| _(Django test DB override)_               | `SNIPLINK_DJANGO_DB`          |
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

The engine blocks **exact** short codes listed in `sniplink.toml#reserved_codes`
(default: `api`, `admin`, `dashboard`, `static`, `favicon.ico`, `links`).
The list applies to vanity aliases **and** auto-generated Base62/random codes.
Codes like `api-v2` are allowed. The legacy TOML key `reserved_prefixes` is
still accepted. Sequential Base62 ids are enumerable — see ADR 0002.

## Tests

```powershell
$env:PYTHONPATH="src;web"   # Linux/macOS: export PYTHONPATH=src:web
python -m pytest
```

The suite has **253 tests** (unit, integration, concurrency, Django). Coverage
is collected on the `sniplink` package with branch tracking; CI enforces a
**95%** aggregate floor (`--cov-fail-under=95` in `pyproject.toml`). Current
instrumented coverage is **~98%** — core, CLI, async health checker, and WSGI
modules are fully covered; Django views are tested under `tests/integration/django/`
but live outside `--cov=sniplink`.

Install dev deps before running locally:

```powershell
python -m pip install -e ".[dev]" -c requirements-lock.txt
```

`pytest-asyncio` is in the `dev` extras and is required for the
`asyncio_mode = "auto"` pytest setting. Without it, the suite still runs but
emits an "Unknown config option" warning (suppressed via `filterwarnings`).

Concurrency tests fan multiple threads against a shared SQLite file in WAL
mode; the `UNIQUE(short_code)` constraint decides who wins a same-alias race.
See ADR 0004 and `tests/conftest.py`.

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

## Known limitations

- **Enumerable Base62 codes** — sequential ids produce guessable short codes (`/1`, `/2`); use `--random` or vanity aliases when that matters (ADR 0002).
- **Dev defaults** — `DEBUG=true` and a static `SECRET_KEY` in `settings.py`; set `SNIPLINK_DJANGO_DEBUG=false` and `SNIPLINK_SECRET_KEY` for non-local runs (see `docs/security.md`).
- **Single-file SQLite** — not HA; production would use Postgres behind the same `Storage` contract.
- **HTMX stats vs API stats** — when `SNIPLINK_API_KEY` is set, direct browser access to `/links/{code}/stats` requires the key; dashboard HTMX stats remain same-origin.
- **JSON metadata on CLI-first DBs** — migration `0005` normalizes rows; full `JSON_VALID` enforcement applies on greenfield `schema.sql` bootstrap.

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

- [Architecture overview](docs/architecture.md)
- [Defense FAQ](docs/defense-faq.md)
- [Security & privacy](docs/security.md)
- [Submission checklist](docs/submission-checklist.md)
- [Protocol evidence](docs/protocol-evidence.md)
- [Demo script](docs/demo-script.md)
- [Production reflection](docs/production-reflection.md) (includes container vs production notes)
- [Milestone timeline](docs/planning/timeline.md)
- Architecture decision records live in [docs/adr](docs/adr).

## Cross-platform notes

Commands above use PowerShell line continuation (backtick). On Linux/macOS use
`\` instead, or single-line commands. Set `PYTHONPATH=src:web` when running
pytest outside Windows.

## Submission

Tag the hand-in commit:

```powershell
git tag -a v1.0-capstone -m "Capstone submission"
```

Smoke-run `docs/submission-checklist.md` before submitting.
