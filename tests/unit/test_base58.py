"""Round-trip tests for the Base58 codec."""

from __future__ import annotations

import pytest

from sniplink.codecs import Base58Codec


@pytest.mark.parametrize("number", [0, 1, 57, 58, 100, 12345, 9_999_999])
def test_base58_round_trips_representative_numbers(number: int):
    codec = Base58Codec()
    assert codec.decode(codec.encode(number)) == number


def test_base58_alphabet_drops_ambiguous_characters():
    codec = Base58Codec()
    for char in ("0", "O", "I", "l"):
        assert char not in codec.alphabet


def test_base58_rejects_invalid_input():
    codec = Base58Codec()
    with pytest.raises(ValueError):
        codec.encode(-1)
    with pytest.raises(ValueError):
        codec.decode("")
    with pytest.raises(ValueError):
        codec.decode("0")  # explicitly excluded from base58
