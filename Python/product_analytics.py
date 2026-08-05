

"""
product_analytics.py
=====================

Production-quality analytics pipeline for the Product Analytics Dashboard
portfolio project.

The script ingests raw user-event data (Dataset/user_events.csv), cleans it,
computes a comprehensive set of product KPIs, performs multi-dimensional
segmentation, generates a full suite of charts, derives automated business
insights, and exports everything to the Output/ directory.

Run directly:
    python Python/product_analytics.py

Author: Product Analytics Dashboard
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")  # Headless backend - safe for servers / CI
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

# --------------------------------------------------------------------------
# GLOBAL CONFIGURATION
# --------------------------------------------------------------------------

# All paths are derived relative to this file, so the script can be executed
# from any working directory without ever hardcoding an absolute path.
PROJECT_ROOT: Path = Path(__file__).resolve().parent.parent
DATASET_PATH: Path = PROJECT_ROOT / "Dataset" / "user_events.csv"
OUTPUT_DIR: Path = PROJECT_ROOT / "Output"
FIGURES_DIR: Path = OUTPUT_DIR / "figures"
REPORTS_DIR: Path = OUTPUT_DIR / "reports"

FIGURE_DPI: int = 300
SESSION_DURATION_UPPER_BOUND_SECONDS: int = 3600  # 1 hour cap for outliers

# Canonical funnel stages present in the raw event stream.
FUNNEL_STAGES: list[str] = ["App Open", "Search", "Add to Cart", "Purchase"]

sns.set_theme(style="whitegrid", palette="deep")
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(message)s",
    datefmt="%H:%M:%S",
    handlers=[logging.StreamHandler(sys.stdout)],
)
logger = logging.getLogger("product_analytics")


# --------------------------------------------------------------------------
# 1. DATA LOADING
# --------------------------------------------------------------------------
def load_data(path: Path = DATASET_PATH) -> pd.DataFrame:
    """Load the raw user-events dataset from disk.

    Args:
        path: Absolute path to the source CSV file.

    Returns:
        A raw, unprocessed pandas DataFrame.

    Raises:
        FileNotFoundError: If the dataset cannot be located.
    """
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found at {path}. Run Dataset/generate_dataset.py first."
        )

    df = pd.read_csv(path)
    logger.info("Loaded %s rows and %s columns from %s", *df.shape, path.name)
    return df


# --------------------------------------------------------------------------
# 2. DATA CLEANING
# --------------------------------------------------------------------------
def clean_data(df: pd.DataFrame) -> pd.DataFrame:
    """Clean and normalize the raw event data.

    Handles missing values, duplicate rows, incorrect datatypes, and
    outliers in ``session_duration``.

    Args:
        df: Raw DataFrame as returned by ``load_data``.

    Returns:
        A cleaned copy of the DataFrame, ready for KPI calculation.
    """
    df = df.copy()
    initial_rows = len(df)

    # --- Datatype correction -------------------------------------------------
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")
    df["event_timestamp"] = pd.to_datetime(df["event_timestamp"], errors="coerce")

    numeric_cols = [
        "session_duration",
        "revenue",
        "level_completed",
        "purchase_amount",
        "retention_day",
    ]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # --- Missing value handling ----------------------------------------------
    # Categorical gaps are filled with an explicit "Unknown" label rather than
    # being dropped, since discarding rows would understate volume metrics.
    categorical_defaults = {
        "city": "Unknown",
        "app_version": "Unknown",
        "campaign": "None",
    }
    for col, default in categorical_defaults.items():
        if col in df.columns:
            df[col] = df[col].fillna(default)

    # Rows missing critical identifiers or the event timestamp cannot be
    # analyzed meaningfully and are dropped.
    critical_cols = ["user_id", "session_id", "event_date", "event_name"]
    before = len(df)
    df = df.dropna(subset=critical_cols)
    dropped_critical = before - len(df)

    # Numeric fields default to 0 when missing (e.g. no purchase occurred).
    df[numeric_cols] = df[numeric_cols].fillna(0)

    # --- Duplicate removal ----------------------------------------------------
    duplicates_removed = df.duplicated().sum()
    df = df.drop_duplicates()

    # --- Outlier handling: session_duration -----------------------------------
    # Sessions beyond a reasonable ceiling (e.g. the injected 24h anomalies)
    # are treated as data-entry errors and capped at the 99th percentile
    # rather than dropped, to preserve row counts for other metrics.
    p99 = df["session_duration"].quantile(0.99)
    cap = min(p99, SESSION_DURATION_UPPER_BOUND_SECONDS)
    outliers_capped = (df["session_duration"] > cap).sum()
    df["session_duration"] = df["session_duration"].clip(lower=0, upper=cap)

    # Negative or nonsensical purchase/revenue values are floored at zero.
    df["revenue"] = df["revenue"].clip(lower=0)
    df["purchase_amount"] = df["purchase_amount"].clip(lower=0)

    # --- Normalize string casing / whitespace ---------------------------------
    string_cols = df.select_dtypes(include=["object"]).columns
    for col in string_cols:
        df[col] = df[col].astype(str).str.strip()

    logger.info(
        "Cleaning complete | rows: %s -> %s | dropped_critical: %s | "
        "duplicates_removed: %s | session_duration_outliers_capped: %s",
        initial_rows,
        len(df),
        dropped_critical,
        duplicates_removed,
        outliers_capped,
    )
    return df.reset_index(drop=True)


# --------------------------------------------------------------------------
# 3. KPI CALCULATION
# --------------------------------------------------------------------------
def calculate_kpis(df: pd.DataFrame) -> dict[str, Any]:
    """Compute the full suite of product and business KPIs.

    Args:
        df: Cleaned event-level DataFrame.

    Returns:
        A dictionary of KPI name -> value (scalars, Series, or DataFrames).
    """
    metrics: dict[str, Any] = {}

    purchases = df[df["event_name"] == "Purchase"]
    paying_users = purchases.loc[purchases["purchase_amount"] > 0, "user_id"].nunique()
    total_users = df["user_id"].nunique()
    total_revenue = float(df["revenue"].sum())

    # --- Core volume metrics ---------------------------------------------------
    metrics["total_users"] = total_users
    metrics["total_events"] = len(df)
    metrics["total_sessions"] = df["session_id"].nunique()

    dau = df.groupby(df["event_date"].dt.date)["user_id"].nunique()
    metrics["daily_active_users"] = dau
    metrics["avg_dau"] = float(dau.mean())

    df["year_month"] = df["event_date"].dt.to_period("M")
    mau = df.groupby("year_month")["user_id"].nunique()
    metrics["monthly_active_users"] = mau
    metrics["avg_mau"] = float(mau.mean())

    # --- Revenue metrics --------------------------------------------------------
    metrics["total_revenue"] = total_revenue
    metrics["arpu"] = total_revenue / total_users if total_users else 0.0
    metrics["arppu"] = total_revenue / paying_users if paying_users else 0.0
    metrics["avg_purchase_value"] = (
        float(purchases.loc[purchases["purchase_amount"] > 0, "purchase_amount"].mean())
        if paying_users
        else 0.0
    )
    metrics["paying_users"] = paying_users

    # --- Engagement metrics -------------------------------------------------------
    metrics["avg_session_duration"] = float(df["session_duration"].mean())
    metrics["median_session_duration"] = float(df["session_duration"].median())

    # --- Conversion & purchase rates ------------------------------------------
    metrics["conversion_rate_pct"] = (
        100 * paying_users / total_users if total_users else 0.0
    )
    metrics["purchase_rate_pct"] = (
        100 * len(purchases) / len(df) if len(df) else 0.0
    )

    # --- Returning user share ------------------------------------------------
    user_type_counts = df.drop_duplicates("user_id")["user_type"].value_counts()
    returning_pct = (
        100 * user_type_counts.get("Returning", 0) / total_users if total_users else 0.0
    )
    metrics["returning_user_pct"] = float(returning_pct)

    # --- Revenue breakdowns ---------------------------------------------------
    metrics["revenue_per_country"] = (
        df.groupby("country")["revenue"].sum().sort_values(ascending=False)
    )
    metrics["revenue_per_device"] = (
        df.groupby("device_type")["revenue"].sum().sort_values(ascending=False)
    )
    metrics["revenue_per_campaign"] = (
        df.groupby("campaign")["revenue"].sum().sort_values(ascending=False)
    )

    logger.info(
        "KPIs calculated | total_users=%s | total_revenue=$%.2f | ARPU=$%.2f | "
        "conversion_rate=%.2f%%",
        total_users,
        total_revenue,
        metrics["arpu"],
        metrics["conversion_rate_pct"],
    )
    return metrics


# --------------------------------------------------------------------------
# 4. SEGMENTATION
# --------------------------------------------------------------------------
def perform_segmentation(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Aggregate revenue, event volume, and user counts across key dimensions.

    Args:
        df: Cleaned event-level DataFrame.

    Returns:
        Dictionary mapping a segmentation name to its summary DataFrame.
    """
    dimensions = [
        "country",
        "city",
        "device_type",
        "os",
        "traffic_source",
        "campaign",
        "subscription",
        "user_type",
        "retention_day",
    ]

    segments: dict[str, pd.DataFrame] = {}
    for dim in dimensions:
        if dim not in df.columns:
            continue
        summary = (
            df.groupby(dim)
            .agg(
                users=("user_id", "nunique"),
                events=("event_name", "count"),
                revenue=("revenue", "sum"),
                avg_session_duration=("session_duration", "mean"),
            )
            .sort_values("revenue", ascending=False)
            .reset_index()
        )
        segments[dim] = summary

    logger.info("Segmentation completed across %s dimensions", len(segments))
    return segments


