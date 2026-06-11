""" Base62 codec. """

from __future__ import annotations


class Base62Codec:
    name = "base62"
    alphabet = "0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

    def __init__(self, alphabet: str | None = None) -> None:
        self.alphabet = alphabet or self.alphabet
        if len(set(self.alphabet)) != len(self.alphabet):
            raise ValueError("alphabet must not contain duplicate characters")
        if len(self.alphabet) < 2:
            raise ValueError("alphabet must contain at least two characters")
        self.base = len(self.alphabet)
        self._index = {char: idx for idx, char in enumerate(self.alphabet)}

    def encode(self, number: int) -> str:
        if number < 0:
            raise ValueError("number must be non-negative")
        if number == 0:
            # ``encode(0)`` returns the first alphabet character ("0" for
            # Base62, "1" for Base58) so the round-trip property holds for
            # all non-negative integers. AUTOINCREMENT starts at 1 so this
            # branch is unreachable in normal use, but unit tests rely on
            # it for completeness.
            return self.alphabet[0]

        chars: list[str] = []
        while number:
            number, remainder = divmod(number, self.base)
            chars.append(self.alphabet[remainder])
        return "".join(reversed(chars))

    def decode(self, code: str) -> int:
        if not code:
            raise ValueError("code must not be empty")
        number = 0
        for char in code:
            try:
                value = self._index[char]
            except KeyError as exc:
                # Use self.name so subclasses (Base58) get the right label
                # in the error message — bug #15 in the third-pass review.
                raise ValueError(f"invalid {self.name} character: {char!r}") from exc
            number = number * self.base + value
        return number
