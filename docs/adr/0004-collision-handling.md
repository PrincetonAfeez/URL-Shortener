# ADR 0004: Collision Handling

## Status

Accepted (2026-06-09).

## Decision

Treat the database `UNIQUE(short_code)` constraint as the **only** source of
truth for collision detection. Every code path attempts an insert and
catches `IntegrityError` (mapped to `AliasTaken`). The service retries random
codes up to `collision_retry_limit` and raises `CollisionExhausted`
afterwards.

## Context

A pre-check (`SELECT ... WHERE short_code = ?` then `INSERT`) is a textbook
time-of-check / time-of-use race: two requests both see the code as free and
both attempt to insert, and one of them silently overwrites the other if no
constraint is present. The constraint is what makes the race safe, so we
delete the pre-check entirely and rely on the constraint failing.

This is provable. `tests/concurrency/test_concurrent_code_creation.py` fans
40 inserts across 8 threads, then asserts every returned code is unique.

### SQLite-specific subtlety

The stock SQLite driver opens connections in deferred-transaction mode and
takes the writer lock implicitly when the first `INSERT` runs. That means in
the *default* configuration the second concurrent insert simply waits — the
`IntegrityError` retry path never fires, and the test passes without proving
anything.

`SQLiteStorage._connect` therefore turns on WAL (`journal_mode = WAL`) so
readers and writers can interleave. The concurrency tests open separate
``SQLiteStorage`` instances against a shared file-backed database; SQLite's
writer lock plus the ``UNIQUE`` constraint means the loser of a same-alias
race receives ``IntegrityError`` mapped to ``AliasTaken``. See
``tests/conftest.py#concurrent_sqlite_db_path``.

### Click-count race

The click counter has the same shape. The `record_click` path uses
`UPDATE links SET click_count = click_count + 1 WHERE id = ?` in both the
SQLite store and the `DjangoStorage` adapter (`F("click_count") + 1`). Naive
`link.click_count += 1; link.save()` would silently lose updates under
concurrency; the atomic SQL update wins by being a single statement.

## Consequences

- The capstone gets to demonstrate the *correct* concurrency pattern instead
  of the most common bug.
- Every storage backend (SQLite, Django ORM) must expose the same
  `AliasTaken` semantics. The `Storage` protocol enforces it; both
  implementations are tested.
- The retry budget is finite, so an adversary can't burn unbounded CPU. Once
  the budget runs out, the API returns `409 Conflict` (alias path) or `503`
  for `CollisionExhausted` (random/base62 path); the CLI uses exit code `7`
  (`EXHAUSTED`) via `exit_codes.py`.

## Alternatives considered

- **App-level lock** around the create path. Rejected: defeats the database
  authority point and would not generalize beyond one process.
- **Optimistic concurrency token**. Overkill for a capstone and irrelevant to
  the `UNIQUE`-constraint teaching path.