# --------------------------------------------------------------------------
# 5. VISUALIZATIONS
# --------------------------------------------------------------------------
def _save_figure(fig: plt.Figure, filename: str) -> None:
    """Save a matplotlib figure to FIGURES_DIR at the standard DPI, then close it."""
    path = FIGURES_DIR / filename
    fig.savefig(path, dpi=FIGURE_DPI, bbox_inches="tight")
    plt.close(fig)
    logger.info("Saved figure -> %s", path.name)


def create_visualizations(df: pd.DataFrame) -> None:
    """Generate and persist the full chart suite to Output/figures/.

    Args:
        df: Cleaned event-level DataFrame.
    """
    FIGURES_DIR.mkdir(parents=True, exist_ok=True)

    # 1. DAU Trend ---------------------------------------------------------------
    dau = df.groupby(df["event_date"].dt.date)["user_id"].nunique()
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(dau.index, dau.values, color="#2563eb", linewidth=1.5)
    ax.set_title("Daily Active Users Trend")
    ax.set_xlabel("Date")
    ax.set_ylabel("Active Users")
    fig.autofmt_xdate()
    _save_figure(fig, "01_dau_trend.png")

    # 2. Revenue Trend -------------------------------------------------------------
    revenue_trend = df.groupby(df["event_date"].dt.date)["revenue"].sum()
    fig, ax = plt.subplots(figsize=(12, 5))
    ax.plot(revenue_trend.index, revenue_trend.values, color="#16a34a", linewidth=1.5)
    ax.set_title("Daily Revenue Trend")
    ax.set_xlabel("Date")
    ax.set_ylabel("Revenue ($)")
    fig.autofmt_xdate()
    _save_figure(fig, "02_revenue_trend.png")

    # 3. Revenue by Country ---------------------------------------------------------
    rev_country = df.groupby("country")["revenue"].sum().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(x=rev_country.values, y=rev_country.index, hue=rev_country.index, ax=ax, palette="Blues_r", legend=False)
    ax.set_title("Revenue by Country")
    ax.set_xlabel("Revenue ($)")
    ax.set_ylabel("Country")
    _save_figure(fig, "03_revenue_by_country.png")

    # 4. Revenue by Device -----------------------------------------------------------
    rev_device = df.groupby("device_type")["revenue"].sum().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(8, 5))
    sns.barplot(x=rev_device.index, y=rev_device.values, hue=rev_device.index, ax=ax, palette="Greens_r", legend=False)
    ax.set_title("Revenue by Device Type")
    ax.set_xlabel("Device Type")
    ax.set_ylabel("Revenue ($)")
    _save_figure(fig, "04_revenue_by_device.png")

    # 5. Device Distribution Pie Chart -----------------------------------------------
    device_counts = df["device_type"].value_counts()
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.pie(
        device_counts.values,
        labels=device_counts.index,
        autopct="%1.1f%%",
        startangle=90,
        colors=sns.color_palette("pastel"),
    )
    ax.set_title("Device Type Distribution")
    _save_figure(fig, "05_device_distribution_pie.png")

    # 6. Revenue by Campaign ----------------------------------------------------------
    rev_campaign = df.groupby("campaign")["revenue"].sum().sort_values(ascending=False)
    fig, ax = plt.subplots(figsize=(10, 6))
    sns.barplot(x=rev_campaign.values, y=rev_campaign.index, hue=rev_campaign.index, ax=ax, palette="Oranges_r", legend=False)
    ax.set_title("Revenue by Campaign")
    ax.set_xlabel("Revenue ($)")
    ax.set_ylabel("Campaign")
    _save_figure(fig, "06_revenue_by_campaign.png")

    # 7. Traffic Source Distribution ----------------------------------------------------
    traffic_counts = df["traffic_source"].value_counts()
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.barplot(x=traffic_counts.values, y=traffic_counts.index, hue=traffic_counts.index, ax=ax, palette="Purples_r", legend=False)
    ax.set_title("Traffic Source Distribution")
    ax.set_xlabel("Event Count")
    ax.set_ylabel("Traffic Source")
    _save_figure(fig, "07_traffic_source_distribution.png")

    # 8. Funnel Chart -----------------------------------------------------------------
    funnel_counts = [df[df["event_name"] == stage]["user_id"].nunique() for stage in FUNNEL_STAGES]
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.barplot(x=funnel_counts, y=FUNNEL_STAGES, hue=FUNNEL_STAGES, ax=ax, palette="viridis", legend=False)
    for i, value in enumerate(funnel_counts):
        ax.text(value, i, f" {value:,}", va="center", fontsize=10)
    ax.set_title("User Funnel: App Open -> Search -> Add to Cart -> Purchase")
    ax.set_xlabel("Unique Users")
    _save_figure(fig, "08_funnel_chart.png")

    # 9. Session Duration Histogram -----------------------------------------------------
    fig, ax = plt.subplots(figsize=(9, 5))
    sns.histplot(df["session_duration"], bins=40, kde=True, color="#0891b2", ax=ax)
    ax.set_title("Session Duration Distribution")
    ax.set_xlabel("Session Duration (seconds)")
    ax.set_ylabel("Frequency")
    _save_figure(fig, "09_session_duration_histogram.png")

    # 10. Subscription Distribution -----------------------------------------------------
    sub_counts = df.drop_duplicates("user_id")["subscription"].value_counts()
    fig, ax = plt.subplots(figsize=(7, 7))
    ax.pie(
        sub_counts.values,
        labels=sub_counts.index,
        autopct="%1.1f%%",
        startangle=90,
        colors=sns.color_palette("Set2"),
    )
    ax.set_title("Subscription Tier Distribution")
    _save_figure(fig, "10_subscription_distribution.png")

    # 11. Returning vs New Users -----------------------------------------------------
    user_type_counts = df.drop_duplicates("user_id")["user_type"].value_counts()
    fig, ax = plt.subplots(figsize=(7, 5))
    sns.barplot(x=user_type_counts.index, y=user_type_counts.values, hue=user_type_counts.index, ax=ax, palette="coolwarm", legend=False)
    ax.set_title("Returning vs New Users")
    ax.set_xlabel("User Type")
    ax.set_ylabel("Unique Users")
    _save_figure(fig, "11_returning_vs_new_users.png")

    # 12. Retention Analysis -----------------------------------------------------------
    retention_counts = df.drop_duplicates("user_id").groupby("retention_day")["user_id"].nunique()
    retention_counts = retention_counts.sort_index()
    fig, ax = plt.subplots(figsize=(9, 5))
    retention_labels = retention_counts.index.astype(str)
    sns.barplot(x=retention_labels, y=retention_counts.values, hue=retention_labels, ax=ax, palette="magma", legend=False)
    ax.set_title("User Retention by Day")
    ax.set_xlabel("Retention Day")
    ax.set_ylabel("Unique Users")
    _save_figure(fig, "12_retention_analysis.png")

    logger.info("All 12 visualizations generated successfully")


