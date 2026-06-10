# ADR 0005: WSGI Placement

## Status

Accepted (2026-06-09).

## Decision

Ship a small hand-written WSGI redirect app (`sniplink.wsgi_app.app`)
alongside the raw socket server and the Django web layer. The hand-written
app handles the redirect path only; the Django app owns the dashboard and the
JSON API. **Both** sit behind a single SQLite file so the three front ends
agree about the data.

## Context

The three HTTP-shaped adapters are deliberately stacked at different levels:

1. **Raw socket server** — `socket.accept()`, hand-built response bytes.
   Proves HTTP-over-TCP.
2. **Hand-written WSGI app** — reads `environ`, calls `start_response`,
   returns an iterable of bytes. Proves the Python web server interface that
   Django can speak.
3. **Django** — same request/response idea at a higher level, with HTMX in
   front for the dashboard.

Django can also run through ASGI in modern deployments. This capstone
intentionally uses WSGI to keep the synchronous request/response boundary
visible; ASGI placement is mentioned in the production reflection but not in
scope.

### Two storage backends, one SQLite file

The CLI / raw socket / WSGI path uses `sniplink.storage.SQLiteStorage`. The
Django path uses `links.storage_adapter.DjangoStorage` (Django ORM). Both
implement `sniplink.storage.base.Storage`.

The risk is two SQLite files holding split data. The rule, enforced at the
config layer: both backends point at the same file by default
(`sniplink.toml#database_path`). The Django settings module reads
`SNIPLINK_DJANGO_DB` to allow per-test isolation, but in normal runs Django
and the CLI see the same links. This is the single most important
"do not silently fork the truth" rule in the project.

### Why the WSGI app is not the only Python web app

`wsgiref.simple_server` is single-threaded and stdlib-documented as
development-only. Production WSGI deployments use Gunicorn / uWSGI. The
capstone says this in the CLI helptext and in the README — the goal is to
show the interface, not to ship a server.

## Consequences

- Three independent integration tests prove the same redirect behavior across
  the three adapters (`tests/integration/test_raw_socket_redirect.py`,
  `tests/integration/test_wsgi_redirect.py`,
  `tests/integration/django/test_api_basic.py` and
  `tests/integration/test_redirect_parity.py`).
- A reviewer can run the demo three times — `curl -v` against ports 9000
  (raw), 9100 (WSGI), and 8000 (Django) — and see the same status line,
  `Location`, and `Cache-Control` header.
- The single-file rule means switching `sniplink.toml#database_path` is
  enough to move every adapter onto a shared DB without code changes.

## Alternatives considered

- **Skip the hand-written WSGI app, lean on Django.** Rejected: would hide
  the very interface the capstone is supposed to demonstrate.
- **Run Django through ASGI.** Out of scope; revisited in the production
  reflection.
