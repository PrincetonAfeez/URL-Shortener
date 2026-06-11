"""Tests for lifecycle validation. """

from datetime import timedelta

import pytest

from sniplink.core import SniplinkService
from sniplink.exceptions import CodeDeleted, CodeDisabled, CodeExpired, InvalidDestinationURL
from sniplink.models import utc_now
from sniplink.storage import SQLiteStorage


@pytest.fixture
def service(tmp_path):
    svc = SniplinkService(SQLiteStorage(tmp_path / "test.db"))
    svc.initialize()
    return svc


def test_validation_rejects_unsafe_schemes(service):
    with pytest.raises(InvalidDestinationURL):
        service.create_link("javascript:alert(1)")


def test_disable_delete_and_expire_map_to_gone_exceptions(service):
    disabled = service.create_link("https://example.com", alias="disabled")
    deleted = service.create_link("https://example.org", alias="deleted")
    expired = service.create_link("https://example.net", alias="expired")
    service.expire_link(expired.short_code, utc_now() - timedelta(seconds=1))

    service.disable_link(disabled.short_code)
    service.delete_link(deleted.short_code)

    with pytest.raises(CodeDisabled):
        service.resolve("disabled")
    with pytest.raises(CodeDeleted):
        service.resolve("deleted")
    with pytest.raises(CodeExpired):
        service.resolve(expired.short_code)


def test_max_clicks_expires_after_limit(service):
    link = service.create_link("https://example.com", alias="once", max_clicks=1)
    service.resolve(link.short_code)
    with pytest.raises(CodeExpired):
        service.resolve(link.short_code)
