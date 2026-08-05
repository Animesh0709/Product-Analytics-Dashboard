"""
rfm.py
======

RFM (Recency, Frequency, Monetary) Customer Segmentation (Part 5).

Segments users into six standard lifecycle buckets:
    Champions, Loyal Customers, Potential Loyalists,
    Need Attention, At Risk, Lost Customers

using quintile scoring on Recency / Frequency / Monetary, computed from the
SQL layer's ``user_level_aggregate`` output.
"""

from __future__ import annotations

import logging

import pandas as pd

from sql_engine import user_level_aggregate, FilterDict

logger = logging.getLogger(__name__)

SEGMENT_RECOMMENDATIONS: dict[str, str] = {
    "Champions": "Reward with early access and loyalty perks; use as advocates/referrals.",
    "Loyal Customers": "Upsell higher tiers and subscriptions; keep engagement high with regular touchpoints.",
    "Potential Loyalists": "Offer onboarding nudges and limited-time incentives to build the habit.",
    "Need Attention": "Send re-engagement campaigns and personalized offers before they churn.",
    "At Risk": "Trigger win-back campaigns with discounts; investigate root cause of drop-off.",
    "Lost Customers": "Deprioritize spend; consider low-cost reactivation email only.",
}


def _score_quintile(series: pd.Series, ascending: bool) -> pd.Series:
    """Score a numeric series into 1-5 quintile bins.

    Args:
        series: Numeric values to bin.
        ascending: If True, higher raw value -> higher score (Frequency,
            Monetary). If False, higher raw value -> lower score (Recency,
            where fewer days-since-last-seen is better).

    Returns:
        Integer series of scores 1-5.
    """
    try:
        ranks = series.rank(method="first")
        bins = pd.qcut(ranks, 5, labels=[1, 2, 3, 4, 5])
        scores = bins.astype(int)
    except ValueError:
        # Not enough distinct values to form 5 quintiles; fall back to a
        # coarser rank-based split.
        scores = pd.Series(3, index=series.index)
    return scores if ascending else (6 - scores)


def _segment_from_scores(r: int, f: int, m: int) -> str:
    """Map an (R, F, M) score triple to a named lifecycle segment."""
    rfm_avg = (f + m) / 2
    if r >= 4 and rfm_avg >= 4:
        return "Champions"
    if r >= 3 and rfm_avg >= 3:
        return "Loyal Customers"
    if r >= 3 and rfm_avg >= 2:
        return "Potential Loyalists"
    if r == 2 and rfm_avg >= 2:
        return "Need Attention"
    if r <= 2 and rfm_avg >= 2:
        return "At Risk"
    return "Lost Customers"


def build_rfm_table(filters: FilterDict | None = None, snapshot_date: str | None = None) -> pd.DataFrame:
    """Compute per-user RFM scores and lifecycle segment.

    Args:
        filters: Optional dashboard filter dict.
        snapshot_date: ISO date string to compute recency against; defaults
            to the max event date observed in the (filtered) data.

    Returns:
        DataFrame with columns: user_id, recency_days, frequency, monetary,
        R, F, M, rfm_segment.
    """
    raw = user_level_aggregate(filters)
    if raw.empty:
        return pd.DataFrame()

    raw["last_event_date"] = pd.to_datetime(raw["last_event_date"])
    anchor = pd.to_datetime(snapshot_date) if snapshot_date else raw["last_event_date"].max()
    raw["recency_days"] = (anchor - raw["last_event_date"]).dt.days

    raw["R"] = _score_quintile(raw["recency_days"], ascending=False)
    raw["F"] = _score_quintile(raw["frequency"], ascending=True)
    raw["M"] = _score_quintile(raw["monetary"], ascending=True)

    raw["rfm_segment"] = [
        _segment_from_scores(r, f, m) for r, f, m in zip(raw["R"], raw["F"], raw["M"])
    ]
    return raw[["user_id", "recency_days", "frequency", "monetary", "R", "F", "M", "rfm_segment"]]


def rfm_segment_summary(rfm_table: pd.DataFrame) -> pd.DataFrame:
    """Aggregate the RFM table into a per-segment summary with recommendations.

    Args:
        rfm_table: Output of :func:`build_rfm_table`.

    Returns:
        DataFrame with columns: rfm_segment, users, pct_of_total,
        avg_recency_days, avg_frequency, total_monetary, recommendation.
    """
    if rfm_table.empty:
        return pd.DataFrame()

    total_users = len(rfm_table)
    summary = (
        rfm_table.groupby("rfm_segment")
        .agg(
            users=("user_id", "nunique"),
            avg_recency_days=("recency_days", "mean"),
            avg_frequency=("frequency", "mean"),
            total_monetary=("monetary", "sum"),
        )
        .reset_index()
    )
    summary["pct_of_total"] = (summary["users"] / total_users * 100).round(1)
    summary["avg_recency_days"] = summary["avg_recency_days"].round(1)
    summary["avg_frequency"] = summary["avg_frequency"].round(1)
    summary["total_monetary"] = summary["total_monetary"].round(2)
    summary["recommendation"] = summary["rfm_segment"].map(SEGMENT_RECOMMENDATIONS)
    return summary.sort_values("total_monetary", ascending=False).reset_index(drop=True)
