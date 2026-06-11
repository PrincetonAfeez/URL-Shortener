"""Structured logging configuration.

Two formatters are wired up: a JSON one for production-shaped logs and a
plain text one for local hacking. Both run on the stdlib ``logging`` module —
the capstone deliberately avoids structlog so the dependency tree stays
small enough to defend at the panel.

Use :func:`configure_logging` once at process start (CLI, ``manage.py``,
WSGI app, raw socket server). It is idempotent.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from typing import Any

from sniplink.observability.redaction import redact_mapping

# Record attributes that ``logging`` always sets — anything else on the
# record is treated as a structured extra and folded into the JSON payload.
_RESERVED_RECORD_ATTRS = frozenset(
    {
        "args",
        "asctime",
        "created",
        "exc_info",
        "exc_text",
        "filename",
        "funcName",
        "levelname",
        "levelno",
        "lineno",
        "message",
        "module",
        "msecs",
        "msg",
        "name",
        "pathname",
        "process",
        "processName",
        "relativeCreated",
        "stack_info",
        "thread",
        "threadName",
        "taskName",
    }
)


class JSONFormatter(logging.Formatter):
    """Emit one JSON object per log record.

    Extra fields passed via ``logger.info("msg", extra={...})`` are merged into
    the top-level object and passed through :func:`redact_mapping` so secrets
    never reach the sink.
    """

    def __init__(self, *, redact_keys: Iterable[str] = ()) -> None:
        super().__init__()
        self._redact_keys = frozenset(key.lower() for key in redact_keys)

    def format(self, record: logging.LogRecord) -> str:
        payload: dict[str, Any] = {
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "timestamp": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
        }
        extras = {
            key: value
            for key, value in record.__dict__.items()
            if key not in _RESERVED_RECORD_ATTRS and not key.startswith("_")
        }
        if extras:
            payload["extra"] = redact_mapping(extras, self._redact_keys)
        if record.exc_info:
            payload["exception"] = self.formatException(record.exc_info)
        return json.dumps(payload, default=str, sort_keys=True)


def log_redirect_decision(
    adapter: str,
    *,
    short_code: str,
    status_code: int,
    destination_url: str | None,
    lookup_ms: float,
    result: str = "found",
) -> None:
    """Emit one structured ``redirect_served`` log line.

    Called by the raw-socket server, the hand-written WSGI app, and the
    Django redirect view so the three adapters report the same fields. With
    :class:`JSONFormatter` configured, the ``extra`` dict ends up as
    top-level structured fields (see ``observability.logging.JSONFormatter``).
    With the plain formatter the fields are appended to the message line.
    """

    logger = logging.getLogger("sniplink.redirect")
    logger.info(
        "redirect_served",
        extra={
            "adapter": adapter,
            "short_code": short_code,
            "status_code": status_code,
            "destination_url": destination_url,
            "lookup_ms": round(lookup_ms, 3),
            "result": result,
        },
    )


def configure_logging(
    level: str = "INFO",
    *,
    format: str = "json",
    redact_keys: Iterable[str] = (),
) -> None:
    """Install the chosen formatter on the root logger.

    Re-runs cleanly — existing handlers are removed first so test runs that
    repeatedly initialize logging do not accumulate handlers.
    """

    root = logging.getLogger()
    for handler in list(root.handlers):
        root.removeHandler(handler)

    handler = logging.StreamHandler()
    if format == "json":
        handler.setFormatter(JSONFormatter(redact_keys=redact_keys))
    else:
        handler.setFormatter(
            logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s")
        )

    root.addHandler(handler)
    root.setLevel(getattr(logging, level.upper(), logging.INFO))
