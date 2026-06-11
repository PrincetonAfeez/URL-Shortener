"""Rename Django auto-generated index names to stable canonical names.

CLI ``schema.sql`` bootstrap creates different index names
(``idx_links_short_code``, etc.). This migration renames whichever legacy
name is present and skips missing indexes so ``migrate --fake-initial`` after
``sniplink init-db`` succeeds.
"""

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


# Each tuple lists acceptable source names for one canonical Django index.
_INDEX_RENAME_CANDIDATES: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("links_short_code_idx", ("links_link_short_c_8ec64e_idx", "idx_links_short_code")),
    ("links_created_at_idx", ("links_link_created_789b6d_idx", "idx_links_created_at")),
    (
        "links_lifecycle_idx",
        ("links_link_disable_02489a_idx", "idx_links_lifecycle"),
    ),
    (
        "clicks_link_clicked_idx",
        ("links_click_link_id_a8dd16_idx", "idx_clicks_link_id"),
    ),
    (
        "health_link_checked_idx",
        ("links_healt_link_id_d8db9b_idx", "idx_health_link_checked"),
    ),
)


def _recreate_index(schema_editor, old_name: str, new_name: str) -> None:
    """SQLite in this environment lacks ``ALTER INDEX … RENAME``."""

    connection = schema_editor.connection
    with connection.cursor() as cursor:
        row = cursor.execute(
            "SELECT sql FROM sqlite_master WHERE type='index' AND name=%s",
            [old_name],
        ).fetchone()
        if not row or not row[0]:
            return
        create_sql = row[0]
        for pattern in (
            f'INDEX "{old_name}"',
            f"INDEX '{old_name}'",
            f"INDEX {old_name}",
        ):
            if pattern in create_sql:
                create_sql = create_sql.replace(pattern, f'INDEX "{new_name}"', 1)
                break
        else:
            return
        cursor.execute(create_sql)
        cursor.execute(f'DROP INDEX "{old_name}"')


def rename_indexes_when_present(apps, schema_editor) -> None:
    existing = _existing_indexes(schema_editor)
    for new_name, old_names in _INDEX_RENAME_CANDIDATES:
        if new_name in existing:
            continue
        for old_name in old_names:
            if old_name in existing:
                _recreate_index(schema_editor, old_name, new_name)
                existing.discard(old_name)
                existing.add(new_name)
                break


class Migration(migrations.Migration):
    dependencies = [
        ("links", "0002_rename_canonical_tables"),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            database_operations=[
                migrations.RunPython(
                    rename_indexes_when_present,
                    migrations.RunPython.noop,
                ),
            ],
            state_operations=[
                migrations.RenameIndex(
                    model_name="link",
                    new_name="links_short_code_idx",
                    old_name="links_link_short_c_8ec64e_idx",
                ),
                migrations.RenameIndex(
                    model_name="link",
                    new_name="links_created_at_idx",
                    old_name="links_link_created_789b6d_idx",
                ),
                migrations.RenameIndex(
                    model_name="link",
                    new_name="links_lifecycle_idx",
                    old_name="links_link_disable_02489a_idx",
                ),
                migrations.RenameIndex(
                    model_name="click",
                    new_name="clicks_link_clicked_idx",
                    old_name="links_click_link_id_a8dd16_idx",
                ),
                migrations.RenameIndex(
                    model_name="healthcheckresult",
                    new_name="health_link_checked_idx",
                    old_name="links_healt_link_id_d8db9b_idx",
                ),
            ],
        ),
    ]
