# Schema Reference

## Overview

`sniplink` uses a small relational schema centered on shortened links. The `links` table owns the short-code mapping. The `clicks` table records redirect analytics. The `health_check_results` table records outbound health-check probes for saved destinations.

## Entity Summary

| Table | Role |
| --- | --- |
| `links` | Stores each short code and its destination URL. |
| `clicks` | Stores click/redirect events for analytics. |
| `health_check_results` | Stores health-check attempts for destination URLs. |

## `links`

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `INTEGER` | Yes | Primary key; autoincremented internal identifier. |
| `short_code` | `TEXT` | Yes | Public short code; unique. |
| `destination_url` | `TEXT` | Yes | Full URL that the short code redirects to. |
| `redirect_status` | `INTEGER` | Yes | Defaults to `302`; allowed values are `301`, `302`, `307`, `308`. |
| `created_at` | `TEXT` | Yes | Timestamp when the link was created. |
| `expires_at` | `TEXT` | No | Optional expiration timestamp. |
| `disabled_at` | `TEXT` | No | Optional timestamp marking the link disabled. |
| `deleted_at` | `TEXT` | No | Optional soft-delete timestamp. |
| `max_clicks` | `INTEGER` | No | Optional click limit; must be `NULL` or at least `1`. |
| `click_count` | `INTEGER` | Yes | Cached click counter; defaults to `0`; cannot be negative. |
| `metadata` | `TEXT` | Yes | JSON text; defaults to `{}` and must pass `json_valid`. |

### Link lifecycle fields

A link is normally active when:

- `disabled_at IS NULL`
- `deleted_at IS NULL`
- `expires_at IS NULL OR expires_at > current timestamp`
- `max_clicks IS NULL OR click_count < max_clicks`

## `clicks`

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `INTEGER` | Yes | Primary key; autoincremented internal identifier. |
| `link_id` | `INTEGER` | Yes | Foreign key to `links.id`; cascades on delete. |
| `clicked_at` | `TEXT` | Yes | Timestamp when the click occurred. |
| `referrer` | `TEXT` | No | Optional referring URL/header. |
| `user_agent` | `TEXT` | No | Optional user-agent string. |

## `health_check_results`

| Column | Type | Required | Notes |
| --- | --- | --- | --- |
| `id` | `INTEGER` | Yes | Primary key; autoincremented internal identifier. |
| `link_id` | `INTEGER` | Yes | Foreign key to `links.id`; cascades on delete. |
| `checked_at` | `TEXT` | Yes | Timestamp when the health check ran. |
| `status_code` | `INTEGER` | No | HTTP status code returned by the destination, when available. |
| `error` | `TEXT` | No | Error message for failed checks. |
| `elapsed_ms` | `REAL` | Yes | Request duration in milliseconds. |
| `redirect_count` | `INTEGER` | Yes | Number of redirects followed; defaults to `0`. |

## Indexes

| Index | Table | Columns | Purpose |
| --- | --- | --- | --- |
| `idx_links_created_at` | `links` | `created_at` | Speeds chronological listing/reporting. |
| `idx_links_lifecycle` | `links` | `disabled_at`, `deleted_at`, `expires_at` | Speeds active/gone lifecycle checks. |
| `idx_clicks_link_clicked` | `clicks` | `link_id`, `clicked_at` | Speeds per-link click history and stats. |
| `idx_health_link_checked` | `health_check_results` | `link_id`, `checked_at` | Speeds per-link health-check history. |

## Relationships

- One `links` row can have many `clicks` rows.
- One `links` row can have many `health_check_results` rows.
- Deleting a link cascades to its click analytics and health-check history.
