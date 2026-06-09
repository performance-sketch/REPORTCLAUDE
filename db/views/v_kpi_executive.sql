CREATE OR REPLACE VIEW v_kpi_executive AS
SELECT
    CURRENT_DATE - INTERVAL '30 days'           AS period_start,
    CURRENT_DATE                                 AS period_end,

    -- Meta Ads
    COALESCE(SUM(m.spend), 0)                   AS meta_spend,
    COALESCE(SUM(m.impressions), 0)             AS impressions,
    COALESCE(SUM(m.clicks), 0)                  AS clicks,
    COALESCE(SUM(m.purchases), 0)               AS meta_purchases,
    COALESCE(SUM(m.conversion_value), 0)        AS meta_conversion_value,

    -- Rezdy confirmadas
    COALESCE(b.confirmed_count, 0)              AS bookings_confirmed,
    COALESCE(b.created_count, 0)                AS bookings_created,
    COALESCE(b.cancelled_count, 0)              AS bookings_cancelled,
    COALESCE(b.confirmed_revenue, 0)            AS confirmed_revenue,
    COALESCE(b.total_pax, 0)                    AS total_pax,

    -- KPIs derivados
    CASE WHEN COALESCE(SUM(m.spend), 0) > 0
         THEN ROUND(COALESCE(b.confirmed_revenue, 0) / SUM(m.spend), 4)
         ELSE NULL END                           AS roas_real,

    CASE WHEN COALESCE(b.confirmed_count, 0) > 0
         THEN ROUND(COALESCE(SUM(m.spend), 0) / b.confirmed_count, 2)
         ELSE NULL END                           AS cac,

    CASE WHEN COALESCE(b.confirmed_count, 0) > 0
         THEN ROUND(COALESCE(b.confirmed_revenue, 0) / b.confirmed_count, 2)
         ELSE NULL END                           AS avg_ticket,

    CASE WHEN COALESCE(SUM(m.impressions), 0) > 0
         THEN ROUND(SUM(m.clicks) / SUM(m.impressions) * 100, 4)
         ELSE NULL END                           AS ctr_pct,

    CASE WHEN COALESCE(SUM(m.clicks), 0) > 0
         THEN ROUND(SUM(m.spend) / SUM(m.clicks), 4)
         ELSE NULL END                           AS cpc,

    CASE WHEN COALESCE(SUM(m.impressions), 0) > 0
         THEN ROUND(SUM(m.spend) * 1000 / SUM(m.impressions), 4)
         ELSE NULL END                           AS cpm,

    CASE WHEN COALESCE(SUM(m.clicks), 0) > 0
         THEN ROUND(COALESCE(b.created_count::numeric, 0) / SUM(m.clicks), 4)
         ELSE NULL END                           AS click_to_booking_rate,

    CASE WHEN COALESCE(b.created_count, 0) > 0
         THEN ROUND(COALESCE(b.cancelled_count::numeric, 0) / b.created_count, 4)
         ELSE NULL END                           AS cancellation_rate

FROM fact_meta_ad_performance_daily m
CROSS JOIN (
    SELECT
        COUNT(*) FILTER (WHERE order_status = 'CONFIRMED')                          AS confirmed_count,
        COUNT(*)                                                                      AS created_count,
        COUNT(*) FILTER (WHERE order_status IN ('CANCELLED','ABANDONED_CART'))       AS cancelled_count,
        SUM(gross_revenue) FILTER (WHERE order_status = 'CONFIRMED')                AS confirmed_revenue,
        SUM(quantity)                                                                 AS total_pax
    FROM fact_rezdy_bookings
    WHERE booking_created_at >= CURRENT_DATE - INTERVAL '30 days'
) b
WHERE m.date >= CURRENT_DATE - INTERVAL '30 days'
GROUP BY b.confirmed_count, b.created_count, b.cancelled_count, b.confirmed_revenue, b.total_pax;
