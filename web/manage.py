#!/usr/bin/env python

"""Django management command for the sniplink web app. """

from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> None:
    root = Path(__file__).resolve().parent.parent
    sys.path.insert(0, str(root / "src"))
    sys.path.insert(0, str(root / "web"))
    os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sniplink_web.settings")

    from django.core.management import execute_from_command_line

    execute_from_command_line(sys.argv)


if __name__ == "__main__":
    main()
