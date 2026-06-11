# Schema Folder — URL Shortener / sniplink

This folder documents the simple database schema for the `sniplink` URL shortener project.

The application stores three core entities:

1. `links` — the shortened URL records.
2. `clicks` — redirect/click analytics tied to a link.
3. `health_check_results` — async health-check results tied to a link.

## Files

| File | Purpose |
| --- | --- |
| `database_schema.sql` | SQLite DDL for the three canonical tables and indexes. |
| `schema_reference.md` | Human-readable schema/data dictionary. |
| `entity_relationships.mmd` | Mermaid ERD diagram for documentation tools that support Mermaid. |
| `sample_queries.sql` | Useful SQL queries for inspection, analytics, and health checks. |

## How to use

To create a fresh SQLite database manually:

```bash
sqlite3 sniplink.db < Schema/database_schema.sql
```

For normal project usage, prefer the existing application bootstrap commands:

```bash
sniplink init-db
# or, for Django-first setup
python web/manage.py migrate
```

This folder is meant to make the schema easy to review in a portfolio, README, technical design document, or project defense.
