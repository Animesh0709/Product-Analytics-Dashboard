"""
styles.py
=========

Shared visual theme constants for the Product Analytics Platform.

Centralizes the colors used by the new Analytics Center / Cohort / RFM /
Anomaly modules so they stay visually consistent with the existing dark
theme already defined inline in ``streamlit_app.py`` (which is left
untouched). Import from here in any NEW module instead of redefining
colors ad hoc.
"""

from __future__ import annotations

PLOTLY_TEMPLATE: str = "plotly_dark"

CHART_COLORWAY: list[str] = [
    "#3b82f6", "#22c55e", "#f97316", "#a855f7",
    "#ef4444", "#06b6d4", "#eab308", "#ec4899",
]

SEGMENT_COLORS: dict[str, str] = {
    "Champions": "#22c55e",
    "Loyal Customers": "#3b82f6",
    "Potential Loyalists": "#06b6d4",
    "Need Attention": "#eab308",
    "At Risk": "#f97316",
    "Lost Customers": "#ef4444",
}

SEVERITY_COLORS: dict[str, str] = {
    "high": "#ef4444",
    "medium": "#eab308",
    "info": "#3b82f6",
}

RETENTION_HEATMAP_SCALE: list[list[float | str]] = [
    [0.0, "#0e1117"], [0.25, "#1e3a5f"], [0.5, "#1d6fa5"],
    [0.75, "#22c55e"], [1.0, "#bef264"],
]

BRAND_PRIMARY: str = "#3b82f6"
BRAND_ACCENT: str = "#a855f7"
CARD_BG: str = "#161b26"
CARD_BORDER: str = "#262c3d"
