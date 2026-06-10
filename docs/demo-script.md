# Demo Script

## 1. Core and CLI

```powershell
sniplink init-db
sniplink create https://example.com --alias demo
sniplink resolve demo
sniplink list
sniplink stats demo
```

Explain that the CLI calls the same framework-free service used by every HTTP
adapter.

## 2. Raw HTTP Redirect

```powershell
sniplink serve-raw --port 9000
curl -v http://localhost:9000/demo
```

Show the status line, `Location`, `Cache-Control`, and `Content-Length`.

## 3. 404 vs 410

```powershell
curl -v http://localhost:9000/missing
sniplink delete demo
curl -v http://localhost:9000/demo
```

Unknown codes return `404`; deleted/disabled/expired codes return `410`.

## 4. WSGI

```powershell
sniplink serve-wsgi --port 9100
curl -v http://localhost:9100/demo
```

Point to `environ`, `start_response`, and the returned byte iterable.

## 5. Django + HTMX

If you already ran `sniplink init-db` in section 1, adopt the existing tables:

```powershell
python web/manage.py migrate --fake-initial
python web/manage.py runserver 127.0.0.1:8000
```

Greenfield Django-first setup:

```powershell
python web/manage.py migrate
python web/manage.py runserver 127.0.0.1:8000
```

Open `http://127.0.0.1:8000/`, create a link, inspect stats, disable it, and
try redirecting again.

## 6. JSON API

```powershell
curl -i -X POST http://127.0.0.1:8000/api/links `
  -H "Content-Type: application/json" `
  -d "{\"url\":\"https://example.com\",\"alias\":\"api-demo\"}"
curl -i http://127.0.0.1:8000/api/links/api-demo
curl -i http://127.0.0.1:8000/api/links/api-demo/stats
curl -i -X DELETE http://127.0.0.1:8000/api/links/api-demo
```

## 7. Async Health Checker

```powershell
sniplink check-health --concurrency 10 --timeout 5
```

Explain why asyncio belongs in concurrent outbound network checks instead of
being forced into the WSGI request path.
