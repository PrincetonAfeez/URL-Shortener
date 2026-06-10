# ADR 0002: Sequential IDs vs Random Codes

## Status

Accepted (2026-06-09).

## Decision

Default new links to sequential Base62 codes derived from the auto-increment
primary key, and offer random tokens as an opt-in strategy via
`--random` / `"strategy": "random"`. Vanity aliases override both.

## Context

Sequential codes are the canonical teaching path:

- Trivial to encode and decode, which is the point of ADR 0001.
- The collision story is the **alias** path: a vanity alias may already
  occupy the slot the new ID encodes to. The service handles that by
  inserting a `__pending_<uuid>` placeholder row, encoding the resulting `id`,
  and then `UPDATE`ing the placeholder to the real code under the `UNIQUE`
  constraint.

Random codes are needed when public links should not reveal creation order
(competitor analytics, link enumeration). They retry up to
`collision_retry_limit` (default 8) and raise `CollisionExhausted` if every
attempt loses the race against the constraint.

## Consequences

- Sequential codes leak two facts: how many links exist, and rough creation
  order. The README calls this out so reviewers see the trade-off was
  understood, not missed.
- The placeholder-row pattern is **not free**: every Base62 create touches the
  database twice (`INSERT` then `UPDATE`). For a capstone that is the right
  trade — it lets the `UNIQUE` constraint stay the source of truth (ADR 0004)
  without resorting to `last_insert_rowid()` gymnastics.
- Random codes need extra entropy as the table grows. Length is configurable
  via `sniplink.toml#random_token_length`; the project ships with 7, which is
  fine until the table passes roughly a million links.

## Alternatives considered

- **Sequence-based hashids** (Hashids library). Rejected: hides the
  positional-encoding teaching value behind a third-party black box.
- **Per-request UUIDv7**. Rejected: still encodes a timestamp ordering, just
  less obviously.