# --------------------------------------------------------------------------
# 6. BUSINESS INSIGHTS
# --------------------------------------------------------------------------
def generate_business_insights(df: pd.DataFrame, metrics: dict[str, Any]) -> list[str]:
    """Derive plain-language, automated business insights from the KPIs.

    Args:
        df: Cleaned event-level DataFrame.
        metrics: Dictionary returned by ``calculate_kpis``.

    Returns:
        A list of at least 20 human-readable insight strings.
    """
    insights: list[str] = []

    rev_country = metrics["revenue_per_country"]
    rev_device = metrics["revenue_per_device"]
    rev_campaign = metrics["revenue_per_campaign"]

    top_country = rev_country.idxmax()
    top_device = rev_device.idxmax()
    top_campaign_series = rev_campaign[rev_campaign.index != "None"]
    top_campaign = top_campaign_series.idxmax() if not top_campaign_series.empty else rev_campaign.idxmax()

    traffic_counts = df["traffic_source"].value_counts()
    best_traffic = traffic_counts.idxmax()

    event_counts = df["event_name"].value_counts()
    most_popular_event = event_counts.idxmax()

    daily_counts = df.groupby(df["event_date"].dt.day_name())["user_id"].count()
    peak_day = daily_counts.idxmax()

    sub_revenue = df.groupby("subscription")["revenue"].sum().sort_values(ascending=False)
    top_sub_tier = sub_revenue.idxmax()

    funnel_counts = [df[df["event_name"] == stage]["user_id"].nunique() for stage in FUNNEL_STAGES]
    funnel_drop = (
        100 * (1 - funnel_counts[-1] / funnel_counts[0]) if funnel_counts[0] else 0.0
    )

    os_counts = df["os"].value_counts()
    top_os = os_counts.idxmax()

    city_rev = df[df["city"] != "Unknown"].groupby("city")["revenue"].sum().sort_values(ascending=False)
    top_city = city_rev.idxmax() if not city_rev.empty else "N/A"

    # --- 1-20+ insights ---------------------------------------------------------
    insights.append(
        f"1. {top_country} generates the highest revenue at ${rev_country.max():,.2f}, "
        f"representing {100 * rev_country.max() / rev_country.sum():.1f}% of total revenue."
    )
    insights.append(
        f"2. '{top_campaign}' is the highest performing marketing campaign, "
        f"driving ${top_campaign_series.max() if not top_campaign_series.empty else rev_campaign.max():,.2f} in revenue."
    )
    insights.append(
        f"3. {top_device} devices contribute the most revenue (${rev_device.max():,.2f}), "
        f"suggesting the product experience is strongest on this platform."
    )
    insights.append(
        f"4. '{best_traffic}' is the leading traffic source by event volume "
        f"({traffic_counts.max():,} events), making it the most valuable acquisition channel."
    )
    insights.append(
        f"5. The average purchase value across paying users is ${metrics['avg_purchase_value']:.2f}, "
        f"while ARPPU stands at ${metrics['arppu']:.2f}."
    )
    insights.append(
        f"6. Returning users make up {metrics['returning_user_pct']:.1f}% of the user base, "
        f"underscoring the importance of retention over pure acquisition."
    )
    insights.append(
        f"7. {peak_day} is the peak activity day of the week, an ideal window for "
        f"push notifications and promotional campaigns."
    )
    insights.append(
        f"8. '{most_popular_event}' is the most frequent event overall "
        f"({event_counts.max():,} occurrences), indicating the core engagement loop."
    )
    insights.append(
        f"9. The '{top_sub_tier}' subscription tier generates the most revenue "
        f"(${sub_revenue.max():,.2f}), highlighting where monetization is concentrated."
    )
    insights.append(
        f"10. Overall conversion rate (users who purchased) is {metrics['conversion_rate_pct']:.2f}%, "
        f"leaving meaningful headroom for funnel optimization."
    )
    insights.append(
        f"11. Average session duration is {metrics['avg_session_duration']:.1f} seconds "
        f"(median {metrics['median_session_duration']:.1f}s), indicating typical engagement depth per visit."
    )
    insights.append(
        "12. Growth recommendation: double down on paid and organic channels resembling "
        f"'{best_traffic}', since it already drives the highest engagement volume."
    )
    insights.append(
        f"13. Marketing recommendation: reallocate budget toward '{top_campaign}'-style campaigns "
        "given its outsized revenue contribution relative to other campaigns."
    )
    insights.append(
        "14. Product recommendation: investigate friction points between the 'Add to Cart' and "
        "'Purchase' steps, since this is typically where the largest funnel drop-off occurs."
    )
    insights.append(
        "15. Customer retention recommendation: launch a loyalty or win-back program targeting "
        "'New' users, who convert to 'Returning' status at a lower rate than desired."
    )
    insights.append(
        f"16. The overall purchase event rate is {metrics['purchase_rate_pct']:.2f}% of all logged events, "
        "suggesting purchase intent signals could be surfaced earlier in the user journey."
    )
    insights.append(
        f"17. {top_os} is the dominant operating system among users "
        f"({os_counts.max():,} events), and should be prioritized for QA and performance testing."
    )
    insights.append(
        f"18. Average revenue per user (ARPU) is ${metrics['arpu']:.2f} across all "
        f"{metrics['total_users']:,} users, a useful baseline for evaluating future feature launches."
    )
    insights.append(
        f"19. {top_city} is the top revenue-generating city, indicating a geographic hotspot "
        "worth targeting with localized campaigns."
    )
    insights.append(
        f"20. From App Open to Purchase, the user funnel shows an overall drop-off of "
        f"{funnel_drop:.1f}%, highlighting the scale of the conversion opportunity."
    )
    insights.append(
        f"21. Total platform revenue stands at ${metrics['total_revenue']:,.2f} generated by "
        f"{metrics['paying_users']:,} paying users out of {metrics['total_users']:,} total users."
    )
    insights.append(
        f"22. Monthly active users average {metrics['avg_mau']:.0f}, compared to a daily active "
        f"user average of {metrics['avg_dau']:.0f}, giving an approximate stickiness (DAU/MAU) ratio "
        f"of {100 * metrics['avg_dau'] / metrics['avg_mau']:.1f}%." if metrics.get("avg_mau") else "22. Insufficient data to compute stickiness ratio."
    )
    insights.append(
        "23. Product recommendation: session durations are heavily right-skewed, so consider "
        "segmenting engagement analysis by session-length cohort rather than using averages alone."
    )
    insights.append(
        "24. Marketing recommendation: campaigns with 'None' as their label represent organic, "
        "non-attributed revenue and should be excluded when judging paid-campaign ROI."
    )

    logger.info("Generated %s automated business insights", len(insights))
    return insights


