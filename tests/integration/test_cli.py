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


def cli_help(*subcommand):
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(["src", "web", env.get("PYTHONPATH", "")])
    return subprocess.run(
        [sys.executable, "-m", "sniplink", *subcommand, "--help"],
        check=True,
        capture_output=True,
        text=True,
        env=env,
    ).stdout


def test_init_db_prints_django_fake_initial_hint(tmp_path):
    result = run_cli(tmp_path, "init-db")
    assert "migrate --fake-initial" in result.stdout


def test_create_help_documents_flags():
    help_text = cli_help("create")

    assert "custom vanity short code" in help_text
    assert "HTTP redirect status" in help_text
    assert "ISO 8601 expiration timestamp" in help_text
    assert "maximum number of redirect clicks" in help_text
    assert "print the created link as JSON" in help_text


def test_other_subcommand_help_documents_flags():
    resolve_help = cli_help("resolve")
    assert "print the resolved destination as JSON" in resolve_help

    list_help = cli_help("list")
    assert "include soft-deleted links" in list_help

    expire_help = cli_help("expire")
    assert "ISO 8601 timestamp to expire the link at" in expire_help

    raw_help = cli_help("serve-raw")
    assert "host interface for the raw socket redirect server" in raw_help
    assert "TCP port for the raw socket redirect server" in raw_help

    wsgi_help = cli_help("serve-wsgi")
    assert "host interface for the hand-written WSGI demo server" in wsgi_help
    assert "TCP port for the hand-written WSGI demo server" in wsgi_help

    health_help = cli_help("check-health")
    assert "destination URLs to check" in health_help
    assert "per-link health-check timeout in seconds" in health_help
    assert "allow health checks against private" in health_help


def test_cli_create_resolve_list_delete(tmp_path):
    created = run_cli(tmp_path, "create", "https://example.com", "--alias", "demo")
    assert "demo -> https://example.com/" in created.stdout

    resolved = run_cli(tmp_path, "resolve", "demo")
    assert resolved.stdout.strip() == "https://example.com/"

    listed = run_cli(tmp_path, "list")
    assert "demo" in listed.stdout

    deleted = run_cli(tmp_path, "delete", "demo")
    assert "demo -> https://example.com/" in deleted.stdout
