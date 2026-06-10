# Capstone Timeline

Calendar plan for the sniplink milestones. Fill in real dates against your
submission deadline. The week-numbers are placeholders; substitute the
actual ISO weeks.

## Milestone calendar

| Week | Milestone | Definition of done |
| ---- | --------- | ------------------ |
| W-10 | **0 — Scaffold** | `pyproject.toml`, `sniplink.toml`, `.gitignore`, `LICENSE`, CI green, README skeleton, ADR 0001 stub. |
| W-9  | **1 — Core engine** | `core/service.py` create + resolve, `SQLiteStorage`, Base62 codec, dataclass models, unit tests for codec round-trip. |
| W-8  | **2 — Collision & lifecycle** | Random-token codec, vanity aliases, `UNIQUE` constraint, retry budget, `CollisionExhausted`, expiry / disable / soft-delete. Concurrency test passes. ADR 0002 + 0004 written. |
| W-7  | **3 — CLI** | `sniplink create / resolve / list / stats / disable / delete / expire`, TOML config, JSON + table output, exit codes. Integration test `test_cli.py` passes. |
| W-6  | **4 — Raw socket HTTP** | `socket()` lifecycle, GET + HEAD redirect, 400/404/405/410/414, `curl -v` demo captured in `docs/protocol-evidence.md`. |
| W-5  | **5 — Hand-written WSGI** | `environ` + `start_response`, same redirect behavior as raw socket, `wsgiref.simple_server` driver. ADR 0005 written. |
| W-4  | **6 — Django + HTMX** | Storage adapter, redirect view, dashboard form, link list, stats panel, disable/delete via HTMX, CSRF wired through `hx-headers`. 404/410 templates render. |
| W-3  | **7 — JSON API** | `POST /api/links` returns `201 Created` + `Location`, alias clash returns `409`, body cap returns `413`, JSON error envelope, `tests/integration/django/test_api_basic.py` passes. |
| W-2  | **8 — Async health checker** | `asyncio.open_connection` HEAD, concurrency cap, total timeout, private-host guard, `sniplink check-health`. ADR 0006 written. |
| W-1  | **9 — Documentation + defense prep** | ADRs 0001–0007 final, `protocol-evidence.md`, `demo-script.md`, `production-reflection.md`, README polish, coverage gate at **80%** (`core ≥ 85%`). |
| W-0  | **10 — Submission** | Tag the release, smoke-run every demo from `demo-script.md`, hand in. |

## Stretch backlog (only after Milestone 9 ships)

These have explicit "do not pull forward" markers so the protocol thesis
does not get diluted:

- Full API-key auth (rotation, scopes, rate limits) — optional ``SNIPLINK_API_KEY`` env gate ships in core; hardened auth stays stretch (extends ADR 0005).
- Token-bucket rate limiter (`429 Too Many Requests`, `Retry-After`).
- Interstitial preview page (phishing safety).
- Idempotent long-URL dedup (extends ADR 0002).
- Bulk CSV import via `sniplink import`.
- QR codes in the dashboard.
- Geo + advanced UA-family breakdown.
- Caching layer with documented invalidation (extends ADR 0007).
- `asyncio.open_connection` TLS-phase timing (extends ADR 0006).

## Risk register

| Risk | Mitigation |
| ---- | ---------- |
| Scope creep into auth, rate limit, caching | Hard rule — touch nothing on the stretch list until Milestone 9 ships. |
| Tests pass for the wrong reason (SQLite serializes writers) | `concurrent_sqlite_db_path` fixture + ADR 0004. |
| CLI + Django end up with split SQLite files | Settings module + CLI both read `sniplink.toml#database_path` (ADR 0005). |
| Async work creeps into the WSGI request path | ADR 0006 + integration tests covering sync redirect behavior. |
| HTMX form posts bypass CSRF | `hx-headers` in `base.html` + middleware in `sniplink_web.settings` (ADR 0005). |
