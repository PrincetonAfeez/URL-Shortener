# Architecture Decision Record
## App — URL Shortener
**Redirect Systems Group | Document 1 of 5**
**Status: Accepted**

---

## Context

The Redirect Systems group requires a capstone URL shortener named `sniplink` that demonstrates HTTP, TCP sockets, redirect semantics, WSGI, Django, SQLite, JSON APIs, and asyncio without duplicating business logic across front ends.

The core design problem is deceptively simple: accept a destination URL, assign a short code, resolve that short code into an HTTP redirect, record click analytics, and enforce lifecycle rules. The project expands that problem across multiple protocol layers:

```text
CLI / raw socket HTTP / WSGI / Django + HTMX / JSON API / async tools
    -> framework-free core service
        -> storage interface
            -> SQLite adapter or Django ORM adapter
```

The selected architecture keeps the redirect engine framework-free. CLI commands, the raw TCP server, the hand-written WSGI app, Django views, JSON API endpoints, and async health checks are all adapters over the same service and storage contract.

---

## Decisions

### Decision 1 — Use one framework-free service as the engine

**Chosen:** `SniplinkService` owns link creation, code assignment, resolution, click recording, lifecycle transitions, stats access, validation, and collision retry behavior.

**Rejected:** Letting the CLI, raw server, WSGI app, Django views, and JSON API each implement their own URL-shortening logic.

**Reason:** Redirect behavior must stay consistent across every front end. One core service prevents drift and makes testing easier.

---

### Decision 2 — Depend on a storage protocol, not a concrete database

**Chosen:** Define a `Storage` protocol implemented by SQLite and Django ORM adapters.

**Rejected:** Importing SQLite directly throughout the service or making the Django ORM the only persistence layer.

**Reason:** The capstone is meant to show the same engine behind multiple front ends. A storage protocol keeps the core independent from framework concerns.

---

### Decision 3 — Share canonical table names across SQLite and Django

**Chosen:** Use `links`, `clicks`, and `health_check_results` as the shared canonical tables.

**Rejected:** Maintaining separate CLI tables and Django tables.

**Reason:** Users can initialize with the CLI or Django first, then use the other adapter against the same database. The schema and Django model `db_table` settings keep both sides aligned.

---

### Decision 4 — Use sequential Base62 codes by default

**Chosen:** Insert a pending row, use its database id, then encode that id with Base62.

**Rejected:** Pure random tokens only.

**Reason:** Sequential Base62 makes code generation explainable and demonstrates how short codes can be derived from database ids. The design explicitly documents that enumerable codes are a known trade-off.

---

### Decision 5 — Support random tokens as an alternate strategy

**Chosen:** Provide `--random` / `code_strategy="random"` using `RandomTokenCodec` with cryptographic randomness from `secrets.choice()`.

**Rejected:** Forcing all users onto enumerable Base62 codes.

**Reason:** Random codes provide a better option when enumeration matters, while keeping Base62 as the teaching baseline.

---

### Decision 6 — Use exact reserved short codes

**Chosen:** Block exact reserved codes such as `api`, `admin`, `dashboard`, `static`, `favicon.ico`, and `links`.

**Rejected:** Blocking prefixes such as all codes beginning with `api`.

**Reason:** Exact blocking protects important routes while keeping valid codes like `api-v2` available.

---

### Decision 7 — Validate destination URLs before storage

**Chosen:** Normalize destination URLs by allowing only `http` and `https`, requiring a host, removing fragments and userinfo, rejecting self-reference, enforcing a max length, and normalizing default ports.

**Rejected:** Storing user input as-is.

**Reason:** URL shorteners are redirect systems. Unsafe destinations and self-referential redirects can create broken loops or credential leakage.

---

### Decision 8 — Enforce lifecycle gates before redirect

**Chosen:** Links can be active, expired, disabled, soft-deleted, or click-capped. Resolution rejects deleted/disabled/expired links and uses the storage layer to atomically enforce max-click limits.

**Rejected:** Checking lifecycle state only in UI/API adapters.

**Reason:** Every redirect path must behave the same way. Lifecycle enforcement belongs in the core and storage contract.

---

### Decision 9 — Record clicks atomically in storage

**Chosen:** The storage adapters must increment `click_count` with a conditional update that also checks disabled/deleted/expired/max-click state, then insert the click row.

**Rejected:** Read the link, check `click_count`, then update in a separate step.

**Reason:** Concurrent redirects could otherwise exceed `max_clicks`. The conditional update makes the quota check and increment one atomic operation.

---

### Decision 10 — Make raw socket HTTP a teaching adapter

**Chosen:** Implement a small raw TCP server that calls `socket()`, `bind()`, `listen()`, `accept()`, `recv()`, and `sendall()`.

**Rejected:** Using only Django development server or only WSGI.

**Reason:** The capstone must show HTTP redirects over raw TCP. The raw server makes request parsing and response serialization visible.

