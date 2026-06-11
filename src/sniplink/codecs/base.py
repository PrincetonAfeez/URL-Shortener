""" Base codec protocol. """

from __future__ import annotations

from typing import Protocol


class CodeCodec(Protocol):
    name: str

    def encode(self, number: int) -> str:
        """Encode a non-negative integer as a short code."""

    def decode(self, code: str) -> int:
        """Decode a short code into a non-negative integer."""
