# ADR 0001: Encoding Scheme

## Status

Accepted (2026-06-09).

## Decision

Implement hand-written Base62 as the required sequential codec, ship a random
token codec for public-style links, and provide Base58 as a small stretch
codec.

## Context

Base62 maps integers into `0-9a-zA-Z` using repeated division by the alphabet
length. It is compact, URL-safe, and easy to demonstrate in a defense:

```text
id 125 -> 125 = 2*62 + 1 -> "21" in base62
```

Base58 drops the visually ambiguous characters (`0`, `O`, `I`, `l`). Random
tokens use `secrets.choice` over the Base62 alphabet and never decode back to
an integer.

All three codecs implement the same `CodeCodec` protocol so the service layer
can swap them at runtime via the `--random` CLI flag or the `strategy` API
field.

## Consequences

- Sequential Base62 codes are short and deterministic, but **enumerable**.
  Anyone iterating `/1`, `/2`, `/3` can scrape every public link. The
  enumeration trade-off is the subject of ADR 0002.
- Random tokens need a database `UNIQUE` constraint plus retry logic, which
  is documented in ADR 0004.
- The custom alphabet plumbing is one constructor argument; Base58 is
  effectively a subclass that swaps the alphabet. The pluggability is the
  architecture point — adding a fourth scheme is a one-file change.

## Alternatives considered

- **UUIDs** in the URL. Rejected: too long, no positional-encoding teaching
  value.
- **Hash of the destination URL.** Rejected: collides on identical
  destinations and locks idempotency in by default instead of leaving it as a
  documented stretch (ADR 0007).
