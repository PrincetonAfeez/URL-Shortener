"""Response writer. """

from __future__ import annotations

from email.utils import formatdate

REASONS = {
    200: "OK",
    201: "Created",
    204: "No Content",
    301: "Moved Permanently",
    302: "Found",
    307: "Temporary Redirect",
    308: "Permanent Redirect",
    400: "Bad Request",
    404: "Not Found",
    405: "Method Not Allowed",
    410: "Gone",
    414: "URI Too Long",
    500: "Internal Server Error",
    505: "HTTP Version Not Supported",
}


def build_response(
    status_code: int,
    *,
    headers: dict[str, str] | None = None,
    body: bytes = b"",
    method: str = "GET",
) -> bytes:
    reason = REASONS.get(status_code, "Unknown")
    outgoing = {
        "Date": formatdate(usegmt=True),
        "Connection": "close",
        **(headers or {}),
    }
    outgoing.setdefault("Content-Length", str(len(body)))
    if body and "Content-Type" not in outgoing:
        outgoing["Content-Type"] = "text/plain; charset=utf-8"

    lines = [f"HTTP/1.1 {status_code} {reason}"]
    lines.extend(f"{name}: {value}" for name, value in outgoing.items())
    head = ("\r\n".join(lines) + "\r\n\r\n").encode("iso-8859-1")
    return head if method.upper() == "HEAD" else head + body


def redirect_response(
    *,
    location: str,
    status_code: int = 302,
    method: str = "GET",
) -> bytes:
    return build_response(
        status_code,
        headers={
            "Location": location,
            "Cache-Control": "no-store",
            "Content-Length": "0",
        },
        body=b"",
        method=method,
    )


def error_response(
    status_code: int,
    message: str,
    *,
    method: str = "GET",
    allow: str | None = None,
) -> bytes:
    """Build a 4xx/5xx response.

    ``allow`` is the value for the ``Allow`` header. RFC 9110 requires it on
    ``405 Method Not Allowed`` and the raw socket server passes
    ``"GET, HEAD"`` there.
    """

    body = f"{status_code} {REASONS.get(status_code, 'Error')}: {message}\n".encode(
        "utf-8"
    )
    headers: dict[str, str] = {"Cache-Control": "no-store"}
    if allow is not None:
        headers["Allow"] = allow
    return build_response(
        status_code,
        headers=headers,
        body=body,
        method=method,
    )
