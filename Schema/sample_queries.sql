-- Schema/sample_queries.sql
-- Useful inspection queries for the sniplink schema.

-- 1. List newest links first.
SELECT
    id,
    short_code,
    destination_url,
    redirect_status,
    created_at,
    click_count
FROM links
ORDER BY created_at DESC;

-- 2. Resolve an active short code.
-- Replace :short_code with the target code when using a client that supports parameters.
SELECT
    id,
    short_code,
    destination_url,
    redirect_status
FROM links
WHERE short_code = :short_code
  AND disabled_at IS NULL
  AND deleted_at IS NULL
  AND (expires_at IS NULL OR expires_at > datetime('now'))
  AND (max_clicks IS NULL OR click_count < max_clicks);

-- 3. Count clicks per link.
SELECT
    l.short_code,
    l.destination_url,
    COUNT(c.id) AS recorded_clicks,
    l.click_count AS cached_click_count
FROM links AS l
LEFT JOIN clicks AS c ON c.link_id = l.id
GROUP BY l.id, l.short_code, l.destination_url, l.click_count
ORDER BY recorded_clicks DESC;

-- 4. Show recent click events.
SELECT
    l.short_code,
    c.clicked_at,
    c.referrer,
    c.user_agent
FROM clicks AS c
JOIN links AS l ON l.id = c.link_id
ORDER BY c.clicked_at DESC
LIMIT 50;

-- 5. Show latest health-check result per link.
WITH latest_checks AS (
    SELECT
        link_id,
        MAX(checked_at) AS latest_checked_at
    FROM health_check_results
    GROUP BY link_id
)
SELECT
    l.short_code,
    h.checked_at,
    h.status_code,
    h.error,
    h.elapsed_ms,
    h.redirect_count
FROM health_check_results AS h
JOIN latest_checks AS lc
  ON lc.link_id = h.link_id
 AND lc.latest_checked_at = h.checked_at
JOIN links AS l ON l.id = h.link_id
ORDER BY h.checked_at DESC;
