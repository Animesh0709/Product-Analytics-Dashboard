"""
sql_engine.py
=============

SQL Analytics Layer for the Product Analytics Platform.

This module moves business calculations that were previously done in
Pandas into parameterized SQL, executed against the SQLite database built
by ``database.py``. It exposes 30+ named query functions that mirror the
KPIs and breakdowns used across the dashboard (DAU/WAU/MAU, revenue,
funnels, retention, growth rates, top-N breakdowns, etc.).

Every function returns a pandas DataFrame and accepts an optional
``filters`` dict with the SAME shape used by the Streamlit sidebar so the
SQL layer and the existing pandas layer stay consistent:

    filters = {
        "start_date": "2025-01-01", "end_date": "2025-06-30",
        "countries": [...], "devices": [...], "campaigns": [...],
        "user_types": [...], "subscriptions": [...], "traffic_sources": [...],
    }

All string values are passed as bound parameters (never f-string'd into the
SQL body) to avoid injection issues, even though this is a local analytics
database.
"""

from __future__ import annotations

import logging
from typing import Any

import pandas as pd

from database import run_query

logger = logging.getLogger(__name__)

TABLE = "user_events"

FilterDict = dict[str, Any]


# --------------------------------------------------------------------------
# FILTER -> WHERE CLAUSE BUILDER
# --------------------------------------------------------------------------
def _build_where(filters: FilterDict | None) -> tuple[str, list[Any]]:
    """Translate a dashboard filter dict into a SQL WHERE clause + params.

    Args:
        filters: Optional filter dictionary (see module docstring for shape).

    Returns:
        Tuple of (where_clause_string, bound_params_list). where_clause_string
        is either "" or starts with " WHERE ...".
    """
    if not filters:
        return "", []

    clauses: list[str] = []
    params: list[Any] = []

    if filters.get("start_date"):
        clauses.append("event_date >= ?")
        params.append(str(filters["start_date"]))
    if filters.get("end_date"):
        clauses.append("event_date <= ?")
        params.append(str(filters["end_date"]))

    multi_map = {
        "countries": "country",
        "devices": "device_type",
        "campaigns": "campaign",
        "user_types": "user_type",
        "subscriptions": "subscription",
        "traffic_sources": "traffic_source",
    }
    for filter_key, column in multi_map.items():
        values = filters.get(filter_key)
        if values:
            placeholders = ",".join("?" for _ in values)
            clauses.append(f"{column} IN ({placeholders})")
            params.extend(values)

    if not clauses:
        return "", []
    return " WHERE " + " AND ".join(clauses), params


def _q(sql: str, filters: FilterDict | None = None) -> pd.DataFrame:
    """Append a WHERE clause built from ``filters`` to ``sql`` (which must
    contain a ``{where}`` placeholder) and execute it."""
    where, params = _build_where(filters)
    return run_query(sql.format(where=where), tuple(params) if params else None)


# --------------------------------------------------------------------------
# 1-3. ACTIVE USERS: DAU / WAU / MAU
# --------------------------------------------------------------------------
def dau(filters: FilterDict | None = None) -> pd.DataFrame:
    """Daily Active Users."""
    sql = f"""
        SELECT event_date AS date, COUNT(DISTINCT user_id) AS dau
        FROM {TABLE}
        {{where}}
        GROUP BY event_date
        ORDER BY event_date
    """
    return _q(sql, filters)


def wau(filters: FilterDict | None = None) -> pd.DataFrame:
    """Weekly Active Users (ISO year-week buckets)."""
    sql = f"""
        SELECT strftime('%Y-W%W', event_date) AS year_week,
               COUNT(DISTINCT user_id) AS wau
        FROM {TABLE}
        {{where}}
        GROUP BY year_week
        ORDER BY year_week
    """
    return _q(sql, filters)


def mau(filters: FilterDict | None = None) -> pd.DataFrame:
    """Monthly Active Users."""
    sql = f"""
        SELECT strftime('%Y-%m', event_date) AS year_month,
               COUNT(DISTINCT user_id) AS mau
        FROM {TABLE}
        {{where}}
        GROUP BY year_month
        ORDER BY year_month
    """
    return _q(sql, filters)