---

### Decision 11 — Keep WSGI as a parallel protocol demonstration

**Chosen:** Implement a hand-written WSGI app using `environ`, `start_response`, and byte iterables.

**Rejected:** Treating Django as the only WSGI example.

**Reason:** WSGI is the bridge between raw HTTP and web frameworks. A small hand-written app shows that boundary clearly.

---

### Decision 12 — Use Django + HTMX as the dashboard adapter

**Chosen:** Add a Django dashboard and JSON API on top of the same core service through `DjangoStorage`.

**Rejected:** Making the project only a CLI/raw-server exercise.

**Reason:** The project needs to show how the same domain engine can power a higher-level web framework and interactive UI.

---

### Decision 13 — Keep redirect path synchronous; use asyncio for health checks

**Chosen:** The redirect path stays synchronous. Asyncio is used for concurrent outbound HEAD health checks.

**Rejected:** Forcing asyncio into WSGI/Django redirect handling.

**Reason:** WSGI is synchronous by design. Health checking is a better educational fit for asyncio because it performs many outbound network requests with timeouts and a concurrency cap.

---

### Decision 14 — Do not add application caching for redirects

**Chosen:** No in-process redirect lookup cache. Redirect responses use `Cache-Control: no-store`.

**Rejected:** Add an LRU cache around short-code resolution.

**Reason:** Link lifecycle transitions create invalidation requirements. The project avoids a cache until it can handle disabled, deleted, expired, and click-capped states correctly.

---

### Decision 15 — Use stable CLI exit codes

**Chosen:** Map not found, gone, alias conflict, collision exhaustion, usage errors, and generic failures to stable exit codes.

**Rejected:** Returning only `0` or `1`.

**Reason:** URL shortener CLI commands are scriptable. Stable exit codes make automation safer.

---

## Consequences

**Positive:**
- All adapters share one core service.
- SQLite and Django ORM can operate on the same tables.
- Raw socket, WSGI, Django, API, CLI, and async paths are all demonstrated.
- Redirect semantics are consistent across front ends.
- Click caps are protected by atomic storage updates.
- Reserved codes protect framework/API routes.
- API errors use envelopes and status mapping.
- Health checks demonstrate asyncio without complicating the redirect path.
- Test coverage can focus on the framework-free core and adapter contracts.

**Negative / Trade-offs:**
- Base62 codes are enumerable.
- SQLite is not a high-availability production store.
- No redirect cache means every redirect checks storage.
- WSGI demo server is development-only.
- Django and SQLite adapters must be kept schema-compatible.
- Async health checker records total elapsed time, not DNS/connect/TLS/TTFB breakdowns.
- API-key auth exists, but full auth/rate-limiting is out of scope.

---

## Alternatives Not Explored

- PostgreSQL as primary production store.
- Redis caching for redirects.
- Distributed ID generation.
- QR code generation.
- Geo/device analytics.
- User accounts and ownership.
- Bulk import/export.
- Public CORS-enabled API.
- ASGI-native redirect app.
- Rate-limited API gateway.
- Non-enumerable random tokens as the only strategy.

---

*Constitution reference: Article 1 (Python fundamentals and architectural thinking), Article 3.3 (scope discipline), Article 4 (quality proportional to scope), Article 5 (trade-off documentation), Article 6 (behavior verification), and Article 7 (progressive complexity).*

---


# Technical Design Document
## App — URL Shortener
**Redirect Systems Group | Document 2 of 5**

---

## Overview

`sniplink` is a Python URL-shortener capstone that exposes a framework-free redirect engine through multiple front ends:

- CLI commands
- raw socket HTTP redirect server
- hand-written WSGI app
- Django + HTMX dashboard
- JSON API
- asyncio health checker

**Distribution:** `sniplink`  
**Python:** `>=3.11`  
**Runtime dependency:** Django `>=5.0,<6.0`  
**Primary command:** `sniplink`  
**Primary engine:** `SniplinkService`  
**Primary persistence:** SQLite file with optional Django ORM adapter  
**Coverage gate:** 95% aggregate on `sniplink`

---

## System Context

```text
CLI command
Raw socket HTTP server
Hand-written WSGI app
Django + HTMX dashboard
JSON API
Async health checker
  │
  ▼
SniplinkService
  │
  ├── validation
  ├── lifecycle gates
  ├── code assignment
  ├── click recording
  ├── stats access
  └── health result persistence
  │
  ▼
Storage protocol
  ├── SQLiteStorage
  └── DjangoStorage
        │
        ▼
links / clicks / health_check_results
```

---

## Module-Level Structure

