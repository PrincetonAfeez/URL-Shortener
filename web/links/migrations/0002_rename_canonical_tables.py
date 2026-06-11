"""Reconcile Django legacy table names with the CLI ``schema.sql`` bootstrap.

Three upgrade paths exist in the wild:

1. **Django-first** — ``0001`` created ``links_link``; rename to ``links``.
2. **CLI-first** — ``sniplink init-db`` created ``links``; ``0001`` also
   created empty ``links_link`` shadows; drop the legacy duplicates.
3. **Greenfield** — updated ``0001`` already targets ``links``; no-op.
"""

from __future__ import annotations

from django.db import migrations


_LEGACY_TO_CANONICAL = (
    ("links_link", "links"),
    ("links_click", "clicks"),
    ("links_healthcheckresult", "health_check_results"),
)


def _table_count(schema_editor, table: str) -> int:
    with schema_editor.connection.cursor() as cursor:
        row = cursor.execute(f'SELECT COUNT(*) FROM "{table}"').fetchone()
        return int(row[0])


def _existing_tables(schema_editor) -> set[str]:
    with schema_editor.connection.cursor() as cursor:
        return {
            row[0]
            for row in cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }


def reconcile_canonical_tables(apps, schema_editor) -> None:
    tables = _existing_tables(schema_editor)
    for legacy, canonical in _LEGACY_TO_CANONICAL:
        has_legacy = legacy in tables
        has_canonical = canonical in tables
        if has_legacy and not has_canonical:
            schema_editor.execute(
                f'ALTER TABLE "{legacy}" RENAME TO "{canonical}"'
            )
            tables.discard(legacy)
            tables.add(canonical)
        elif has_legacy and has_canonical:
            legacy_rows = _table_count(schema_editor, legacy)
            canonical_rows = _table_count(schema_editor, canonical)
            if legacy_rows > 0 and canonical_rows == 0:
                schema_editor.execute(
                    f'INSERT INTO "{canonical}" SELECT * FROM "{legacy}"'
                )
                schema_editor.execute(f'DROP TABLE IF EXISTS "{legacy}"')
            elif legacy_rows == 0:
                schema_editor.execute(f'DROP TABLE IF EXISTS "{legacy}"')
            elif legacy_rows > 0:
                raise RuntimeError(
                    f"Cannot reconcile {legacy!r} and {canonical!r}: "
                    "both tables contain rows; manual merge required."
                )


class Migration(migrations.Migration):
    dependencies = [
        ("links", "0001_initial"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    reconcile_canonical_tables,
                    migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.AlterModelTable(name="Link", table="links"),
                migrations.AlterModelTable(name="Click", table="clicks"),
                migrations.AlterModelTable(
                    name="HealthCheckResult",
                    table="health_check_results",
                ),
            ],
        ),
    ]
