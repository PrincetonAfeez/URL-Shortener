"""Tests for ``sniplink.config.load_config``.

The TOML file is the single source of truth shared by the CLI and Django, so
this is the one module that absolutely needs coverage: a bug here silently
affects every adapter.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from sniplink.config import (
    DEFAULT_BASE_ALIASES,
    DEFAULT_RESERVED_CODES,
    load_config,
)


def _write_toml(path: Path, body: str) -> None:
    path.write_text(body, encoding="utf-8")


def test_load_config_returns_defaults_when_toml_is_missing(tmp_path: Path):
    config = load_config(config_path=tmp_path / "missing.toml")

    assert config.default_base_url == "http://localhost:8000"
    assert config.default_redirect_status == 302
    assert config.reserved_codes == DEFAULT_RESERVED_CODES
    assert config.base_aliases == DEFAULT_BASE_ALIASES
    assert config.api.max_body_bytes == 64 * 1024
    assert config.logging.format == "json"


def test_load_config_reads_toml_overrides(tmp_path: Path):
    toml_path = tmp_path / "sniplink.toml"
    _write_toml(
        toml_path,
        """
[sniplink]
database_path = "demo.db"
default_base_url = "http://example.test"
default_redirect_status = 307
collision_retry_limit = 16
reserved_prefixes = ["foo", "bar"]
base_aliases = ["http://short.example"]

[sniplink.api]
max_body_bytes = 4096

[sniplink.logging]
level = "DEBUG"
format = "plain"
redact_keys = ["x-token"]
""",
    )

    config = load_config(config_path=toml_path)

    assert config.database_path == (tmp_path / "demo.db").resolve()
    assert config.default_base_url == "http://example.test"
    assert config.default_redirect_status == 307
    assert config.collision_retry_limit == 16
    assert config.reserved_codes == ("foo", "bar")
    assert config.base_aliases == ("http://short.example",)
    assert config.api.max_body_bytes == 4096
    assert config.logging.level == "DEBUG"
    assert config.logging.format == "plain"
    assert config.logging.redact_keys == ("x-token",)


def test_env_vars_beat_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    toml_path = tmp_path / "sniplink.toml"
    _write_toml(
        toml_path,
        """
[sniplink]
default_base_url = "http://from-toml"
[sniplink.logging]
level = "WARNING"
""",
    )
    monkeypatch.setenv("SNIPLINK_BASE_URL", "http://from-env")
    monkeypatch.setenv("SNIPLINK_LOG_LEVEL", "ERROR")

    config = load_config(config_path=toml_path)

    assert config.default_base_url == "http://from-env"
    assert config.logging.level == "ERROR"


def test_argument_beats_env_and_toml(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    toml_path = tmp_path / "sniplink.toml"
    _write_toml(
        toml_path,
        """
[sniplink]
database_path = "toml.db"
""",
    )
    monkeypatch.setenv("SNIPLINK_DB", "env.db")

    config = load_config("arg.db", config_path=toml_path)

    # Relative paths anchor on the TOML's directory.
    assert config.database_path == (tmp_path / "arg.db").resolve()


def test_database_path_resolves_relative_to_toml_directory(tmp_path: Path):
    toml_path = tmp_path / "subdir" / "sniplink.toml"
    toml_path.parent.mkdir()
    _write_toml(
        toml_path,
        """
[sniplink]
database_path = "sniplink.db"
""",
    )

    config = load_config(config_path=toml_path)

    assert config.database_path == (toml_path.parent / "sniplink.db").resolve()


def test_database_path_absolute_is_used_unchanged(tmp_path: Path):
    abs_db = tmp_path / "absolute.db"
    toml_path = tmp_path / "sniplink.toml"
    _write_toml(
        toml_path,
        f'[sniplink]\ndatabase_path = "{abs_db.as_posix()}"\n',
    )

    config = load_config(config_path=toml_path)

    assert config.database_path == abs_db
