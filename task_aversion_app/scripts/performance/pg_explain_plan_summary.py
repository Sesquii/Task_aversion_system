#!/usr/bin/env python3
"""
EXPLAIN/plan-focused: run EXPLAIN (FORMAT TEXT) on critical queries and summarize plans.

Parses plan output for scan type (Seq Scan vs Index Scan), estimated rows, and cost range.
Produces a compact summary table for per-SQL-type coverage and actionable plan data.
Extends pg_analyze_queries.py with plan parsing and summary output; does not duplicate it.

Requires DATABASE_URL=postgresql://... Run from task_aversion_app:
  python scripts/performance/pg_explain_plan_summary.py [--user-id N]
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
try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
    load_dotenv()
except ImportError:
    pass


def parse_plan_lines(lines: List[str]) -> Tuple[str, Optional[str], Optional[str], Optional[str]]:
    """
    Parse EXPLAIN (FORMAT TEXT) output for scan type, cost, and rows.
    Returns (scan_type, cost_range, rows_est, index_name).
    """
    plan_text = " ".join(lines)
    scan_type: str = "unknown"
    cost_range: Optional[str] = None
    rows_est: Optional[str] = None
    index_name: Optional[str] = None

    # Prefer first line that has a Scan (top-level plan node)
    for line in lines:
        line_stripped = line.strip()
        if "Seq Scan" in line_stripped:
            scan_type = "Seq Scan"
            break
        idx = line_stripped.find("Index Scan")
        if idx >= 0:
            scan_type = "Index Scan"
            # Optional: extract index name "using idx_..."
            using = re.search(r"using (\S+)", line_stripped, re.IGNORECASE)
            if using:
                index_name = using.group(1)
            break
        if "Index Only Scan" in line_stripped:
            scan_type = "Index Only Scan"
            using = re.search(r"using (\S+)", line_stripped, re.IGNORECASE)
            if using:
                index_name = using.group(1)
            break

    # cost=0.00..15.30
    cost_m = re.search(r"cost=([\d.]+)\.\.([\d.]+)", plan_text)
    if cost_m:
        cost_range = f"{cost_m.group(1)}..{cost_m.group(2)}"

    # rows=123
    rows_m = re.search(r"rows=(\d+)", plan_text)
    if rows_m:
        rows_est = rows_m.group(1)

    return (scan_type, cost_range, rows_est, index_name)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="EXPLAIN (FORMAT TEXT) critical queries and summarize scan type, cost, rows"
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
        (
            "Single instance by id",
            "SELECT * FROM task_instances WHERE user_id = :uid AND instance_id = :instance_id",
        ),
    ]
    # instance_id is VARCHAR; use string. Use a placeholder; script does not query real id.
    params: Any = {"uid": uid, "instance_id": "1"}

    summaries: List[Tuple[str, str, Optional[str], Optional[str], Optional[str]]] = []
    with engine.connect() as conn:
        for name, sql in queries:
            try:
                stmt = f"{explain_prefix} {sql}"
                r = conn.execute(text(stmt), params)
                lines = [row[0] for row in r if row[0]]
                scan_type, cost_range, rows_est, index_name = parse_plan_lines(lines)
                summaries.append((name, scan_type, cost_range, rows_est, index_name))
            except (ValueError, TypeError) as e:
                print(f"[FAIL] {name}: {e}")
                summaries.append((name, "error", None, None, None))

    # Print summary table
    print("EXPLAIN plan summary (FORMAT TEXT)")
    print("=" * 72)
    fmt = "%-45s %-18s %-12s %-8s %s"
    print(fmt % ("Query", "Scan type", "Cost range", "Rows", "Index"))
    print("-" * 72)
    for name, scan_type, cost_range, rows_est, index_name in summaries:
        cost_s = cost_range if cost_range else "-"
        rows_s = rows_est if rows_est else "-"
        idx_s = index_name if index_name else "-"
        # Truncate long names
        name_short = name[:44] if len(name) > 44 else name
        print(fmt % (name_short, scan_type, cost_s, rows_s, idx_s))
    print()
    print("[INFO] Prefer Index Scan over Seq Scan for large tables; check row estimates.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
