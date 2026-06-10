# ADR 0007: Caching Decision

## Status

Accepted (2026-06-09).

## Decision

Do **not** add an application-layer cache (in-process LRU, Redis, anything)
in the core build. Send `Cache-Control: no-store` on every tracked redirect.
Caching graduates from stretch to core only if and when there is time to
write the invalidation story honestly.

## Context

A redirect cache is the obvious next move for a read-heavy shortener: the
short-code lookup is hot, the destination URL rarely changes, and lookups
near a million per second are tractable on a single core. The trap is what
*tomorrow* costs.

Every link lifecycle transition becomes a cache-invalidation event:

| Transition                  | What the cache must do      |
| --------------------------- | --------------------------- |
| `sniplink delete demo`      | drop entry, do not serve stale |
| `disable_link` / `expire`   | drop entry                  |
| `set_expiry` to past time   | drop entry                  |
| API `POST` overwrite        | refuse (or invalidate) entry |
| Health-checker flags dead   | optional negative cache TTL |

It also interacts with analytics: a cached `302` means the redirect handler
never runs, so no click row is written. The `Cache-Control: no-store`
response header is the workaround we *do* ship — it pushes the "don't cache"
decision onto clients and intermediaries instead of trying to solve it on
the server.

### Single-process LRU caveat (when a cache is eventually added)

The natural starting point is a `functools.lru_cache`-style in-process LRU.
That is fine under `manage.py runserver` (one process) and the raw socket
server (one process), but it is wrong under a Gunicorn deployment with N
workers:

- The cache fragments across workers — each maintains its own copy.
- `sniplink delete demo` in one worker does not invalidate the cached entry
  in the other N-1 workers, so requests routed to those workers continue to
  redirect.

Production caching has to be process-external (Redis, Memcached, a CDN).
The production reflection captures this. If a cache lands in this repo
later, it must:

1. Be guarded by a config flag (default off).
2. Document its eviction policy and TTL.
3. Cache **only** active links — `LinkGone` results stay uncached so
   404/410 responses are always live.
4. Invalidate on every `service.disable_link` / `delete_link` /
   `set_expiry` call.

## Consequences

- Redirect latency is whatever SQLite delivers (typically sub-millisecond on
  the indexed `short_code` lookup, which is fine for the demo).
- The capstone does not have to defend a cache-invalidation policy it could
  not actually test.
- The README and the production-reflection document explain what changes if
  a cache is added later, so the absence is a choice, not an oversight.

## Alternatives considered

- **In-process LRU at the service layer.** Rejected for the core build for
  the reasons above; possible as a marked-stretch task.
- **Reverse-proxy cache (Varnish / Nginx).** Out of scope — would also break
  click counting unless paired with `Cache-Control: no-store`, which we
  already send.
