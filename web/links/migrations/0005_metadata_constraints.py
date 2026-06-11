"""Normalize ``metadata`` for CLI-first shared databases."""

from __future__ import annotations

from django.db import migrations, models


def normalize_metadata(apps, schema_editor) -> None:
    with schema_editor.connection.cursor() as cursor:
        cursor.execute(
            "UPDATE links SET metadata = '{}' WHERE metadata IS NULL OR metadata = ''"
        )


class Migration(migrations.Migration):
    dependencies = [
        ("links", "0004_reconcile_schema"),
    ]

    operations = [
        migrations.RunPython(normalize_metadata, migrations.RunPython.noop),
        migrations.AlterField(
            model_name="link",
            name="metadata",
            field=models.JSONField(blank=True, default=dict),
        ),
    ]