```text
URL-Shortener/
  src/sniplink/
    __init__.py
    models.py
    exceptions.py
    config.py
    core/
      service.py
      factory.py
      validation.py
      lifecycle.py
    codecs/
      base62.py
      base58.py
      random_token.py
    storage/
      base.py
      sqlite_store.py
      schema.sql
    raw_http/
      server.py
      request_parser.py
      response_writer.py
    wsgi_app/
      app.py
    api/
      errors.py
      serializers.py
      validation.py
    async_tools/
      health_checker.py
    cli/
      main.py
      exit_codes.py
      output.py
    observability/
  web/
    manage.py
    sniplink_web/
      settings.py
      urls.py
    links/
      models.py
      views.py
      storage_adapter.py
      migrations/
      templates/
  tests/
  pyproject.toml
  requirements.txt
  requirements-lock.txt
  sniplink.toml
```

---

## Core Data Flow — Create Link

```text
adapter receives destination URL
  │
  ▼
SniplinkService.create_link()
  ├── choose redirect status
  ├── validate max_clicks
  ├── validate future expiry
  ├── normalize destination URL
  ├── reject self-reference
  ├── if alias: validate exact alias and insert
  ├── if base62:
  │     ├── insert pending __pending_<uuid> row
  │     ├── encode database id with Base62
  │     ├── reject reserved code
  │     ├── update pending row to final short code
  │     └── retry on collision up to limit
  └── if random:
        ├── generate random token
        ├── reject reserved code
        ├── insert row
        └── retry on collision up to limit
```

---

## Core Data Flow — Resolve Link

```text
GET /<code> or service.resolve(code)
  │
  ▼
reject reserved code
  │
  ▼
storage.get_link(code)
  │
  ▼
ensure_link_available()
  ├── deleted -> gone
  ├── disabled -> gone
  └── expired -> gone
  │
  ▼
record_click?
  ├── HEAD / resolve -- no click: read-only quota check
  └── GET redirect:
        storage.record_click()
          ├── conditional UPDATE increments click_count
          ├── checks disabled/deleted/expired/max_clicks atomically
          └── inserts click row
  │
  ▼
RedirectDecision(short_code, destination_url, status_code, link)
```

---

## Core Models

### `Link`

Represents one short link.

Fields:
- `id`
- `short_code`
- `destination_url`
- `redirect_status`
- `created_at`
- `expires_at`
- `disabled_at`
- `deleted_at`
- `max_clicks`
- `click_count`
- `metadata`

---

### `Click`

Represents one tracked redirect event.

Fields:
- `id`
- `link_id`
- `clicked_at`
- `referrer`
- `user_agent`

The project intentionally does not store client IP addresses by default.

---

### `RedirectDecision`

Result returned by the core service when a code resolves.

Fields:
- `short_code`
- `destination_url`
- `status_code`
- `link`

---

### `HealthCheckResult`

Result of the async outbound health checker.

Fields:
- `link_id`
- `checked_at`
- `status_code`
- `error`
- `elapsed_ms`
- `redirect_count`

---

## Storage Contract

The `Storage` protocol declares:

- `initialize()`
- `insert_link()`
- `insert_pending_link()`
- `update_short_code()`
- `delete_pending_link()`
- `get_link()`
- `get_link_by_id()`
- `list_links()`
- `mark_disabled()`
- `mark_deleted()`
- `set_expiry()`
- `record_click()`
- `stats()`
- `save_health_result()`

The most important contract rule is `record_click()`: implementations must atomically gate max-click limits with the same update that increments `click_count`.

---

## SQLite Storage Design

`SQLiteStorage`:
- creates parent directory when needed
- initializes from `storage/schema.sql`
- sets WAL mode during initialization
- opens per-operation connections with `foreign_keys=ON`
- closes connections reliably
- distinguishes unique constraint failures from other `IntegrityError` cases
- uses pending `__pending_<uuid>` rows for Base62 assignment
- cleans stale pending rows
- soft-deletes links with `deleted_at`
- stores click and health rows
- serializes metadata as JSON text

Canonical tables:
- `links`
- `clicks`
- `health_check_results`

---

## Django Storage Design

`DjangoStorage` implements the same storage protocol using Django ORM models.

Important behavior:
- `insert_link()` maps `IntegrityError` to `AliasTaken`
- `update_short_code()` uses `select_for_update()`
- pending links use the same `__pending_` pattern
- `record_click()` uses a conditional `UPDATE` with `F("click_count") + 1`
- `stats()` reads recorded clicks through the `clicks` relation
- `save_health_result()` writes to the shared health table
- model `db_table` values align with SQLite schema

---

## Codecs

### `Base62Codec`

Alphabet:
```text
0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ
```

Behavior:
- validates unique alphabet
- encodes non-negative integers
- returns the first alphabet character for `0`
- decodes by multiplying base and adding character indexes
- rejects invalid characters

---

### `RandomTokenCodec`

Behavior:
- validates positive length
- defaults to Base62 alphabet
- generates `length` random characters with `secrets.choice()`
- does not encode/decode integers

---

## Validation Rules

