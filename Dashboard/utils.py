"""
utils.py
========

Small shared utilities used across the new analytics modules: logging
setup, number formatting, and safe-division helpers. Kept dependency-free
(stdlib only) so it can be imported from anywhere without risk of circular
imports.
"""

from __future__ import annotations

import logging
from typing import Any


def get_logger(name: str) -> logging.Logger:
    """Return a module logger with a consistent format, configured once.

    Args:
        name: Usually ``__name__`` of the calling module.

    Returns:
        A configured ``logging.Logger`` instance.
    """
    logger = logging.getLogger(name)
    if not logging.getLogger().handlers and not logger.handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        )
    return logger


def safe_div(numerator: float, denominator: float, default: float = 0.0) -> float:
    """Divide two numbers, returning ``default`` instead of raising on /0.

    Args:
        numerator: Dividend.
        denominator: Divisor.
        default: Value to return if denominator is 0 or None.

    Returns:
        numerator / denominator, or default.
    """
    if not denominator:
        return default
    return numerator / denominator


def fmt_currency(value: float, symbol: str = "$") -> str:
    """Format a number as a compact currency string, e.g. $12.3K, $4.1M."""
    if value is None:
        return f"{symbol}0"
    abs_value = abs(value)
    sign = "-" if value < 0 else ""
    if abs_value >= 1_000_000:
        return f"{sign}{symbol}{abs_value / 1_000_000:.1f}M"
    if abs_value >= 1_000:
        return f"{sign}{symbol}{abs_value / 1_000:.1f}K"
    return f"{sign}{symbol}{abs_value:,.2f}"


def fmt_number(value: float) -> str:
    """Format a number as a compact string, e.g. 12.3K, 4.1M."""
    if value is None:
        return "0"
    abs_value = abs(value)
    sign = "-" if value < 0 else ""
    if abs_value >= 1_000_000:
        return f"{sign}{abs_value / 1_000_000:.1f}M"
    if abs_value >= 1_000:
        return f"{sign}{abs_value / 1_000:.1f}K"
    return f"{sign}{abs_value:,.0f}"


def fmt_pct(value: float, decimals: int = 1) -> str:
    """Format a number as a percentage string, e.g. 12.3%."""
    if value is None:
        return "0%"
    return f"{value:.{decimals}f}%"


def first_present(d: dict[str, Any], keys: list[str], default: Any = None) -> Any:
    """Return the first non-missing value among ``keys`` found in ``d``."""
    for key in keys:
        if key in d and d[key] is not None:
            return d[key]
    return default
