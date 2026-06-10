# Protocol Evidence

## Raw Socket Lifecycle

`sniplink.raw_http.server.RawHTTPServer` demonstrates the TCP flow directly:

1. `socket.socket(socket.AF_INET, socket.SOCK_STREAM)`
2. `bind((host, port))`
3. `listen()`
4. `accept()`
5. `recv()` until `\r\n\r\n`
6. parse the HTTP request line and headers
7. call the core service
8. `sendall()` serialized HTTP response bytes
9. close the client connection

## Redirect Response Shape

Tracked redirects default to `302 Found` and include:

```http
HTTP/1.1 302 Found
Location: https://example.com/
Cache-Control: no-store
Content-Length: 0
Connection: close
```

`Cache-Control: no-store` keeps browser and intermediary caching from hiding
click tracking behavior during the demo.

## Status Semantics

- `302 Found`: default tracked redirect.
- `301 Moved Permanently`: available per link, but risky for analytics because
  clients and intermediaries may cache it aggressively.
- `307 Temporary Redirect`: available when method preservation is the behavior
  being demonstrated.
- `308 Permanent Redirect`: permanent redirect with method preservation (RFC 9110).
- `404 Not Found`: short code never existed.
- `410 Gone`: short code existed but is expired, disabled, or deleted.

### Example: `308 Permanent Redirect`

```http
HTTP/1.1 308 Permanent Redirect
Location: https://example.com/
Cache-Control: no-store
Content-Length: 0
Connection: close
```

### Example: `410 Gone` after disable

```powershell
sniplink create https://example.com --alias demo
sniplink disable demo
curl -v http://localhost:9000/demo
```

```http
HTTP/1.1 410 Gone
Content-Type: text/plain; charset=utf-8
Cache-Control: no-store
Content-Length: 20

short code is gone
```

## HEAD Behavior

The raw socket, WSGI, and Django redirect paths accept `HEAD`. They return the
same status and headers as `GET`, but with no response body and no click record.

```powershell
curl -v -X HEAD http://localhost:9000/demo
```

```http
HTTP/1.1 302 Found
Location: https://example.com/
Cache-Control: no-store
Content-Length: 0
Connection: close
```

`click_count` remains unchanged after `HEAD` (verified in
`tests/integration/test_redirect_parity.py` and
`tests/integration/django/test_django_redirect.py`).

## WSGI Evidence

`sniplink.wsgi_app.app.make_app` reads `REQUEST_METHOD` and `PATH_INFO` from
`environ`, calls `start_response(status, headers)`, and returns an iterable of
bytes. This is intentionally small so it is easy to compare with the raw socket
server and with Django's higher-level WSGI deployment model.

## API Evidence

The Django JSON API returns:

- `201 Created` with `Location` for `POST /api/links`
- `200 OK` for inspect and stats
- `204 No Content` for delete
- `409 Conflict` for vanity alias conflicts
- consistent JSON error envelopes
