
USE product_analytics_db;


SELECT 
    event_date,
    COUNT(DISTINCT user_id) AS DAU
FROM user_events
GROUP BY event_date
ORDER BY event_date DESC;


SELECT 
    YEARWEEK(event_timestamp, 1) AS year_week,
    COUNT(DISTINCT user_id) AS WAU
FROM user_events
GROUP BY year_week
ORDER BY year_week DESC;


SELECT 
    DATE_FORMAT(event_date, '%Y-%m') AS year_month,
    COUNT(DISTINCT user_id) AS MAU
FROM user_events
GROUP BY year_month
ORDER BY year_month DESC;


SELECT 
    DATE_FORMAT(event_date, '%Y-%m') AS year_month,
    SUM(revenue) AS total_revenue,
    COUNT(DISTINCT user_id) AS total_users,
    COUNT(DISTINCT CASE WHEN revenue > 0 THEN user_id END) AS paying_users,
    ROUND(SUM(revenue) / COUNT(DISTINCT user_id), 2) AS ARPU,
    ROUND(SUM(revenue) / NULLIF(COUNT(DISTINCT CASE WHEN revenue > 0 THEN user_id END), 0), 2) AS ARPPU
FROM user_events
GROUP BY year_month
ORDER BY year_month DESC;


WITH funnel_counts AS (
    SELECT 
        SUM(CASE WHEN event_name = 'App Open' THEN 1 ELSE 0 END) AS app_opens,
        SUM(CASE WHEN event_name = 'Search' THEN 1 ELSE 0 END) AS searches,
        SUM(CASE WHEN event_name = 'Add to Cart' THEN 1 ELSE 0 END) AS add_to_carts,
        SUM(CASE WHEN event_name = 'Purchase' THEN 1 ELSE 0 END) AS purchases
    FROM user_events
)
SELECT 
    app_opens,
    searches,
    add_to_carts,
    purchases,
    ROUND(searches * 100.0 / NULLIF(app_opens, 0), 2) AS open_to_search_pct,
    ROUND(add_to_carts * 100.0 / NULLIF(searches, 0), 2) AS search_to_cart_pct,
    ROUND(purchases * 100.0 / NULLIF(add_to_carts, 0), 2) AS cart_to_purchase_pct,
    ROUND(purchases * 100.0 / NULLIF(app_opens, 0), 2) AS overall_conversion_pct
FROM funnel_counts;


WITH user_first_seen AS (
    SELECT 
        user_id,
        MIN(event_date) AS first_date,
        DATE_FORMAT(MIN(event_date), '%Y-%m') AS cohort_month
    FROM user_events
    GROUP BY user_id
),
user_activity AS (
    SELECT DISTINCT
        e.user_id,
        f.cohort_month,
        DATE_FORMAT(e.event_date, '%Y-%m') AS activity_month
    FROM user_events e
    JOIN user_first_seen f ON e.user_id = f.user_id
)
SELECT 
    cohort_month,
    activity_month,
    COUNT(DISTINCT user_id) AS active_users
FROM user_activity
GROUP BY cohort_month, activity_month
ORDER BY cohort_month, activity_month;

SELECT 
    traffic_source,
    campaign,
    COUNT(DISTINCT user_id) AS total_users,
    SUM(revenue) AS total_revenue,
    ROUND(AVG(revenue), 2) AS avg_revenue_per_user
FROM user_events
GROUP BY traffic_source, campaign
ORDER BY total_revenue DESC
LIMIT 10;