def stickiness_dau_mau(filters: FilterDict | None = None) -> pd.DataFrame:
    """DAU/MAU stickiness ratio per month (engagement quality signal)."""
    sql = f"""
        WITH daily AS (
            SELECT strftime('%Y-%m', event_date) AS ym, event_date,
                   COUNT(DISTINCT user_id) AS d
            FROM {TABLE} {{where}}
            GROUP BY event_date
        ), monthly AS (
            SELECT strftime('%Y-%m', event_date) AS ym,
                   COUNT(DISTINCT user_id) AS m
            FROM {TABLE} {{where}}
            GROUP BY ym
        )
        SELECT daily.ym AS year_month,
               ROUND(AVG(daily.d), 1) AS avg_dau,
               monthly.m AS mau,
               ROUND(100.0 * AVG(daily.d) / NULLIF(monthly.m, 0), 2) AS stickiness_pct
        FROM daily JOIN monthly ON daily.ym = monthly.ym
        GROUP BY daily.ym
        ORDER BY daily.ym
    """
    return _q(sql, filters)


# --------------------------------------------------------------------------
# 4-6. REVENUE / ARPU / ARPPU
# --------------------------------------------------------------------------
def revenue_trend(filters: FilterDict | None = None) -> pd.DataFrame:
    """Daily revenue trend."""
    sql = f"""
        SELECT event_date AS date, ROUND(SUM(revenue), 2) AS revenue
        FROM {TABLE} {{where}}
        GROUP BY event_date ORDER BY event_date
    """
    return _q(sql, filters)


def monthly_revenue(filters: FilterDict | None = None) -> pd.DataFrame:
    """Monthly revenue, total users, paying users, ARPU, ARPPU."""
    sql = f"""
        SELECT strftime('%Y-%m', event_date) AS year_month,
               ROUND(SUM(revenue), 2) AS total_revenue,
               COUNT(DISTINCT user_id) AS total_users,
               COUNT(DISTINCT CASE WHEN revenue > 0 THEN user_id END) AS paying_users,
               ROUND(SUM(revenue) / NULLIF(COUNT(DISTINCT user_id), 0), 2) AS arpu,
               ROUND(SUM(revenue) / NULLIF(COUNT(DISTINCT CASE WHEN revenue > 0 THEN user_id END), 0), 2) AS arppu
        FROM {TABLE} {{where}}
        GROUP BY year_month ORDER BY year_month
    """
    return _q(sql, filters)


def arpu_overall(filters: FilterDict | None = None) -> pd.DataFrame:
    """Overall ARPU / ARPPU across the full filtered window."""
    sql = f"""
        SELECT ROUND(SUM(revenue), 2) AS total_revenue,
               COUNT(DISTINCT user_id) AS total_users,
               COUNT(DISTINCT CASE WHEN revenue > 0 THEN user_id END) AS paying_users,
               ROUND(SUM(revenue) / NULLIF(COUNT(DISTINCT user_id), 0), 2) AS arpu,
               ROUND(SUM(revenue) / NULLIF(COUNT(DISTINCT CASE WHEN revenue > 0 THEN user_id END), 0), 2) AS arppu
        FROM {TABLE} {{where}}
    """
    return _q(sql, filters)


def revenue_per_session(filters: FilterDict | None = None) -> pd.DataFrame:
    """Revenue per session, overall."""
    sql = f"""
        SELECT ROUND(SUM(revenue), 2) AS total_revenue,
               COUNT(DISTINCT session_id) AS total_sessions,
               ROUND(SUM(revenue) / NULLIF(COUNT(DISTINCT session_id), 0), 4) AS revenue_per_session
        FROM {TABLE} {{where}}
    """
    return _q(sql, filters)


def purchase_frequency(filters: FilterDict | None = None) -> pd.DataFrame:
    """Average number of purchase events per paying user."""
    sql = f"""
        WITH purchases AS (
            SELECT user_id, COUNT(*) AS purchase_count
            FROM {TABLE} {{where}} {"AND" if _has_where(filters) else "WHERE"} event_name = 'Purchase'
            GROUP BY user_id
        )
        SELECT COUNT(*) AS paying_users,
               ROUND(AVG(purchase_count), 2) AS avg_purchase_frequency,
               MAX(purchase_count) AS max_purchase_frequency
        FROM purchases
    """
    return _q(sql, filters)


def _has_where(filters: FilterDict | None) -> bool:
    return bool(_build_where(filters)[0])


