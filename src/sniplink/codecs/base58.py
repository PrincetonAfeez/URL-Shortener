""" Base58 codec. """

from __future__ import annotations

from sniplink.codecs.base62 import Base62Codec


class Base58Codec(Base62Codec):
    name = "base58"
    alphabet = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