Destination URL:
- required
- trimmed
- length-limited
- scheme must be `http` or `https`
- host required
- default ports removed
- userinfo removed
- fragment removed
- self-reference rejected against configured base URL and aliases

Alias:
- regex: `^[A-Za-z0-9_-]{1,64}$`
- lowercased
- exact reserved-code match rejected
- `__pending_` prefix rejected

Redirect status:
- allowed: `301`, `302`, `307`, `308`

Max clicks:
- `None` or integer at least `1`

Expiry:
- must be future if provided

---

## Raw HTTP Server

`RawHTTPServer`:
- creates a TCP socket
- sets `SO_REUSEADDR`
- binds/listens/accepts
- reads request headers up to a byte limit
- times out slow clients
- parses request line and headers
- supports `GET` and `HEAD`
- rejects unsupported methods with `405` and `Allow: GET, HEAD`
- rejects too-long paths with `414`
- extracts only single-segment short codes
- resolves through `SniplinkService`
- sends manual HTTP/1.1 redirect or error bytes
- always closes the connection
- keeps serving after malformed requests

---

## WSGI App

The hand-written WSGI app:
- receives `environ`
- reads method and `PATH_INFO`
- supports `GET` and `HEAD`
- rejects unsupported methods with `405`
- rejects long paths with `414`
- rejects missing/reserved codes
- resolves through `SniplinkService`
- returns redirects with `Location`, `Cache-Control: no-store`, and `Content-Length: 0`
- maps missing code to `404`
- maps gone lifecycle states to `410`
- returns bodyless responses for `HEAD`

---

## Django / HTMX / API Design

Django uses:
- `Link`
- `Click`
- `HealthCheckResult`
- `DjangoStorage`
- dashboard view
- redirect view
- HTMX partials
- JSON API endpoints

Redirect view behavior:
- supports `GET` and `HEAD`
- rejects reserved codes
- enforces request path length
- records clicks only for `GET`
- returns `Location`, `Cache-Control: no-store`, and `Content-Length: 0`

Dashboard behavior:
- `GET` renders dashboard
- `POST` creates links
- HTMX requests receive partials
- lifecycle actions update partial rows

JSON API behavior:
- `POST /api/links` creates and returns `201 Created` with `Location`
- `GET /api/links/{code}` returns link details
- `DELETE /api/links/{code}` soft-deletes and returns `204`
- `POST /api/links/{code}/disable` disables and is strict
- `POST /api/links/{code}/expire` expires immediately or at supplied timestamp
- `GET /api/links/{code}/stats` returns stats
- optional API-key auth via `X-API-Key` or `Authorization: Bearer ...`
- request body cap enforces payload size

---

## Async Health Checker

`AsyncHealthChecker`:
- uses `asyncio.open_connection()` directly
- sends manual `HEAD` requests
- supports concurrency through `asyncio.Semaphore`
- follows redirects up to a limit
- records total elapsed milliseconds
- rejects private, loopback, and link-local targets by default
- can persist results through `Storage.save_health_result()` in a worker thread

---

## Error Handling

Domain exceptions include:
- `InvalidDestinationURL`
- `InvalidAlias`
- `CodeNotFound`
- `CodeExpired`
- `CodeDisabled`
- `CodeDeleted`
- `AliasTaken`
- `CollisionExhausted`
- `StorageError`
- `AuthError`
- `RedirectLimitExceeded`

API status mapping:
- bad destination/alias: `400`
- not found: `404`
- gone: `410`
- auth failure: `401`
- alias conflict: `409`
- collision exhaustion: `503`
- unsupported value: `400`
- unknown domain failure: `500`

---

## Known Limits

- Sequential Base62 codes are enumerable.
- SQLite is not HA.
- No redirect lookup cache.
- No user accounts or per-user ownership.
- No QR code generation.
- No public CORS configuration.
- No IP address storage by default.
- Health checker does not break timing into DNS/connect/TLS/TTFB.
- `wsgiref.simple_server` is single-threaded and development-only.

---

## Verification Summary

The repo configures:
- pytest 8 minimum
- strict markers and strict config
- pytest-asyncio auto mode
- pytest-django dev support
- coverage on `sniplink` with branch tracking
- coverage fail-under 95
- Ruff lint and format
- mypy strict on the framework-free core
- CI on Python 3.11 and 3.12
- integration and concurrency test markers

---

*Constitution reference: Article 4 (engineering quality), Article 6 (behavior verification), Article 7 (progressive complexity), and Article 8 (valid learner work).*

---


# Interface Design Specification
## App — URL Shortener
**Redirect Systems Group | Document 3 of 5**

---

## Public CLI Interface

### Console script

```powershell
sniplink <command> [options]
```

### Global options

| Option | Description |
|---|---|
| `--version` | Print `sniplink` version |
| `--db PATH` | Override SQLite database path |
| `--base-url URL` | Override base URL used to display short URLs |
| `--log-level LEVEL` | Override logging level |

---

## CLI Commands

