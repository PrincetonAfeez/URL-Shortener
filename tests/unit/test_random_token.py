"""Tests for the random token codec. """

from sniplink.codecs import RandomTokenCodec


def test_random_token_uses_configured_length_and_alphabet():
    codec = RandomTokenCodec(length=12, alphabet="abc")
    token = codec.generate()
    assert len(token) == 12
    assert set(token) <= {"a", "b", "c"}
