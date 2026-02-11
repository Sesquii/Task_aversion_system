#!/usr/bin/env python3
"""
EXPLAIN/plan-focused: run EXPLAIN (ANALYZE, BUFFERS) on analytics/dashboard SQL.

Covers queries that feed analytics and dashboard (task_instances by user_id,
completed_only, active list). Prints full plan and a one-line summary with
scan type, actual rows, and buffer stats for actionable plan data.
Builds on pg_analyze_queries.py with analytics-oriented queries and summary.

Requires DATABASE_URL=postgresql://... Run from task_aversion_app:
  python scripts/performance/pg_explain_analytics_queries.py [--user-id N] [--no-execute]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from typing import Any, List, Optional, Tuple

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def summarize_plan(lines: List[str]) -> Tuple[str, Optional[str], Optional[str]]:
    """
    Extract from EXPLAIN (ANALYZE, BUFFERS) output: scan type, actual rows, buffer line.
    Returns (scan_type, actual_rows, buffers_summary).
    """
    plan_text = "\n".join(lines)
    scan_type = "unknown"
    actual_rows: Optional[str] = None
    buffers_summary: Optional[str] = None

    for line in lines:
        s = line.strip()
        if "Seq Scan" in s:
            scan_type = "Seq Scan"
            break
        if "Index Scan" in s:
            scan_type = "Index Scan"
            break
        if "Index Only Scan" in s:
            scan_type = "Index Only Scan"
            break

    # actual time=... rows=N
    m = re.search(r"rows=(\d+)", plan_text)
    if m:
        actual_rows = m.group(1)

    # Buffers: shared hit=N read=N
    buf = re.search(r"Buffers:\s*(.+?)(?:\n|$)", plan_text, re.DOTALL)
    if buf:
        buffers_summary = buf.group(1).strip().replace("\n", " ")[:60]

    return (scan_type, actual_rows, buffers_summary)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EXPLAIN (ANALYZE, BUFFERS) on analytics/dashboard queries"
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=1,
        help="user_id for WHERE clauses (default 1)",
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
    explain_mode = (
        "EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)"
        if not args.no_execute
        else "EXPLAIN (FORMAT TEXT)"
    )

    queries: List[Tuple[str, str]] = [
        (
            "Dashboard: all instances (metrics)",
            "SELECT * FROM task_instances WHERE user_id = :uid",
        ),
        (
            "Analytics/relief: completed instances only",
            "SELECT * FROM task_instances WHERE user_id = :uid AND completed_at IS NOT NULL",
        ),
        (
            "Dashboard sidebar: active instances",
            """SELECT * FROM task_instances
               WHERE user_id = :uid AND is_completed = false AND is_deleted = false
               AND status NOT IN ('completed', 'cancelled')""",
        ),
    ]
    params: Any = {"uid": uid}

    with engine.connect() as conn:
        for name, sql in queries:
            print("=" * 72)
            print(name)
            print("=" * 72)
            try:
                stmt = f"{explain_mode} {sql}"
                r = conn.execute(text(stmt), params)
                lines = [row[0] for row in r if row[0]]
                for line in lines:
                    print(line)
                scan_type, actual_rows, buffers_summary = summarize_plan(lines)
                row_s = actual_rows if actual_rows else "N/A"
                buf_s = buffers_summary if buffers_summary else "N/A"
                print("[SUMMARY] scan=%s actual_rows=%s buffers=%s" % (scan_type, row_s, buf_s))
            except (ValueError, TypeError) as e:
                print(f"[FAIL] {e}")
            print()

    print("[INFO] Prefer Index Scan; high shared read or large actual rows may need indexing.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