### `init-db`

```powershell
sniplink init-db
```

Initializes the SQLite database and prints Django migration guidance for CLI-first setup.

---

### `create`

```powershell
sniplink create https://example.com
sniplink create https://example.com --alias demo
sniplink create https://example.com --random
sniplink create https://example.com --redirect-status 307
sniplink create https://example.com --expires-at 2026-12-31T23:59:00+00:00
sniplink create https://example.com --max-clicks 10 --json
```

Options:
- `--alias`
- `--random`
- `--redirect-status`
- `--expires-at`
- `--max-clicks`
- `--json`
- command-level `--base-url`

---

### `resolve`

```powershell
sniplink resolve demo
sniplink resolve demo --json
```

Resolves without counting a click.

---

### `list`

```powershell
sniplink list
sniplink list --include-deleted
```

Lists stored links.

---

### `stats`

```powershell
sniplink stats demo
```

Validates that the link is still resolvable without click recording, then prints JSON stats.

---

### `disable`

```powershell
sniplink disable demo
```

Marks the link disabled. Already-gone links produce a gone-style error.

---

### `delete`

```powershell
sniplink delete demo
```

Soft-deletes the link.

---

### `expire`

```powershell
sniplink expire demo
sniplink expire demo --at 2026-12-31T23:59:00+00:00
```

Sets link expiry to now or to a provided timestamp.

---

### `serve-raw`

```powershell
sniplink serve-raw --host 127.0.0.1 --port 9000
```

Runs the raw TCP redirect server.

---

### `serve-wsgi`

```powershell
sniplink serve-wsgi --host 127.0.0.1 --port 9100
```

Runs the hand-written WSGI app on `wsgiref.simple_server`.

---

### `check-health`

```powershell
sniplink check-health --concurrency 10 --timeout 5
sniplink check-health --allow-private
```

Runs concurrent async HEAD checks against active destination URLs and persists results.

---

## CLI Exit Codes

| Code | Meaning |
|---:|---|
| `0` | Success |
| `1` | Generic runtime failure |
| `2` | Usage error / invalid flag value |
| `4` | Short code not found |
| `5` | Link is gone: expired, disabled, or deleted |
| `6` | Alias conflict |
| `7` | Collision retry budget exhausted |

---

## Public Python Interface

### Core import

```python
from sniplink.core import SniplinkService
from sniplink.storage import SQLiteStorage
from sniplink.core.factory import build_sniplink_service
from sniplink.config import load_config
```

### Example

```python
from sniplink.config import load_config
from sniplink.core.factory import build_sniplink_service
from sniplink.storage import SQLiteStorage

config = load_config()
storage = SQLiteStorage(config.database_path)
service = build_sniplink_service(storage, config)
service.initialize()

link = service.create_link("https://example.com", alias="demo")
decision = service.resolve("demo", record_click=True)
print(decision.destination_url)
```

---

## `SniplinkService` Contract

### `create_link()`

```python
create_link(
    destination_url,
    *,
    alias=None,
    code_strategy="base62",
    redirect_status=None,
    expires_at=None,
    max_clicks=None,
    metadata=None,
) -> Link
```

Rules:
- validates destination URL
- validates alias when provided
- uses configured default redirect status when omitted
- supports only `301`, `302`, `307`, `308`
- supports `base62` and `random` strategies
- rejects past expiry
- rejects `max_clicks < 1`
- retries code collisions up to limit

---

### `resolve()`

```python
resolve(
    short_code,
    *,
    record_click=True,
    referrer=None,
    user_agent=None,
) -> RedirectDecision
```

Behavior:
- reserved code => not found
- missing code => not found
- deleted/disabled/expired/capped => gone
- `record_click=False` performs read-only lifecycle/quota gate
- `record_click=True` records click atomically

---

### Lifecycle methods

```python
disable_link(short_code) -> Link
delete_link(short_code) -> Link
expire_link(short_code, when) -> Link
list_links(include_deleted=False) -> list[Link]
list_active_links() -> list[Link]
stats(short_code) -> dict
```

---

## Raw HTTP Interface

### Request

```http
GET /demo HTTP/1.1
Host: localhost:9000
```

```http
HEAD /demo HTTP/1.1
Host: localhost:9000
```

### Success response

```http
HTTP/1.1 302 Found
Location: https://example.com
Cache-Control: no-store
Content-Length: 0
Connection: close
```

Allowed redirect status codes:
- `301`
- `302`
- `307`
- `308`

### Error responses

| Condition | Status |
|---|---:|
| malformed request | `400` |
| missing code | `404` |
| reserved code | `404` |
| code not found | `404` |
| disabled / deleted / expired / capped | `410` |
| unsupported method | `405` + `Allow: GET, HEAD` |
| path too long | `414` |
| internal domain error | `500` |

`HEAD` returns headers without body.

---

## WSGI Interface

The WSGI app is built with:

