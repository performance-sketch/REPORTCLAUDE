CREATE OR REPLACE VIEW v_funnel AS
WITH meta AS (
    SELECT
        campaign_id,
        campaign_name,
        SUM(impressions)         AS impressions,
        SUM(clicks)              AS clicks,
        SUM(landing_page_views)  AS landing_page_views,
        SUM(spend)               AS spend
    FROM fact_meta_ad_performance_daily
    GROUP BY campaign_id, campaign_name
),
bookings AS (
    SELECT
        utm_campaign                                                                          AS campaign_name,
        COUNT(*)                                                                              AS bookings_created,
        COUNT(*) FILTER (WHERE order_status = 'CONFIRMED')                                  AS bookings_confirmed,
        COALESCE(SUM(gross_revenue) FILTER (WHERE order_status = 'CONFIRMED'), 0)           AS confirmed_revenue
    FROM fact_rezdy_bookings
    GROUP BY utm_campaign
)
SELECT
    m.campaign_id,
    m.campaign_name,
    m.impressions,
    m.clicks,
    m.landing_page_views,
    m.spend,
    COALESCE(b.bookings_created, 0)                                   AS bookings_created,
    COALESCE(b.bookings_confirmed, 0)                                 AS bookings_confirmed,
    COALESCE(b.confirmed_revenue, 0)                                  AS confirmed_revenue,

    CASE WHEN m.impressions > 0 THEN ROUND(m.clicks / m.impressions, 6) END           AS imp_to_click_rate,
    CASE WHEN m.clicks > 0 THEN ROUND(b.bookings_created::numeric / m.clicks, 6) END  AS click_to_booking_rate,
    CASE WHEN b.bookings_created > 0
         THEN ROUND(b.bookings_confirmed::numeric / b.bookings_created, 4) END         AS booking_confirmation_rate,
    CASE WHEN b.bookings_created > 0 THEN ROUND(m.spend / b.bookings_created, 2) END  AS cost_per_booking_created,
    CASE WHEN b.bookings_confirmed > 0 THEN ROUND(m.spend / b.bookings_confirmed, 2) END AS cost_per_booking_confirmed,
    CASE WHEN m.clicks > 0 THEN ROUND(b.confirmed_revenue / m.clicks, 4) END          AS revenue_per_click,
    CASE WHEN m.spend > 0 THEN ROUND(b.confirmed_revenue / m.spend, 4) END             AS roas_real

FROM meta m
LEFT JOIN bookings b ON LOWER(b.campaign_name) = LOWER(m.campaign_name)
ORDER BY m.spend DESC;
