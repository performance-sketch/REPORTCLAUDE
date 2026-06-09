CREATE OR REPLACE VIEW v_meta_ads_daily AS
SELECT
    date,
    account_id,
    account_name,
    campaign_id,
    campaign_name,
    SUM(impressions)           AS impressions,
    SUM(reach)                 AS reach,
    SUM(clicks)                AS clicks,
    SUM(link_clicks)           AS link_clicks,
    SUM(landing_page_views)    AS landing_page_views,
    SUM(spend)                 AS spend,
    SUM(leads)                 AS leads,
    SUM(purchases)             AS purchases,
    SUM(conversion_value)      AS conversion_value,

    CASE WHEN SUM(impressions) > 0
         THEN ROUND(SUM(clicks) / SUM(impressions) * 100, 4) END    AS ctr_pct,
    CASE WHEN SUM(clicks) > 0
         THEN ROUND(SUM(spend) / SUM(clicks), 4) END                AS cpc,
    CASE WHEN SUM(impressions) > 0
         THEN ROUND(SUM(spend) * 1000 / SUM(impressions), 4) END    AS cpm,
    CASE WHEN SUM(purchases) > 0
         THEN ROUND(SUM(spend) / SUM(purchases), 2) END             AS cpa,
    CASE WHEN SUM(spend) > 0
         THEN ROUND(SUM(conversion_value) / SUM(spend), 4) END      AS roas_meta

FROM fact_meta_ad_performance_daily
GROUP BY date, account_id, account_name, campaign_id, campaign_name
ORDER BY date DESC, spend DESC;