# --------------------------------------------------------------------------
# 7. SAVE REPORTS
# --------------------------------------------------------------------------
def save_reports(
    metrics: dict[str, Any],
    segments: dict[str, pd.DataFrame],
    insights: list[str],
) -> None:
    """Persist all summary metrics, segments, and insights to Output/reports/.

    Args:
        metrics: Dictionary returned by ``calculate_kpis``.
        segments: Dictionary returned by ``perform_segmentation``.
        insights: List of insight strings from ``generate_business_insights``.
    """
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # --- summary_metrics.csv ----------------------------------------------------
    scalar_metrics = {
        k: v for k, v in metrics.items() if isinstance(v, (int, float, str))
    }
    summary_df = pd.DataFrame(
        list(scalar_metrics.items()), columns=["metric", "value"]
    )
    summary_df.to_csv(REPORTS_DIR / "summary_metrics.csv", index=False)

    # --- business_insights.txt ---------------------------------------------------
    insights_path = REPORTS_DIR / "business_insights.txt"
    with insights_path.open("w", encoding="utf-8") as f:
        f.write("PRODUCT ANALYTICS - AUTOMATED BUSINESS INSIGHTS\n")
        f.write("=" * 55 + "\n\n")
        f.write("\n".join(insights))
        f.write("\n")

    # --- top_countries.csv ---------------------------------------------------------
    if "country" in segments:
        segments["country"].to_csv(REPORTS_DIR / "top_countries.csv", index=False)

    # --- campaign_performance.csv ---------------------------------------------------
    if "campaign" in segments:
        segments["campaign"].to_csv(REPORTS_DIR / "campaign_performance.csv", index=False)

    # --- device_summary.csv ---------------------------------------------------------
    if "device_type" in segments:
        segments["device_type"].to_csv(REPORTS_DIR / "device_summary.csv", index=False)

    # --- analytics_summary.json (bonus) -----------------------------------------------
    json_safe: dict[str, Any] = {}
    for key, value in metrics.items():
        if isinstance(value, pd.Series):
            json_safe[key] = {str(idx): float(v) for idx, v in value.items()}
        elif isinstance(value, pd.DataFrame):
            json_safe[key] = value.to_dict(orient="records")
        elif isinstance(value, (np.integer, np.floating)):
            json_safe[key] = value.item()
        else:
            json_safe[key] = value

    with (REPORTS_DIR / "analytics_summary.json").open("w", encoding="utf-8") as f:
        json.dump(json_safe, f, indent=2, default=str)

    logger.info("All reports saved to %s", REPORTS_DIR)


# --------------------------------------------------------------------------
# 8. MAIN PIPELINE
# --------------------------------------------------------------------------
def main() -> None:
    """Execute the end-to-end analytics pipeline with a professional progress log."""
    try:
        FIGURES_DIR.mkdir(parents=True, exist_ok=True)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

        logger.info("Loading Dataset...")
        raw_df = load_data()

        logger.info("Cleaning Dataset...")
        clean_df = clean_data(raw_df)

        logger.info("Calculating KPIs...")
        metrics = calculate_kpis(clean_df)

        logger.info("Segmenting Dataset...")
        segments = perform_segmentation(clean_df)

        logger.info("Generating Charts...")
        create_visualizations(clean_df)

        logger.info("Generating Insights...")
        insights = generate_business_insights(clean_df, metrics)

        logger.info("Saving Reports...")
        save_reports(metrics, segments, insights)

        logger.info("Pipeline Completed Successfully.")

    except FileNotFoundError as exc:
        logger.error("Pipeline aborted - missing input file: %s", exc)
        sys.exit(1)
    except Exception as exc:  # noqa: BLE001 - top-level safety net for a CLI tool
        logger.exception("Pipeline failed with an unexpected error: %s", exc)
        sys.exit(1)


if __name__ == "__main__":
    main()