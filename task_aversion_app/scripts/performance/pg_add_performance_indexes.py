#!/usr/bin/env python3
"""
PostgreSQL: add performance indexes that may be missing.

Creates composite index on task_instances (user_id, status, is_completed, is_deleted)
so list_active_instances and dashboard load can use a single index. Uses
CREATE INDEX CONCURRENTLY to avoid long locks (cannot run inside a transaction).

Run once after migrations. Requires DATABASE_URL pointing to PostgreSQL.

Usage:
  cd task_aversion_app
  set DATABASE_URL=postgresql://...
  python scripts/performance/pg_add_performance_indexes.py [--dry-run]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
    load_dotenv()
except ImportError:
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="Add performance indexes (CONCURRENTLY)")
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Only print what would be done",
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

    # CONCURRENTLY must run outside a transaction (autocommit)
    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        isolation_level="AUTOCOMMIT",
    )

    indexes = [
        {
            "name": "idx_task_instances_user_active",
            "sql": """CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_instances_user_active
                      ON task_instances (user_id, status, is_completed, is_deleted)""",
            "reason": "Covers list_active_instances and dashboard sidebar (user_id first).",
        },
        {
            "name": "idx_task_instances_user_completed_at",
            "sql": """CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_instances_user_completed_at
                      ON task_instances (user_id, completed_at)
                      WHERE completed_at IS NOT NULL""",
            "reason": "Covers _load_instances(completed_only=True) for relief summary.",
        },
    ]

    with engine.connect() as conn:
        for idx in indexes:
            # Check if already exists
            r = conn.execute(
                text(
                    """
                    SELECT 1 FROM pg_indexes
                    WHERE schemaname = 'public' AND indexname = :name
                    """
                ),
                {"name": idx["name"]},
            )
            if r.fetchone():
                print(f"  [SKIP] {idx['name']} already exists.")
                continue
            if args.dry_run:
                print(f"  [DRY-RUN] Would create: {idx['name']}")
                print(f"           {idx['reason']}")
                continue
            try:
                conn.execute(text(idx["sql"].replace("\n", " ").strip()))
                print(f"  [OK] Created {idx['name']}")
                print(f"       {idx['reason']}")
            except Exception as e:
                print(f"  [FAIL] {idx['name']}: {e}")

    if not args.dry_run:
        print("\n[SUCCESS] Run pg_maintain.py --analyze-only to update statistics.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
