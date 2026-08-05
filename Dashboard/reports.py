"""
reports.py
==========

Executive PDF Report Generator (Part 7).

Builds ``Output/reports/executive_report.pdf`` combining:
    - Executive summary text
    - Core KPI table
    - Revenue trend / top-country / device-mix charts (rendered with
      matplotlib to PNG, then embedded — no external browser/JS dependency)
    - Business insights & recommendations
    - Supporting data tables (top campaigns, top countries)

Built with ReportLab (pure-Python, no system dependencies), so it works
in any environment without a headless-Chrome/wkhtmltopdf install.
"""

from __future__ import annotations

import io
from datetime import datetime
from pathlib import Path
from typing import Any

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import pandas as pd
from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image, PageBreak,
)

from utils import get_logger

logger = get_logger(__name__)

BASE_DIR: Path = Path(__file__).resolve().parent.parent
OUTPUT_REPORTS_DIR: Path = BASE_DIR / "Output" / "reports"
DEFAULT_REPORT_PATH: Path = OUTPUT_REPORTS_DIR / "executive_report.pdf"

# Consistent muted palette for embedded matplotlib charts (print-friendly).
CHART_COLORS: list[str] = ["#3b82f6", "#22c55e", "#f97316", "#a855f7", "#ef4444", "#06b6d4"]


def _fig_to_image(fig: plt.Figure, width: float = 6.3 * inch) -> Image:
    """Render a matplotlib figure to an in-memory PNG and wrap it as a
    ReportLab ``Image`` flowable, preserving aspect ratio."""
    buf = io.BytesIO()
    fig.savefig(buf, format="png", dpi=160, bbox_inches="tight", facecolor="white")
    plt.close(fig)
    buf.seek(0)
    img = Image(buf)
    aspect = img.imageHeight / float(img.imageWidth)
    img.drawWidth = width
    img.drawHeight = width * aspect
    return img


def _chart_revenue_trend(revenue_trend_df: pd.DataFrame) -> Image | None:
    if revenue_trend_df is None or revenue_trend_df.empty:
        return None
    fig, ax = plt.subplots(figsize=(8, 3.2))
    ax.plot(pd.to_datetime(revenue_trend_df["date"]), revenue_trend_df["revenue"],
            color=CHART_COLORS[0], linewidth=1.6)
    ax.set_title("Daily Revenue Trend", fontsize=11, fontweight="bold")
    ax.set_ylabel("Revenue")
    ax.grid(alpha=0.25)
    fig.autofmt_xdate()
    return _fig_to_image(fig)


def _chart_top_countries(top_countries_df: pd.DataFrame) -> Image | None:
    if top_countries_df is None or top_countries_df.empty:
        return None
    df = top_countries_df.head(10).sort_values("revenue")
    fig, ax = plt.subplots(figsize=(8, 3.2))
    ax.barh(df["country"], df["revenue"], color=CHART_COLORS[1])
    ax.set_title("Top Countries by Revenue", fontsize=11, fontweight="bold")
    ax.set_xlabel("Revenue")
    fig.tight_layout()
    return _fig_to_image(fig)


def _chart_device_mix(device_df: pd.DataFrame) -> Image | None:
    if device_df is None or device_df.empty:
        return None
    fig, ax = plt.subplots(figsize=(4.2, 3.2))
    ax.pie(
        device_df["revenue"], labels=device_df.iloc[:, 0], autopct="%1.0f%%",
        colors=CHART_COLORS, textprops={"fontsize": 8},
    )
    ax.set_title("Revenue by Device", fontsize=11, fontweight="bold")
    return _fig_to_image(fig, width=3.4 * inch)


def _df_to_table(df: pd.DataFrame, max_rows: int = 12) -> Table:
    """Convert a small DataFrame into a styled ReportLab Table flowable."""
    display_df = df.head(max_rows).copy()
    for col in display_df.columns:
        if pd.api.types.is_float_dtype(display_df[col]):
            display_df[col] = display_df[col].round(2)
    data = [list(display_df.columns)] + display_df.astype(str).values.tolist()
    table = Table(data, hAlign="LEFT", repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#1f2937")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTSIZE", (0, 0), (-1, -1), 7.5),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
        ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
    ]))
    return table


