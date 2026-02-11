#!/usr/bin/env python3
"""
SELECT-focused query log analysis: SELECT counts and DB time by route.

Part of per-SQL-type coverage (SELECT). Complements analyze_query_log_bottlenecks.py
by focusing only on SELECT queries: how many SELECTs run per route and how much
DB time those requests use. Uses the same logs/query_log.txt format (requires
ENABLE_QUERY_LOGGING and at least one dashboard load).

Outputs actionable counts and timings: SELECTs per route, mean SELECTs per request,
mean DB time per request. Use to find which routes drive the most read load.

Usage:
  cd task_aversion_app
  python scripts/performance/select_log_by_route.py [path/to/query_log.txt]
"""
from __future__ import annotations

import re
import sys
from collections import defaultdict
from pathlib import Path


def classify_query(q: str) -> str:
    """Classify as SELECT, INSERT, UPDATE, DELETE, PRAGMA, other."""
    u = q.strip().upper()
    if u.startswith("PRAGMA"):
        return "PRAGMA"
    if u.startswith("SELECT"):
        return "SELECT"
    if u.startswith("INSERT"):
        return "INSERT"
    if u.startswith("UPDATE"):
        return "UPDATE"
    if u.startswith("DELETE"):
        return "DELETE"
    return "other"


def parse_log(path: Path) -> list[dict]:
    """Parse query_log.txt. Returns list of request dicts with path, query_list, db_time_ms."""
    text = path.read_text(encoding="utf-8", errors="replace")
    requests: list[dict] = []

    for block in re.split(r"\n={80}\n", text):
        block = block.strip()
        if not block:
            continue

        req: dict = {
            "path": None,
            "method": "GET",
            "db_time_ms": None,
            "query_list": [],
        }

        for line in block.split("\n"):
            line = line.strip()
            if not line:
                continue

            m = re.match(r"\[\d{4}-\d{2}-\d{2}[^\]]*\]\s+(GET|POST|PUT|DELETE)\s+(\S+)", line)
            if m:
                req["method"] = m.group(1)
                req["path"] = m.group(2)
                continue

            if "Total DB time:" in line:
                val = re.search(r"([\d.]+)\s*ms", line)
                req["db_time_ms"] = float(val.group(1)) if val else None
                continue

            if re.match(r"^\s*\d+\.\s+", line):
                q = re.sub(r"^\s*\d+\.\s+", "", line)
                req["query_list"].append(q)

        if req.get("path") is not None:
            requests.append(req)

    return requests


def main() -> int:
    base = Path(__file__).resolve().parent.parent.parent
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else base / "logs" / "query_log.txt"

    if not log_path.is_file():
        print(f"[FAIL] Log file not found: {log_path}")
        print("  Generate with ENABLE_QUERY_LOGGING=1 and load the dashboard.")
        return 1

    requests = parse_log(log_path)
    if not requests:
        print("[INFO] No request entries in log.")
        return 0

    # Per-route: list of (n_selects, db_time_ms)
    by_route: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for r in requests:
        path_key = f"{r['method']} {r['path']}"
        n_select = sum(1 for q in r["query_list"] if classify_query(q) == "SELECT")
        db_ms = r["db_time_ms"] if r.get("db_time_ms") is not None else 0.0
        by_route[path_key].append((n_select, db_ms))

    # Aggregate: request count, total SELECTs, mean SELECTs/request, mean DB time
    route_stats: list[tuple[str, int, int, float, float]] = []
    for path_key, rows in by_route.items():
        n_requests = len(rows)
        total_selects = sum(r[0] for r in rows)
        mean_selects = total_selects / n_requests if n_requests else 0.0
        times = [r[1] for r in rows if r[1] > 0]
        mean_db_ms = sum(times) / len(times) if times else 0.0
        route_stats.append((path_key, n_requests, total_selects, mean_selects, mean_db_ms))

    route_stats.sort(key=lambda x: (-x[2], -x[4]))  # by total SELECTs, then mean DB time

    print("=" * 72)
    print("SELECT LOG BY ROUTE (SELECT-focused; actionable counts and timings)")
    print("=" * 72)
    print(f"Log: {log_path}")
    print(f"Total requests: {len(requests)}")
    total_selects_all = sum(r[2] for r in route_stats)
    print(f"Total SELECT queries in log: {total_selects_all}")
    print()

    print("--- By route: SELECT count and mean DB time ---")
    for path_key, n_req, total_sel, mean_sel, mean_db in route_stats[:25]:
        print(f"  {total_sel:5d} SELECTs  mean/req={mean_sel:6.1f}  mean_DB={mean_db:8.1f} ms  n={n_req:4d}  {path_key}")
    print()

    # Dashboard summary
    dashboard_key = "GET /"
    if dashboard_key in by_route:
        rows = by_route[dashboard_key]
        total_sel = sum(r[0] for r in rows)
        times = [r[1] for r in rows if r[1] > 0]
        print("--- Dashboard (GET /) SELECT summary ---")
        print(f"  Requests: {len(rows)}")
        print(f"  SELECTs: total={total_sel}  mean per request={total_sel / len(rows):.1f}")
        if times:
            print(f"  DB time:  mean={sum(times) / len(times):.1f} ms")
        print()
    else:
        print("--- Dashboard (GET /) not in log. Load main page with query logging on. ---")
        print()

    print("[INFO] SELECT-focused for per-SQL-type coverage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
