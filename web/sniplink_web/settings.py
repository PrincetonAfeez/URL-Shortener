"""Django settings — reads engine config from ``sniplink.toml``.

The CLI / raw socket server / WSGI app and the Django app all flow through
:func:`sniplink.config.load_config`. That keeps the database path, redirect
defaults, and limits in one place; otherwise the two front ends could quietly
disagree about where ``sniplink.db`` lives.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
ROOT_DIR = BASE_DIR.parent
sys.path.insert(0, str(ROOT_DIR / "src"))

# Importing this requires src/ to be on sys.path (line above).
from sniplink.config import load_config  # noqa: E402

_CONFIG = load_config()

SECRET_KEY = os.environ.get("SNIPLINK_SECRET_KEY", "sniplink-dev-key-change-in-prod")
DEBUG = os.environ.get("SNIPLINK_DJANGO_DEBUG", "true").lower() != "false"
ALLOWED_HOSTS = ["127.0.0.1", "localhost", "testserver"]

INSTALLED_APPS = [
    "django.contrib.contenttypes",
    "django.contrib.staticfiles",
    "links.apps.LinksConfig",
]

# CSRF middleware is included so HTMX form posts go through the standard
# Django protection (see ADR 0005). The JSON API endpoints opt out individually
# with @csrf_exempt because they have no session-cookie attack surface.
MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
]

ROOT_URLCONF = "sniplink_web.urls"
WSGI_APPLICATION = "sniplink_web.wsgi.application"

# The Django ORM and the SQLiteStorage both point at the same file by default.
# Override with SNIPLINK_DJANGO_DB for hermetic test runs.
DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": os.environ.get("SNIPLINK_DJANGO_DB", str(_CONFIG.database_path)),
    }
}

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.csrf",
                "django.template.context_processors.request",
            ],
        },
    }
]

STATIC_URL = "static/"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
USE_TZ = True
TIME_ZONE = "UTC"

# Hard cap on API request bodies — anything larger raises
# django.core.exceptions.RequestDataTooBig before the view sees it. The API
# views catch that and return 413 Payload Too Large.
DATA_UPLOAD_MAX_MEMORY_SIZE = _CONFIG.api.max_body_bytes
FILE_UPLOAD_MAX_MEMORY_SIZE = _CONFIG.api.max_body_bytes

# Surfaced for the views / templates so they don't have to re-load the TOML
# on every request (bug #5 in the fourth-pass review). Add more values here
# rather than calling sniplink.config.load_config from the views.
SNIPLINK_BASE_URL = os.environ.get("SNIPLINK_BASE_URL", _CONFIG.default_base_url)
SNIPLINK_API_MAX_BODY_BYTES = _CONFIG.api.max_body_bytes
SNIPLINK_RESERVED_CODES = tuple(_CONFIG.reserved_codes)
SNIPLINK_RESERVED_PREFIXES = SNIPLINK_RESERVED_CODES
SNIPLINK_BASE_ALIASES = tuple(_CONFIG.base_aliases)
SNIPLINK_DEFAULT_REDIRECT_STATUS = _CONFIG.default_redirect_status
SNIPLINK_COLLISION_RETRY_LIMIT = _CONFIG.collision_retry_limit
SNIPLINK_API_KEY = os.environ.get("SNIPLINK_API_KEY")
SNIPLINK_MAX_REQUEST_PATH_BYTES = _CONFIG.max_request_path_bytes
