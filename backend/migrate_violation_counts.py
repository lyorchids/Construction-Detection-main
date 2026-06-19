"""Migrate violation data to normalized violation_counts table.

Run:  python backend/migrate_violation_counts.py

Migration sources (in order of preference):
  1. Old v_* columns on detection_records (if they exist)
  2. violations table (aggregated counts)

This script does NOT drop old columns (fallback safety).
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.database import engine, Base
from app.models.violation_count import ViolationCount
from sqlalchemy import text

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

COLUMN_TO_TYPE: dict[str, str] = {
    'v_no_hardhat': 'warning_no_hardhat',
    'v_no_mask': 'warning_no_mask',
    'v_no_safety_vest': 'warning_no_safety_vest',
    'v_in_controlled_area': 'warning_people_in_controlled_area',
    'v_in_pole_area': 'warning_people_in_controlled_area',
    'v_fire': 'warning_fire',
    'v_smoke': 'warning_smoke',
}


def _has_column(conn, table: str, column: str) -> bool:
    cols = conn.execute(
        text(f"PRAGMA table_info({table})")
    ).all()
    return any(col[1] == column for col in cols)


def migrate() -> None:
    logger.info("Step 1: ensure violation_counts table exists...")
    Base.metadata.create_all(engine, tables=[ViolationCount.__table__])

    with engine.connect() as conn:
        existing = conn.execute(
            text("SELECT COUNT(*) FROM violation_counts")
        ).scalar()
        if existing and existing > 0:
            logger.info(f"violation_counts already has {existing} rows, skipping")
            return

        logger.info("Step 2: checking available data sources...")

        # Source A: old v_* columns
        has_old_cols = _has_column(conn, 'detection_records', 'v_no_hardhat')

        if has_old_cols:
            logger.info("Source A: migrating from detection_records v_* columns...")
            inserts = []
            for db_column, vtype in COLUMN_TO_TYPE.items():
                inserts.append(
                    f"SELECT id AS record_id, '{vtype}' AS violation_type, "
                    f"\"{db_column}\" AS cnt "
                    f"FROM detection_records WHERE \"{db_column}\" > 0"
                )
            union_sql = " UNION ALL ".join(inserts)
            sql = (
                f"INSERT INTO violation_counts (record_id, violation_type, count) "
                f"SELECT record_id, violation_type, SUM(cnt) FROM ({union_sql}) "
                f"AS _sub GROUP BY record_id, violation_type"
            )
            result = conn.execute(text(sql))
            logger.info(f"Inserted {result.rowcount} rows from v_* columns")
            return

        # Source B: violations table
        has_violations = _has_column(conn, 'violations', 'violation_type')
        if has_violations:
            v_count = conn.execute(text("SELECT COUNT(*) FROM violations")).scalar()
            if v_count and v_count > 0:
                logger.info(f"Source B: migrating {v_count} rows from violations table...")
                sql = (
                    "INSERT INTO violation_counts (record_id, violation_type, count) "
                    "SELECT record_id, violation_type, COUNT(*) "
                    "FROM violations GROUP BY record_id, violation_type"
                )
                result = conn.execute(text(sql))
                logger.info(f"Inserted {result.rowcount} rows from violations table")
                return

        logger.info("No legacy data found — nothing to migrate.")
        logger.info("New detections will populate violation_counts automatically.")


if __name__ == '__main__':
    migrate()
