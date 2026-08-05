"""
filters.py
==========

Adapter between the existing Streamlit sidebar filter state (as built by
``render_sidebar_filters`` in ``streamlit_app.py``) and the SQL engine's
filter-dict shape (``sql_engine.FilterDict``). Kept as its own module so
every new analytics module (cohort, rfm, anomaly, sql_engine consumers)
shares one exact translation, instead of re-deriving it inline.
"""

from __future__ import annotations

from typing import Any


def to_sql_filters(ui_filters: dict[str, Any]) -> dict[str, Any]:
    """Translate the dashboard sidebar filter dict into SQL engine filters.

    Args:
        ui_filters: Dict as returned by ``render_sidebar_filters``, e.g.
            {"date_range": (start, end), "countries": [...], "devices": [...],
             "campaigns": [...], "user_types": [...], "subscriptions": [...],
             "traffic_sources": [...]}.

    Returns:
        Dict shaped for ``sql_engine`` functions:
            {"start_date": "YYYY-MM-DD", "end_date": "YYYY-MM-DD",
             "countries": [...], "devices": [...], ...}
    """
    sql_filters: dict[str, Any] = {}

    date_range = ui_filters.get("date_range")
    if isinstance(date_range, (tuple, list)) and len(date_range) == 2:
        start, end = date_range
        if start:
            sql_filters["start_date"] = str(start)
        if end:
            sql_filters["end_date"] = str(end)

    passthrough_keys = [
        "countries", "devices", "campaigns", "user_types",
        "subscriptions", "traffic_sources",
    ]
    for key in passthrough_keys:
        values = ui_filters.get(key)
        if values:
            sql_filters[key] = list(values)

    return sql_filters
