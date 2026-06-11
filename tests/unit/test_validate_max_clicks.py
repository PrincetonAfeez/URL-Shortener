"""Tests for the validate max clicks. """

import pytest

from sniplink.core.validation import validate_max_clicks


def test_validate_max_clicks_accepts_none_and_positive():
    assert validate_max_clicks(None) is None
    assert validate_max_clicks(1) == 1


def test_validate_max_clicks_rejects_zero_and_negative():
    with pytest.raises(ValueError, match="at least 1"):
        validate_max_clicks(0)
    with pytest.raises(ValueError, match="at least 1"):
        validate_max_clicks(-3)