def generate_executive_report(
    kpis: dict[str, Any],
    insights: list[str],
    recommendations: list[str],
    revenue_trend_df: pd.DataFrame | None = None,
    top_countries_df: pd.DataFrame | None = None,
    device_df: pd.DataFrame | None = None,
    campaign_table: pd.DataFrame | None = None,
    country_table: pd.DataFrame | None = None,
    output_path: Path = DEFAULT_REPORT_PATH,
) -> Path:
    """Generate the full executive PDF report.

    Args:
        kpis: Dict of core KPI name -> value (rendered as a 2-column table).
        insights: List of business insight strings.
        recommendations: List of executive recommendation strings.
        revenue_trend_df: Optional DataFrame with columns (date, revenue).
        top_countries_df: Optional DataFrame with columns (country, revenue, users).
        device_df: Optional DataFrame with a label column + 'revenue'.
        campaign_table: Optional campaign performance DataFrame.
        country_table: Optional country summary DataFrame.
        output_path: Destination PDF path.

    Returns:
        Path to the generated PDF file.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)
    styles = getSampleStyleSheet()
    title_style = ParagraphStyle("TitleX", parent=styles["Title"], textColor=colors.HexColor("#111827"))
    h2_style = ParagraphStyle("H2X", parent=styles["Heading2"], textColor=colors.HexColor("#1f2937"),
                               spaceBefore=14, spaceAfter=6)
    body_style = ParagraphStyle("BodyX", parent=styles["BodyText"], fontSize=9.5, leading=13)
    bullet_style = ParagraphStyle("BulletX", parent=body_style, leftIndent=12, spaceAfter=4)

    doc = SimpleDocTemplate(
        str(output_path), pagesize=letter,
        leftMargin=0.6 * inch, rightMargin=0.6 * inch,
        topMargin=0.6 * inch, bottomMargin=0.6 * inch,
        title="Product Analytics Platform - Executive Report",
    )

    story: list[Any] = []
    story.append(Paragraph("Product Analytics Platform", title_style))
    story.append(Paragraph("Executive Summary Report", styles["Heading3"]))
    story.append(Paragraph(
        f"Generated {datetime.now().strftime('%Y-%m-%d %H:%M')} &middot; "
        f"Reflects current dashboard filter selection", body_style,
    ))
    story.append(Spacer(1, 12))

    # --- KPI table ---------------------------------------------------------
    story.append(Paragraph("Key Performance Indicators", h2_style))
    kpi_rows = [["Metric", "Value"]] + [[str(k).replace("_", " ").title(), str(v)] for k, v in kpis.items()]
    kpi_table = Table(kpi_rows, hAlign="LEFT", colWidths=[2.6 * inch, 2.6 * inch])
    kpi_table.setStyle(TableStyle([
        ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#3b82f6")),
        ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
        ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
        ("FONTSIZE", (0, 0), (-1, -1), 9),
        ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#cccccc")),
        ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#f3f4f6")]),
    ]))
    story.append(kpi_table)

    # --- Charts --------------------------------------------------------------
    story.append(Paragraph("Trends & Breakdowns", h2_style))
    rev_img = _chart_revenue_trend(revenue_trend_df) if revenue_trend_df is not None else None
    if rev_img:
        story.append(rev_img)
        story.append(Spacer(1, 8))

    countries_img = _chart_top_countries(top_countries_df) if top_countries_df is not None else None
    device_img = _chart_device_mix(device_df) if device_df is not None else None
    if countries_img:
        story.append(countries_img)
    if device_img:
        story.append(Spacer(1, 8))
        story.append(device_img)

    # --- Insights --------------------------------------------------------------
    story.append(PageBreak())
    story.append(Paragraph("Business Insights", h2_style))
    for line in insights:
        story.append(Paragraph(f"&bull; {line}", bullet_style))

    story.append(Paragraph("Executive Recommendations", h2_style))
    for line in recommendations:
        story.append(Paragraph(f"&bull; {line}", bullet_style))

    # --- Tables --------------------------------------------------------------
    if campaign_table is not None and not campaign_table.empty:
        story.append(Paragraph("Top Campaigns", h2_style))
        story.append(_df_to_table(campaign_table))
        story.append(Spacer(1, 10))

    if country_table is not None and not country_table.empty:
        story.append(Paragraph("Top Countries", h2_style))
        story.append(_df_to_table(country_table))

    doc.build(story)
    logger.info("Executive report generated at %s", output_path)
    return output_path


if __name__ == "__main__":
    # Standalone smoke-test using live SQL data.
    import sql_engine as sq

    snap = sq.kpi_snapshot()
    kpi_dict = snap.iloc[0].to_dict() if not snap.empty else {}
    generate_executive_report(
        kpis=kpi_dict,
        insights=["Sample insight for standalone report generation."],
        recommendations=["Sample recommendation for standalone report generation."],
        revenue_trend_df=sq.revenue_trend(),
        top_countries_df=sq.top_countries(10),
        device_df=sq.revenue_by_device(),
        campaign_table=sq.top_campaigns(10),
        country_table=sq.top_countries(10),
    )
    print(f"Report written to {DEFAULT_REPORT_PATH}")