# --------------------------------------------------------------------------
# 7-9. REVENUE BREAKDOWNS
# --------------------------------------------------------------------------
def revenue_by_country(filters: FilterDict | None = None) -> pd.DataFrame:
    """Revenue, users and ARPU by country, ranked descending."""
    sql = f"""
        SELECT country,
               ROUND(SUM(revenue), 2) AS revenue,
               COUNT(DISTINCT user_id) AS users,
               ROUND(SUM(revenue) / NULLIF(COUNT(DISTINCT user_id), 0), 2) AS arpu
        FROM {TABLE} {{where}}
        GROUP BY country ORDER BY revenue DESC
    """
    return _q(sql, filters)


def revenue_by_device(filters: FilterDict | None = None) -> pd.DataFrame:
    """Revenue, users and ARPU by device type, ranked descending."""
    sql = f"""
        SELECT device_type,
               ROUND(SUM(revenue), 2) AS revenue,
               COUNT(DISTINCT user_id) AS users,
               ROUND(SUM(revenue) / NULLIF(COUNT(DISTINCT user_id), 0), 2) AS arpu
        FROM {TABLE} {{where}}
        GROUP BY device_type ORDER BY revenue DESC
    """
    return _q(sql, filters)


def revenue_by_campaign(filters: FilterDict | None = None) -> pd.DataFrame:
    """Revenue, users and ARPU by campaign, ranked descending."""
    sql = f"""
        SELECT campaign,
               ROUND(SUM(revenue), 2) AS revenue,
               COUNT(DISTINCT user_id) AS users,
               ROUND(SUM(revenue) / NULLIF(COUNT(DISTINCT user_id), 0), 2) AS arpu
        FROM {TABLE} {{where}}
        GROUP BY campaign ORDER BY revenue DESC
    """
    return _q(sql, filters)


def revenue_by_traffic_source(filters: FilterDict | None = None) -> pd.DataFrame:
    """Revenue and users by traffic source."""
    sql = f"""
        SELECT traffic_source,
               ROUND(SUM(revenue), 2) AS revenue,
               COUNT(DISTINCT user_id) AS users
        FROM {TABLE} {{where}}
        GROUP BY traffic_source ORDER BY revenue DESC
    """
    return _q(sql, filters)


def revenue_by_subscription(filters: FilterDict | None = None) -> pd.DataFrame:
    """Revenue and users by subscription tier."""
    sql = f"""
        SELECT subscription,
               ROUND(SUM(revenue), 2) AS revenue,
               COUNT(DISTINCT user_id) AS users,
               ROUND(SUM(revenue) / NULLIF(COUNT(DISTINCT user_id), 0), 2) AS arpu
        FROM {TABLE} {{where}}
        GROUP BY subscription ORDER BY revenue DESC
    """
    return _q(sql, filters)


# --------------------------------------------------------------------------
# 10. FUNNEL
# --------------------------------------------------------------------------
def funnel(
    stages: list[str] | None = None,
    filters: FilterDict | None = None,
) -> pd.DataFrame:
    """User-level conversion funnel across ordered event stages.

    Args:
        stages: Ordered list of event_name values, e.g.
            ["App Open", "Search", "Add to Cart", "Purchase"].
        filters: Optional dashboard filter dict.

    Returns:
        DataFrame with one row per stage: stage, users, conversion_from_prev_pct,
        conversion_from_first_pct.
    """
    stages = stages or ["App Open", "Search", "Add to Cart", "Purchase"]
    where, params = _build_where(filters)
    rows = []
    for stage in stages:
        stage_where = where + (" AND " if where else " WHERE ") + "event_name = ?"
        sql = f"SELECT COUNT(DISTINCT user_id) AS users FROM {TABLE}{stage_where}"
        df = run_query(sql, tuple(params + [stage]))
        rows.append({"stage": stage, "users": int(df["users"].iloc[0]) if not df.empty else 0})

    out = pd.DataFrame(rows)
    first = out["users"].iloc[0] if not out.empty and out["users"].iloc[0] else 1
    out["conversion_from_first_pct"] = (out["users"] / first * 100).round(2)
    out["conversion_from_prev_pct"] = (
        out["users"].pct_change().fillna(0) * 100 + 100
    ).round(2)
    out.loc[0, "conversion_from_prev_pct"] = 100.0
    return out