```python
from sniplink.wsgi_app import make_app

app = make_app(service, reserved_codes=config.reserved_codes)
```

Contract:
- reads `REQUEST_METHOD`
- reads `PATH_INFO`
- returns iterable of bytes
- calls `start_response(status, headers)`
- supports `GET` and `HEAD`
- uses same redirect and error semantics as raw socket server

---

## Django Web Interface

### Dashboard

```text
GET /
POST /
```

Behavior:
- `GET` renders dashboard
- `POST` creates a link
- HTMX POST returns partial success/error blocks
- lifecycle actions are CSRF-protected form posts

### Redirect

```text
GET /<code>
HEAD /<code>
```

Behavior:
- `GET` records clicks
- `HEAD` resolves without click
- success returns redirect response
- not found returns `404`
- gone returns `410`

---

## JSON API Interface

### Create link

```http
POST /api/links
Content-Type: application/json
```

Payload:

```json
{
  "url": "https://example.com",
  "alias": "demo",
  "strategy": "base62",
  "redirect_status": 302,
  "expires_at": null,
  "max_clicks": null,
  "metadata": {}
}
```

Response:
- `201 Created`
- `Location` header set to short URL
- JSON link payload

---

### Link detail

```http
GET /api/links/demo
```

Returns JSON link payload or error envelope.

---

### Delete link

```http
DELETE /api/links/demo
```

Returns `204 No Content`. Delete is idempotent at the API lifecycle level.

---

### Disable link

```http
POST /api/links/demo/disable
```

Strict lifecycle behavior: disabling an already-disabled/gone link returns gone-style error.

---

### Expire link

```http
POST /api/links/demo/expire
Content-Type: application/json
```

Payload:

```json
{"expires_at": "2026-12-31T23:59:00+00:00"}
```

Empty payload expires immediately.

---

### Stats

```http
GET /api/links/demo/stats
```

Returns stats JSON.

---

## API Auth Contract

When `SNIPLINK_API_KEY` is set, JSON API calls require one of:

```http
X-API-Key: <key>
```

or:

```http
Authorization: Bearer <key>
```

Comparison uses constant-time `secrets.compare_digest()`.

---

## API Error Envelope

```json
{
  "error": {
    "type": "InvalidDestinationURL",
    "message": "only http and https URLs are allowed"
  }
}
```

---

## Configuration Interface

Source:

```text
sniplink.toml
```

Precedence:

```text
function argument / CLI --db > environment variable > TOML > dataclass default
```

Important environment variables:
- `SNIPLINK_DB`
- `SNIPLINK_BASE_URL`
- `SNIPLINK_REDIRECT_STATUS`
- `SNIPLINK_COLLISION_RETRIES`
- `SNIPLINK_API_MAX_BODY_BYTES`
- `SNIPLINK_LOG_LEVEL`
- `SNIPLINK_LOG_FORMAT`
- `SNIPLINK_API_KEY`
- `SNIPLINK_DJANGO_DB`

---

## Database Interface

Canonical tables:

```text
links
clicks
health_check_results
```

Important constraints:
- `links.short_code` is unique
- redirect status limited to `301`, `302`, `307`, `308`
- `max_clicks` must be null or at least `1`
- `click_count` cannot be negative
- metadata must be valid JSON
- clicks cascade on link delete

---

*Constitution reference: Article 4 (input/output boundaries), Article 6 (verification), and Article 8 (understandable and verifiable work).*

---


# Runbook
## App — URL Shortener
**Redirect Systems Group | Document 4 of 5**

---

## Requirements

### Runtime

- Python 3.11 or newer
- Django 5.x
- SQLite

### Development

- pytest
- pytest-asyncio
- pytest-cov
- pytest-django
- Ruff
- mypy
- django-stubs

---

## Installation

### Full contributor setup

```powershell
python -m pip install -r requirements.txt
python -m pip install -e ".[dev]" -c requirements-lock.txt
```

### Runtime-only setup

```powershell
python -m pip install -r requirements.txt
python -m pip install -e .
```

---

## Quick Start — CLI + Raw Server

```powershell
sniplink init-db
sniplink create https://example.com
sniplink list
sniplink serve-raw --port 9000
```

In another terminal:

```powershell
curl -v http://localhost:9000/1
```

Expected:
- HTTP redirect response
- `Location` header points at destination
- `Cache-Control: no-store`
- `Content-Length: 0`

---

## Quick Start — Django Dashboard

### Existing CLI-created database

```powershell
python web/manage.py migrate --fake-initial
python web/manage.py runserver 127.0.0.1:8000
```

### Greenfield Django-first database

```powershell
python web/manage.py migrate
python web/manage.py runserver 127.0.0.1:8000
```

Open:

```text
http://127.0.0.1:8000/
```

---

## Standard Operations

### Create a short link

```powershell
sniplink create https://example.com --alias demo
```

---

### Create a random-code link

