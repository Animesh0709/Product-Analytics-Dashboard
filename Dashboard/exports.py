"""
exports.py
==========

Advanced Exports (Part 8): CSV, Excel (multi-sheet), JSON, and PDF.

This module is additive — the existing CSV download buttons in
``streamlit_app.py`` are untouched. These helpers back the new "Advanced
Exports" section, returning in-memory bytes so Streamlit's
``st.download_button`` never needs to write to disk.
"""

from __future__ import annotations

import io
import json
from typing import Any

import pandas as pd

from utils import get_logger

logger = get_logger(__name__)


def export_csv_bytes(df: pd.DataFrame) -> bytes:
    """Export a single DataFrame as CSV bytes."""
    return df.to_csv(index=False).encode("utf-8")


def export_excel_bytes(sheets: dict[str, pd.DataFrame]) -> bytes:
    """Export multiple DataFrames as sheets of a single .xlsx workbook.

    Args:
        sheets: Mapping of sheet_name -> DataFrame. Sheet names are
            truncated to Excel's 31-character limit.

    Returns:
        In-memory .xlsx file bytes.
    """
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="xlsxwriter") as writer:
        workbook = writer.book
        header_fmt = workbook.add_format({
            "bold": True, "bg_color": "#1f2937", "font_color": "white", "border": 1,
        })
        for sheet_name, df in sheets.items():
            safe_name = sheet_name[:31] if sheet_name else "Sheet1"
            if df is None or df.empty:
                df = pd.DataFrame({"info": ["No data for current selection"]})
            df.to_excel(writer, sheet_name=safe_name, index=False)
            worksheet = writer.sheets[safe_name]
            for col_idx, col_name in enumerate(df.columns):
                worksheet.write(0, col_idx, col_name, header_fmt)
                width = min(max(12, int(df[col_name].astype(str).str.len().max() or 12) + 2), 40)
                worksheet.set_column(col_idx, col_idx, width)
    buffer.seek(0)
    return buffer.getvalue()


def export_json_bytes(payload: dict[str, Any]) -> bytes:
    """Export an arbitrary JSON-serializable dict as pretty-printed bytes."""
    return json.dumps(payload, indent=2, default=str).encode("utf-8")


def dataframe_dict_for_json(sheets: dict[str, pd.DataFrame]) -> dict[str, list[dict]]:
    """Convert a dict of DataFrames into a JSON-friendly dict of record lists."""
    return {
        name: (df.to_dict(orient="records") if df is not None and not df.empty else [])
        for name, df in sheets.items()
    }