# --------------------------------------------------------------------------
# 11-12. RETENTION
# --------------------------------------------------------------------------
def retention_by_day_bucket(filters: FilterDict | None = None) -> pd.DataFrame:
    """User counts per ``retention_day`` bucket already present in the
    dataset (0, 1, 3, 7, 14, 30, 60...)."""
    sql = f"""
        SELECT retention_day, COUNT(DISTINCT user_id) AS users
        FROM {TABLE} {{where}}
        GROUP BY retention_day ORDER BY retention_day
    """
    return _q(sql, filters)


def retention_overall_rate(filters: FilterDict | None = None) -> pd.DataFrame:
    """Overall retention rate: share of users seen again after day 0."""
    sql = f"""
        WITH first_seen AS (
            SELECT user_id, MIN(event_date) AS first_date
            FROM {TABLE} {{where}}
            GROUP BY user_id
        ), returned AS (
            SELECT DISTINCT e.user_id
            FROM {TABLE} e JOIN first_seen f ON e.user_id = f.user_id
            WHERE e.event_date > f.first_date
        )
        SELECT (SELECT COUNT(*) FROM first_seen) AS total_users,
               (SELECT COUNT(*) FROM returned) AS returning_users,
               ROUND(100.0 * (SELECT COUNT(*) FROM returned) /
                     NULLIF((SELECT COUNT(*) FROM first_seen), 0), 2) AS retention_rate_pct
    """
    return _q(sql, filters)


def returning_vs_new_users(filters: FilterDict | None = None) -> pd.DataFrame:
    """Split of events/users between New and Returning ``user_type``."""
    sql = f"""
        SELECT user_type,
               COUNT(DISTINCT user_id) AS users,
               COUNT(*) AS events,
               ROUND(SUM(revenue), 2) AS revenue
        FROM {TABLE} {{where}}
        GROUP BY user_type ORDER BY users DESC
    """
    return _q(sql, filters)


# --------------------------------------------------------------------------
# 13-14. GROWTH RATES
# --------------------------------------------------------------------------
def monthly_growth(filters: FilterDict | None = None) -> pd.DataFrame:
    """Month-over-month user growth % and revenue growth %."""
    sql = f"""
        SELECT strftime('%Y-%m', event_date) AS year_month,
               COUNT(DISTINCT user_id) AS active_users,
               ROUND(SUM(revenue), 2) AS revenue
        FROM {TABLE} {{where}}
        GROUP BY year_month ORDER BY year_month
    """
    df = _q(sql, filters)
    if df.empty:
        return df
    df["user_growth_pct"] = df["active_users"].pct_change().mul(100).round(2)
    df["revenue_growth_pct"] = df["revenue"].pct_change().mul(100).round(2)
    return df


def weekly_growth(filters: FilterDict | None = None) -> pd.DataFrame:
    """Week-over-week user growth % and revenue growth %."""
    sql = f"""
        SELECT strftime('%Y-W%W', event_date) AS year_week,
               COUNT(DISTINCT user_id) AS active_users,
               ROUND(SUM(revenue), 2) AS revenue
        FROM {TABLE} {{where}}
        GROUP BY year_week ORDER BY year_week
    """
    df = _q(sql, filters)
    if df.empty:
        return df
    df["user_growth_pct"] = df["active_users"].pct_change().mul(100).round(2)
    df["revenue_growth_pct"] = df["revenue"].pct_change().mul(100).round(2)
    return df


def campaign_growth(filters: FilterDict | None = None) -> pd.DataFrame:
    """Month-over-month growth % of revenue per campaign."""
    sql = f"""
        SELECT campaign, strftime('%Y-%m', event_date) AS year_month,
               ROUND(SUM(revenue), 2) AS revenue
        FROM {TABLE} {{where}}
        GROUP BY campaign, year_month ORDER BY campaign, year_month
    """
    df = _q(sql, filters)
    if df.empty:
        return df
    df["revenue_growth_pct"] = df.groupby("campaign")["revenue"].pct_change().mul(100).round(2)
    return df


# --------------------------------------------------------------------------
# 15. TOP COUNTRIES / 16. TOP CITIES
# --------------------------------------------------------------------------
def top_countries(n: int = 10, filters: FilterDict | None = None) -> pd.DataFrame:
    """Top-N countries by revenue."""
    sql = f"""
        SELECT country, ROUND(SUM(revenue), 2) AS revenue,
               COUNT(DISTINCT user_id) AS users
        FROM {TABLE} {{where}}
        GROUP BY country ORDER BY revenue DESC LIMIT {int(n)}
    """
    return _q(sql, filters)