```powershell
sniplink create https://example.com --random
```

---

### Resolve without click

```powershell
sniplink resolve demo
```

---

### Show stats

```powershell
sniplink stats demo
```

---

### Disable

```powershell
sniplink disable demo
```

---

### Soft-delete

```powershell
sniplink delete demo
```

---

### Expire immediately

```powershell
sniplink expire demo
```

---

### Run WSGI demo

```powershell
sniplink serve-wsgi --port 9100
```

---

### Run health checks

```powershell
sniplink check-health --concurrency 10 --timeout 5
```

For local URLs:

```powershell
sniplink check-health --allow-private
```

---

## JSON API Smoke Test

```powershell
curl -i -X POST http://127.0.0.1:8000/api/links `
  -H "Content-Type: application/json" `
  -d "{\"url\":\"https://example.com\",\"alias\":\"demo\"}"

curl -i http://127.0.0.1:8000/api/links/demo
curl -i http://127.0.0.1:8000/api/links/demo/stats
curl -i -X POST http://127.0.0.1:8000/api/links/demo/disable
curl -i -X DELETE http://127.0.0.1:8000/api/links/demo
```

With API key:

```powershell
$env:SNIPLINK_API_KEY="dev-key"
curl -i http://127.0.0.1:8000/api/links/demo -H "X-API-Key: dev-key"
```

---

## Health Checks

### CLI version

```powershell
sniplink --version
```

Expected:
```text
sniplink 0.1.0
```

---

### Database initialization

```powershell
sniplink init-db
```

Expected:
- database file exists
- `links`, `clicks`, and `health_check_results` tables exist

---

### Raw redirect

```powershell
curl -i http://localhost:9000/demo
```

Expected:
- `301`, `302`, `307`, or `308`
- `Location` header
- no response body

---

### Gone link

```powershell
sniplink disable demo
curl -i http://localhost:9000/demo
```

Expected:
```text
410 Gone
```

---

### Not found link

```powershell
curl -i http://localhost:9000/missing
```

Expected:
```text
404 Not Found
```

---

## Running Tests

```powershell
$env:PYTHONPATH="src;web"
python -m pytest
```

Linux/macOS:

```bash
PYTHONPATH=src:web python -m pytest
```

---

## Quality Gates

### Ruff

```powershell
python -m ruff check .
python -m ruff format --check .
```

### Mypy

```powershell
python -m mypy src/sniplink/core
```

### Coverage

```powershell
python -m pytest --cov-report=html
```

CI enforces:

```text
--cov-fail-under=95
```

---

## CI Parity

GitHub Actions runs:
- Python 3.11 and 3.12
- install runtime requirements
- install editable dev package with lock constraints
- Ruff lint
- Ruff format check
- mypy on `src/sniplink/core`
- pytest with coverage
- coverage artifact upload on Python 3.11

---

## Failure Modes

### Invalid destination URL

Common causes:
- missing URL
- unsupported scheme
- missing host
- self-reference
- URL too long

Expected:
- CLI usage/failure output
- API `400`

---

### Invalid alias

Common causes:
- invalid characters
- too long
- reserved exact code
- `__pending_` prefix

Expected:
- API `400`
- CLI usage/failure output

---

### Alias conflict

Cause:
- duplicate short code

Expected:
- CLI exit code `6`
- API `409`

---

### Collision retry exhausted

Cause:
- Base62/random assignment collided until retry limit exhausted

Expected:
- CLI exit code `7`
- API `503`

---

### Gone link

Cause:
- expired
- disabled
- soft-deleted
- max clicks exhausted

Expected:
- raw/WSGI/Django redirect path returns `410`
- CLI exit code `5`
- API `410`

---

### API unauthorized

Cause:
- `SNIPLINK_API_KEY` is set but missing/wrong key supplied

Expected:
- API `401`

---

### Body too large

Cause:
- API request exceeds configured body cap

Expected:
- API `413`

---

### Raw server method not allowed

Cause:
- non-GET/HEAD request to raw redirect server

Expected:
- `405 Method Not Allowed`
- `Allow: GET, HEAD`

---

### Health checker rejects private host

Cause:
- destination resolves to private, loopback, or link-local address

Expected:
- error recorded unless `--allow-private` is supplied

---

## Troubleshooting Decision Tree

```text
Short link does not redirect
  ├── Does the code exist?
  │     └── sniplink resolve <code>
  ├── Is the link gone?
  │     ├── disabled_at set?
  │     ├── deleted_at set?
  │     ├── expires_at in past?
  │     └── max_clicks exhausted?
  ├── Is the path reserved?
  │     └── check reserved_codes in sniplink.toml
  ├── Is the raw/WSGI/Django adapter using the same DB?
  │     └── inspect SNIPLINK_DB / sniplink.toml / SNIPLINK_DJANGO_DB
  ├── Is Django migrated against a CLI-first DB?
  │     └── run migrate --fake-initial when appropriate
  └── Is request method unsupported?
        └── use GET or HEAD
```

