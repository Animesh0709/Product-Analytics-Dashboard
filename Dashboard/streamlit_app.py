"""
streamlit_app.py
=================

Executive-grade, dark-themed Streamlit dashboard for the Product Analytics
Dashboard portfolio project.

This app is a pure consumer of data:
    - Dataset/user_events.csv               (raw event-level data, filtered live)
    - Output/reports/summary_metrics.csv     (pipeline-generated summary)
    - Output/reports/campaign_performance.csv
    - Output/reports/device_summary.csv
    - Output/reports/business_insights.txt

It does NOT regenerate, clean, or overwrite any analytics artifacts produced
by Python/product_analytics.py. All filtering and interactive charting is
performed in-memory on a cached copy of the raw dataset.

Run with:
    streamlit run Dashboard/streamlit_app.py
"""

from __future__ import annotations

import json
from datetime import timedelta
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# --------------------------------------------------------------------------
# PLATFORM EXTENSIONS (additive — SQLite/SQL analytics, cohort, RFM,
# anomaly detection, executive PDF report, advanced exports).
# Import is best-effort so the original dashboard keeps working even if an
# optional dependency (reportlab/xlsxwriter/matplotlib) is missing.
# --------------------------------------------------------------------------
try:
    from analytics import render_platform_extensions
    _PLATFORM_EXTENSIONS_AVAILABLE = True
except Exception as _ext_exc:  # pragma: no cover
    _PLATFORM_EXTENSIONS_AVAILABLE = False
    _PLATFORM_EXTENSIONS_ERROR = _ext_exc

# --------------------------------------------------------------------------
# PATH CONFIGURATION (pathlib only - no hardcoded absolute paths)
# --------------------------------------------------------------------------
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATASET_PATH: Path = BASE_DIR / "Dataset" / "user_events.csv"
REPORTS_DIR: Path = BASE_DIR / "Output" / "reports"
FIGURES_DIR: Path = BASE_DIR / "Output" / "figures"

SUMMARY_METRICS_PATH: Path = REPORTS_DIR / "summary_metrics.csv"
CAMPAIGN_PERFORMANCE_PATH: Path = REPORTS_DIR / "campaign_performance.csv"
DEVICE_SUMMARY_PATH: Path = REPORTS_DIR / "device_summary.csv"
TOP_COUNTRIES_PATH: Path = REPORTS_DIR / "top_countries.csv"
BUSINESS_INSIGHTS_PATH: Path = REPORTS_DIR / "business_insights.txt"
ANALYTICS_SUMMARY_JSON_PATH: Path = REPORTS_DIR / "analytics_summary.json"

FUNNEL_STAGES: list[str] = ["App Open", "Search", "Add to Cart", "Purchase"]

