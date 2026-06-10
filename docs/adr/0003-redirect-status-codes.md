# ADR 0003: Redirect Status Codes

## Status

Accepted (2026-06-09).

## Decision

Default tracked redirects to `302 Found`. Allow `301`, `307`, and `308`
per-link. Return `404 Not Found` for codes that never existed and `410 Gone`
for codes that existed and should no longer redirect (expired, disabled,
soft-deleted). Always send `Cache-Control: no-store` on tracked redirect
responses. Support `HEAD` on every redirect adapter (raw socket, WSGI,
Django).

## Context

The five redirect codes the project actually thinks about:

| Code | Cached?         | Method preserving? | Use                                         |
| ---- | --------------- | ------------------ | ------------------------------------------- |
| 301  | aggressively    | no                 | Permanent, untracked — disables analytics   |
| 302  | not by default  | no                 | The capstone default                        |
| 303  | not by default  | no (forces GET)    | Discussed in defense, not in core scope     |
| 307  | not by default  | **yes**            | Temporary + method preservation             |
| 308  | aggressively    | **yes**            | Permanent + method preservation             |

`Cache-Control: no-store` is the safety belt: even when a link is configured
for `301`/`308`, the demo can prove the click counter changes on every
request because intermediaries are forbidden from caching. In production a
shortener might let `301` actually be cached; the trade-off is documented but
not the default here.

`410 Gone` vs `404 Not Found` is the easiest semantic to defend. `404` means
*never existed* (`/never-created`); `410` means *existed and is gone*
(`/demo` after `sniplink delete demo`). Treating them as the same code is the
most common shortener-tutorial bug and we explicitly do not.

`HEAD` returns the same status line and headers as `GET`, with no body and no
click recorded. The raw socket parser dispatches both; `response_writer.py`
omits the body when `method == "HEAD"`. Tests assert this in
`tests/unit/test_response_writer.py`.

## Consequences

- One test per adapter asserts exact status code + `Location` header value.
  See `tests/unit/test_response_writer.py`,
  `tests/integration/test_raw_socket_redirect.py`,
  `tests/integration/test_wsgi_redirect.py`,
  `tests/integration/django/test_api_basic.py` and
  `tests/integration/test_redirect_parity.py`.
- `301`/`308` are exposed in the dashboard `select` so reviewers can play with
  caching behavior in the demo, but the defaults stay safe.
- The `410` decision means `disabled`, `deleted`, and `expired` all collapse
  into one HTTP status, which is the basis for the `LinkGone` exception base
  class. Three subclasses give the logs a `reason`; the HTTP layer only cares
  about `LinkGone`.

## Alternatives considered

- **Return `200 OK` with an HTML interstitial** ("you're being sent to..."):
  deferred to stretch scope (phishing safety) and not part of the protocol
  story.
- **Return `503` for disabled links**: rejected — that codes a server failure,
  not a lifecycle decision.
