"""Tests for ``sniplink.api.errors.status_for_exception`` and the JSON envelope."""

from __future__ import annotations

import pytest

from sniplink.api import error_envelope, status_for_exception
from sniplink.exceptions import (
    AliasTaken,
    AuthError,
    CodeDeleted,
    CodeDisabled,
    CodeExpired,
    CodeNotFound,
    CollisionExhausted,
    InvalidAlias,
    InvalidDestinationURL,
    LinkGone,
    SniplinkError,
)


@pytest.mark.parametrize(
    "exc, expected_status",
    [
        (InvalidDestinationURL("bad"), 400),
        (InvalidAlias("bad"), 400),
        (ValueError("unsupported redirect status: 999"), 400),
        (CodeNotFound("missing"), 404),
        (CodeExpired("dead"), 410),
        (CodeDisabled("off"), 410),
        (CodeDeleted("gone"), 410),
        (LinkGone("any"), 410),
        (AuthError("nope"), 401),
        (AliasTaken("dup"), 409),
        (CollisionExhausted("retries"), 503),
        (SniplinkError("generic"), 500),
        (RuntimeError("unexpected"), 500),
    ],
)
def test_status_for_exception_table(exc: Exception, expected_status: int):
    assert status_for_exception(exc) == expected_status


def test_error_envelope_carries_type_and_message():
    envelope = error_envelope(InvalidAlias("alias too long"))

    assert envelope == {
        "error": {
            "type": "InvalidAlias",
            "message": "alias too long",
        }
    }