def top_cities(n: int = 10, filters: FilterDict | None = None) -> pd.DataFrame:
    """Top-N cities by revenue."""
    sql = f"""
        SELECT city, country, ROUND(SUM(revenue), 2) AS revenue,
               COUNT(DISTINCT user_id) AS users
        FROM {TABLE} {{where}}
        GROUP BY city, country ORDER BY revenue DESC LIMIT {int(n)}
    """
    return _q(sql, filters)


def top_campaigns(n: int = 10, filters: FilterDict | None = None) -> pd.DataFrame:
    """Top-N campaigns by revenue."""
    sql = f"""
        SELECT campaign, ROUND(SUM(revenue), 2) AS revenue,
               COUNT(DISTINCT user_id) AS users,
               ROUND(SUM(revenue) / NULLIF(COUNT(DISTINCT user_id), 0), 2) AS arpu
        FROM {TABLE} {{where}}
        GROUP BY campaign ORDER BY revenue DESC LIMIT {int(n)}
    """
    return _q(sql, filters)


# --------------------------------------------------------------------------
# 17. TRAFFIC SOURCE ANALYSIS
# --------------------------------------------------------------------------
def traffic_source_analysis(filters: FilterDict | None = None) -> pd.DataFrame:
    """Users, sessions, conversion rate and revenue by traffic source."""
    sql = f"""
        SELECT traffic_source,
               COUNT(DISTINCT user_id) AS users,
               COUNT(DISTINCT session_id) AS sessions,
               COUNT(DISTINCT CASE WHEN event_name = 'Purchase' THEN user_id END) AS converters,
               ROUND(100.0 * COUNT(DISTINCT CASE WHEN event_name = 'Purchase' THEN user_id END)
                     / NULLIF(COUNT(DISTINCT user_id), 0), 2) AS conversion_rate_pct,
               ROUND(SUM(revenue), 2) AS revenue
        FROM {TABLE} {{where}}
        GROUP BY traffic_source ORDER BY revenue DESC
    """
    return _q(sql, filters)


# --------------------------------------------------------------------------
# 18. SUBSCRIPTION ANALYSIS
# --------------------------------------------------------------------------
def subscription_analysis(filters: FilterDict | None = None) -> pd.DataFrame:
    """Users, revenue, ARPU and average session duration by subscription tier."""
    sql = f"""
        SELECT subscription,
               COUNT(DISTINCT user_id) AS users,
               ROUND(SUM(revenue), 2) AS revenue,
               ROUND(SUM(revenue) / NULLIF(COUNT(DISTINCT user_id), 0), 2) AS arpu,
               ROUND(AVG(session_duration), 1) AS avg_session_duration
        FROM {TABLE} {{where}}
        GROUP BY subscription ORDER BY revenue DESC
    """
    return _q(sql, filters)


# --------------------------------------------------------------------------
# 19-20. DEVICE / OS BREAKDOWNS
# --------------------------------------------------------------------------
def device_breakdown(filters: FilterDict | None = None) -> pd.DataFrame:
    """Users, sessions and revenue by device type."""
    sql = f"""
        SELECT device_type, COUNT(DISTINCT user_id) AS users,
               COUNT(DISTINCT session_id) AS sessions,
               ROUND(SUM(revenue), 2) AS revenue
        FROM {TABLE} {{where}}
        GROUP BY device_type ORDER BY revenue DESC
    """
    return _q(sql, filters)


def os_breakdown(filters: FilterDict | None = None) -> pd.DataFrame:
    """Users and revenue by operating system."""
    sql = f"""
        SELECT os, COUNT(DISTINCT user_id) AS users, ROUND(SUM(revenue), 2) AS revenue
        FROM {TABLE} {{where}}
        GROUP BY os ORDER BY revenue DESC
    """
    return _q(sql, filters)


# --------------------------------------------------------------------------
# 21. SESSION ANALYTICS
# --------------------------------------------------------------------------
def session_duration_stats(filters: FilterDict | None = None) -> pd.DataFrame:
    """Overall session duration distribution stats."""
    sql = f"""
        SELECT COUNT(DISTINCT session_id) AS total_sessions,
               ROUND(AVG(session_duration), 1) AS avg_duration,
               MIN(session_duration) AS min_duration,
               MAX(session_duration) AS max_duration
        FROM {TABLE} {{where}}
    """
    return _q(sql, filters)


