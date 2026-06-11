"""Django bootstrap shared by every test under ``tests/integration/django/``.

Module-level setup runs once per pytest invocation:

* a fresh SQLite file is created under ``tempfile.mkdtemp(...)`` and
  registered for ``shutil.rmtree`` at interpreter exit, so successive runs
  do not leak ``sniplink_django_tests_*.sqlite3`` files into the system
  temp folder (bug #30 in the second-pass review).
* ``django.setup()`` is called once so test modules can do
  ``from links import models`` at the top.
* ``call_command("migrate")`` builds the schema in the temp DB.

The autouse DB fixture lives **only** in this subdirectory's conftest, so
non-Django integration tests (raw socket / WSGI / CLI / async health
checker) do not pay the transactional-DB setup cost — see bug #11 in the
third-pass review.
"""

from __future__ import annotations

import atexit
import os
import shutil
import tempfile

import pytest

_TMP_ROOT = tempfile.mkdtemp(prefix="sniplink_django_test_")
atexit.register(shutil.rmtree, _TMP_ROOT, ignore_errors=True)

os.environ["SNIPLINK_DJANGO_DB"] = os.path.join(_TMP_ROOT, "test.sqlite3")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "sniplink_web.settings")

import django  # noqa: E402

django.setup()

from django.core.management import call_command  # noqa: E402

call_command("migrate", verbosity=0, interactive=False)


try:
    import pytest_django  # noqa: F401

    _HAS_PYTEST_DJANGO = True
except ImportError:
    _HAS_PYTEST_DJANGO = False


if _HAS_PYTEST_DJANGO:

    @pytest.fixture(autouse=True)
    def _django_db_access(db):  # noqa: PT004
        """Enable DB access for every Django test under transaction rollback."""

        yield

else:

    @pytest.fixture(autouse=True)
    def _django_db_access():  # noqa: PT004
        from links import models

        models.Click.objects.all().delete()
        models.HealthCheckResult.objects.all().delete()
        models.Link.objects.all().delete()
        yield