# --------------------------------------------------------------------------
# PAGE CONFIG
# --------------------------------------------------------------------------
st.set_page_config(
    page_title="Product Analytics Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# --------------------------------------------------------------------------
# EXECUTIVE DARK THEME (custom CSS injection)
# --------------------------------------------------------------------------
DARK_THEME_CSS: str = """
<style>
    /* ---- Global app background & text ---- */
    .stApp {
        background-color: #0e1117;
        color: #e6e6e6;
    }

    /* ---- Sidebar ---- */
    section[data-testid="stSidebar"] {
        background-color: #12161f;
        border-right: 1px solid #232838;
    }
    section[data-testid="stSidebar"] * {
        color: #e6e6e6 !important;
    }

    /* ---- Headings ---- */
    h1, h2, h3, h4 {
        color: #f5f7fa;
        font-family: "Segoe UI", "Helvetica Neue", Arial, sans-serif;
    }

    /* ---- KPI card ---- */
    .kpi-card {
        background: linear-gradient(145deg, #161b26, #1c2130);
        border: 1px solid #262c3d;
        border-radius: 14px;
        padding: 18px 20px;
        text-align: left;
        box-shadow: 0 4px 14px rgba(0, 0, 0, 0.35);
        height: 100%;
    }
    .kpi-label {
        font-size: 0.8rem;
        color: #9aa4b8;
        text-transform: uppercase;
        letter-spacing: 0.06em;
        margin-bottom: 6px;
    }
    .kpi-value {
        font-size: 1.65rem;
        font-weight: 700;
        color: #ffffff;
    }
    .kpi-sub {
        font-size: 0.75rem;
        color: #5f6b85;
        margin-top: 4px;
    }
    .kpi-delta {
        font-size: 0.82rem;
        font-weight: 600;
        margin-top: 6px;
        display: inline-block;
    }
    .kpi-delta-up { color: #22c55e; }
    .kpi-delta-down { color: #ef4444; }
    .kpi-delta-flat { color: #9aa4b8; }
    .kpi-prev {
        font-size: 0.72rem;
        color: #5f6b85;
        margin-top: 2px;
    }

    /* ---- Advanced KPI card (compact variant) ---- */
    .kpi-card-sm {
        background: linear-gradient(145deg, #14181f, #191e2b);
        border: 1px solid #232838;
        border-radius: 12px;
        padding: 14px 16px;
        text-align: left;
        height: 100%;
    }
    .kpi-card-sm .kpi-label { font-size: 0.72rem; }
    .kpi-card-sm .kpi-value { font-size: 1.25rem; }

    /* ---- Executive summary chip ---- */
    .exec-chip {
        background: linear-gradient(145deg, #151a2b, #1a2036);
        border: 1px solid #2b3350;
        border-left: 4px solid #a855f7;
        border-radius: 10px;
        padding: 10px 14px;
        margin-bottom: 10px;
        height: 100%;
    }
    .exec-chip .exec-label {
        font-size: 0.72rem;
        color: #9aa4b8;
        text-transform: uppercase;
        letter-spacing: 0.05em;
        margin-bottom: 4px;
    }
    .exec-chip .exec-value {
        font-size: 1.05rem;
        font-weight: 700;
        color: #f5f7fa;
    }

    /* ---- Insight card ---- */
    .insight-card {
        background-color: #151a25;
        border-left: 4px solid #3b82f6;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
        color: #d7dde8;
        font-size: 0.92rem;
        line-height: 1.4rem;
    }

    /* ---- Recommendation card ---- */
    .reco-card {
        background-color: #171325;
        border-left: 4px solid #eab308;
        border-radius: 8px;
        padding: 12px 16px;
        margin-bottom: 10px;
        color: #e9e4d8;
        font-size: 0.92rem;
        line-height: 1.4rem;
    }

    /* ---- Section divider spacing ---- */
    .section-title {
        margin-top: 28px;
        margin-bottom: 6px;
        font-size: 1.25rem;
        font-weight: 600;
        color: #f5f7fa;
        border-bottom: 1px solid #232838;
        padding-bottom: 6px;
    }

    /* ---- Dataframe / table tweaks ---- */
    .stDataFrame {
        border: 1px solid #232838;
        border-radius: 8px;
    }

    /* ---- Buttons ---- */
    .stDownloadButton button {
        background-color: #1f2937;
        color: #e6e6e6;
        border: 1px solid #334155;
        border-radius: 8px;
    }
    .stDownloadButton button:hover {
        background-color: #2563eb;
        border-color: #2563eb;
        color: #ffffff;
    }
</style>
"""
st.markdown(DARK_THEME_CSS, unsafe_allow_html=True)

# Consistent dark template for every Plotly chart in the app.
PLOTLY_TEMPLATE: str = "plotly_dark"
CHART_COLORWAY: list[str] = [
    "#3b82f6", "#22c55e", "#f97316", "#a855f7",
    "#ef4444", "#06b6d4", "#eab308", "#ec4899",
]


# --------------------------------------------------------------------------
# DATA LOADING (cached)
# --------------------------------------------------------------------------
@st.cache_data(show_spinner="Loading raw event data...")
def load_raw_data(path: Path) -> pd.DataFrame:
    """Load and lightly type-cast the raw user-events dataset.

    Args:
        path: Path to Dataset/user_events.csv.

    Returns:
        A DataFrame with parsed dates and numeric columns. Empty DataFrame
        if the file is missing.
    """
    if not path.exists():
        return pd.DataFrame()

    df = pd.read_csv(path)
    df["event_date"] = pd.to_datetime(df["event_date"], errors="coerce")

    numeric_cols = ["session_duration", "revenue", "purchase_amount", "retention_day"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)

    categorical_defaults = {"city": "Unknown", "app_version": "Unknown", "campaign": "None"}
    for col, default in categorical_defaults.items():
        if col in df.columns:
            df[col] = df[col].fillna(default)

    df = df.dropna(subset=["event_date", "user_id"])
    return df


@st.cache_data(show_spinner=False)
def load_csv_report(path: Path) -> pd.DataFrame | None:
    """Load a pipeline-generated CSV report, returning None if missing/unreadable."""
    if not path.exists():
        return None
    try:
        return pd.read_csv(path)
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def load_text_report(path: Path) -> str | None:
    """Load a pipeline-generated text report, returning None if missing."""
    if not path.exists():
        return None
    try:
        return path.read_text(encoding="utf-8")
    except Exception:
        return None


@st.cache_data(show_spinner=False)
def load_file_bytes(path: Path) -> bytes | None:
    """Read raw bytes of a file for download buttons, returning None if missing."""
    if not path.exists():
        return None
    try:
        return path.read_bytes()
    except Exception:
        return None


# --------------------------------------------------------------------------
# FILTERING
# --------------------------------------------------------------------------
# Session-state keys for every sidebar filter widget. Centralizing them here
# means the "Reset Filters" action and widget instantiation always agree.
FILTER_STATE_KEYS: dict[str, str] = {
    "date_range": "filter_date_range",
    "countries": "filter_countries",
    "campaigns": "filter_campaigns",
    "devices": "filter_devices",
    "user_types": "filter_user_types",
    "subscriptions": "filter_subscriptions",
    "traffic_sources": "filter_traffic_sources",
}


def _init_filter_defaults(df: pd.DataFrame) -> None:
    """Seed st.session_state with sensible defaults the first time the app runs.

    Args:
        df: Raw (unfiltered) event-level DataFrame, used to derive the full
            date range on first load.
    """
    min_date = df["event_date"].min().date()
    max_date = df["event_date"].max().date()

    st.session_state.setdefault(FILTER_STATE_KEYS["date_range"], (min_date, max_date))
    st.session_state.setdefault(FILTER_STATE_KEYS["countries"], [])
    st.session_state.setdefault(FILTER_STATE_KEYS["campaigns"], [])
    st.session_state.setdefault(FILTER_STATE_KEYS["devices"], [])
    st.session_state.setdefault(FILTER_STATE_KEYS["user_types"], [])
    st.session_state.setdefault(FILTER_STATE_KEYS["subscriptions"], [])
    st.session_state.setdefault(FILTER_STATE_KEYS["traffic_sources"], [])


def _reset_filters(df: pd.DataFrame) -> None:
    """Clear all filter widgets back to their "show everything" defaults."""
    min_date = df["event_date"].min().date()
    max_date = df["event_date"].max().date()

    st.session_state[FILTER_STATE_KEYS["date_range"]] = (min_date, max_date)
    st.session_state[FILTER_STATE_KEYS["countries"]] = []
    st.session_state[FILTER_STATE_KEYS["campaigns"]] = []
    st.session_state[FILTER_STATE_KEYS["devices"]] = []
    st.session_state[FILTER_STATE_KEYS["user_types"]] = []
    st.session_state[FILTER_STATE_KEYS["subscriptions"]] = []
    st.session_state[FILTER_STATE_KEYS["traffic_sources"]] = []


def render_sidebar_filters(df: pd.DataFrame) -> dict[str, Any]:
    """Render sidebar filter widgets, grouped into labeled sections, and
    return the selected filter state.

    All widgets are bound to ``st.session_state`` via explicit ``key=`` values
    so selections persist across reruns and can be programmatically reset.

    Args:
        df: Raw (unfiltered) event-level DataFrame.

    Returns:
        Dictionary of selected filter values (mirrors st.session_state).
    """
    st.sidebar.markdown("## 🎛️ Filters")

    _init_filter_defaults(df)

    min_date = df["event_date"].min().date()
    max_date = df["event_date"].max().date()

    with st.sidebar.expander("📅 Time", expanded=True):
        date_range = st.date_input(
            "Date Range",
            min_value=min_date,
            max_value=max_date,
            key=FILTER_STATE_KEYS["date_range"],
        )

    with st.sidebar.expander("🌍 Geography", expanded=True):
        countries = sorted(df["country"].dropna().unique().tolist())
        selected_countries = st.multiselect(
            "Country", options=countries, key=FILTER_STATE_KEYS["countries"]
        )

    with st.sidebar.expander("📱 Device", expanded=False):
        devices = sorted(df["device_type"].dropna().unique().tolist())
        selected_devices = st.multiselect(
            "Device", options=devices, key=FILTER_STATE_KEYS["devices"]
        )

    with st.sidebar.expander("📢 Marketing", expanded=False):
        campaigns = sorted(df["campaign"].dropna().unique().tolist())
        selected_campaigns = st.multiselect(
            "Campaign", options=campaigns, key=FILTER_STATE_KEYS["campaigns"]
        )
        traffic_sources = sorted(df["traffic_source"].dropna().unique().tolist())
        selected_traffic_sources = st.multiselect(
            "Traffic Source", options=traffic_sources, key=FILTER_STATE_KEYS["traffic_sources"]
        )

    with st.sidebar.expander("👥 Users", expanded=False):
        user_types = sorted(df["user_type"].dropna().unique().tolist())
        selected_user_types = st.multiselect(
            "User Type", options=user_types, key=FILTER_STATE_KEYS["user_types"]
        )
        subscriptions = sorted(df["subscription"].dropna().unique().tolist())
        selected_subscriptions = st.multiselect(
            "Subscription", options=subscriptions, key=FILTER_STATE_KEYS["subscriptions"]
        )

    st.sidebar.markdown("---")
    st.sidebar.caption(
        "Leave a filter empty to include all values for that dimension."
    )
    st.sidebar.button(
        "🔄 Reset Filters",
        on_click=_reset_filters,
        args=(df,),
        width="stretch",
    )

    return {
        "date_range": date_range,
        "countries": selected_countries,
        "campaigns": selected_campaigns,
        "devices": selected_devices,
        "user_types": selected_user_types,
        "subscriptions": selected_subscriptions,
        "traffic_sources": selected_traffic_sources,
    }


def apply_filters(df: pd.DataFrame, filters: dict[str, Any]) -> pd.DataFrame:
    """Apply the sidebar filter selections to the raw DataFrame.

    Every dataframe consumed elsewhere in the app (KPIs, charts, insights,
    downloads) is derived from the output of this function, so a single
    filter change here propagates everywhere automatically.

    Args:
        df: Raw event-level DataFrame.
        filters: Dictionary returned by ``render_sidebar_filters``.

    Returns:
        The filtered DataFrame.
    """
    filtered = df.copy()

    date_range = filters.get("date_range")
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_date, end_date = date_range
        filtered = filtered[
            (filtered["event_date"] >= pd.Timestamp(start_date))
            & (filtered["event_date"] <= pd.Timestamp(end_date))
        ]

    if filters.get("countries"):
        filtered = filtered[filtered["country"].isin(filters["countries"])]

    if filters.get("campaigns"):
        filtered = filtered[filtered["campaign"].isin(filters["campaigns"])]

    if filters.get("devices"):
        filtered = filtered[filtered["device_type"].isin(filters["devices"])]

    if filters.get("user_types"):
        filtered = filtered[filtered["user_type"].isin(filters["user_types"])]

    if filters.get("subscriptions"):
        filtered = filtered[filtered["subscription"].isin(filters["subscriptions"])]

    if filters.get("traffic_sources"):
        filtered = filtered[filtered["traffic_source"].isin(filters["traffic_sources"])]

    return filtered


def build_previous_period_filters(filters: dict[str, Any]) -> dict[str, Any] | None:
    """Derive a filters dict for the period immediately preceding the current
    date-range selection, keeping every other filter dimension identical.

    This powers period-over-period KPI growth (Phase 2) without touching the
    original ``apply_filters`` contract.

    Args:
        filters: The active filters dict returned by ``render_sidebar_filters``.

    Returns:
        A new filters dict with a shifted ``date_range``, or None if the
        current date range is not a valid (start, end) pair.
    """
    date_range = filters.get("date_range")
    if not (isinstance(date_range, tuple) and len(date_range) == 2):
        return None

    start_date, end_date = date_range
    period_length = (end_date - start_date).days + 1
    prev_end = start_date - timedelta(days=1)
    prev_start = prev_end - timedelta(days=period_length - 1)

    prev_filters = dict(filters)
    prev_filters["date_range"] = (prev_start, prev_end)
    return prev_filters


# --------------------------------------------------------------------------
# KPI CALCULATION
# --------------------------------------------------------------------------
def compute_kpis(df: pd.DataFrame) -> dict[str, float]:
    """Compute the top-line KPI set for the currently filtered dataset.

    Args:
        df: Filtered event-level DataFrame.

    Returns:
        Dictionary of KPI name -> numeric value.
    """
    if df.empty:
        return {
            "total_users": 0, "dau": 0.0, "mau": 0.0, "revenue": 0.0,
            "arpu": 0.0, "conversion_rate": 0.0, "avg_purchase_value": 0.0,
            "paying_users": 0, "total_sessions": 0, "total_purchases": 0,
        }

    total_users = df["user_id"].nunique()
    total_revenue = float(df["revenue"].sum())

    dau_series = df.groupby(df["event_date"].dt.date)["user_id"].nunique()
    dau = float(dau_series.mean()) if not dau_series.empty else 0.0

    mau_series = df.groupby(df["event_date"].dt.to_period("M"))["user_id"].nunique()
    mau = float(mau_series.mean()) if not mau_series.empty else 0.0

    purchases = df[df["event_name"] == "Purchase"]
    paying_users = purchases.loc[purchases["purchase_amount"] > 0, "user_id"].nunique()

    arpu = total_revenue / total_users if total_users else 0.0
    conversion_rate = 100 * paying_users / total_users if total_users else 0.0
    avg_purchase_value = (
        float(purchases.loc[purchases["purchase_amount"] > 0, "purchase_amount"].mean())
        if paying_users
        else 0.0
    )

    return {
        "total_users": total_users,
        "dau": dau,
        "mau": mau,
        "revenue": total_revenue,
        "arpu": arpu,
        "conversion_rate": conversion_rate,
        "avg_purchase_value": avg_purchase_value,
        "paying_users": int(paying_users),
        "total_sessions": int(df["session_id"].nunique()),
        "total_purchases": int((purchases["purchase_amount"] > 0).sum()),
    }


# --------------------------------------------------------------------------
# ADVANCED KPI CALCULATION (Phase 2 additions)
# --------------------------------------------------------------------------
def compute_advanced_kpis(df: pd.DataFrame, kpis: dict[str, float]) -> dict[str, Any]:
    """Compute the extended executive KPI set layered on top of ``compute_kpis``.

    Args:
        df: Filtered event-level DataFrame.
        kpis: Dictionary returned by ``compute_kpis`` for the same df.

    Returns:
        Dictionary of advanced KPI name -> value (numeric or string).
    """
    if df.empty:
        return {
            "stickiness": 0.0, "avg_session_duration": 0.0, "returning_pct": 0.0,
            "paying_users": 0, "revenue_per_session": 0.0, "revenue_per_purchase": 0.0,
            "top_country": "N/A", "top_device": "N/A",
        }

    stickiness = 100 * kpis["dau"] / kpis["mau"] if kpis["mau"] else 0.0

    returning = df.drop_duplicates("user_id")["user_type"].value_counts()
    total_filtered_users = df["user_id"].nunique()
    returning_pct = (
        100 * returning.get("Returning", 0) / total_filtered_users if total_filtered_users else 0.0
    )

    revenue_per_session = kpis["revenue"] / kpis["total_sessions"] if kpis["total_sessions"] else 0.0
    revenue_per_purchase = kpis["revenue"] / kpis["total_purchases"] if kpis["total_purchases"] else 0.0

    rev_country = df.groupby("country")["revenue"].sum()
    top_country = rev_country.idxmax() if not rev_country.empty and rev_country.max() > 0 else "N/A"

    rev_device = df.groupby("device_type")["revenue"].sum()
    top_device = rev_device.idxmax() if not rev_device.empty and rev_device.max() > 0 else "N/A"

    return {
        "stickiness": stickiness,
        "avg_session_duration": float(df["session_duration"].mean()),
        "returning_pct": returning_pct,
        "paying_users": kpis["paying_users"],
        "revenue_per_session": revenue_per_session,
        "revenue_per_purchase": revenue_per_purchase,
        "top_country": top_country,
        "top_device": top_device,
    }


def format_compact_number(value: float, prefix: str = "", suffix: str = "") -> str:
    """Format a large number compactly (e.g. $1.13M, 42.6K), like an
    executive BI tool. Falls back to plain formatting under 1,000.

    Args:
        value: The numeric value to format.
        prefix: String to prepend (e.g. "$").
        suffix: String to append (e.g. "%").

    Returns:
        A compact, human-readable string.
    """
    abs_value = abs(value)
    if abs_value >= 1_000_000_000:
        text = f"{value / 1_000_000_000:.2f}B"
    elif abs_value >= 1_000_000:
        text = f"{value / 1_000_000:.2f}M"
    elif abs_value >= 1_000:
        text = f"{value / 1_000:.1f}K"
    else:
        text = f"{value:,.2f}" if isinstance(value, float) and not value.is_integer() else f"{value:,.0f}"
    return f"{prefix}{text}{suffix}"


def pct_change(current: float, previous: float | None) -> float | None:
    """Compute percentage change of current vs previous, guarding zero/None."""
    if previous is None or previous == 0:
        return None
    return 100 * (current - previous) / previous


def render_kpi_card(
    col,
    label: str,
    value: str,
    sub: str = "",
    delta_pct: float | None = None,
    prev_label: str | None = None,
    compact: bool = False,
) -> None:
    """Render a single KPI as a styled HTML card inside a Streamlit column.

    Args:
        col: Streamlit column/container to render into.
        label: KPI name.
        value: Pre-formatted current-period value.
        sub: Optional small caption line.
        delta_pct: Growth percentage vs the previous period (None hides the badge).
        prev_label: Optional label describing the comparison value shown under the delta.
        compact: Use the smaller "advanced KPI" card style.
    """
    delta_html = ""
    if delta_pct is not None:
        if delta_pct > 0.05:
            arrow_class, arrow = "kpi-delta-up", "▲"
        elif delta_pct < -0.05:
            arrow_class, arrow = "kpi-delta-down", "▼"
        else:
            arrow_class, arrow = "kpi-delta-flat", "▬"
        delta_html = f'<div class="kpi-delta {arrow_class}">{arrow} {delta_pct:+.1f}%</div>'
        if prev_label:
            delta_html += f'<div class="kpi-prev">{prev_label}</div>'

    card_class = "kpi-card-sm" if compact else "kpi-card"
    col.markdown(
        f"""
        <div class="{card_class}">
            <div class="kpi-label">{label}</div>
            <div class="kpi-value">{value}</div>
            <div class="kpi-sub">{sub}</div>
            {delta_html}
        </div>
        """,
        unsafe_allow_html=True,
    )


def render_kpi_section(kpis: dict[str, float], prev_kpis: dict[str, float] | None) -> None:
    """Render the full row of top KPI cards, each with current value, previous
    period comparison, growth %, and an up/down indicator.

    Args:
        kpis: Current-period KPI dictionary from ``compute_kpis``.
        prev_kpis: Previous-period KPI dictionary (same shape), or None if
            a comparison period couldn't be computed.
    """
    st.markdown('<div class="section-title">📌 Key Performance Indicators</div>', unsafe_allow_html=True)

    def _delta(key: str) -> float | None:
        if prev_kpis is None:
            return None
        return pct_change(kpis[key], prev_kpis.get(key))

    def _prev_label(key: str, fmt) -> str | None:
        if prev_kpis is None:
            return None
        return f"prev: {fmt(prev_kpis.get(key, 0))}"

    cols = st.columns(7)
    render_kpi_card(cols[0], "Total Users", f"{kpis['total_users']:,}")
    render_kpi_card(
        cols[1], "DAU (avg)", f"{kpis['dau']:.0f}",
        delta_pct=_delta("dau"), prev_label=_prev_label("dau", lambda v: f"{v:.0f}"),
    )
    render_kpi_card(
        cols[2], "MAU (avg)", f"{kpis['mau']:.0f}",
        delta_pct=_delta("mau"), prev_label=_prev_label("mau", lambda v: f"{v:.0f}"),
    )
    render_kpi_card(
        cols[3], "Revenue", format_compact_number(kpis["revenue"], prefix="$"),
        delta_pct=_delta("revenue"), prev_label=_prev_label("revenue", lambda v: format_compact_number(v, prefix="$")),
    )
    render_kpi_card(
        cols[4], "ARPU", f"${kpis['arpu']:.2f}",
        delta_pct=_delta("arpu"), prev_label=_prev_label("arpu", lambda v: f"${v:.2f}"),
    )
    render_kpi_card(
        cols[5], "Conversion Rate", f"{kpis['conversion_rate']:.2f}%",
        delta_pct=_delta("conversion_rate"), prev_label=_prev_label("conversion_rate", lambda v: f"{v:.2f}%"),
    )
    render_kpi_card(
        cols[6], "Avg Purchase Value", f"${kpis['avg_purchase_value']:.2f}",
        delta_pct=_delta("avg_purchase_value"), prev_label=_prev_label("avg_purchase_value", lambda v: f"${v:.2f}"),
    )

    if prev_kpis is None:
        st.caption("Previous-period comparison unavailable for this date selection (not enough prior history).")


def render_advanced_kpi_section(adv_kpis: dict[str, Any]) -> None:
    """Render the extended KPI row: stickiness, session duration, returning
    users %, paying users, revenue efficiency, and top dimensions.

    Args:
        adv_kpis: Dictionary returned by ``compute_advanced_kpis``.
    """
    st.markdown('<div class="section-title">🧭 Advanced KPIs</div>', unsafe_allow_html=True)
    cols = st.columns(8)
    render_kpi_card(cols[0], "Stickiness (DAU/MAU)", f"{adv_kpis['stickiness']:.1f}%", compact=True)
    render_kpi_card(cols[1], "Avg Session Duration", f"{adv_kpis['avg_session_duration']:.0f}s", compact=True)
    render_kpi_card(cols[2], "Returning Users", f"{adv_kpis['returning_pct']:.1f}%", compact=True)
    render_kpi_card(cols[3], "Paying Users", f"{adv_kpis['paying_users']:,}", compact=True)
    render_kpi_card(cols[4], "Revenue / Session", f"${adv_kpis['revenue_per_session']:.2f}", compact=True)
    render_kpi_card(cols[5], "Revenue / Purchase", f"${adv_kpis['revenue_per_purchase']:.2f}", compact=True)
    render_kpi_card(cols[6], "Top Country", f"{adv_kpis['top_country']}", compact=True)
    render_kpi_card(cols[7], "Top Device", f"{adv_kpis['top_device']}", compact=True)


def render_executive_summary(
    df: pd.DataFrame, kpis: dict[str, float], adv_kpis: dict[str, Any], prev_kpis: dict[str, float] | None
) -> None:
    """Render the Executive Summary strip shown above the KPI cards.

    Surfaces the handful of numbers a Product/Exec would want to see in the
    first five seconds: revenue growth, best-performing dimensions, funnel
    drop-off, returning-user rate, and average session duration. Recomputed
    live from the filtered dataset on every filter change.

    Args:
        df: Filtered event-level DataFrame.
        kpis: Dictionary from ``compute_kpis``.
        adv_kpis: Dictionary from ``compute_advanced_kpis``.
        prev_kpis: Previous-period KPI dictionary, or None.
    """
    st.markdown('<div class="section-title">📈 Executive Summary</div>', unsafe_allow_html=True)

    revenue_growth = pct_change(kpis["revenue"], prev_kpis.get("revenue")) if prev_kpis else None
    revenue_growth_text = f"{revenue_growth:+.1f}%" if revenue_growth is not None else "N/A"

    rev_campaign = df.groupby("campaign")["revenue"].sum()
    non_none_campaign = rev_campaign[rev_campaign.index != "None"]
    top_campaign_series = non_none_campaign if not non_none_campaign.empty else rev_campaign
    best_campaign = top_campaign_series.idxmax() if not top_campaign_series.empty and top_campaign_series.max() > 0 else "N/A"

    traffic_counts = df["traffic_source"].value_counts()
    top_traffic = traffic_counts.idxmax() if not traffic_counts.empty else "N/A"

    sub_revenue = df.groupby("subscription")["revenue"].sum()
    top_subscription = sub_revenue.idxmax() if not sub_revenue.empty and sub_revenue.max() > 0 else "N/A"

    funnel_counts = [df[df["event_name"] == stage]["user_id"].nunique() for stage in FUNNEL_STAGES]
    funnel_drop = (100 * (1 - funnel_counts[-1] / funnel_counts[0])) if funnel_counts[0] else 0.0

    chips = [
        ("Revenue Growth", revenue_growth_text),
        ("Best Country", adv_kpis["top_country"]),
        ("Best Campaign", best_campaign),
        ("Best Device", adv_kpis["top_device"]),
        ("Top Traffic Source", top_traffic),
        ("Top Subscription (Revenue)", top_subscription),
        ("Funnel Drop-off", f"{funnel_drop:.1f}%"),
        ("Returning Users", f"{adv_kpis['returning_pct']:.1f}%"),
        ("Avg Session Duration", f"{adv_kpis['avg_session_duration']:.0f}s"),
    ]

    cols = st.columns(3)
    for idx, (chip_label, chip_value) in enumerate(chips):
        with cols[idx % 3]:
            st.markdown(
                f"""
                <div class="exec-chip">
                    <div class="exec-label">{chip_label}</div>
                    <div class="exec-value">{chip_value}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )


# --------------------------------------------------------------------------
# CHART BUILDERS (all return Plotly figures)
# --------------------------------------------------------------------------
def chart_revenue_trend(df: pd.DataFrame) -> go.Figure:
    """Gradient-filled area chart of daily revenue over time."""
    trend = df.groupby(df["event_date"].dt.date)["revenue"].sum().reset_index()
    trend.columns = ["date", "revenue"]
    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=trend["date"], y=trend["revenue"], mode="lines", fill="tozeroy",
            line=dict(color=CHART_COLORWAY[0], width=2.5, shape="spline"),
            fillcolor="rgba(59,130,246,0.28)",
            hovertemplate="%{x}<br>Revenue: $%{y:,.2f}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Revenue Trend", xaxis_title="Date", yaxis_title="Revenue ($)",
        template=PLOTLY_TEMPLATE,
    )
    return fig


def chart_dau_trend(df: pd.DataFrame) -> go.Figure:
    """Smoothed line chart of daily active users over time (3-day rolling
    average with a spline curve), with the raw daily series shown faintly
    underneath for reference."""
    trend = df.groupby(df["event_date"].dt.date)["user_id"].nunique().reset_index()
    trend.columns = ["date", "active_users"]
    trend["smoothed"] = trend["active_users"].rolling(3, min_periods=1, center=True).mean()

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=trend["date"], y=trend["active_users"], mode="lines", name="Daily",
            line=dict(color="rgba(34,197,94,0.25)", width=1),
            hoverinfo="skip",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=trend["date"], y=trend["smoothed"], mode="lines", name="Smoothed (3d avg)",
            line=dict(color=CHART_COLORWAY[1], width=2.5, shape="spline"),
            hovertemplate="%{x}<br>Active Users: %{y:.0f}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Daily Active Users Trend", xaxis_title="Date", yaxis_title="Active Users",
        template=PLOTLY_TEMPLATE, showlegend=False,
    )
    return fig


def chart_revenue_by_country(df: pd.DataFrame) -> go.Figure:
    """Interactive Plotly choropleth map of revenue by country."""
    grouped = df.groupby("country")["revenue"].sum().reset_index()
    fig = px.choropleth(
        grouped, locations="country", locationmode="country names", color="revenue",
        color_continuous_scale="Blues", template=PLOTLY_TEMPLATE,
        hover_name="country",
    )
    fig.update_layout(
        title="Revenue by Country", geo=dict(bgcolor="rgba(0,0,0,0)", showframe=False),
        margin=dict(l=0, r=0, t=50, b=0),
    )
    return fig


def chart_revenue_by_device(df: pd.DataFrame) -> go.Figure:
    """Treemap of revenue by device type."""
    grouped = df.groupby("device_type")["revenue"].sum().reset_index()
    grouped = grouped[grouped["revenue"] > 0]
    fig = px.treemap(
        grouped, path=["device_type"], values="revenue", color="revenue",
        color_continuous_scale="Blues", template=PLOTLY_TEMPLATE,
    )
    fig.update_traces(
        hovertemplate="%{label}<br>Revenue: $%{value:,.2f}<extra></extra>",
        texttemplate="%{label}<br>$%{value:,.0f}",
    )
    fig.update_layout(title="Revenue by Device", margin=dict(l=0, r=0, t=50, b=0))
    return fig


def chart_campaign_performance(df: pd.DataFrame) -> go.Figure:
    """Interactive horizontal bar chart of revenue by marketing campaign,
    with value labels and rich hover tooltips."""
    grouped = df.groupby("campaign")["revenue"].sum().sort_values(ascending=True).reset_index()
    fig = px.bar(
        grouped, x="revenue", y="campaign", orientation="h", template=PLOTLY_TEMPLATE,
        color="revenue", color_continuous_scale="Oranges", text="revenue",
    )
    fig.update_traces(
        texttemplate="$%{text:,.0f}", textposition="outside",
        hovertemplate="%{y}<br>Revenue: $%{x:,.2f}<extra></extra>",
    )
    fig.update_layout(title="Campaign Performance", xaxis_title="Revenue ($)", yaxis_title="Campaign")
    return fig


def chart_traffic_source(df: pd.DataFrame) -> go.Figure:
    """Donut chart of event volume share by traffic source."""
    grouped = df["traffic_source"].value_counts().reset_index()
    grouped.columns = ["traffic_source", "events"]
    fig = px.pie(
        grouped, names="traffic_source", values="events", hole=0.55,
        template=PLOTLY_TEMPLATE, color_discrete_sequence=CHART_COLORWAY,
    )
    fig.update_traces(
        textinfo="label+percent",
        hovertemplate="%{label}<br>Events: %{value:,}<br>Share: %{percent}<extra></extra>",
    )
    fig.update_layout(title="Traffic Source Distribution")
    return fig


def chart_subscription_distribution(df: pd.DataFrame) -> go.Figure:
    """Pie chart of subscription tier distribution across unique users."""
    grouped = df.drop_duplicates("user_id")["subscription"].value_counts().reset_index()
    grouped.columns = ["subscription", "users"]
    fig = px.pie(
        grouped, names="subscription", values="users", template=PLOTLY_TEMPLATE,
        color_discrete_sequence=CHART_COLORWAY, hole=0.45,
    )
    fig.update_layout(title="Subscription Distribution")
    return fig


def chart_retention_analysis(df: pd.DataFrame) -> go.Figure:
    """Retention heatmap: unique users by acquisition week (rows) x retention
    day (columns). Falls back gracefully to a single-row heatmap if only one
    week of data is present in the current filter selection."""
    working = df.dropna(subset=["retention_day"]).copy()
    if working.empty:
        fig = go.Figure()
        fig.update_layout(title="Retention Analysis", template=PLOTLY_TEMPLATE)
        return fig

    working["cohort_week"] = working["event_date"].dt.to_period("W").astype(str)
    pivot = working.pivot_table(
        index="cohort_week", columns="retention_day", values="user_id",
        aggfunc="nunique", fill_value=0,
    ).sort_index()
    pivot = pivot.reindex(sorted(pivot.columns), axis=1)

    fig = px.imshow(
        pivot, color_continuous_scale="Magma", template=PLOTLY_TEMPLATE, aspect="auto",
        labels=dict(x="Retention Day", y="Cohort Week", color="Unique Users"),
    )
    fig.update_layout(title="Retention Analysis (Cohort Heatmap)")
    return fig


def _gaussian_kde(values: np.ndarray, grid_points: int = 200) -> tuple[np.ndarray, np.ndarray]:
    """Compute a simple Gaussian kernel density estimate without a SciPy
    dependency, using Silverman's rule of thumb for bandwidth.

    Args:
        values: 1-D array of observed session durations.
        grid_points: Number of points to evaluate the density curve at.

    Returns:
        (x_grid, density) arrays for plotting.
    """
    values = values[~np.isnan(values)]
    n = len(values)
    if n < 2 or values.std() == 0:
        x_grid = np.linspace(values.min() if n else 0, values.max() if n else 1, grid_points)
        return x_grid, np.zeros_like(x_grid)

    std = values.std(ddof=1)
    bandwidth = 1.06 * std * n ** (-1 / 5)
    bandwidth = bandwidth if bandwidth > 0 else 1.0

    x_grid = np.linspace(values.min(), values.max(), grid_points)
    diffs = (x_grid[:, None] - values[None, :]) / bandwidth
    density = np.exp(-0.5 * diffs ** 2).sum(axis=1) / (n * bandwidth * np.sqrt(2 * np.pi))
    return x_grid, density


def chart_session_duration_histogram(df: pd.DataFrame) -> go.Figure:
    """Histogram of session duration (seconds) with a KDE curve overlay."""
    durations = df["session_duration"].to_numpy(dtype=float)

    fig = go.Figure()
    fig.add_trace(
        go.Histogram(
            x=durations, nbinsx=40, histnorm="probability density",
            marker=dict(color=CHART_COLORWAY[5], opacity=0.65),
            name="Distribution",
            hovertemplate="Duration: %{x:.0f}s<br>Density: %{y:.4f}<extra></extra>",
        )
    )
    x_grid, density = _gaussian_kde(durations)
    fig.add_trace(
        go.Scatter(
            x=x_grid, y=density, mode="lines", name="KDE",
            line=dict(color="#f97316", width=2.5),
            hovertemplate="Duration: %{x:.0f}s<br>Density: %{y:.4f}<extra></extra>",
        )
    )
    fig.update_layout(
        title="Session Duration Distribution", xaxis_title="Session Duration (s)",
        yaxis_title="Density", template=PLOTLY_TEMPLATE, bargap=0.02,
    )
    return fig


def chart_funnel(df: pd.DataFrame) -> go.Figure:
    """Interactive funnel chart across the core product funnel stages."""
    counts = [df[df["event_name"] == stage]["user_id"].nunique() for stage in FUNNEL_STAGES]
    fig = go.Figure(
        go.Funnel(
            y=FUNNEL_STAGES,
            x=counts,
            textinfo="value+percent initial",
            marker={"color": CHART_COLORWAY[: len(FUNNEL_STAGES)]},
        )
    )
    fig.update_layout(title="User Funnel", template=PLOTLY_TEMPLATE)
    return fig


def render_chart_grid(df: pd.DataFrame) -> None:
    """Lay out the full interactive chart suite in a responsive two-column grid."""
    st.markdown('<div class="section-title">📈 Trends</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.plotly_chart(chart_revenue_trend(df), width="stretch")
    c2.plotly_chart(chart_dau_trend(df), width="stretch")

    st.markdown('<div class="section-title">💰 Revenue Breakdown</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.plotly_chart(chart_revenue_by_country(df), width="stretch")
    c2.plotly_chart(chart_revenue_by_device(df), width="stretch")

    c1, c2 = st.columns(2)
    c1.plotly_chart(chart_campaign_performance(df), width="stretch")
    c2.plotly_chart(chart_traffic_source(df), width="stretch")

    st.markdown('<div class="section-title">👥 Engagement & Retention</div>', unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    c1.plotly_chart(chart_subscription_distribution(df), width="stretch")
    c2.plotly_chart(chart_retention_analysis(df), width="stretch")

    c1, c2 = st.columns(2)
    c1.plotly_chart(chart_session_duration_histogram(df), width="stretch")
    c2.plotly_chart(chart_funnel(df), width="stretch")


# --------------------------------------------------------------------------
# EXECUTIVE RECOMMENDATIONS (Phase 5)
# --------------------------------------------------------------------------
def compute_executive_recommendations(
    df: pd.DataFrame, kpis: dict[str, float], adv_kpis: dict[str, Any], prev_kpis: dict[str, float] | None
) -> list[str]:
    """Generate 8-12 action-oriented executive recommendations from the
    currently filtered dataset. Distinct from the (descriptive) Business
    Insights panel below — these are framed as decisions/next steps.

    Args:
        df: Filtered event-level DataFrame.
        kpis: Dictionary from ``compute_kpis``.
        adv_kpis: Dictionary from ``compute_advanced_kpis``.
        prev_kpis: Previous-period KPI dictionary, or None.

    Returns:
        A list of recommendation strings.
    """
    if df.empty:
        return ["No data available for the current filter selection — widen filters to generate recommendations."]

    recos: list[str] = []

    if prev_kpis:
        rev_growth = pct_change(kpis["revenue"], prev_kpis.get("revenue"))
        if rev_growth is not None:
            if rev_growth > 0:
                recos.append(f"✅ Revenue is up {rev_growth:.1f}% vs. the previous period — sustain current spend allocation.")
            else:
                recos.append(f"⚠️ Revenue is down {abs(rev_growth):.1f}% vs. the previous period — investigate before the next budget cycle.")

        conv_growth = pct_change(kpis["conversion_rate"], prev_kpis.get("conversion_rate"))
        if conv_growth is not None and conv_growth < -1:
            recos.append(f"⚠️ Conversion rate declined {abs(conv_growth):.1f}% — review onboarding and checkout friction.")
        elif conv_growth is not None and conv_growth > 1:
            recos.append(f"✅ Conversion rate improved {conv_growth:.1f}% — identify and replicate what changed.")

    rev_campaign = df.groupby("campaign")["revenue"].sum().sort_values(ascending=False)
    non_none_campaign = rev_campaign[rev_campaign.index != "None"]
    if not non_none_campaign.empty and non_none_campaign.sum() > 0:
        top_campaign = non_none_campaign.index[0]
        share = 100 * non_none_campaign.iloc[0] / non_none_campaign.sum()
        recos.append(f"📢 '{top_campaign}' generates {share:.1f}% of attributed campaign revenue — consider increasing its budget allocation.")
        if len(non_none_campaign) > 1:
            weakest_campaign = non_none_campaign.index[-1]
            recos.append(f"🔻 '{weakest_campaign}' is the weakest attributed campaign — consider reallocating its budget.")

    rev_country = df.groupby("country")["revenue"].sum().sort_values(ascending=False)
    if not rev_country.empty and rev_country.sum() > 0:
        top_country = rev_country.index[0]
        share = 100 * rev_country.iloc[0] / rev_country.sum()
        recos.append(f"🌍 {top_country} contributes {share:.1f}% of revenue — prioritize localized campaigns and support for this market.")

    conv_by_device = (
        df[df["event_name"] == "Purchase"].groupby("device_type")["user_id"].nunique()
        / df.groupby("device_type")["user_id"].nunique()
        * 100
    ).dropna().sort_values(ascending=False)
    if not conv_by_device.empty:
        recos.append(f"📱 {conv_by_device.index[0]} users convert at the highest rate ({conv_by_device.iloc[0]:.1f}%) — prioritize this platform in product and creative testing.")

    if adv_kpis["returning_pct"] and prev_kpis:
        recos.append(f"🔄 Returning users make up {adv_kpis['returning_pct']:.1f}% of the base — nurture this segment with loyalty or retention offers.")

    funnel_counts = [df[df["event_name"] == stage]["user_id"].nunique() for stage in FUNNEL_STAGES]
    biggest_drop_pct, biggest_drop_stage = 0.0, None
    for i in range(1, len(funnel_counts)):
        if funnel_counts[i - 1]:
            drop = 100 * (1 - funnel_counts[i] / funnel_counts[i - 1])
            if drop > biggest_drop_pct:
                biggest_drop_pct, biggest_drop_stage = drop, (FUNNEL_STAGES[i - 1], FUNNEL_STAGES[i])
    if biggest_drop_stage:
        recos.append(f"🔽 The steepest funnel drop-off ({biggest_drop_pct:.1f}%) happens between '{biggest_drop_stage[0]}' and '{biggest_drop_stage[1]}' — prioritize UX fixes at this step.")

    sub_revenue = df.groupby("subscription")["revenue"].sum().sort_values(ascending=False)
    if not sub_revenue.empty and sub_revenue.sum() > 0:
        recos.append(f"💳 The '{sub_revenue.index[0]}' subscription tier drives the most revenue — consider upsell campaigns targeting lower tiers.")

    if adv_kpis["stickiness"] < 20:
        recos.append(f"📉 Stickiness (DAU/MAU) is only {adv_kpis['stickiness']:.1f}% — invest in habit-forming features or push/notification re-engagement.")
    else:
        recos.append(f"✅ Stickiness (DAU/MAU) is a healthy {adv_kpis['stickiness']:.1f}%, indicating strong daily engagement relative to the monthly base.")

    traffic_counts = df["traffic_source"].value_counts()
    if not traffic_counts.empty:
        recos.append(f"🚦 '{traffic_counts.index[0]}' drives the most traffic — validate attribution and double down if ROAS is favorable.")

    return recos[:12]


def render_executive_recommendations(
    df: pd.DataFrame, kpis: dict[str, float], adv_kpis: dict[str, Any], prev_kpis: dict[str, float] | None
) -> None:
    """Render the Executive Recommendations panel as styled action cards."""
    st.markdown('<div class="section-title">💡 Executive Recommendations</div>', unsafe_allow_html=True)
    st.caption("Action-oriented recommendations generated live from the currently filtered data.")

    recos = compute_executive_recommendations(df, kpis, adv_kpis, prev_kpis)
    left_col, right_col = st.columns(2)
    for idx, line in enumerate(recos):
        target_col = left_col if idx % 2 == 0 else right_col
        target_col.markdown(f'<div class="reco-card">{line}</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------
# BUSINESS INSIGHTS SECTION
# --------------------------------------------------------------------------
def compute_dynamic_insights(df: pd.DataFrame, kpis: dict[str, float]) -> list[str]:
    """Generate business insights live from the currently filtered dataset.

    Unlike the pipeline's static Output/reports/business_insights.txt (which
    always reflects the full, unfiltered dataset), these insights are
    recomputed on every filter change so they stay in sync with the sidebar.

    Args:
        df: Filtered event-level DataFrame.
        kpis: Dictionary returned by ``compute_kpis`` for the same df.

    Returns:
        A list of human-readable insight strings.
    """
    if df.empty:
        return ["No events match the current filter selection."]

    insights: list[str] = []

    rev_country = df.groupby("country")["revenue"].sum().sort_values(ascending=False)
    rev_device = df.groupby("device_type")["revenue"].sum().sort_values(ascending=False)
    rev_campaign = df.groupby("campaign")["revenue"].sum().sort_values(ascending=False)
    non_none_campaign = rev_campaign[rev_campaign.index != "None"]

    traffic_counts = df["traffic_source"].value_counts()
    event_counts = df["event_name"].value_counts()
    sub_revenue = df.groupby("subscription")["revenue"].sum().sort_values(ascending=False)
    funnel_counts = [df[df["event_name"] == stage]["user_id"].nunique() for stage in FUNNEL_STAGES]

    if not rev_country.empty and rev_country.max() > 0:
        insights.append(
            f"🌍 {rev_country.idxmax()} leads revenue in the current selection at "
            f"${rev_country.max():,.2f} ({100 * rev_country.max() / rev_country.sum():.1f}% of filtered revenue)."
        )
    if not rev_device.empty and rev_device.max() > 0:
        insights.append(
            f"📱 {rev_device.idxmax()} is the top-earning device type "
            f"(${rev_device.max():,.2f}) among the filtered events."
        )
    top_campaign_series = non_none_campaign if not non_none_campaign.empty else rev_campaign
    if not top_campaign_series.empty and top_campaign_series.max() > 0:
        insights.append(
            f"🎯 '{top_campaign_series.idxmax()}' is the strongest campaign in view, "
            f"generating ${top_campaign_series.max():,.2f}."
        )
    if not traffic_counts.empty:
        insights.append(
            f"🚦 '{traffic_counts.idxmax()}' drives the most events "
            f"({traffic_counts.max():,}) in the filtered slice."
        )
    if not event_counts.empty:
        insights.append(
            f"⚡ '{event_counts.idxmax()}' is the most frequent event "
            f"({event_counts.max():,} occurrences) for this selection."
        )
    if not sub_revenue.empty and sub_revenue.max() > 0:
        insights.append(
            f"💳 The '{sub_revenue.idxmax()}' subscription tier contributes the most revenue "
            f"(${sub_revenue.max():,.2f}) among filtered users."
        )

    insights.append(
        f"👥 {kpis['total_users']:,} unique users generated ${kpis['revenue']:,.2f} in revenue "
        f"(ARPU ${kpis['arpu']:.2f})."
    )
    insights.append(
        f"🔁 Conversion rate for this selection is {kpis['conversion_rate']:.2f}%, "
        f"with an average purchase value of ${kpis['avg_purchase_value']:.2f}."
    )
    insights.append(
        f"📊 Average DAU is {kpis['dau']:.0f} and average MAU is {kpis['mau']:.0f} "
        "across the filtered date range."
    )

    if funnel_counts[0]:
        drop_off = 100 * (1 - funnel_counts[-1] / funnel_counts[0])
        insights.append(
            f"🔽 The funnel shows a {drop_off:.1f}% drop-off from '{FUNNEL_STAGES[0]}' to "
            f"'{FUNNEL_STAGES[-1]}' for the current filters."
        )

    returning_users = df.drop_duplicates("user_id")["user_type"].value_counts()
    total_filtered_users = df["user_id"].nunique()
    if total_filtered_users and "Returning" in returning_users.index:
        insights.append(
            f"🔄 Returning users make up "
            f"{100 * returning_users.get('Returning', 0) / total_filtered_users:.1f}% "
            "of the currently filtered user base."
        )

    insights.append(
        f"⏱️ Average session duration in this view is {df['session_duration'].mean():.1f} seconds "
        f"(median {df['session_duration'].median():.1f}s)."
    )

    return insights


def render_insights_section(df: pd.DataFrame, kpis: dict[str, float]) -> None:
    """Render live, filter-aware business insights as styled cards.

    Args:
        df: Filtered event-level DataFrame.
        kpis: Dictionary returned by ``compute_kpis`` for the same df.
    """
    st.markdown('<div class="section-title">💡 Business Insights</div>', unsafe_allow_html=True)
    st.caption("Generated live from the currently filtered data — updates with every filter change.")

    insights = compute_dynamic_insights(df, kpis)

    if not insights:
        st.info("No business insights available for the current filter selection.")
        return

    left_col, right_col = st.columns(2)
    for idx, line in enumerate(insights):
        target_col = left_col if idx % 2 == 0 else right_col
        target_col.markdown(f'<div class="insight-card">{line}</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------
# ADVANCED ANALYTICS & EXECUTIVE TABLES (Phases 6 & 7)
# --------------------------------------------------------------------------
def build_summary_table(df: pd.DataFrame, group_col: str) -> pd.DataFrame:
    """Build a professional executive summary table for any dimension
    (campaign, country, device, subscription, traffic source), with users,
    revenue, ARPU, conversion rate, average purchase value, and % share of
    total filtered revenue.

    Args:
        df: Filtered event-level DataFrame.
        group_col: Column to group by (e.g. "campaign", "country").

    Returns:
        A DataFrame sorted by revenue descending, ready for st.dataframe.
    """
    if df.empty or group_col not in df.columns:
        return pd.DataFrame(columns=[group_col, "users", "revenue", "arpu", "conversion_rate_pct", "avg_purchase_value", "pct_share"])

    purchases = df[df["event_name"] == "Purchase"]
    total_revenue = df["revenue"].sum()

    users = df.groupby(group_col)["user_id"].nunique()
    revenue = df.groupby(group_col)["revenue"].sum()
    paying_users = purchases[purchases["purchase_amount"] > 0].groupby(group_col)["user_id"].nunique()
    avg_purchase = purchases[purchases["purchase_amount"] > 0].groupby(group_col)["purchase_amount"].mean()

    table = pd.DataFrame({"users": users, "revenue": revenue}).fillna(0)
    table["arpu"] = table["revenue"] / table["users"].replace(0, np.nan)
    table["conversion_rate_pct"] = 100 * paying_users.reindex(table.index).fillna(0) / table["users"].replace(0, np.nan)
    table["avg_purchase_value"] = avg_purchase.reindex(table.index)
    table["pct_share"] = 100 * table["revenue"] / total_revenue if total_revenue else 0.0

    table = table.fillna(0).sort_values("revenue", ascending=False).reset_index()
    table = table.rename(columns={group_col: group_col.replace("_", " ").title()})
    return table


def build_monthly_growth_table(df: pd.DataFrame) -> pd.DataFrame:
    """Build a month-over-month growth table for revenue and DAU.

    Args:
        df: Filtered event-level DataFrame.

    Returns:
        DataFrame with month, revenue, revenue_growth_pct, dau, dau_growth_pct.
    """
    if df.empty:
        return pd.DataFrame(columns=["month", "revenue", "revenue_growth_pct", "avg_dau", "dau_growth_pct"])

    monthly = df.copy()
    monthly["month"] = monthly["event_date"].dt.to_period("M").astype(str)

    monthly_revenue = monthly.groupby("month")["revenue"].sum()
    monthly_dau = monthly.groupby(["month", monthly["event_date"].dt.date])["user_id"].nunique().groupby("month").mean()

    result = pd.DataFrame({"revenue": monthly_revenue, "avg_dau": monthly_dau}).sort_index()
    result["revenue_growth_pct"] = result["revenue"].pct_change() * 100
    result["dau_growth_pct"] = result["avg_dau"].pct_change() * 100
    result = result.reset_index().rename(columns={"index": "month"})
    return result


def chart_monthly_growth(monthly_table: pd.DataFrame) -> go.Figure:
    """Combo chart: monthly revenue (bars) and DAU growth % (line, secondary axis)."""
    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=monthly_table["month"], y=monthly_table["revenue"], name="Revenue",
            marker_color=CHART_COLORWAY[0], yaxis="y1",
            hovertemplate="%{x}<br>Revenue: $%{y:,.2f}<extra></extra>",
        )
    )
    fig.add_trace(
        go.Scatter(
            x=monthly_table["month"], y=monthly_table["revenue_growth_pct"], name="Revenue Growth %",
            mode="lines+markers", line=dict(color="#f97316", width=2.5), yaxis="y2",
            hovertemplate="%{x}<br>Growth: %{y:.1f}%<extra></extra>",
        )
    )
    fig.update_layout(
        title="Monthly Revenue & Growth %", template=PLOTLY_TEMPLATE,
        yaxis=dict(title="Revenue ($)"),
        yaxis2=dict(title="Growth %", overlaying="y", side="right"),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


def render_advanced_analytics(df: pd.DataFrame) -> dict[str, pd.DataFrame]:
    """Render the Advanced Analytics section: monthly growth chart, and the
    executive summary tables for campaign, country, device, subscription,
    and traffic source — each with users, revenue, ARPU, conversion rate,
    average purchase value, and % share of revenue. Tables are natively
    sortable by clicking any column header.

    Args:
        df: Filtered event-level DataFrame.
    """
    st.markdown('<div class="section-title">📊 Advanced Analytics</div>', unsafe_allow_html=True)

    monthly_table = build_monthly_growth_table(df)
    if not monthly_table.empty:
        st.plotly_chart(chart_monthly_growth(monthly_table), width="stretch")
        with st.expander("Monthly Growth Table"):
            st.dataframe(
                monthly_table.style.format({
                    "revenue": "${:,.2f}", "revenue_growth_pct": "{:+.1f}%",
                    "avg_dau": "{:.0f}", "dau_growth_pct": "{:+.1f}%",
                }),
                width="stretch",
            )
    else:
        st.info("Not enough date coverage in the current filter selection to compute monthly growth.")

    st.markdown("#### 🌍 Top Countries")
    country_table = build_summary_table(df, "country")
    st.dataframe(
        country_table.style.format({
            "revenue": "${:,.2f}", "arpu": "${:.2f}", "conversion_rate_pct": "{:.2f}%",
            "avg_purchase_value": "${:.2f}", "pct_share": "{:.1f}%",
        }),
        width="stretch",
    )

    st.markdown("#### 📢 Campaign Performance (Revenue Efficiency)")
    st.caption("No ad-spend/cost data is available in the source dataset, so 'ROI' is expressed as revenue efficiency (ARPU, conversion, and revenue share) rather than a true cost-based ROI.")
    campaign_table = build_summary_table(df, "campaign")
    st.dataframe(
        campaign_table.style.format({
            "revenue": "${:,.2f}", "arpu": "${:.2f}", "conversion_rate_pct": "{:.2f}%",
            "avg_purchase_value": "${:.2f}", "pct_share": "{:.1f}%",
        }),
        width="stretch",
    )

    c1, c2 = st.columns(2)
    with c1:
        st.markdown("#### 📱 Device Comparison")
        device_table = build_summary_table(df, "device_type")
        st.dataframe(
            device_table.style.format({
                "revenue": "${:,.2f}", "arpu": "${:.2f}", "conversion_rate_pct": "{:.2f}%",
                "avg_purchase_value": "${:.2f}", "pct_share": "{:.1f}%",
            }),
            width="stretch",
        )
    with c2:
        st.markdown("#### 💳 Subscription Comparison")
        subscription_table = build_summary_table(df, "subscription")
        st.dataframe(
            subscription_table.style.format({
                "revenue": "${:,.2f}", "arpu": "${:.2f}", "conversion_rate_pct": "{:.2f}%",
                "avg_purchase_value": "${:.2f}", "pct_share": "{:.1f}%",
            }),
            width="stretch",
        )

    st.markdown("#### 🚦 Traffic Source Comparison")
    traffic_table = build_summary_table(df, "traffic_source")
    st.dataframe(
        traffic_table.style.format({
            "revenue": "${:,.2f}", "arpu": "${:.2f}", "conversion_rate_pct": "{:.2f}%",
            "avg_purchase_value": "${:.2f}", "pct_share": "{:.1f}%",
        }),
        width="stretch",
    )

    return {
        "country_table": country_table,
        "campaign_table": campaign_table,
        "device_table": device_table,
        "subscription_table": subscription_table,
        "traffic_table": traffic_table,
    }


# --------------------------------------------------------------------------
# DOWNLOADS SECTION
# --------------------------------------------------------------------------
def build_filtered_summary_metrics(df: pd.DataFrame, kpis: dict[str, float]) -> pd.DataFrame:
    """Build a summary_metrics-style DataFrame from the currently filtered data.

    Args:
        df: Filtered event-level DataFrame.
        kpis: Dictionary returned by ``compute_kpis`` for the same df.

    Returns:
        A two-column (metric, value) DataFrame ready for CSV export.
    """
    rows = {
        "total_users": kpis["total_users"],
        "avg_dau": kpis["dau"],
        "avg_mau": kpis["mau"],
        "total_revenue": kpis["revenue"],
        "arpu": kpis["arpu"],
        "conversion_rate_pct": kpis["conversion_rate"],
        "avg_purchase_value": kpis["avg_purchase_value"],
        "avg_session_duration": float(df["session_duration"].mean()) if not df.empty else 0.0,
        "median_session_duration": float(df["session_duration"].median()) if not df.empty else 0.0,
        "total_events": len(df),
        "total_sessions": df["session_id"].nunique() if not df.empty else 0,
    }
    return pd.DataFrame(list(rows.items()), columns=["metric", "value"])


def build_filtered_campaign_performance(df: pd.DataFrame) -> pd.DataFrame:
    """Build a campaign_performance-style DataFrame from the filtered data."""
    if df.empty or "campaign" not in df.columns:
        return pd.DataFrame(columns=["campaign", "users", "events", "revenue", "avg_session_duration"])
    return (
        df.groupby("campaign")
        .agg(
            users=("user_id", "nunique"),
            events=("event_name", "count"),
            revenue=("revenue", "sum"),
            avg_session_duration=("session_duration", "mean"),
        )
        .sort_values("revenue", ascending=False)
        .reset_index()
    )


def build_filtered_device_summary(df: pd.DataFrame) -> pd.DataFrame:
    """Build a device_summary-style DataFrame from the filtered data."""
    if df.empty or "device_type" not in df.columns:
        return pd.DataFrame(columns=["device_type", "users", "events", "revenue", "avg_session_duration"])
    return (
        df.groupby("device_type")
        .agg(
            users=("user_id", "nunique"),
            events=("event_name", "count"),
            revenue=("revenue", "sum"),
            avg_session_duration=("session_duration", "mean"),
        )
        .sort_values("revenue", ascending=False)
        .reset_index()
    )


def build_business_insights_txt(insights: list[str], recommendations: list[str]) -> str:
    """Build a plain-text export combining live business insights and
    executive recommendations for the current filter selection."""
    lines = ["BUSINESS INSIGHTS", "=" * 60, ""]
    lines.extend(f"- {line}" for line in insights)
    lines.append("")
    lines.append("EXECUTIVE RECOMMENDATIONS")
    lines.append("=" * 60)
    lines.append("")
    lines.extend(f"- {line}" for line in recommendations)
    return "\n".join(lines)


def build_json_report(
    kpis: dict[str, float],
    adv_kpis: dict[str, Any],
    prev_kpis: dict[str, float] | None,
    insights: list[str],
    recommendations: list[str],
) -> str:
    """Build a structured JSON report combining KPIs, advanced KPIs,
    insights, and recommendations for the current filter selection."""
    report = {
        "kpis": kpis,
        "advanced_kpis": adv_kpis,
        "previous_period_kpis": prev_kpis,
        "business_insights": insights,
        "executive_recommendations": recommendations,
    }
    return json.dumps(report, indent=2, default=str)


def render_downloads_section(
    df: pd.DataFrame,
    kpis: dict[str, float],
    adv_kpis: dict[str, Any],
    prev_kpis: dict[str, float] | None,
    tables: dict[str, pd.DataFrame],
) -> None:
    """Render download buttons that export the CURRENTLY FILTERED data as
    CSV/TXT/JSON — Summary, Campaign, Country, Device, Business Insights,
    and a combined JSON report.

    Args:
        df: Filtered event-level DataFrame.
        kpis: Dictionary returned by ``compute_kpis`` for the same df.
        adv_kpis: Dictionary returned by ``compute_advanced_kpis``.
        prev_kpis: Previous-period KPI dictionary, or None.
        tables: Dictionary of executive summary tables from ``render_advanced_analytics``.
    """
    st.markdown('<div class="section-title">⬇️ Downloads</div>', unsafe_allow_html=True)
    st.caption("Exports reflect the active sidebar filters, not the full raw dataset.")

    insights = compute_dynamic_insights(df, kpis)
    recommendations = compute_executive_recommendations(df, kpis, adv_kpis, prev_kpis)

    csv_targets = [
        ("Summary Metrics", build_filtered_summary_metrics(df, kpis), "summary_metrics_filtered.csv"),
        ("Campaign Performance", build_filtered_campaign_performance(df), "campaign_performance_filtered.csv"),
        ("Device Summary", build_filtered_device_summary(df), "device_summary_filtered.csv"),
        ("Country Summary", tables.get("country_table", pd.DataFrame()), "country_summary_filtered.csv"),
    ]

    cols = st.columns(len(csv_targets))
    for col, (label, report_df, filename) in zip(cols, csv_targets):
        with col:
            if report_df is not None and not report_df.empty:
                csv_bytes = report_df.to_csv(index=False).encode("utf-8")
                st.download_button(
                    label=f"Download {label}",
                    data=csv_bytes,
                    file_name=filename,
                    mime="text/csv",
                    width="stretch",
                )
            else:
                st.button(f"{label} unavailable", disabled=True, width="stretch")
                st.caption("No data for the current filter selection.")

    c1, c2 = st.columns(2)
    with c1:
        st.download_button(
            label="Download Business Insights (TXT)",
            data=build_business_insights_txt(insights, recommendations).encode("utf-8"),
            file_name="business_insights_filtered.txt",
            mime="text/plain",
            width="stretch",
        )
    with c2:
        st.download_button(
            label="Download Full Report (JSON)",
            data=build_json_report(kpis, adv_kpis, prev_kpis, insights, recommendations).encode("utf-8"),
            file_name="analytics_report_filtered.json",
            mime="application/json",
            width="stretch",
        )


# --------------------------------------------------------------------------
# MAIN APP
# --------------------------------------------------------------------------
def main() -> None:
    """Entry point: assembles the full dashboard page."""
    st.markdown("# 📊 Product Analytics Dashboard")
    st.caption(
        "Executive overview of user engagement, revenue, and retention — "
        "powered by the analytics pipeline outputs."
    )

    raw_df = load_raw_data(DATASET_PATH)

    if raw_df.empty:
        st.error(
            f"Could not find or load the dataset at `{DATASET_PATH}`. "
            "Please make sure Dataset/user_events.csv exists before running the dashboard."
        )
        st.stop()

    # --- Sidebar filters --------------------------------------------------------
    filters = render_sidebar_filters(raw_df)
    filtered_df = apply_filters(raw_df, filters)

    if filtered_df.empty:
        st.warning("No data matches the current filter selection. Try widening your filters.")
        st.stop()

    # --- Period-over-period comparison -------------------------------------------
    prev_filters = build_previous_period_filters(filters)
    prev_filtered_df = apply_filters(raw_df, prev_filters) if prev_filters else pd.DataFrame()
    prev_kpis = compute_kpis(prev_filtered_df) if not prev_filtered_df.empty else None

    # --- KPIs ----------------------------------------------------------------------
    kpis = compute_kpis(filtered_df)
    adv_kpis = compute_advanced_kpis(filtered_df, kpis)

    # --- Executive Summary (above KPI cards) ----------------------------------------
    render_executive_summary(filtered_df, kpis, adv_kpis, prev_kpis)

    st.markdown("---")

    # --- KPI cards (with period-over-period growth) ---------------------------------
    render_kpi_section(kpis, prev_kpis)
    render_advanced_kpi_section(adv_kpis)

    st.markdown("---")

    # --- Charts --------------------------------------------------------------------
    render_chart_grid(filtered_df)

    st.markdown("---")

    # --- Executive Recommendations (action-oriented, dynamic) -----------------------
    render_executive_recommendations(filtered_df, kpis, adv_kpis, prev_kpis)

    st.markdown("---")

    # --- Business insights (recomputed live from the filtered data) -----------------
    render_insights_section(filtered_df, kpis)

    st.markdown("---")

    # --- Advanced analytics & executive tables --------------------------------------
    tables = render_advanced_analytics(filtered_df)

    st.markdown("---")

    # --- Downloads (export the filtered data, not the static pipeline reports) ------
    render_downloads_section(filtered_df, kpis, adv_kpis, prev_kpis, tables)

    st.markdown("---")
    st.caption(
        f"Showing {len(filtered_df):,} of {len(raw_df):,} events | "
        "Data source: Dataset/user_events.csv | Reports: Output/reports/"
    )

    # --- Extended platform: SQL Analytics Center, Cohort, RFM, Anomaly,
    #     Executive Report & Advanced Exports (new, additive) ------------------
    if _PLATFORM_EXTENSIONS_AVAILABLE:
        render_platform_extensions(filters)
    else:
        st.info(
            "Extended platform modules (SQL Analytics Center, Cohort Retention, "
            "RFM Segmentation, Anomaly Detection, Executive Reports) could not be "
            f"loaded: {_PLATFORM_EXTENSIONS_ERROR}"
        )


if __name__ == "__main__":
    main()