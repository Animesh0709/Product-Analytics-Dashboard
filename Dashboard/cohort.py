"""
cohort.py
=========

Cohort Retention Analysis (Part 4).

Builds a monthly-acquisition-cohort retention table showing what share of
each cohort was still active at Day 1 / Day 3 / Day 7 / Day 14 / Day 30,
ready to render as an interactive Plotly heatmap.

Design notes:
    - A user's "cohort" is the calendar month of their first-ever event
      (first_seen date), computed in SQL via ``sql_engine.user_first_and_activity_dates``.
    - For each user we compute the set of "days since first seen" on which
      they had ANY event, then check membership at the requested day
      milestones. A user counts as retained at day N if they had at least
      one event on first_date + N (exact-day match), which is the standard
      definition for milestone-based retention curves.
"""

from __future__ import annotations

import logging

import pandas as pd

from sql_engine import user_first_and_activity_dates, FilterDict

logger = logging.getLogger(__name__)

RETENTION_DAYS: list[int] = [1, 3, 7, 14, 30]


def build_cohort_table(filters: FilterDict | None = None) -> pd.DataFrame:
    """Build a cohort x retention-day matrix of retention rates (%).

    Args:
        filters: Optional dashboard filter dict (see ``sql_engine`` for shape).

    Returns:
        DataFrame indexed by cohort_month (YYYY-MM) with one column per
        retention day milestone ("Day 1", "Day 3", ...), values are
        retention percentages (0-100), plus a ``cohort_size`` column.
    """
    raw = user_first_and_activity_dates(filters)
    if raw.empty:
        return pd.DataFrame()

    raw["cohort_date"] = pd.to_datetime(raw["cohort_date"])
    raw["event_date"] = pd.to_datetime(raw["event_date"])
    raw["days_since_first"] = (raw["event_date"] - raw["cohort_date"]).dt.days
    raw["cohort_month"] = raw["cohort_date"].dt.to_period("M").astype(str)

    cohort_sizes = raw.groupby("cohort_month")["user_id"].nunique()

    rows = []
    for cohort_month, group in raw.groupby("cohort_month"):
        size = cohort_sizes.loc[cohort_month]
        row = {"cohort_month": cohort_month, "cohort_size": int(size)}
        for day in RETENTION_DAYS:
            retained_users = group.loc[group["days_since_first"] == day, "user_id"].nunique()
            row[f"Day {day}"] = round(100.0 * retained_users / size, 2) if size else 0.0
        rows.append(row)

    table = pd.DataFrame(rows).sort_values("cohort_month").reset_index(drop=True)
    return table


def cohort_heatmap_matrix(cohort_table: pd.DataFrame) -> tuple[list[str], list[str], list[list[float]]]:
    """Reshape the cohort table into (x_labels, y_labels, z_matrix) for a
    Plotly heatmap.

    Args:
        cohort_table: Output of :func:`build_cohort_table`.

    Returns:
        Tuple of (day_labels, cohort_month_labels, values_matrix).
    """
    if cohort_table.empty:
        return [], [], []
    day_labels = [f"Day {d}" for d in RETENTION_DAYS]
    cohort_labels = cohort_table["cohort_month"].tolist()
    z = cohort_table[day_labels].values.tolist()
    return day_labels, cohort_labels, z


def cohort_summary_insights(cohort_table: pd.DataFrame) -> list[str]:
    """Generate plain-English insights from the cohort retention table."""
    if cohort_table.empty:
        return ["Not enough data to compute cohort retention."]

    insights = []
    day1_col, day30_col = "Day 1", "Day 30"
    if day1_col in cohort_table and cohort_table[day1_col].notna().any():
        avg_d1 = cohort_table[day1_col].mean()
        insights.append(f"Average Day 1 retention across cohorts is {avg_d1:.1f}%.")
    if day30_col in cohort_table and cohort_table[day30_col].notna().any():
        avg_d30 = cohort_table[day30_col].mean()
        insights.append(f"Average Day 30 retention across cohorts is {avg_d30:.1f}%.")
        best = cohort_table.loc[cohort_table[day30_col].idxmax()]
        insights.append(
            f"The strongest cohort is {best['cohort_month']} with {best[day30_col]:.1f}% Day 30 retention."
        )
    return insights
