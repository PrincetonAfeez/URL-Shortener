"""Request parser. """

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote, urlsplit


class BadRequest(ValueError):
    pass


class UriTooLong(ValueError):
    pass


@dataclass(slots=True)
class HTTPRequest:
    method: str
    path: str
    query_string: str
    http_version: str
    headers: dict[str, str]


def parse_http_request(raw: bytes, *, max_path_length: int = 2048) -> HTTPRequest:
    header_bytes = raw.split(b"\r\n\r\n", 1)[0]
    try:
        text = header_bytes.decode("iso-8859-1")
    except UnicodeDecodeError as exc:
        raise BadRequest("request headers are not decodable") from exc

    lines = text.split("\r\n")
    if not lines or not lines[0].strip():
        raise BadRequest("missing request line")

    parts = lines[0].split()
    if len(parts) != 3:
        raise BadRequest("malformed request line")
    method, target, http_version = parts
    if not http_version.startswith("HTTP/"):
        raise BadRequest("missing HTTP version")
    if len(target) > max_path_length:
        raise UriTooLong("request target is too long")

    parsed = urlsplit(target)
    headers: dict[str, str] = {}
    for line in lines[1:]:
        if not line:
            continue
        if ":" not in line:
            raise BadRequest("malformed header line")
        name, value = line.split(":", 1)
        headers[name.strip().lower()] = value.strip()

    return HTTPRequest(
        method=method.upper(),
        path=unquote(parsed.path or "/"),
        query_string=parsed.query,
        http_version=http_version,
        headers=headers,
    )


def path_too_long(path: str, *, max_path_length: int = 2048) -> bool:
    """Return ``True`` when ``path`` exceeds the configured byte budget."""

    return len(path) > max_path_length


def extract_code(path: str) -> str | None:
    """Return the single-segment short code, or ``None`` for any other path.

    Multi-segment paths (``/demo/extra``) are rejected outright so a short
    code cannot accidentally shadow a longer URL — the resolver receives
    only what the demo paths are supposed to look like. See bug #10 in the
    third-pass code review.
    """

    stripped = path.strip("/")
    if not stripped:
        return None
    if "/" in stripped:
        return None
    return stripped
