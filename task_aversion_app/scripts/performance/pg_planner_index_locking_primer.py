#!/usr/bin/env python3
"""
PostgreSQL educational primer: planner, indexes, and locking (PG ops/educational).

Focus: **PostgreSQL operations / educational**. Teaches how the query planner
chooses plans, how indexes affect Seq Scan vs Index Scan, and how row-level
locking (FOR UPDATE, FOR SHARE) works. Complements pg_explain_* scripts by
explaining the concepts. Optional --live runs one EXPLAIN on a simple query
to show plan output. No DB required for the primer; DATABASE_URL needed for --live.

Usage:
  cd task_aversion_app
  python scripts/performance/pg_planner_index_locking_primer.py [--live]
  set DATABASE_URL=postgresql://...
  python scripts/performance/pg_planner_index_locking_primer.py --live [--user-id N]
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


def print_primer() -> None:
    """Print educational primer on planner, indexes, and locking."""
    print("=" * 72)
    print("POSTGRESQL: PLANNER, INDEXES, AND LOCKING (primer)")
    print("=" * 72)
    print()
    print("--- 1. Query planner ---")
    print("  The planner turns SQL into an execution plan. It estimates cost using:")
    print("  - pg_class statistics (reltuples, relpages) and pg_statistics")
    print("  - random_page_cost, seq_page_cost, work_mem, etc.")
    print("  Run ANALYZE (or pg_maintain.py) so stats are up to date.")
    print()
    print("--- 2. Scan types ---")
    print("  - Seq Scan: read the whole table. Good for small tables or when")
    print("    most rows match. Cost grows with table size.")
    print("  - Index Scan / Index Only Scan: use an index to find rows. Good when")
    print("    predicates match index columns (e.g. WHERE user_id = ?).")
    print("  - Bitmap Index Scan: build a bitmap from index, then heap fetch.")
    print("  Use pg_explain_plan_summary.py or pg_explain_scan_types.py to see")
    print("  which scan type your queries get.")
    print()
    print("--- 3. Indexes ---")
    print("  - B-tree: default; good for =, <, >, ORDER BY. Left-prefix: (a,b,c)")
    print("    can serve WHERE a=? AND b=? but not WHERE b=? alone.")
    print("  - GIN: good for containment (arrays, jsonb, full text).")
    print("  Unused indexes add write cost. Check pg_index_review.py --suggest and")
    print("  index_catalog_with_usage.py --live for usage.")
    print()
    print("--- 4. Row-level locking ---")
    print("  - FOR UPDATE: exclusive row lock; blocks other FOR UPDATE and UPDATE.")
    print("  - FOR NO KEY UPDATE: weaker; allows SELECT ... FOR KEY SHARE.")
    print("  - FOR SHARE: shared lock; multiple transactions can hold FOR SHARE.")
    print("  - FOR KEY SHARE: weakest; allows FOR NO KEY UPDATE on same row.")
    print("  Lock order matters: avoid deadlocks by locking in a consistent order.")
    print()
    print("--- 5. Table-level locks ---")
    print("  - ACCESS SHARE: SELECT only. Does not conflict with others.")
    print("  - ROW EXCLUSIVE: INSERT/UPDATE/DELETE. Conflicts with SHARE, EXCLUSIVE.")
    print("  - ACCESS EXCLUSIVE: DDL (DROP, TRUNCATE). Blocks all.")
    print("  VACUUM and CREATE INDEX CONCURRENTLY use weaker locks to avoid blocking.")
    print()


def run_live_example(user_id: int) -> int:
    """Run one EXPLAIN on a simple query and print plan. Returns 0 on success."""
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url or not database_url.startswith("postgresql"):
        print("[FAIL] --live requires DATABASE_URL pointing to PostgreSQL.")
        return 1
    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        print("[FAIL] sqlalchemy required. pip install sqlalchemy psycopg2-binary")
        return 1

    engine = create_engine(database_url, pool_pre_ping=True)
    with engine.connect() as conn:
        # Simple query that might use an index (task_instances by user_id)
        print("--- Live EXPLAIN (example query) ---")
        print(f"  Query: SELECT ... FROM task_instances WHERE user_id = {user_id} LIMIT 10")
        print()
        try:
            result = conn.execute(
                text("EXPLAIN (FORMAT TEXT) SELECT id, task_id, status FROM task_instances WHERE user_id = :uid LIMIT 10"),
                {"uid": user_id},
            )
            for row in result:
                print("  " + (row[0] or ""))
        except Exception as e:
            print(f"  [WARN] EXPLAIN failed (table may not exist): {e}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Educational primer on PostgreSQL planner, indexes, locking"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run one EXPLAIN on a sample query (requires DATABASE_URL)",
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=1,
        metavar="N",
        help="User ID for --live example query (default 1)",
    )
    args = parser.parse_args()

    print_primer()
    if args.live:
        return run_live_example(args.user_id)
    print("[INFO] Focus: PG ops/educational. Use --live to see a sample EXPLAIN.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
