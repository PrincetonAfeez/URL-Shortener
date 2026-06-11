"""WSGI application for the sniplink web app. """

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT_DIR / "src"))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sniplink_web.settings")

from django.core.wsgi import get_wsgi_application

application = get_wsgi_application()
