#!/usr/bin/env python3
"""
Cross-cutting: SELECT + EXPLAIN for dashboard hot path.

Combines (1) query-log analysis for GET /: extract SELECT queries, count and
summarize patterns, and (2) EXPLAIN on canonical dashboard SELECTs (task_instances
by user_id, active list, completed-only) for enmeshed optimization. Use --live
with DATABASE_URL to run EXPLAIN; without --live only the log-derived SELECT
summary is printed. Yields meaningful data in both modes.

Run from task_aversion_app:
  python scripts/performance/dashboard_select_explain_hot_path.py [path/to/query_log.txt] [--live] [--user-id N]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path
from collections import Counter

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def normalize_query(q: str) -> str:
    """Strip param tail and collapse whitespace for pattern grouping."""
    s = re.sub(r"\s*\|\s*Params:.*$", "", q, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    return (s[:150] + "...") if len(s) > 150 else s


def parse_log(path: Path) -> list[dict]:
    """Parse query_log.txt; return list of request dicts with path, method, query_list."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        raise ValueError(f"Cannot read log: {e}") from e

    requests: list[dict] = []
    blocks = re.split(r"\n={80}\n", text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        req: dict = {"path": None, "method": "GET", "query_list": []}

        for line in block.split("\n"):
            line_stripped = line.strip()
            if not line_stripped:
                continue

            m = re.match(r"\[\d{4}-\d{2}-\d{2}[^\]]*\]\s+(GET|POST|PUT|DELETE)\s+(\S+)", line_stripped)
            if m:
                req["method"] = m.group(1)
                req["path"] = m.group(2)
                continue

            if "Query Details" in line_stripped:
                continue
            if re.match(r"^\s*\d+\.\s+", line_stripped):
                q = re.sub(r"^\s*\d+\.\s+", "", line_stripped)
                req["query_list"].append(q)
                continue

        if req.get("path") is not None:
            requests.append(req)

    return requests


def is_select(q: str) -> bool:
    """True if query looks like a SELECT (after stripping param tail)."""
    s = re.sub(r"\s*\|\s*Params:.*$", "", q, flags=re.IGNORECASE).strip().upper()
    return s.startswith("SELECT")


def run_explain(engine, user_id: int, no_execute: bool) -> None:
    """Run EXPLAIN on canonical dashboard SELECTs and print plan summary."""
    from sqlalchemy import text

    explain_mode = (
        "EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)"
        if not no_execute
        else "EXPLAIN (FORMAT TEXT)"
    )
    params: dict = {"uid": user_id}

    queries = [
        ("All instances (metrics)", "SELECT * FROM task_instances WHERE user_id = :uid"),
        (
            "Completed only (analytics/relief)",
            "SELECT * FROM task_instances WHERE user_id = :uid AND completed_at IS NOT NULL",
        ),
        (
            "Active list (sidebar)",
            """SELECT * FROM task_instances
               WHERE user_id = :uid AND is_completed = false AND is_deleted = false
               AND status NOT IN ('completed', 'cancelled')""",
        ),
    ]

    for name, sql in queries:
        print("--- EXPLAIN: %s ---" % name)
        try:
            stmt = f"{explain_mode} {sql}"
            with engine.connect() as conn:
                r = conn.execute(text(stmt), params)
                lines = [row[0] for row in r if row[0]]
        except (ValueError, TypeError) as e:
            print("[FAIL] %s" % e)
            print()
            continue

        for line in lines:
            print(line)

        plan_text = "\n".join(lines)
        scan_type = "unknown"
        for line in lines:
            if "Seq Scan" in line:
                scan_type = "Seq Scan"
                break
            if "Index Scan" in line:
                scan_type = "Index Scan"
                break
            if "Index Only Scan" in line:
                scan_type = "Index Only Scan"
                break
        m = re.search(r"rows=(\d+)", plan_text)
        actual_rows = m.group(1) if m else "N/A"
        print("[SUMMARY] scan=%s actual_rows=%s" % (scan_type, actual_rows))
        print()


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SELECT (from dashboard log) + EXPLAIN for dashboard hot path"
    )
    parser.add_argument(
        "log_path",
        nargs="?",
        default=None,
        help="Path to query_log.txt (default: task_aversion_app/logs/query_log.txt)",
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Run EXPLAIN on canonical dashboard SELECTs (requires DATABASE_URL=postgresql://...)",
    )
    parser.add_argument("--user-id", type=int, default=1, help="user_id for EXPLAIN (default 1)")
    parser.add_argument(
        "--no-execute",
        action="store_true",
        help="Use EXPLAIN only (no ANALYZE) when --live",
    )
    args = parser.parse_args()

    base = Path(__file__).resolve().parent.parent.parent
    log_path = Path(args.log_path) if args.log_path else base / "logs" / "query_log.txt"

    print("=" * 72)
    print("DASHBOARD SELECT + EXPLAIN (cross-cutting: log SELECT summary + EXPLAIN)")
    print("=" * 72)

    # Part 1: SELECT summary from dashboard (GET /) in query log
    if log_path.is_file():
        try:
            requests = parse_log(log_path)
        except ValueError as e:
            print("[FAIL] %s" % e)
            return 1
        dashboard_loads = [r for r in requests if (r.get("method"), r.get("path")) == ("GET", "/")]
        if dashboard_loads:
            all_selects: list[str] = []
            for req in dashboard_loads:
                for q in req.get("query_list") or []:
                    if is_select(q):
                        all_selects.append(q)
            pattern_counter = Counter(normalize_query(q) for q in all_selects)
            print("[INFO] Dashboard (GET /): %d SELECTs across %d load(s)" % (
                len(all_selects), len(dashboard_loads)))
            if pattern_counter:
                print("Top SELECT patterns (normalized):")
                for pat, cnt in pattern_counter.most_common(10):
                    print("  %3d x %s" % (cnt, pat[:100] + ("..." if len(pat) > 100 else "")))
        else:
            print("[INFO] No GET / requests in log. Load dashboard with ENABLE_QUERY_LOGGING=1.")
    else:
        print("[INFO] No query log at %s; skipping SELECT summary." % log_path)

    print()

    # Part 2: EXPLAIN on canonical dashboard SELECTs (optional, --live)
    if args.live:
        database_url = os.getenv("DATABASE_URL", "")
        if not database_url or not database_url.startswith("postgresql"):
            print("[FAIL] --live requires DATABASE_URL=postgresql://...")
            return 1
        try:
            from sqlalchemy import create_engine
        except ImportError:
            print("[FAIL] sqlalchemy required. pip install sqlalchemy psycopg2-binary")
            return 1
        engine = create_engine(database_url, pool_pre_ping=True)
        print("EXPLAIN on canonical dashboard SELECTs (user_id=%s):" % args.user_id)
        run_explain(engine, args.user_id, args.no_execute)
        print("[INFO] Prefer Index Scan; Seq Scan on large tables may need indexing.")
    else:
        print("[INFO] Use --live to run EXPLAIN on canonical dashboard SELECTs.")

    return 0


if __name__ == "__main__":
    sys.exit(main())
