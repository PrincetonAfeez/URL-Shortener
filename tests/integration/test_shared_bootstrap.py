"""Prove CLI-first and Django-first paths share one ``links`` table."""

from __future__ import annotations

import os
import subprocess
import sys

REPO = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))


def _env(db_path: str) -> dict[str, str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = os.pathsep.join(["src", "web", env.get("PYTHONPATH", "")])
    env["SNIPLINK_DJANGO_DB"] = db_path
    return env


def test_cli_first_then_migrate_reconciles_tables(tmp_path):
    db_path = str(tmp_path / "cli-first.db")
    env = _env(db_path)

    subprocess.run(
        [sys.executable, "-m", "sniplink", "--db", db_path, "init-db"],
        check=True,
        cwd=REPO,
        env=env,
    )
    subprocess.run(
        [sys.executable, "-m", "sniplink", "--db", db_path, "create", "https://example.com", "--alias", "cli"],
        check=True,
        cwd=REPO,
        env=env,
    )
    subprocess.run(
        [
            sys.executable,
            "web/manage.py",
            "migrate",
            "--fake-initial",
            "--verbosity",
            "0",
        ],
        check=True,
        cwd=REPO,
        env=env,
    )

    import sqlite3

    with sqlite3.connect(db_path) as conn:
        tables = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "links" in tables
        assert "links_link" not in tables
        (code,) = conn.execute("SELECT short_code FROM links").fetchone()
        assert code == "cli"
        indexes = {
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }
        assert "clicks_link_clicked_idx" in indexes
        assert "links_short_code_idx" not in indexes


def test_django_first_then_cli_create_writes_same_table(tmp_path):
    db_path = str(tmp_path / "django-first.db")
    env = _env(db_path)

    subprocess.run(
        [sys.executable, "web/manage.py", "migrate", "--verbosity", "0"],
        check=True,
        cwd=REPO,
        env=env,
    )
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "sniplink",
            "--db",
            db_path,
            "create",
            "https://example.org",
            "--alias",
            "shared",
        ],
        check=True,
        capture_output=True,
        text=True,
        cwd=REPO,
        env=env,
    )
    assert "shared -> https://example.org/" in result.stdout

    import sqlite3

    with sqlite3.connect(db_path) as conn:
        rows = conn.execute("SELECT short_code FROM links ORDER BY id").fetchall()
        assert ("shared",) in rows


def test_django_orm_reads_cli_created_row(tmp_path):
    db_path = str(tmp_path / "e2e-shared.db")
    env = _env(db_path)

    subprocess.run(
        [sys.executable, "web/manage.py", "migrate", "--verbosity", "0"],
        check=True,
        cwd=REPO,
        env=env,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "sniplink",
            "--db",
            db_path,
            "create",
            "https://example.net",
            "--alias",
            "e2e",
        ],
        check=True,
        cwd=REPO,
        env=env,
    )
    subprocess.run(
        [
            sys.executable,
            "web/manage.py",
            "shell",
            "-c",
            "from links.models import Link; assert Link.objects.filter(short_code='e2e').exists()",
        ],
        check=True,
        cwd=REPO,
        env=env,
    )