def sessions_per_user(filters: FilterDict | None = None) -> pd.DataFrame:
    """Average sessions per user."""
    sql = f"""
        WITH per_user AS (
            SELECT user_id, COUNT(DISTINCT session_id) AS sessions
            FROM {TABLE} {{where}}
            GROUP BY user_id
        )
        SELECT COUNT(*) AS total_users, ROUND(AVG(sessions), 2) AS avg_sessions_per_user,
               MAX(sessions) AS max_sessions_per_user
        FROM per_user
    """
    return _q(sql, filters)


# --------------------------------------------------------------------------
# 22. EVENT FREQUENCY
# --------------------------------------------------------------------------
def event_frequency(filters: FilterDict | None = None) -> pd.DataFrame:
    """Event counts and unique users by event_name."""
    sql = f"""
        SELECT event_name, COUNT(*) AS event_count, COUNT(DISTINCT user_id) AS users
        FROM {TABLE} {{where}}
        GROUP BY event_name ORDER BY event_count DESC
    """
    return _q(sql, filters)


# --------------------------------------------------------------------------
# 23. APP VERSION ANALYSIS
# --------------------------------------------------------------------------
def app_version_breakdown(filters: FilterDict | None = None) -> pd.DataFrame:
    """Users and revenue by app version."""
    sql = f"""
        SELECT app_version, COUNT(DISTINCT user_id) AS users, ROUND(SUM(revenue), 2) AS revenue
        FROM {TABLE} {{where}}
        GROUP BY app_version ORDER BY users DESC
    """
    return _q(sql, filters)


# --------------------------------------------------------------------------
# 24. COUNTRY x DEVICE CROSS-TAB
# --------------------------------------------------------------------------
def country_device_matrix(filters: FilterDict | None = None) -> pd.DataFrame:
    """Revenue cross-tab of country x device_type (top 10 countries by revenue)."""
    where, params = _build_where(filters)
    sql = f"""
        WITH top10 AS (
            SELECT country FROM {TABLE} {where}
            GROUP BY country ORDER BY SUM(revenue) DESC LIMIT 10
        )
        SELECT e.country, e.device_type, ROUND(SUM(e.revenue), 2) AS revenue
        FROM {TABLE} e
        JOIN top10 t ON e.country = t.country
        GROUP BY e.country, e.device_type
    """
    return run_query(sql, tuple(params) if params else None)


# --------------------------------------------------------------------------
# 25. LEVEL PROGRESSION
# --------------------------------------------------------------------------
def level_progression(filters: FilterDict | None = None) -> pd.DataFrame:
    """Distribution of users by highest ``level_completed``."""
    sql = f"""
        SELECT level_completed, COUNT(DISTINCT user_id) AS users
        FROM {TABLE} {{where}}
        GROUP BY level_completed ORDER BY level_completed
    """
    return _q(sql, filters)


# --------------------------------------------------------------------------
# 26. PURCHASE AMOUNT DISTRIBUTION
# --------------------------------------------------------------------------
def purchase_amount_distribution(filters: FilterDict | None = None) -> pd.DataFrame:
    """Purchase-amount buckets (simple binning) for paying events."""
    sql = f"""
        SELECT CASE
                 WHEN purchase_amount <= 0 THEN 'No purchase'
                 WHEN purchase_amount < 10 THEN '0-10'
                 WHEN purchase_amount < 25 THEN '10-25'
                 WHEN purchase_amount < 50 THEN '25-50'
                 WHEN purchase_amount < 100 THEN '50-100'
                 ELSE '100+'
               END AS bucket,
               COUNT(*) AS events,
               ROUND(SUM(purchase_amount), 2) AS total_amount
        FROM {TABLE} {{where}}
        GROUP BY bucket
    """
    return _q(sql, filters)


# --------------------------------------------------------------------------
# 27. NEW USER ACQUISITION TREND
# --------------------------------------------------------------------------
def new_user_acquisition_trend(filters: FilterDict | None = None) -> pd.DataFrame:
    """Daily count of first-time-seen users (acquisition trend)."""
    sql = f"""
        WITH first_seen AS (
            SELECT user_id, MIN(event_date) AS first_date
            FROM {TABLE} {{where}}
            GROUP BY user_id
        )
        SELECT first_date AS date, COUNT(*) AS new_users
        FROM first_seen GROUP BY first_date ORDER BY first_date
    """
    return _q(sql, filters)


