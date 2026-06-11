-- Schema/database_schema.sql
-- Simple SQLite schema for the sniplink URL shortener.
-- Canonical application tables: links, clicks, health_check_results.

PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS links (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    short_code TEXT NOT NULL UNIQUE,
    destination_url TEXT NOT NULL,
    redirect_status INTEGER NOT NULL DEFAULT 302
        CHECK (redirect_status IN (301, 302, 307, 308)),
    created_at TEXT NOT NULL,
    expires_at TEXT,
    disabled_at TEXT,
    deleted_at TEXT,
    max_clicks INTEGER
        CHECK (max_clicks IS NULL OR max_clicks >= 1),
    click_count INTEGER NOT NULL DEFAULT 0
        CHECK (click_count >= 0),
    metadata TEXT NOT NULL DEFAULT '{}'
        CHECK (json_valid(metadata))
);

CREATE INDEX IF NOT EXISTS idx_links_created_at
    ON links(created_at);

CREATE INDEX IF NOT EXISTS idx_links_lifecycle
    ON links(disabled_at, deleted_at, expires_at);

CREATE TABLE IF NOT EXISTS clicks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id INTEGER NOT NULL
        REFERENCES links(id) ON DELETE CASCADE,
    clicked_at TEXT NOT NULL,
    referrer TEXT,
    user_agent TEXT
);

CREATE INDEX IF NOT EXISTS idx_clicks_link_clicked
    ON clicks(link_id, clicked_at);

CREATE TABLE IF NOT EXISTS health_check_results (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    link_id INTEGER NOT NULL
        REFERENCES links(id) ON DELETE CASCADE,
    checked_at TEXT NOT NULL,
    status_code INTEGER,
    error TEXT,
    elapsed_ms REAL NOT NULL,
    redirect_count INTEGER NOT NULL DEFAULT 0
);

CREATE INDEX IF NOT EXISTS idx_health_link_checked
    ON health_check_results(link_id, checked_at);
