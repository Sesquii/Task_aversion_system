#!/usr/bin/env python3
"""
PostgreSQL query analysis: run EXPLAIN (ANALYZE, BUFFERS) on critical dashboard patterns.

These mirror the main queries used by Analytics._load_instances and
InstanceManager.list_active_instances. Use this to verify index usage and
identify sequential scans or high buffer I/O.

Requires DATABASE_URL pointing to PostgreSQL. Uses a sample user_id (default 1)
for filtering; override with --user-id. Run against a copy of production data
for realistic plans.

Usage:
  cd task_aversion_app
  set DATABASE_URL=postgresql://...
  python scripts/performance/pg_analyze_queries.py [--user-id 1] [--no-execute]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> int:
    parser = argparse.ArgumentParser(description="EXPLAIN ANALYZE critical dashboard queries")
    parser.add_argument(
        "--user-id",
        type=int,
        default=1,
        help="user_id to use in WHERE (default 1)",
    )
    parser.add_argument(
        "--no-execute",
        action="store_true",
        help="Use EXPLAIN only (no ANALYZE). Does not execute queries.",
    )
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url or not database_url.startswith("postgresql"):
        print("[FAIL] DATABASE_URL must be set and point to PostgreSQL.")
        return 1

    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        print("[FAIL] sqlalchemy required. pip install sqlalchemy psycopg2-binary")
        return 1

    engine = create_engine(database_url, pool_pre_ping=True)
    uid = args.user_id
    explain_mode = "EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)" if not args.no_execute else "EXPLAIN (FORMAT TEXT)"

    # Queries mirror Analytics._load_instances and InstanceManager.list_active_instances
    queries = [
        (
            "Load all instances (dashboard metrics)",
            "SELECT * FROM task_instances WHERE user_id = :uid",
        ),
        (
            "Load completed instances only (relief summary)",
            "SELECT * FROM task_instances WHERE user_id = :uid AND completed_at IS NOT NULL",
        ),
        (
            "List active instances (dashboard sidebar)",
            """SELECT * FROM task_instances
               WHERE user_id = :uid AND is_completed = false AND is_deleted = false
               AND status NOT IN ('completed', 'cancelled')""",
        ),
    ]

    params = {"uid": uid}
    with engine.connect() as conn:
        for name, sql in queries:
            print("=" * 72)
            print(name)
            print("=" * 72)
            try:
                stmt = f"{explain_mode} {sql}"
                r = conn.execute(text(stmt), params)
                for row in r:
                    print(row[0])
            except Exception as e:
                print(f"[FAIL] {e}")
            print()

    print("[INFO] Look for Seq Scan on task_instances; Index Scan using idx_* is preferred.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
