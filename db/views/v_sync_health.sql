CREATE OR REPLACE VIEW v_sync_health AS
WITH last_sync AS (
    SELECT DISTINCT ON (source)
        source,
        sync_type,
        started_at,
        finished_at,
        status,
        records_processed,
        records_failed,
        error_message,
        EXTRACT(EPOCH FROM (finished_at - started_at))::int AS duration_seconds
    FROM fact_sync_health
    ORDER BY source, started_at DESC
),
pending_events AS (
    SELECT
        source,
        COUNT(*) FILTER (WHERE processing_status = 'pending')  AS pending_count,
        COUNT(*) FILTER (WHERE processing_status = 'error')    AS error_count,
        MAX(received_at)                                         AS last_received_at
    FROM raw_events
    GROUP BY source
)
SELECT
    ls.source,
    ls.sync_type,
    ls.started_at          AS last_sync_started,
    ls.finished_at         AS last_sync_finished,
    ls.status              AS last_sync_status,
    ls.records_processed,
    ls.records_failed,
    ls.duration_seconds,
    ls.error_message,
    COALESCE(pe.pending_count, 0)  AS pending_events,
    COALESCE(pe.error_count, 0)    AS error_events,
    pe.last_received_at
FROM last_sync ls
LEFT JOIN pending_events pe USING (source);
