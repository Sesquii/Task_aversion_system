#!/usr/bin/env python3
"""
Analytics page and routes: query log stats for /analytics paths.

Targets the Analytics area: main page (/analytics) and analytics sub-routes
(/analytics/emotional-flow, /analytics/factors-comparison, /analytics/relief-comparison,
/analytics/glossary). Parses logs/query_log.txt and reports SELECT counts and mean DB
time per analytics route. Use to attribute load to analytics pages after loading them
with ENABLE_QUERY_LOGGING=1.

Needs query log. Run from task_aversion_app:
  python scripts/performance/analytics_query_log_routes.py [path/to/query_log.txt]
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
        print("  Generate with ENABLE_QUERY_LOGGING=1 and load analytics pages.")
        return 1

    requests = parse_log(log_path)
    analytics_requests = [r for r in requests if r.get("path") and "/analytics" in r["path"]]
    if not analytics_requests:
        print("[INFO] No analytics routes in log. Load /analytics or sub-pages with query logging on.")
        return 0

    by_route: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for r in analytics_requests:
        path_key = f"{r['method']} {r['path']}"
        n_select = sum(1 for q in r["query_list"] if classify_query(q) == "SELECT")
        db_ms = r["db_time_ms"] if r.get("db_time_ms") is not None else 0.0
        by_route[path_key].append((n_select, db_ms))

    route_stats: list[tuple[str, int, int, float, float]] = []
    for path_key, rows in by_route.items():
        n_requests = len(rows)
        total_selects = sum(x[0] for x in rows)
        mean_selects = total_selects / n_requests if n_requests else 0.0
        times = [x[1] for x in rows if x[1] > 0]
        mean_db_ms = sum(times) / len(times) if times else 0.0
        route_stats.append((path_key, n_requests, total_selects, mean_selects, mean_db_ms))

    route_stats.sort(key=lambda x: (-x[2], -x[4]))

    print("=" * 72)
    print("ANALYTICS QUERY LOG ROUTES (Analytics page and elements)")
    print("=" * 72)
    print("Target: /analytics, emotional flow, relief comparison, factors comparison, glossary.")
    print(f"Log: {log_path}")
    print(f"Analytics requests: {len(analytics_requests)}  (total in log: {len(requests)})")
    total_selects = sum(r[2] for r in route_stats)
    print(f"Total SELECTs (analytics routes): {total_selects}")
    print()
    print("--- By analytics route: SELECT count and mean DB time ---")
    for path_key, n_req, total_sel, mean_sel, mean_db in route_stats:
        print(f"  {total_sel:5d} SELECTs  mean/req={mean_sel:6.1f}  mean_DB={mean_db:8.1f} ms  n={n_req:4d}  {path_key}")
    print()
    print("[INFO] Needs query log. Use ENABLE_QUERY_LOGGING=1 and load analytics pages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
