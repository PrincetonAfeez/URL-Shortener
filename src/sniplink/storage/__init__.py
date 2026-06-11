"""Storage components. """

from sniplink.storage.base import Storage
from sniplink.storage.sqlite_store import SQLiteStorage

__all__ = ["SQLiteStorage", "Storage"]