---

## Maintenance Notes

- Keep `SniplinkService` framework-free.
- Preserve the `Storage` protocol boundary.
- Keep SQLite schema and Django `db_table` models aligned.
- Add tests before changing lifecycle semantics.
- Add tests before changing reserved-code behavior.
- Keep max-click enforcement atomic in both storage adapters.
- Do not add redirect caching without invalidation design.
- Keep raw server and WSGI redirect behavior in parity.
- Keep API error envelopes stable.
- Keep API-key handling constant-time.

---

*Constitution reference: Article 6 (behavior verification), Article 5 (constraints and trade-offs), and Article 8 (verifiable learner work).*

---


# Lessons Learned
## App — URL Shortener
**Redirect Systems Group | Document 5 of 5**

---

## Why This Design Was Chosen

This design was chosen because URL shortening is a strong capstone for protocol and architecture work. The redirect itself is simple, but the surrounding boundaries are not: raw TCP, HTTP request parsing, status codes, WSGI, Django, JSON APIs, SQLite constraints, click analytics, lifecycle transitions, and async health checks all intersect.

The most important decision was to keep the engine framework-free. `SniplinkService` is the center. Everything else is an adapter. That makes the project more than a Django app or a CLI script. It becomes a demonstration of layered architecture.

The second important decision was to make SQLite and Django share the same table names. This turns persistence into a real adapter problem rather than a duplicate data problem.

---

## What Was Intentionally Omitted

**User accounts:** The project demonstrates short-link mechanics, not ownership or authentication workflows.

**Redirect cache:** Caching was omitted because disabled, expired, deleted, and max-click states make invalidation non-trivial.

**Rate limiting:** API/request rate limiting is a stretch goal, not core V1 behavior.

**CORS:** Dashboard and API share an origin; cross-origin scripted access is out of scope.

**QR codes:** Useful, but not central to protocol learning.

**Geo analytics:** Would require IP storage or external lookup, which expands privacy scope.

**PostgreSQL:** SQLite is enough for the capstone; the storage contract leaves room for Postgres later.

**ASGI-first app:** WSGI was chosen intentionally to show the synchronous Python web boundary.

---

## Biggest Weakness

The biggest weakness is enumerable sequential Base62 codes. They are easy to teach and easy to test, but they are guessable. The project correctly documents this rather than hiding it. Random tokens exist when enumeration matters.

The second weakness is single-file SQLite. It is excellent for a capstone and local demos, but a production service would need a more robust database and operational backup strategy.

The third weakness is lack of caching. That is a deliberate trade-off. Correctness around lifecycle state is more important than optimizing redirect lookup prematurely.

---

## Scaling Considerations

**If traffic grows:**
- move persistence to PostgreSQL behind the same `Storage` contract
- add connection pooling at the database layer
- measure redirect latency before adding cache
- add structured metrics for redirect decisions

**If privacy requirements grow:**
- keep IP storage off by default
- add retention policies for click rows
- redact more headers in observability
- document analytics limits clearly

**If public API use grows:**
- add real authentication and API keys per user
- add rate limiting
- add CORS only when there is a trusted browser client story
- add idempotency keys for create operations

**If redirect cache is added:**
- design invalidation for disable/delete/expire/max-click transitions
- keep single-process vs multi-process behavior explicit
- avoid stale cache serving gone links

---

## What the Next Refactor Would Be

1. **PostgreSQL storage adapter** — prove the storage protocol can support a production-grade database.

2. **Structured redirect metrics** — track adapter, code, status, and lookup timing through a consistent observability pipeline.

3. **Idempotent API create support** — add an idempotency-key pattern for API clients.

4. **Redirect cache experiment** — only after defining invalidation for every lifecycle transition.

5. **More detailed health timing** — break elapsed time into DNS, connect, TLS, and first byte phases.

---

## What This Project Taught

- **Adapters are powerful when the core is clean.** The same engine can power CLI, raw sockets, WSGI, Django, JSON API, and async tooling.

- **Redirects are lifecycle decisions.** A short code is not just found/not found; it can be disabled, deleted, expired, capped, or active.

- **Atomic updates matter.** `max_clicks` cannot be enforced safely with a separate read and update.

- **Reserved routes protect the app.** Codes like `api` and `admin` should not compete with application paths.

- **WSGI is worth understanding.** It clarifies how Django receives HTTP without requiring Django internals first.

- **Asyncio belongs where it fits.** Concurrent outbound health checks are a better use of asyncio than forcing async into a WSGI redirect path.

- **Production claims need production behavior.** The README correctly calls out dev defaults, enumerable codes, SQLite limits, and `wsgiref` limits.

---

*Constitution v2.0 checklist: This document satisfies Article 5 (trade-off documentation), Article 6 (verification), and Article 7 (progressive complexity) for URL Shortener.*
