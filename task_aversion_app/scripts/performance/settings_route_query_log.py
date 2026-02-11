#!/usr/bin/env python3
"""
Settings page: query log analysis for Settings routes only.

Targets the Settings page (/settings, ui/settings_page.py) and its main areas:
settings landing, CSV import path, score weights, productivity settings,
and cancellation penalties. Parses logs/query_log.txt and filters to routes
that belong to Settings: GET/POST /settings, /settings/composite-score-weights,
/settings/productivity-settings, /settings/cancellation-penalties. Reports
per-route request count, total queries, mean queries per request, and mean
DB time. Produces meaningful performance data (query count, timings) for
Settings flows. Needs query log (ENABLE_QUERY_LOGGING).

Usage:
  cd task_aversion_app
  python scripts/performance/settings_route_query_log.py [path/to/query_log.txt]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from collections import defaultdict


SETTINGS_PATH_PREFIX = "/settings"


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

        if req.get("path") is not None and req["path"].startswith(SETTINGS_PATH_PREFIX):
            requests.append(req)

    return requests


def main() -> int:
    # Script lives in task_aversion_app/scripts/performance/
    base = Path(__file__).resolve().parent.parent.parent
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else base / "logs" / "query_log.txt"

    if not log_path.is_file():
        print(f"[FAIL] Log file not found: {log_path}")
        print("  Generate with ENABLE_QUERY_LOGGING=1 and load Settings pages.")
        return 1

    requests = parse_log(log_path)
    if not requests:
        print("[INFO] No Settings route entries in log.")
        print("  Visit /settings (and subpages) with query logging on, then re-run.")
        return 0

    by_route: dict[str, list[tuple[int, float]]] = defaultdict(list)
    for r in requests:
        path_key = f"{r['method']} {r['path']}"
        n_queries = len(r["query_list"])
        db_ms = r["db_time_ms"] if r.get("db_time_ms") is not None else 0.0
        by_route[path_key].append((n_queries, db_ms))

    route_stats: list[tuple[str, int, int, float, float]] = []
    for path_key, rows in by_route.items():
        n_requests = len(rows)
        total_queries = sum(r[0] for r in rows)
        mean_queries = total_queries / n_requests if n_requests else 0.0
        times = [r[1] for r in rows if r[1] > 0]
        mean_db_ms = sum(times) / len(times) if times else 0.0
        route_stats.append((path_key, n_requests, total_queries, mean_queries, mean_db_ms))

    route_stats.sort(key=lambda x: (-x[2], -x[4]))

    print("=" * 72)
    print("SETTINGS ROUTE QUERY LOG (Settings routes only; counts and timings)")
    print("=" * 72)
    print("Targets: Settings page (landing, CSV import, score weights,")
    print("         productivity settings, cancellation penalties).")
    print()
    print(f"Log: {log_path}")
    print(f"Settings requests in log: {len(requests)}")
    total_queries_all = sum(r[2] for r in route_stats)
    print(f"Total queries (Settings routes): {total_queries_all}")
    print()

    print("--- By route ---")
    for path_key, n_req, total_q, mean_q, mean_db in route_stats:
        print(f"  {total_q:5d} queries  mean/req={mean_q:6.1f}  mean_DB={mean_db:8.1f} ms  n={n_req:4d}  {path_key}")
    print()

    print("[INFO] Use this to see which Settings route drives the most DB load.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
