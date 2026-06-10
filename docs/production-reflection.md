# Production Reflection

This educational shortener proves HTTP redirects, raw TCP sockets, WSGI,
Django integration, database-backed uniqueness, and async network tooling.

## Shipped in core (not just discussed)

- **Optional API-key gate** — set `SNIPLINK_API_KEY`; JSON API accepts
  `X-API-Key` or `Authorization: Bearer …` (`web/links/views.py`).
- **CSRF on HTMX forms** — dashboard mutations use Django CSRF middleware.
- **Private-host guard** on async health checks (unless `--allow-private`).
- **Structured logging** with header redaction.
- **WAL mode** on shared SQLite (CLI `init-db` + Django `connection_created` hook).

## Production next steps

| Area | Sketch |
| ---- | ------ |
| Abuse prevention | Rate limit at reverse proxy or `api_create` middleware |
| Phishing / malware | Interstitial preview page (stretch in timeline) |
| HTTPS | Terminate TLS at nginx/Caddy; sniplink stays HTTP internally |
| Observability | Export redirect decisions to metrics; alert on 5xx rate |
| Analytics writes | Queue click rows to a worker instead of inline INSERT |
| Cache | Redis with explicit invalidation on disable/delete/expire (ADR 0007) |
| Auth | Rotate API keys, per-client scopes — beyond single shared env key |
| Custom domains | Host-based routing in front of redirect adapter |
| Database | Postgres adapter implementing the same `Storage` protocol |
| Privacy review | DPIA for referrer/UA retention; optional IP hashing |

Those additions are intentionally **discussed with concrete hook points** rather
than fully implemented so the capstone stays focused on networking and protocol
mastery.
