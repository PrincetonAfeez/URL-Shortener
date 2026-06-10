# Security & Privacy

## Privacy posture (lead with this in defense)

**Stored on each click:** `User-Agent`, `Referer`, timestamp.

**Not stored:** client IP addresses.

**Logs:** `observability.redaction` strips `Authorization`, `X-API-Key`, and
secret-shaped fields before JSON log emission.

## Threat model (academic scope)

| Surface | Risk | Mitigation in sniplink |
| ------- | ---- | ---------------------- |
| Open JSON API (dev) | Unauthenticated create/delete when `SNIPLINK_API_KEY` unset | Document dev-only; set key for demos |
| HTMX dashboard | CSRF on form posts | `CsrfViewMiddleware` + `hx-headers` CSRF token |
| Health checker SSRF | Probe internal networks | Private/loopback hosts rejected unless `--allow-private` |
| Guessable Base62 codes | Enumeration of `/1`, `/2`, … | Documented in ADR 0002; random strategy available |
| Self-referencing short links | Redirect loops | `normalize_destination_url` blocks destinations pointing at sniplink origins |

## Authentication

- **Implemented:** optional single shared key via `SNIPLINK_API_KEY` on JSON API
  (`X-API-Key` or `Authorization: Bearer …`), compared with
  `secrets.compare_digest`.
- **Stretch (not implemented):** key rotation, scopes, per-client rate limits.

## Deployment defaults

For any non-local run:

```powershell
$env:SNIPLINK_DJANGO_DEBUG = "false"
$env:SNIPLINK_SECRET_KEY = "<random-secret>"
$env:SNIPLINK_API_KEY = "<shared-demo-key>"
```

`DEBUG=true` and the dev `SECRET_KEY` in `settings.py` are intentional for
local capstone work only.

## Stats access

When `SNIPLINK_API_KEY` is set, `/api/links/{code}/stats` requires the key.
HTMX stats from the dashboard (`HX-Request: true`) remain available to the
same-origin session — document as trusted-local-only behavior.
