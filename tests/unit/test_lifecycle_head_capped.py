"""HEAD and resolve-without-click must respect max_clicks."""

from __future__ import annotations

import pytest

from sniplink.exceptions import CodeExpired


def test_head_resolve_raises_after_max_clicks(service):
    link = service.create_link("https://example.com", alias="capped", max_clicks=1)
    service.resolve(link.short_code)
    with pytest.raises(CodeExpired):
        service.resolve(link.short_code, record_click=False)
