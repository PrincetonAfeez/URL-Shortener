"""Tests for the CLI. """

import os
import subprocess
import sys


def run_cli(tmp_path, *args):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(["src", "web", env.get("PYTHONPATH", "")])
    return subprocess.run(
        [
            sys.executable,
            "-m",
            "sniplink",
            "--db",
            str(tmp_path / "cli.db"),
            "--base-url",
            "http://short.test",
            *args,
        ],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def test_init_db_prints_django_fake_initial_hint(tmp_path):
    result = run_cli(tmp_path, "init-db")
    assert "migrate --fake-initial" in result.stdout


def test_cli_create_resolve_list_delete(tmp_path):
    created = run_cli(tmp_path, "create", "https://example.com", "--alias", "demo")
    assert "demo -> https://example.com/" in created.stdout

    resolved = run_cli(tmp_path, "resolve", "demo")
    assert resolved.stdout.strip() == "https://example.com/"

    listed = run_cli(tmp_path, "list")
    assert "demo" in listed.stdout

    deleted = run_cli(tmp_path, "delete", "demo")
    assert "demo -> https://example.com/" in deleted.stdout
