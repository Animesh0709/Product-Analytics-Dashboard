"""
analytics.py
============

Orchestrates the new portfolio-grade sections added on top of the existing
dashboard: the SQL-powered Analytics Center (Part 3), Cohort Retention
(Part 4), RFM Segmentation (Part 5), Anomaly Detection (Part 6), the
Executive PDF Report (Part 7), and Advanced Exports (Part 8).

``streamlit_app.py`` imports and calls ``render_platform_extensions(ui_filters)``
once, near the end of ``main()``, passing the SAME filter dict already
produced by its own sidebar. Nothing in the existing file is modified;
this module is purely additive.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

import anomaly
import charts
import cohort
import exports
import kpis
import reports
import rfm
import sql_engine as sq
from filters import to_sql_filters
from utils import get_logger

logger = get_logger(__name__)


def _section_title(text: str) -> None:
    st.markdown(f'<div class="section-title">{text}</div>', unsafe_allow_html=True)


# --------------------------------------------------------------------------
# PART 3 — ANALYTICS CENTER
# --------------------------------------------------------------------------
def render_analytics_center(sql_filters: dict[str, Any]) -> dict[str, pd.DataFrame]:
    """Render the SQL-powered Analytics Center tab.

    Returns:
        Dict of the key tables computed here, reused by downstream sections
        (executive report, exports) so they aren't recomputed twice.
    """
    st.caption("Every figure below is computed live in SQLite via `sql_engine.py` — 30+ named queries.")

    snapshot_df = sq.kpi_snapshot(sql_filters)
    snapshot_row = snapshot_df.iloc[0].to_dict() if not snapshot_df.empty else {}
    kpis.render_kpi_row(kpis.build_sql_kpi_cards(snapshot_row))

    st.markdown("#### Growth")
    g1, g2 = st.columns(2)
    monthly_growth_df = sq.monthly_growth(sql_filters)
    with g1:
        st.plotly_chart(
            charts.growth_line_chart(monthly_growth_df, "year_month", "user_growth_pct", "Monthly User Growth %"),
            width="stretch",
        )
    with g2:
        st.plotly_chart(
            charts.growth_line_chart(monthly_growth_df, "year_month", "revenue_growth_pct", "Monthly Revenue Growth %"),
            width="stretch",
        )

    weekly_growth_df = sq.weekly_growth(sql_filters)
    st.plotly_chart(
        charts.growth_line_chart(weekly_growth_df, "year_week", "revenue_growth_pct", "Weekly Revenue Growth %"),
        width="stretch",
    )

    campaign_growth_df = sq.campaign_growth(sql_filters)
    top5_campaigns = (
        campaign_growth_df.groupby("campaign")["revenue"].sum().nlargest(5).index.tolist()
        if not campaign_growth_df.empty else []
    )
    if top5_campaigns:
        st.plotly_chart(
            charts.growth_line_chart(
                campaign_growth_df[campaign_growth_df["campaign"].isin(top5_campaigns)],
                "year_month", "revenue_growth_pct", "Campaign Revenue Growth % (Top 5 Campaigns)",
            ),
            width="stretch",
        )

    st.markdown("#### Comparisons")
    c1, c2 = st.columns(2)
    country_df = sq.revenue_by_country(sql_filters)
    device_df = sq.revenue_by_device(sql_filters)
    with c1:
        st.plotly_chart(
            charts.comparison_bar_chart(country_df.head(10), "country", "revenue", "Country Comparison (Revenue)", "h"),
            width="stretch",
        )
    with c2:
        st.plotly_chart(
            charts.comparison_bar_chart(device_df, "device_type", "revenue", "Device Comparison (Revenue)"),
            width="stretch",
        )

    c3, c4 = st.columns(2)
    subscription_df = sq.subscription_analysis(sql_filters)
    traffic_df = sq.traffic_source_analysis(sql_filters)
    with c3:
        st.plotly_chart(
            charts.comparison_bar_chart(subscription_df, "subscription", "revenue", "Subscription Comparison (Revenue)"),
            width="stretch",
        )
    with c4:
        st.plotly_chart(
            charts.comparison_bar_chart(traffic_df, "traffic_source", "revenue", "Traffic Source Comparison (Revenue)", "h"),
            width="stretch",
        )

    st.markdown("#### Top 10 Breakdowns")
    top_campaigns_df = sq.top_campaigns(10, sql_filters)
    top_countries_df = sq.top_countries(10, sql_filters)
    top_cities_df = sq.top_cities(10, sql_filters)

    t1, t2, t3 = st.tabs(["Top 10 Campaigns", "Top 10 Countries", "Top Cities"])
    with t1:
        st.plotly_chart(
            charts.comparison_bar_chart(top_campaigns_df, "campaign", "revenue", "Top 10 Campaigns by Revenue", "h"),
            width="stretch",
        )
        st.dataframe(top_campaigns_df, width="stretch", hide_index=True)
    with t2:
        st.plotly_chart(
            charts.comparison_bar_chart(top_countries_df, "country", "revenue", "Top 10 Countries by Revenue", "h"),
            width="stretch",
        )
        st.dataframe(top_countries_df, width="stretch", hide_index=True)
    with t3:
        st.dataframe(top_cities_df, width="stretch", hide_index=True)

    st.markdown("#### Conversion Funnel")
    st.plotly_chart(charts.funnel_chart(sq.funnel(filters=sql_filters)), width="stretch")

    return {
        "snapshot": snapshot_row, "country_df": country_df, "device_df": device_df,
        "top_campaigns_df": top_campaigns_df, "top_countries_df": top_countries_df,
        "revenue_trend_df": sq.revenue_trend(sql_filters),
    }


# --------------------------------------------------------------------------
# PART 4 — COHORT RETENTION
# --------------------------------------------------------------------------
def render_cohort_section(sql_filters: dict[str, Any]) -> pd.DataFrame:
    """Render the cohort retention heatmap tab. Returns the cohort table for
    reuse by the anomaly-detection section."""
    st.caption("Monthly acquisition cohorts, retention measured at exact Day 1 / 3 / 7 / 14 / 30 milestones.")
    cohort_table = cohort.build_cohort_table(sql_filters)

    if cohort_table.empty:
        st.info("Not enough data to build a cohort retention table for the current filters.")
        return cohort_table

    day_labels, cohort_labels, z = cohort.cohort_heatmap_matrix(cohort_table)
    st.plotly_chart(charts.cohort_heatmap(day_labels, cohort_labels, z), width="stretch")

    for line in cohort.cohort_summary_insights(cohort_table):
        st.markdown(f'<div class="insight-card">{line}</div>', unsafe_allow_html=True)

    with st.expander("View cohort data table"):
        st.dataframe(cohort_table, width="stretch", hide_index=True)

    return cohort_table


# --------------------------------------------------------------------------
# PART 5 — RFM SEGMENTATION
# --------------------------------------------------------------------------
def render_rfm_section(sql_filters: dict[str, Any]) -> pd.DataFrame:
    """Render the RFM customer segmentation tab. Returns the summary table."""
    st.caption("Recency / Frequency / Monetary quintile scoring, mapped to six lifecycle segments.")
    rfm_table = rfm.build_rfm_table(sql_filters)

    if rfm_table.empty:
        st.info("Not enough data to compute RFM segments for the current filters.")
        return pd.DataFrame()

    summary = rfm.rfm_segment_summary(rfm_table)

    st.plotly_chart(charts.rfm_treemap(summary), width="stretch")

    st.markdown("#### Segment Summary")
    st.dataframe(
        summary.rename(columns={
            "rfm_segment": "Segment", "users": "Users", "pct_of_total": "% of Users",
            "avg_recency_days": "Avg Recency (days)", "avg_frequency": "Avg Frequency",
            "total_monetary": "Total Revenue", "recommendation": "Recommendation",
        }),
        width="stretch", hide_index=True,
    )

    st.markdown("#### Business Recommendations")
    for _, row in summary.iterrows():
        st.markdown(
            f'<div class="reco-card"><b>{row["rfm_segment"]}</b> '
            f'({row["users"]:,} users, {row["pct_of_total"]}%) — {row["recommendation"]}</div>',
            unsafe_allow_html=True,
        )

    return summary


# --------------------------------------------------------------------------
# PART 6 — ANOMALY DETECTION
# --------------------------------------------------------------------------
def render_anomaly_section(sql_filters: dict[str, Any], cohort_table: pd.DataFrame | None) -> None:
    """Render anomaly warning cards for revenue, traffic, campaigns, retention."""
    st.caption("Statistical outlier detection (rolling z-score, |z| >= 2.0) across core metrics.")
    cards = anomaly.build_anomaly_warning_cards(sql_filters, cohort_table)

    severity_icon = {"high": "🔴", "medium": "🟠", "info": "🔵"}
    for card in cards[:20]:
        icon = severity_icon.get(card["severity"], "🔵")
        border_color = {"high": "#ef4444", "medium": "#eab308", "info": "#3b82f6"}.get(card["severity"], "#3b82f6")
        st.markdown(
            f'<div class="insight-card" style="border-left-color:{border_color};">'
            f'{icon} <b>{card["title"]}</b><br>{card["message"]}</div>',
            unsafe_allow_html=True,
        )


# --------------------------------------------------------------------------
# PART 7 & 8 — EXECUTIVE REPORT + ADVANCED EXPORTS
# --------------------------------------------------------------------------
def render_reporting_section(
    sql_filters: dict[str, Any],
    center_tables: dict[str, Any],
    rfm_summary: pd.DataFrame,
    cohort_table: pd.DataFrame,
) -> None:
    """Render the Executive PDF Report generator + multi-format export buttons."""
    st.caption("Generate a polished PDF for stakeholders, or export the current view in CSV / Excel / JSON / PDF.")

    insights = [
        f"Total revenue for the current selection is {center_tables['snapshot'].get('total_revenue', 0):,.2f} "
        f"across {center_tables['snapshot'].get('total_users', 0):,} users.",
        f"ARPU stands at {center_tables['snapshot'].get('arpu', 0):,.2f} with a conversion rate of "
        f"{center_tables['snapshot'].get('conversion_rate_pct', 0):.2f}%.",
    ]
    if not center_tables["country_df"].empty:
        top_country = center_tables["country_df"].iloc[0]
        insights.append(f"{top_country['country']} is the top-revenue market at {top_country['revenue']:,.2f}.")
    if not rfm_summary.empty:
        champions = rfm_summary[rfm_summary["rfm_segment"] == "Champions"]
        if not champions.empty:
            insights.append(f"Champions make up {champions.iloc[0]['pct_of_total']}% of users but drive outsized revenue.")

    recommendations = [
        "Prioritize retention campaigns for the At Risk and Need Attention RFM segments.",
        "Reallocate marketing spend toward the highest revenue-per-user campaigns.",
        "Investigate any flagged anomalies before the next reporting cycle.",
    ]

    col_pdf, col_dl = st.columns([1, 1])
    with col_pdf:
        if st.button("📄 Generate Executive PDF Report", width="stretch"):
            with st.spinner("Rendering PDF..."):
                path = reports.generate_executive_report(
                    kpis=center_tables["snapshot"],
                    insights=insights,
                    recommendations=recommendations,
                    revenue_trend_df=center_tables["revenue_trend_df"],
                    top_countries_df=center_tables["top_countries_df"],
                    device_df=center_tables["device_df"],
                    campaign_table=center_tables["top_campaigns_df"],
                    country_table=center_tables["top_countries_df"],
                )
            st.success(f"Report generated: {path.name}")
            st.session_state["_executive_report_path"] = str(path)

    report_path = st.session_state.get("_executive_report_path")
    if report_path:
        try:
            with open(report_path, "rb") as f:
                st.download_button(
                    "⬇️ Download Executive Report (PDF)", data=f.read(),
                    file_name="executive_report.pdf", mime="application/pdf", width="stretch",
                )
        except FileNotFoundError:
            st.warning("Report file not found on disk yet — generate it above.")

    st.markdown("#### Multi-format Exports")
    sheets = {
        "KPI Snapshot": pd.DataFrame([center_tables["snapshot"]]),
        "Revenue by Country": center_tables["country_df"],
        "Revenue by Device": center_tables["device_df"],
        "Top Campaigns": center_tables["top_campaigns_df"],
        "RFM Summary": rfm_summary,
        "Cohort Retention": cohort_table,
    }

    e1, e2, e3 = st.columns(3)
    with e1:
        st.download_button(
            "Download CSV (KPI Snapshot)",
            data=exports.export_csv_bytes(pd.DataFrame([center_tables["snapshot"]])),
            file_name="kpi_snapshot.csv", mime="text/csv", width="stretch",
        )
    with e2:
        st.download_button(
            "Download Excel Workbook",
            data=exports.export_excel_bytes(sheets),
            file_name="analytics_platform_export.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            width="stretch",
        )
    with e3:
        st.download_button(
            "Download JSON (Full Bundle)",
            data=exports.export_json_bytes({
                "kpis": center_tables["snapshot"],
                "insights": insights,
                "recommendations": recommendations,
                "tables": exports.dataframe_dict_for_json(sheets),
            }),
            file_name="analytics_platform_export.json", mime="application/json", width="stretch",
        )


# --------------------------------------------------------------------------
# ENTRY POINT CALLED FROM streamlit_app.py
# --------------------------------------------------------------------------
def render_platform_extensions(ui_filters: dict[str, Any]) -> None:
    """Render the full set of new platform sections inside their own tabs.

    Args:
        ui_filters: The filter dict returned by the existing
            ``render_sidebar_filters`` in ``streamlit_app.py``.
    """
    st.markdown("---")
    st.markdown("# 🧠 Product Analytics Platform — Extended Capabilities")
    st.caption(
        "SQLite-backed SQL analytics, cohort retention, RFM segmentation, anomaly "
        "detection, and executive reporting — layered on top of the dashboard above."
    )

    sql_filters = to_sql_filters(ui_filters)

    tab_center, tab_cohort, tab_rfm, tab_anomaly, tab_reports = st.tabs([
        "📊 Analytics Center", "🧬 Cohort Retention", "🎯 RFM Segmentation",
        "🚨 Anomaly Detection", "📄 Reports & Exports",
    ])

    with tab_center:
        center_tables = render_analytics_center(sql_filters)

    with tab_cohort:
        cohort_table = render_cohort_section(sql_filters)

    with tab_rfm:
        rfm_summary = render_rfm_section(sql_filters)

    with tab_anomaly:
        render_anomaly_section(sql_filters, cohort_table)

    with tab_reports:
        render_reporting_section(sql_filters, center_tables, rfm_summary, cohort_table)
