"""Tests for the Base62 codec. """

import pytest

from sniplink.codecs import Base62Codec


def test_base62_round_trips_representative_numbers():
    codec = Base62Codec()
    for number in [0, 1, 10, 61, 62, 125, 3844, 999_999]:
        assert codec.decode(codec.encode(number)) == number


def test_base62_rejects_invalid_input():
    codec = Base62Codec()
    with pytest.raises(ValueError):
        codec.encode(-1)
    with pytest.raises(ValueError):
        codec.decode("")
    with pytest.raises(ValueError):
        codec.decode("!")
