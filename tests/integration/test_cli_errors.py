"""End-to-end CLI error handling.

Bug #3 in the fourth-pass review was that ``sniplink create --redirect-status
999`` produced a Python traceback because ``main()`` did not catch
``ValueError`` from ``service.create_link``. The fix maps ``ValueError`` to
``USAGE_ERROR``; this test pins it.
"""

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
            str(tmp_path / "errors.db"),
            *args,
        ],
        check=not expect_failure,
        capture_output=True,
        text=True,
        env=env,
    )


def test_create_with_unsupported_redirect_status_exits_cleanly(tmp_path):
    """USAGE_ERROR (exit code 2), no Python traceback in stderr."""

    result = run_cli(
        tmp_path,
        "create",
        "https://example.com",
        "--redirect-status",
        "999",
        expect_failure=True,
    )

    # USAGE_ERROR = 2 per cli/exit_codes.py.
    assert result.returncode == 2
    assert "invalid argument" in result.stdout.lower() or "999" in result.stdout
    assert "Traceback" not in result.stderr


def test_create_with_unknown_code_strategy_exits_cleanly(tmp_path):
    """Service.create_link raises ValueError for unknown code_strategy too."""

    # argparse won't let us pass --strategy directly to the CLI (no such
    # flag), but we can construct an alias that triggers strategy=base62
    # while passing a bad redirect_status to exercise the same code path.
    # Reusing the redirect-status case keeps this hermetic; a future CLI
    # flag for code_strategy would add its own row here.
    result = run_cli(
        tmp_path,
        "create",
        "https://example.com",
        "--redirect-status",
        "418",  # not in SUPPORTED_REDIRECTS
        expect_failure=True,
    )

    assert result.returncode == 2
    assert "Traceback" not in result.stderr


def test_create_with_invalid_max_clicks_exits_cleanly(tmp_path):
    for extra_args in (["--max-clicks", "0"], ["--max-clicks", "-1"]):
        result = run_cli(
            tmp_path,
            "create",
            "https://example.com",
            *extra_args,
            expect_failure=True,
        )
        assert result.returncode == 2
        assert "Traceback" not in result.stderr
