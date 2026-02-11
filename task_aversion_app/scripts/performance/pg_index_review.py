#!/usr/bin/env python3
"""
PostgreSQL index review: list indexes, sizes, and suggest optimizations.

Reports:
  - All indexes on task_instances, tasks, and other app tables
  - Table and index sizes
  - Index usage (idx_scan, idx_tup_read) from pg_stat_user_indexes
  - Suggestions: composite (user_id, ...) for hot paths; possibly redundant indexes

Database-side only. Requires DATABASE_URL pointing to PostgreSQL.

Usage:
  cd task_aversion_app
  set DATABASE_URL=postgresql://...
  python scripts/performance/pg_index_review.py [--suggest]
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
    parser = argparse.ArgumentParser(description="PostgreSQL index review")
    parser.add_argument(
        "--suggest",
        action="store_true",
        help="Print suggestions for composite indexes and redundant indexes",
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

    with engine.connect() as conn:
        # Table sizes (relname, size)
        size_sql = text(
            """
            SELECT
                c.relname AS name,
                pg_size_pretty(pg_total_relation_size(c.oid)) AS total_size,
                pg_size_pretty(pg_relation_size(c.oid)) AS table_size
            FROM pg_class c
            JOIN pg_namespace n ON n.oid = c.relnamespace
            WHERE n.nspname = 'public' AND c.relkind = 'r'
            ORDER BY pg_total_relation_size(c.oid) DESC
            """
        )
        print("=" * 72)
        print("TABLE SIZES (public schema)")
        print("=" * 72)
        for row in conn.execute(size_sql):
            print(f"  {row[0]:30} total={row[1]:>10}  table={row[2]:>10}")
        print()

        # Indexes per table (indexdef from pg_indexes)
        idx_sql = text(
            """
            SELECT tablename, indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public'
            ORDER BY tablename, indexname
            """
        )
        print("=" * 72)
        print("INDEXES (table -> index definition)")
        print("=" * 72)
        current_table = None
        for row in conn.execute(idx_sql):
            tname, iname, idef = row[0], row[1], row[2] or ""
            if tname != current_table:
                current_table = tname
                print(f"\n  [{tname}]")
            print(f"    {iname}")
            if idef:
                print(f"      {idef}")
        print()

        # Index sizes
        idx_size_sql = text(
            """
            SELECT
                t.relname AS table_name,
                i.relname AS index_name,
                pg_size_pretty(pg_relation_size(i.oid)) AS index_size
            FROM pg_class t
            JOIN pg_index ix ON ix.indrelid = t.oid
            JOIN pg_class i ON i.oid = ix.indexrelid
            JOIN pg_namespace n ON t.relnamespace = n.oid
            WHERE n.nspname = 'public' AND t.relkind = 'r'
            ORDER BY pg_relation_size(i.oid) DESC
            """
        )
        print("=" * 72)
        print("INDEX SIZES (largest first)")
        print("=" * 72)
        for row in conn.execute(idx_size_sql):
            print(f"  {row[0]:25} {row[1]:45} {row[2]:>10}")
        print()

        # Usage stats (if available)
        try:
            usage_sql = text(
                """
                SELECT
                    schemaname,
                    relname AS table_name,
                    indexrelname AS index_name,
                    idx_scan,
                    idx_tup_read,
                    idx_tup_fetch
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public'
                ORDER BY idx_scan DESC
                """
            )
            print("=" * 72)
            print("INDEX USAGE (idx_scan, idx_tup_read)")
            print("=" * 72)
            for row in conn.execute(usage_sql):
                print(f"  {row[1]:25} {row[2]:45} scan={row[3]:>8} read={row[4]:>10}")
            print()
        except Exception as e:
            print(f"[WARN] Could not read pg_stat_user_indexes: {e}\n")

        if args.suggest:
            print("=" * 72)
            print("SUGGESTIONS (review before applying)")
            print("=" * 72)
            # Check if task_instances has composite (user_id, ...) for active list
            check_comp = text(
                """
                SELECT indexdef FROM pg_indexes
                WHERE schemaname = 'public' AND tablename = 'task_instances'
                AND indexdef LIKE '%user_id%'
                """
            )
            r = list(conn.execute(check_comp))
            has_user_composite = any(
                "user_id" in (row[0] or "") and "status" in (row[0] or "")
                for row in r
            )
            if not has_user_composite:
                print(
                    "  [SUGGEST] task_instances: consider composite index for active list:"
                )
                print(
                    "    CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_instances_user_active"
                )
                print(
                    "    ON task_instances (user_id, status, is_completed, is_deleted);"
                )
                print(
                    "    (Covers list_active_instances filter; user_id first for selectivity.)"
                )
                print()
            # Redundant: single-column indexes that are left-prefix of a composite
            print(
                "  [INFO] If you have both idx_task_instances_user_id and a composite"
            )
            print(
                "         (user_id, status, ...), the composite can serve user_id-only"
            )
            print(
                "         queries; the single-column index may be redundant (check usage)."
            )
            print()

    print("[SUCCESS] Index review complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
