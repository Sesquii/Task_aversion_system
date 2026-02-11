#!/usr/bin/env python3
"""
EXPLAIN/plan-focused: report scan type, row estimate, and cost per critical query.

Runs EXPLAIN (FORMAT TEXT) on key dashboard/analytics queries and prints one
actionable line per query: scan type (Seq Scan vs Index Scan), estimated rows,
and cost range. For per-SQL-type coverage and quick plan comparison.
Extends pg_analyze_queries.py with compact scan-type output; does not duplicate it.

Requires DATABASE_URL=postgresql://... Run from task_aversion_app:
  python scripts/performance/pg_explain_scan_types.py [--user-id N]
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


def extract_scan_and_cost(lines: List[str]) -> Tuple[str, Optional[str], Optional[str]]:
    """Parse EXPLAIN output for scan type, estimated rows, cost. Returns (scan, rows, cost)."""
    text = " ".join(lines)
    scan = "unknown"
    for line in lines:
        s = line.strip()
        if "Seq Scan" in s:
            scan = "Seq Scan"
            break
        if "Index Only Scan" in s:
            scan = "Index Only Scan"
            break
        if "Index Scan" in s:
            scan = "Index Scan"
            break
    rows_m = re.search(r"rows=(\d+)", text)
    cost_m = re.search(r"cost=([\d.]+)\.\.([\d.]+)", text)
    rows_s = rows_m.group(1) if rows_m else None
    cost_s = f"{cost_m.group(1)}..{cost_m.group(2)}" if cost_m else None
    return (scan, rows_s, cost_s)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="One-line scan type, rows, cost per critical query"
    )
    parser.add_argument(
        "--user-id",
        type=int,
        default=1,
        help="user_id for WHERE clauses (default 1)",
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
    explain_prefix = "EXPLAIN (FORMAT TEXT)"

    queries: List[Tuple[str, str]] = [
        ("All instances", "SELECT * FROM task_instances WHERE user_id = :uid"),
        (
            "Completed only",
            "SELECT * FROM task_instances WHERE user_id = :uid AND completed_at IS NOT NULL",
        ),
        (
            "Active list",
            """SELECT * FROM task_instances
               WHERE user_id = :uid AND is_completed = false AND is_deleted = false
               AND status NOT IN ('completed', 'cancelled')""",
        ),
    ]
    params: Any = {"uid": uid}

    print("Query              | Scan type        | Rows (est) | Cost")
    print("-" * 60)
    with engine.connect() as conn:
        for name, sql in queries:
            try:
                r = conn.execute(text(f"{explain_prefix} {sql}"), params)
                lines = [row[0] for row in r if row[0]]
                scan, rows_s, cost_s = extract_scan_and_cost(lines)
                rows_d = rows_s if rows_s else "-"
                cost_d = cost_s if cost_s else "-"
                print("%-18s | %-16s | %-10s | %s" % (name, scan, rows_d, cost_d))
            except (ValueError, TypeError) as e:
                print("%-18s | error: %s" % (name, e))
    print()
    print("[INFO] Seq Scan on large tables may need an index; compare row estimates.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
