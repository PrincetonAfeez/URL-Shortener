"""Reconcile CLI ``schema.sql`` bootstrap with Django constraints and indexes."""

from __future__ import annotations

from django.db import migrations


def _existing_indexes(schema_editor) -> set[str]:
    with schema_editor.connection.cursor() as cursor:
        return {
            row[0]
            for row in cursor.execute(
                "SELECT name FROM sqlite_master WHERE type='index'"
            ).fetchall()
        }


def reconcile_schema(apps, schema_editor) -> None:
    existing = _existing_indexes(schema_editor)
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            """
            CREATE INDEX IF NOT EXISTS clicks_link_clicked_idx
            ON clicks(link_id, clicked_at)
            """
        )
        for orphan in (
            "idx_clicks_link_id",
            "idx_clicks_clicked_at",
            "links_short_code_idx",
            "links_link_short_c_8ec64e_idx",
            "idx_links_short_code",
        ):
            if orphan in existing:
                cursor.execute(f'DROP INDEX IF EXISTS "{orphan}"')
                existing.discard(orphan)


class Migration(migrations.Migration):
    dependencies = [
        ("links", "0003_rename_indexes"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(reconcile_schema, migrations.RunPython.noop),
            ],
            state_operations=[
                migrations.RemoveIndex(
                    model_name="link",
                    name="links_short_code_idx",
                ),
            ],
        ),
    ]