# --------------------------------------------------------------------------
# 28. COUNTRY-LEVEL CONVERSION
# --------------------------------------------------------------------------
def conversion_rate_by_country(filters: FilterDict | None = None) -> pd.DataFrame:
    """Purchase conversion rate by country."""
    sql = f"""
        SELECT country,
               COUNT(DISTINCT user_id) AS users,
               COUNT(DISTINCT CASE WHEN event_name = 'Purchase' THEN user_id END) AS converters,
               ROUND(100.0 * COUNT(DISTINCT CASE WHEN event_name = 'Purchase' THEN user_id END)
                     / NULLIF(COUNT(DISTINCT user_id), 0), 2) AS conversion_rate_pct
        FROM {TABLE} {{where}}
        GROUP BY country ORDER BY conversion_rate_pct DESC
    """
    return _q(sql, filters)


# --------------------------------------------------------------------------
# 29. CAMPAIGN EFFICIENCY (revenue per user, ranked)
# --------------------------------------------------------------------------
def campaign_efficiency(filters: FilterDict | None = None) -> pd.DataFrame:
    """Campaign efficiency ranked by revenue-per-user (ARPU proxy)."""
    sql = f"""
        SELECT campaign,
               COUNT(DISTINCT user_id) AS users,
               ROUND(SUM(revenue), 2) AS revenue,
               ROUND(SUM(revenue) / NULLIF(COUNT(DISTINCT user_id), 0), 2) AS revenue_per_user
        FROM {TABLE} {{where}}
        GROUP BY campaign
        HAVING users > 0
        ORDER BY revenue_per_user DESC
    """
    return _q(sql, filters)


# --------------------------------------------------------------------------
# 30. RAW USER-LEVEL AGGREGATE (feeds RFM module)
# --------------------------------------------------------------------------
def user_level_aggregate(filters: FilterDict | None = None) -> pd.DataFrame:
    """Per-user recency/frequency/monetary raw inputs, used by ``rfm.py``.

    Returns:
        DataFrame with one row per user_id: last_event_date, frequency
        (distinct sessions), monetary (total revenue).
    """
    sql = f"""
        SELECT user_id,
               MAX(event_date) AS last_event_date,
               COUNT(DISTINCT session_id) AS frequency,
               ROUND(SUM(revenue), 2) AS monetary
        FROM {TABLE} {{where}}
        GROUP BY user_id
    """
    return _q(sql, filters)


# --------------------------------------------------------------------------
# 31. DATE-USER MATRIX (feeds cohort.py)
# --------------------------------------------------------------------------
def user_first_and_activity_dates(filters: FilterDict | None = None) -> pd.DataFrame:
    """Every (user_id, event_date) pair plus each user's first-seen date.
    Raw input to the cohort retention module."""
    where, params = _build_where(filters)
    sql = f"""
        WITH first_seen AS (
            SELECT user_id, MIN(event_date) AS cohort_date
            FROM {TABLE} {where}
            GROUP BY user_id
        )
        SELECT DISTINCT e.user_id, f.cohort_date, e.event_date
        FROM {TABLE} e
        JOIN first_seen f ON e.user_id = f.user_id
    """
    return run_query(sql, tuple(params) if params else None)


# --------------------------------------------------------------------------
# 32. CAMPAIGN x DEVICE PERFORMANCE
# --------------------------------------------------------------------------
def campaign_device_performance(filters: FilterDict | None = None) -> pd.DataFrame:
    """Revenue by campaign and device_type combination."""
    sql = f"""
        SELECT campaign, device_type, ROUND(SUM(revenue), 2) AS revenue,
               COUNT(DISTINCT user_id) AS users
        FROM {TABLE} {{where}}
        GROUP BY campaign, device_type ORDER BY revenue DESC
    """
    return _q(sql, filters)


# --------------------------------------------------------------------------
# 33. DAILY EVENT VOLUME (feeds anomaly detection)
# --------------------------------------------------------------------------
def daily_event_volume(filters: FilterDict | None = None) -> pd.DataFrame:
    """Total daily event count (traffic proxy) for anomaly detection."""
    sql = f"""
        SELECT event_date AS date, COUNT(*) AS event_count,
               COUNT(DISTINCT user_id) AS active_users
        FROM {TABLE} {{where}}
        GROUP BY event_date ORDER BY event_date
    """
    return _q(sql, filters)


