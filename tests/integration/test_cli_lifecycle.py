"""CLI exit-code parity for lifecycle commands."""

from __future__ import annotations

import os
import subprocess
import sys


def run_cli(tmp_path, *args, expect_failure: bool = False):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(["src", "web", env.get("PYTHONPATH", "")])
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "sniplink",
            "--db",
            str(tmp_path / "lifecycle.db"),
            *args,
        ],
        check=not expect_failure,
        capture_output=True,
        text=True,
        env=env,
    )


def test_resolve_missing_code_returns_not_found(tmp_path):
    run_cli(tmp_path, "init-db")
    result = run_cli(tmp_path, "resolve", "nope", expect_failure=True)
    assert result.returncode == 4


def test_stats_on_disabled_link_returns_gone(tmp_path):
    run_cli(tmp_path, "init-db")
    run_cli(tmp_path, "create", "https://example.com", "--alias", "off")
    run_cli(tmp_path, "disable", "off")
    result = run_cli(tmp_path, "stats", "off", expect_failure=True)
    assert result.returncode == 5


def test_duplicate_alias_returns_conflict(tmp_path):
    run_cli(tmp_path, "init-db")
    run_cli(tmp_path, "create", "https://example.com", "--alias", "dup")
    result = run_cli(
        tmp_path,
        "create",
        "https://other.example",
        "--alias",
        "dup",
        expect_failure=True,
    )
    assert result.returncode == 6


def test_double_disable_returns_gone(tmp_path):
    run_cli(tmp_path, "init-db")
    run_cli(tmp_path, "create", "https://example.com", "--alias", "twice")
    run_cli(tmp_path, "disable", "twice")
    result = run_cli(tmp_path, "disable", "twice", expect_failure=True)
    assert result.returncode == 5
