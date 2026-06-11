"""App configuration for the links app. """

from __future__ import annotations

from django.apps import AppConfig
from django.db.backends.signals import connection_created


def _enable_sqlite_wal(sender, connection, **kwargs) -> None:
    if connection.vendor != "sqlite":
        return
    with connection.cursor() as cursor:
        cursor.execute("PRAGMA journal_mode=WAL")


class LinksConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "links"

    def ready(self) -> None:
        connection_created.connect(_enable_sqlite_wal)