# --------------------------------------------------------------------------
# 34. SUMMARY KPI SNAPSHOT (single-row, used by KPI cards + PDF report)
# --------------------------------------------------------------------------
def kpi_snapshot(filters: FilterDict | None = None) -> pd.DataFrame:
    """Single-row snapshot of the core executive KPIs, computed in SQL."""
    sql = f"""
        SELECT COUNT(DISTINCT user_id) AS total_users,
               COUNT(DISTINCT session_id) AS total_sessions,
               COUNT(*) AS total_events,
               ROUND(SUM(revenue), 2) AS total_revenue,
               ROUND(SUM(revenue) / NULLIF(COUNT(DISTINCT user_id), 0), 2) AS arpu,
               ROUND(SUM(revenue) / NULLIF(COUNT(DISTINCT CASE WHEN revenue > 0 THEN user_id END), 0), 2) AS arppu,
               ROUND(100.0 * COUNT(DISTINCT CASE WHEN event_name = 'Purchase' THEN user_id END)
                     / NULLIF(COUNT(DISTINCT user_id), 0), 2) AS conversion_rate_pct,
               ROUND(AVG(session_duration), 1) AS avg_session_duration
        FROM {TABLE} {{where}}
    """
    return _q(sql, filters)


# --------------------------------------------------------------------------
# 35. CAMPAIGN COMPARISON (period-agnostic table for Analytics Center)
# --------------------------------------------------------------------------
def campaign_comparison(filters: FilterDict | None = None) -> pd.DataFrame:
    """Full campaign comparison table: users, revenue, ARPU, conversion."""
    sql = f"""
        SELECT campaign,
               COUNT(DISTINCT user_id) AS users,
               ROUND(SUM(revenue), 2) AS revenue,
               ROUND(SUM(revenue) / NULLIF(COUNT(DISTINCT user_id), 0), 2) AS arpu,
               ROUND(100.0 * COUNT(DISTINCT CASE WHEN event_name = 'Purchase' THEN user_id END)
                     / NULLIF(COUNT(DISTINCT user_id), 0), 2) AS conversion_rate_pct
        FROM {TABLE} {{where}}
        GROUP BY campaign ORDER BY revenue DESC
    """
    return _q(sql, filters)


ALL_QUERIES: dict[str, Any] = {
    "dau": dau, "wau": wau, "mau": mau, "stickiness_dau_mau": stickiness_dau_mau,
    "revenue_trend": revenue_trend, "monthly_revenue": monthly_revenue,
    "arpu_overall": arpu_overall, "revenue_per_session": revenue_per_session,
    "purchase_frequency": purchase_frequency, "revenue_by_country": revenue_by_country,
    "revenue_by_device": revenue_by_device, "revenue_by_campaign": revenue_by_campaign,
    "revenue_by_traffic_source": revenue_by_traffic_source,
    "revenue_by_subscription": revenue_by_subscription, "funnel": funnel,
    "retention_by_day_bucket": retention_by_day_bucket,
    "retention_overall_rate": retention_overall_rate,
    "returning_vs_new_users": returning_vs_new_users, "monthly_growth": monthly_growth,
    "weekly_growth": weekly_growth, "campaign_growth": campaign_growth,
    "top_countries": top_countries, "top_cities": top_cities, "top_campaigns": top_campaigns,
    "traffic_source_analysis": traffic_source_analysis,
    "subscription_analysis": subscription_analysis, "device_breakdown": device_breakdown,
    "os_breakdown": os_breakdown, "session_duration_stats": session_duration_stats,
    "sessions_per_user": sessions_per_user, "event_frequency": event_frequency,
    "app_version_breakdown": app_version_breakdown, "country_device_matrix": country_device_matrix,
    "level_progression": level_progression,
    "purchase_amount_distribution": purchase_amount_distribution,
    "new_user_acquisition_trend": new_user_acquisition_trend,
    "conversion_rate_by_country": conversion_rate_by_country,
    "campaign_efficiency": campaign_efficiency, "user_level_aggregate": user_level_aggregate,
    "user_first_and_activity_dates": user_first_and_activity_dates,
    "campaign_device_performance": campaign_device_performance,
    "daily_event_volume": daily_event_volume, "kpi_snapshot": kpi_snapshot,
    "campaign_comparison": campaign_comparison,
}
