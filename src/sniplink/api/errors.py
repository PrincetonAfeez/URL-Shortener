"""Error handling for the API."""

from __future__ import annotations

from sniplink.exceptions import (
    AliasTaken,
    AuthError,
    CodeNotFound,
    CollisionExhausted,
    InvalidAlias,
    InvalidDestinationURL,
    LinkGone,
    SniplinkError,
)


def status_for_exception(exc: Exception) -> int:
    """Map a domain or stdlib exception to the right HTTP status code."""

    if isinstance(exc, (InvalidDestinationURL, InvalidAlias)):
        return 400
    if isinstance(exc, CodeNotFound):
        return 404
    if isinstance(exc, LinkGone):
        return 410
    if isinstance(exc, AuthError):
        return 401
    if isinstance(exc, AliasTaken):
        return 409
    if isinstance(exc, CollisionExhausted):
        # The retry budget is finite but server-side; the caller didn't do
        # anything wrong — surface it as 503 so a retry can succeed later.
        return 503
    # ValueError is what the service raises for unsupported redirect status
    # values or unknown code strategies — both are client-driven errors.
    # Map them BEFORE the SniplinkError catch-all so they don't read as
    # internal failures. See bug #3 in the code review.
    if isinstance(exc, ValueError):
        return 400
    if isinstance(exc, SniplinkError):
        return 500
    return 500


def error_envelope(exc: Exception) -> dict:
    return {
        "error": {
            "type": exc.__class__.__name__,
            "message": str(exc),
        }
    }
