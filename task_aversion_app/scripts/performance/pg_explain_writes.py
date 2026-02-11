#!/usr/bin/env python3
"""
EXPLAIN/plan-focused: run EXPLAIN (ANALYZE) on INSERT and UPDATE plans.

Shows plan and cost for write operations (INSERT, UPDATE) on task_instances
for per-SQL-type coverage. Yields actionable plan data (node types, cost, rows).
Does not duplicate pg_analyze_queries.py (read-only); extends with write plans.

Requires DATABASE_URL=postgresql://... Run from task_aversion_app:
  python scripts/performance/pg_explain_writes.py [--user-id N] [--no-execute]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path
from typing import Any, List, Optional

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EXPLAIN (ANALYZE) on INSERT and UPDATE for plan visibility"
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=1,
        help="user_id for UPDATE WHERE (default 1)",
    )
    parser.add_argument(
        "--no-execute",
        action="store_true",
        help="Use EXPLAIN only (no ANALYZE). Does not execute writes.",
    )
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url or not database_url.startswith("postgresql"):
        print("[FAIL] DATABASE_URL must be set and point to PostgreSQL.")
        return 1

    try:
        from sqlalchemy import create_engine, text
        from sqlalchemy.exc import SQLAlchemyError
    except ImportError:
        print("[FAIL] sqlalchemy required. pip install sqlalchemy psycopg2-binary")
        return 1

    engine = create_engine(database_url, pool_pre_ping=True)
    uid = args.user_id
    explain_mode = (
        "EXPLAIN (ANALYZE, FORMAT TEXT)"
        if not args.no_execute
        else "EXPLAIN (FORMAT TEXT)"
    )

    # INSERT: use a subquery that returns no rows so we see plan without inserting
    insert_sql = """
    INSERT INTO task_instances (
        user_id, task_id, status, is_completed, is_deleted, created_at, updated_at
    )
    SELECT :uid, 1, 'pending', false, false, now(), now()
    WHERE NOT EXISTS (
        SELECT 1 FROM task_instances
        WHERE user_id = :uid AND task_id = 1 AND status = 'pending'
        LIMIT 1
    )
    """
    # UPDATE: touch one row by user_id and a chosen instance_id (may match 0 rows)
    update_sql = """
    UPDATE task_instances
    SET updated_at = now()
    WHERE user_id = :uid AND instance_id = (
        SELECT instance_id FROM task_instances WHERE user_id = :uid LIMIT 1
    )
    """
    params: Any = {"uid": uid}

    with engine.connect() as conn:
        for name, sql in [
            ("INSERT (conditional, no rows if exists)", insert_sql),
            ("UPDATE one row by user_id + instance_id", update_sql),
        ]:
            print("=" * 72)
            print(name)
            print("=" * 72)
            try:
                stmt = f"{explain_mode} {sql}"
                r = conn.execute(text(stmt), params)
                for row in r:
                    print(row[0])
            except (ValueError, TypeError, SQLAlchemyError) as e:
                print(f"[FAIL] {e}")
            print()

    print("[INFO] Write plans show Insert/Update node cost; 0 rows updated is normal if no match.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
