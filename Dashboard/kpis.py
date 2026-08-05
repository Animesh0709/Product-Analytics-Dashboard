"""
kpis.py
=======

KPI card rendering helpers for the new SQL-driven Analytics Center.

Reuses the ``.kpi-card-sm`` CSS class already injected by
``streamlit_app.py``'s dark theme (so visuals stay consistent), without
modifying that file. If this module is ever used outside that app context
(no CSS injected), the cards still degrade gracefully via ``st.metric``.
"""

from __future__ import annotations

from typing import Any

import streamlit as st

from utils import fmt_currency, fmt_number, fmt_pct


def render_kpi_row(cards: list[dict[str, Any]], columns_per_row: int = 4) -> None:
    """Render a row of small KPI cards.

    Args:
        cards: List of {"label": str, "value": str, "sub": str (optional)}.
        columns_per_row: Number of cards per row.
    """
    for start in range(0, len(cards), columns_per_row):
        row = cards[start:start + columns_per_row]
        cols = st.columns(len(row))
        for col, card in zip(cols, row):
            with col:
                sub_html = f'<div class="kpi-sub">{card["sub"]}</div>' if card.get("sub") else ""
                st.markdown(
                    f"""
                    <div class="kpi-card-sm">
                        <div class="kpi-label">{card['label']}</div>
                        <div class="kpi-value">{card['value']}</div>
                        {sub_html}
                    </div>
                    """,
                    unsafe_allow_html=True,
                )


def build_sql_kpi_cards(snapshot_row: dict[str, Any]) -> list[dict[str, Any]]:
    """Build KPI card dicts from a ``sql_engine.kpi_snapshot`` row.

    Args:
        snapshot_row: Single-row dict from ``kpi_snapshot().iloc[0].to_dict()``.

    Returns:
        List of card dicts ready for ``render_kpi_row``.
    """
    if not snapshot_row:
        return []
    return [
        {"label": "Total Users", "value": fmt_number(snapshot_row.get("total_users", 0))},
        {"label": "Total Revenue", "value": fmt_currency(snapshot_row.get("total_revenue", 0))},
        {"label": "ARPU", "value": fmt_currency(snapshot_row.get("arpu", 0))},
        {"label": "ARPPU", "value": fmt_currency(snapshot_row.get("arppu", 0))},
        {"label": "Conversion Rate", "value": fmt_pct(snapshot_row.get("conversion_rate_pct", 0))},
        {"label": "Avg Session (s)", "value": fmt_number(snapshot_row.get("avg_session_duration", 0))},
        {"label": "Total Sessions", "value": fmt_number(snapshot_row.get("total_sessions", 0))},
        {"label": "Total Events", "value": fmt_number(snapshot_row.get("total_events", 0))},
    ]
