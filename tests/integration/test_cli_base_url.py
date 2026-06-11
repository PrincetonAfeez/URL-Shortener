"""CLI --base-url handling and create-without-crash."""

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
            str(tmp_path / "base-url.db"),
            *args,
        ],
        check=not expect_failure,
        capture_output=True,
        text=True,
        env=env,
    )


def test_create_without_base_url_uses_config_default(tmp_path):
    result = run_cli(tmp_path, "create", "https://example.com", "--alias", "plain")
    assert "plain -> https://example.com/" in result.stdout
    assert "short_url: http://localhost:8000/plain" in result.stdout


def test_create_accepts_base_url_after_subcommand(tmp_path):
    result = run_cli(
        tmp_path,
        "create",
        "https://example.com",
        "--alias",
        "late",
        "--base-url",
        "http://short.test",
    )
    assert "short_url: http://short.test/late" in result.stdout
