""" Random token codec. """

from __future__ import annotations

import secrets

from sniplink.codecs.base62 import Base62Codec


class RandomTokenCodec:
    name = "random"

    def __init__(self, length: int = 7, alphabet: str | None = None) -> None:
        if length <= 0:
            raise ValueError("length must be positive")
        self.length = length
        self.alphabet = alphabet or Base62Codec.alphabet
        if len(set(self.alphabet)) != len(self.alphabet):
            raise ValueError("alphabet must not contain duplicate characters")

    def generate(self) -> str:
        return "".join(secrets.choice(self.alphabet) for _ in range(self.length))

    def encode(self, number: int) -> str:
        raise NotImplementedError("random tokens do not encode integers")

    def decode(self, code: str) -> int:
        raise NotImplementedError("random tokens do not decode to integers")
