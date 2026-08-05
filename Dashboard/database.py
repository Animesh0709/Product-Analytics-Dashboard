"""
database.py
============

SQLite integration layer for the Product Analytics Platform.

Responsibilities
-----------------
- Own the single source of truth connection to ``Database/analytics.db``.
- Auto-import ``Dataset/user_events.csv`` into SQLite the first time the
  database does not exist (or is empty), so every other module can query
  SQL instead of repeatedly re-reading the raw CSV.
- Provide a small, well-typed connection/query helper API used by
  ``sql_engine.py`` and the rest of the ``Dashboard`` package.

This module intentionally does NOT touch the existing CSV-based Streamlit
app (``streamlit_app.py``). It is purely additive infrastructure that other
new modules build on top of.

Usage:
    from database import get_connection, ensure_database, run_query

    ensure_database()
    df = run_query("SELECT COUNT(*) AS n FROM user_events")
"""

from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
    )

# --------------------------------------------------------------------------
# PATHS
# --------------------------------------------------------------------------
BASE_DIR: Path = Path(__file__).resolve().parent.parent
DATASET_PATH: Path = BASE_DIR / "Dataset" / "user_events.csv"
DATABASE_DIR: Path = BASE_DIR / "Database"
DATABASE_PATH: Path = DATABASE_DIR / "analytics.db"

TABLE_NAME: str = "user_events"

# Columns expected in the raw dataset, and their target SQLite affinity.
NUMERIC_COLUMNS: list[str] = [
    "session_duration",
    "revenue",
    "level_completed",
    "purchase_amount",
    "retention_day",
]
DATE_COLUMNS: list[str] = ["event_date", "event_timestamp"]


def _connect(db_path: Path = DATABASE_PATH) -> sqlite3.Connection:
    """Open a raw SQLite connection with sane pragmas for analytics workloads.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        A live ``sqlite3.Connection``. Caller is responsible for closing it,
        or better, use :func:`get_connection` as a context manager.
    """
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


class get_connection:
    """Context-manager wrapper around a SQLite connection.

    Example:
        with get_connection() as conn:
            df = pd.read_sql_query("SELECT 1", conn)
    """

    def __init__(self, db_path: Path = DATABASE_PATH) -> None:
        self.db_path = db_path
        self._conn: sqlite3.Connection | None = None

    def __enter__(self) -> sqlite3.Connection:
        self._conn = _connect(self.db_path)
        return self._conn

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        if self._conn is not None:
            if exc_type is None:
                self._conn.commit()
            self._conn.close()


def database_exists_and_populated(db_path: Path = DATABASE_PATH) -> bool:
    """Check whether the SQLite database already exists and has data.

    Args:
        db_path: Path to the SQLite database file.

    Returns:
        True if the DB file exists and ``user_events`` has at least one row.
    """
    if not db_path.exists():
        return False
    try:
        with get_connection(db_path) as conn:
            cur = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                (TABLE_NAME,),
            )
            if cur.fetchone() is None:
                return False
            count = conn.execute(f"SELECT COUNT(*) FROM {TABLE_NAME}").fetchone()[0]
            return count > 0
    except sqlite3.DatabaseError as exc:
        logger.warning("Existing database file looked corrupt (%s); will rebuild.", exc)
        return False


def import_csv_to_sqlite(
    csv_path: Path = DATASET_PATH,
    db_path: Path = DATABASE_PATH,
    chunksize: int = 50_000,
) -> int:
    """Import ``user_events.csv`` into SQLite, creating indexes for the
    columns most commonly used for filtering and aggregation.

    Args:
        csv_path: Path to the source CSV file.
        db_path: Path to the destination SQLite database file.
        chunksize: Number of rows per batch insert (keeps memory bounded on
            large CSVs).

    Returns:
        Total number of rows imported.

    Raises:
        FileNotFoundError: If the source CSV does not exist.
    """
    if not csv_path.exists():
        raise FileNotFoundError(f"Cannot import: dataset not found at {csv_path}")

    DATABASE_DIR.mkdir(parents=True, exist_ok=True)
    logger.info("Building SQLite database at %s from %s", db_path, csv_path)

    total_rows = 0
    with get_connection(db_path) as conn:
        conn.execute(f"DROP TABLE IF EXISTS {TABLE_NAME};")
        conn.commit()

        first_chunk = True
        for chunk in pd.read_csv(csv_path, chunksize=chunksize):
            for col in NUMERIC_COLUMNS:
                if col in chunk.columns:
                    chunk[col] = pd.to_numeric(chunk[col], errors="coerce").fillna(0)
            for col in ("city", "app_version", "campaign"):
                if col in chunk.columns:
                    chunk[col] = chunk[col].fillna("Unknown" if col != "campaign" else "None")

            chunk.to_sql(
                TABLE_NAME,
                conn,
                if_exists="replace" if first_chunk else "append",
                index=False,
            )
            first_chunk = False
            total_rows += len(chunk)

        # Indexes for the dimensions used across the SQL analytics layer.
        index_cols = [
            "user_id", "event_date", "event_name", "country", "device_type",
            "campaign", "traffic_source", "subscription", "user_type",
        ]
        for col in index_cols:
            conn.execute(
                f"CREATE INDEX IF NOT EXISTS idx_{TABLE_NAME}_{col} ON {TABLE_NAME}({col});"
            )
        conn.commit()

    logger.info("Imported %s rows into %s.%s", total_rows, db_path.name, TABLE_NAME)
    return total_rows


def ensure_database(force_rebuild: bool = False) -> Path:
    """Make sure ``Database/analytics.db`` exists and is populated, building
    it from the CSV dataset automatically if needed.

    Args:
        force_rebuild: If True, rebuild the database from CSV even if it
            already exists (useful after the raw dataset changes).

    Returns:
        Path to the ready-to-query SQLite database.
    """
    if force_rebuild or not database_exists_and_populated():
        import_csv_to_sqlite()
    else:
        logger.info("Using existing SQLite database at %s", DATABASE_PATH)
    return DATABASE_PATH


def run_query(sql: str, params: tuple | dict | None = None) -> pd.DataFrame:
    """Run a read query against the analytics database and return a DataFrame.

    Args:
        sql: A SQL SELECT statement (or any statement returning rows).
        params: Optional bind parameters (tuple for ``?`` placeholders or
            dict for ``:name`` placeholders).

    Returns:
        Query results as a pandas DataFrame. Empty DataFrame on error.
    """
    ensure_database()
    try:
        with get_connection() as conn:
            return pd.read_sql_query(sql, conn, params=params)
    except Exception:
        logger.exception("Query failed:\n%s", sql)
        return pd.DataFrame()


def table_row_count() -> int:
    """Return the total number of rows currently in ``user_events``."""
    df = run_query(f"SELECT COUNT(*) AS n FROM {TABLE_NAME}")
    return int(df["n"].iloc[0]) if not df.empty else 0


if __name__ == "__main__":
    # Allows `python Dashboard/database.py` to (re)build the DB standalone.
    ensure_database(force_rebuild=True)
    print(f"analytics.db ready with {table_row_count():,} rows at {DATABASE_PATH}")
