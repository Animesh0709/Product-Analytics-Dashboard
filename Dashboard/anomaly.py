"""
anomaly.py
==========

Automated Anomaly Detection (Part 6).

Detects statistically unusual points in key time series using a rolling
mean/standard-deviation z-score method (simple, explainable, and dependency
-free beyond pandas/numpy — appropriate for a portfolio-grade tool where
interviewers may ask "how does this work?").

Flags:
    - Revenue spikes / drops (daily revenue trend)
    - Campaign anomalies (per-campaign monthly revenue swings)
    - Traffic anomalies (daily event volume / active users)
    - Retention anomalies (cohort Day-N retention outliers)

Each detector returns a tidy DataFrame of anomaly rows plus a short,
human-readable message suitable for a warning card in the UI.
"""

from __future__ import annotations

import logging

import numpy as np
import pandas as pd

from sql_engine import revenue_trend, campaign_growth, daily_event_volume, FilterDict

logger = logging.getLogger(__name__)

Z_THRESHOLD: float = 2.0
MIN_POINTS_FOR_DETECTION: int = 5


def _zscore_anomalies(
    df: pd.DataFrame,
    value_col: str,
    label_cols: list[str],
    z_threshold: float = Z_THRESHOLD,
) -> pd.DataFrame:
    """Flag rows whose value_col is more than `z_threshold` std-devs from
    the series mean.

    Args:
        df: Source DataFrame.
        value_col: Column to test for anomalies.
        label_cols: Columns to keep for identifying the anomalous row(s).
        z_threshold: Z-score cutoff (default 2.0, ~95% CI).

    Returns:
        Subset of df with an added `z_score` and `direction` column, sorted
        by absolute z-score descending. Empty DataFrame if not enough data.
    """
    if df.empty or len(df) < MIN_POINTS_FOR_DETECTION:
        return pd.DataFrame()

    series = df[value_col].astype(float)
    mean, std = series.mean(), series.std(ddof=0)
    if std == 0 or np.isnan(std):
        return pd.DataFrame()

    z = (series - mean) / std
    mask = z.abs() >= z_threshold

    out = df.loc[mask, label_cols + [value_col]].copy()
    out["z_score"] = z.loc[mask].round(2)
    out["direction"] = np.where(z.loc[mask] > 0, "spike", "drop")
    return out.sort_values("z_score", key=lambda s: s.abs(), ascending=False).reset_index(drop=True)


def detect_revenue_anomalies(filters: FilterDict | None = None) -> pd.DataFrame:
    """Detect daily revenue spikes/drops."""
    df = revenue_trend(filters)
    return _zscore_anomalies(df, "revenue", ["date"])


def detect_traffic_anomalies(filters: FilterDict | None = None) -> pd.DataFrame:
    """Detect daily traffic (event volume) spikes/drops."""
    df = daily_event_volume(filters)
    return _zscore_anomalies(df, "event_count", ["date", "active_users"])


def detect_campaign_anomalies(filters: FilterDict | None = None) -> pd.DataFrame:
    """Detect abnormal month-over-month revenue swings per campaign."""
    df = campaign_growth(filters)
    if df.empty or "revenue_growth_pct" not in df:
        return pd.DataFrame()
    valid = df.dropna(subset=["revenue_growth_pct"])
    return _zscore_anomalies(valid, "revenue_growth_pct", ["campaign", "year_month"])


def detect_retention_anomalies(cohort_table: pd.DataFrame) -> pd.DataFrame:
    """Detect cohorts whose Day 30 retention is an outlier vs other cohorts.

    Args:
        cohort_table: Output of ``cohort.build_cohort_table``.

    Returns:
        Anomalous cohort rows with z-score/direction.
    """
    if cohort_table.empty or "Day 30" not in cohort_table:
        return pd.DataFrame()
    valid = cohort_table.dropna(subset=["Day 30"])
    return _zscore_anomalies(valid, "Day 30", ["cohort_month", "cohort_size"])


def build_anomaly_warning_cards(filters: FilterDict | None = None, cohort_table: pd.DataFrame | None = None) -> list[dict]:
    """Run all detectors and produce warning-card-ready dicts for the UI.

    Args:
        filters: Optional dashboard filter dict.
        cohort_table: Pre-computed cohort table (optional; retention
            anomalies are skipped if not provided).

    Returns:
        List of dicts: {severity, title, message}.
    """
    cards: list[dict] = []

    rev = detect_revenue_anomalies(filters)
    for _, row in rev.iterrows():
        cards.append({
            "severity": "high" if abs(row["z_score"]) >= 3 else "medium",
            "title": f"Revenue {row['direction']} on {row['date']}",
            "message": f"Daily revenue of {row['revenue']:.2f} is {row['z_score']:+.2f} std-devs from the mean.",
        })

    traf = detect_traffic_anomalies(filters)
    for _, row in traf.iterrows():
        cards.append({
            "severity": "high" if abs(row["z_score"]) >= 3 else "medium",
            "title": f"Traffic {row['direction']} on {row['date']}",
            "message": f"Event volume of {int(row['event_count'])} is {row['z_score']:+.2f} std-devs from the mean.",
        })

    camp = detect_campaign_anomalies(filters)
    for _, row in camp.iterrows():
        cards.append({
            "severity": "medium",
            "title": f"Campaign anomaly: {row['campaign']} ({row['year_month']})",
            "message": f"Month-over-month revenue change of {row['revenue_growth_pct']:+.1f}% is unusual "
                       f"(z-score {row['z_score']:+.2f}).",
        })

    if cohort_table is not None:
        ret = detect_retention_anomalies(cohort_table)
        for _, row in ret.iterrows():
            cards.append({
                "severity": "medium",
                "title": f"Retention anomaly: cohort {row['cohort_month']}",
                "message": f"Day 30 retention of {row['Day 30']:.1f}% is {row['z_score']:+.2f} std-devs from other cohorts.",
            })

    if not cards:
        cards.append({
            "severity": "info",
            "title": "No anomalies detected",
            "message": "All key metrics are within normal statistical ranges for the current filter selection.",
        })
    return cards
