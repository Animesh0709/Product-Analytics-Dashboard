"""
charts.py
=========

Plotly chart builders for the new Analytics Center, Cohort, and RFM
sections (Parts 3-5). These are additive — the existing chart functions
inside ``streamlit_app.py`` (``render_chart_grid`` etc.) are untouched.

Every function returns a ready-to-render ``plotly.graph_objects.Figure``
so the calling Streamlit code only needs ``st.plotly_chart(fig, ...)``.
"""

from __future__ import annotations

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from styles import CHART_COLORWAY, PLOTLY_TEMPLATE, SEGMENT_COLORS, RETENTION_HEATMAP_SCALE


def _themed(fig: go.Figure, title: str) -> go.Figure:
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title=title,
        margin=dict(t=48, b=24, l=24, r=24),
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def growth_line_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str) -> go.Figure:
    """Line chart for a growth-rate series (e.g. monthly revenue growth %)."""
    if df.empty or y_col not in df:
        return _themed(go.Figure(), title)
    fig = px.line(df, x=x_col, y=y_col, markers=True, color_discrete_sequence=CHART_COLORWAY)
    fig.add_hline(y=0, line_dash="dot", line_color="#5f6b85")
    return _themed(fig, title)


def comparison_bar_chart(df: pd.DataFrame, x_col: str, y_col: str, title: str, orientation: str = "v") -> go.Figure:
    """Generic ranked bar chart for country/device/subscription/traffic-source
    comparisons and Top-N breakdowns."""
    if df.empty:
        return _themed(go.Figure(), title)
    if orientation == "h":
        fig = px.bar(df, x=y_col, y=x_col, orientation="h", color_discrete_sequence=CHART_COLORWAY)
        fig.update_layout(yaxis=dict(autorange="reversed"))
    else:
        fig = px.bar(df, x=x_col, y=y_col, color_discrete_sequence=CHART_COLORWAY)
    return _themed(fig, title)


def funnel_chart(funnel_df: pd.DataFrame) -> go.Figure:
    """Funnel visualization for the conversion funnel query."""
    if funnel_df.empty:
        return _themed(go.Figure(), "Conversion Funnel")
    fig = go.Figure(go.Funnel(
        y=funnel_df["stage"], x=funnel_df["users"],
        textinfo="value+percent initial",
        marker=dict(color=CHART_COLORWAY),
    ))
    return _themed(fig, "Conversion Funnel")


def cohort_heatmap(day_labels: list[str], cohort_labels: list[str], z: list[list[float]]) -> go.Figure:
    """Interactive retention cohort heatmap (Day 1/3/7/14/30 x cohort month)."""
    if not z:
        return _themed(go.Figure(), "Retention Cohort Heatmap")
    fig = go.Figure(data=go.Heatmap(
        z=z, x=day_labels, y=cohort_labels,
        colorscale=RETENTION_HEATMAP_SCALE,
        text=[[f"{v:.1f}%" for v in row] for row in z],
        texttemplate="%{text}",
        colorbar=dict(title="Retention %"),
    ))
    fig.update_yaxes(autorange="reversed")
    return _themed(fig, "Retention Cohort Heatmap")


def rfm_treemap(rfm_summary: pd.DataFrame) -> go.Figure:
    """Treemap of RFM segments sized by user count, colored by segment."""
    if rfm_summary.empty:
        return _themed(go.Figure(), "RFM Customer Segments")
    fig = px.treemap(
        rfm_summary, path=["rfm_segment"], values="users",
        color="rfm_segment", color_discrete_map=SEGMENT_COLORS,
        hover_data={"pct_of_total": True, "total_monetary": True},
    )
    return _themed(fig, "RFM Customer Segments")


def anomaly_scatter(df: pd.DataFrame, x_col: str, y_col: str, title: str) -> go.Figure:
    """Scatter/line chart with anomalous points highlighted (for the
    Anomaly Detection tab's supporting visuals)."""
    if df.empty:
        return _themed(go.Figure(), title)
    fig = px.line(df, x=x_col, y=y_col, markers=True, color_discrete_sequence=CHART_COLORWAY)
    return _themed(fig, title)
