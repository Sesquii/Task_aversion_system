#!/usr/bin/env python3
"""
Full-page dashboard load metrics from the query log.

Targets the main dashboard (page /, built by build_dashboard in ui/dashboard.py).
Parses logs/query_log.txt and reports metrics for GET / only: per-load query count
and total DB time, then summary statistics (min, mean, max, p95) for both.
Use to track dashboard full-page load performance over time or after changes.

Requires ENABLE_QUERY_LOGGING and at least one dashboard load to be logged.

Usage:
  cd task_aversion_app
  python scripts/performance/dashboard_full_page_metrics.py [path/to/query_log.txt]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def parse_log(path: Path) -> list[dict]:
    """Parse query_log.txt; return list of request dicts (path, method, queries, db_time_ms)."""
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

        req: dict = {"path": None, "method": "GET", "queries": None, "db_time_ms": None}

        for line in block.split("\n"):
            line = line.strip()
            if not line:
                continue

            m = re.match(r"\[\d{4}-\d{2}-\d{2}[^\]]*\]\s+(GET|POST|PUT|DELETE)\s+(\S+)", line)
            if m:
                req["method"] = m.group(1)
                req["path"] = m.group(2)
                continue

            if line.startswith("Queries in this request:"):
                val = re.search(r"(\d+)", line)
                req["queries"] = int(val.group(1)) if val else None
                continue

            if "Total DB time:" in line:
                val = re.search(r"([\d.]+)\s*ms", line)
                req["db_time_ms"] = float(val.group(1)) if val else None
                continue

        if req.get("path") is not None:
            requests.append(req)

    return requests


def p95(values: list[float]) -> float:
    """Return 95th percentile (interpolated)."""
    if not values:
        return 0.0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * 0.95
    f = int(k)
    c = f + 1 if f + 1 < len(sorted_vals) else f
    return sorted_vals[f] + (k - f) * (sorted_vals[c] - sorted_vals[f])


def main() -> int:
    base = Path(__file__).resolve().parent.parent.parent
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else base / "logs" / "query_log.txt"

    if not log_path.is_file():
        print(f"[FAIL] Log file not found: {log_path}")
        print("  Generate with ENABLE_QUERY_LOGGING=1 and load the dashboard (GET /).")
        return 1

    try:
        requests = parse_log(log_path)
    except ValueError as e:
        print(f"[FAIL] {e}")
        return 1

    dashboard_key = ("GET", "/")
    dashboard_loads = [
        r for r in requests
        if (r.get("method"), r.get("path")) == dashboard_key
    ]

    if not dashboard_loads:
        print("[INFO] No dashboard (GET /) requests in log.")
        print("  Load the main page at least once with query logging enabled.")
        return 0

    query_counts = [
        r["queries"] for r in dashboard_loads
        if r.get("queries") is not None
    ]
    db_times_ms = [
        r["db_time_ms"] for r in dashboard_loads
        if r.get("db_time_ms") is not None
    ]

    n = len(dashboard_loads)
    n_q = len(query_counts)
    n_t = len(db_times_ms)

    print("=" * 80)
    print("DASHBOARD FULL-PAGE LOAD METRICS (page /, build_dashboard)")
    print("=" * 80)
    print(f"Log: {log_path}")
    print(f"Dashboard loads (GET /): {n}")
    print()

    if query_counts:
        q_min, q_max = min(query_counts), max(query_counts)
        q_mean = sum(query_counts) / n_q
        q_p95 = p95([float(x) for x in query_counts])
        print("--- Query count per dashboard load ---")
        print(f"  Loads with count: {n_q}  min={q_min}  mean={q_mean:.1f}  max={q_max}  p95={q_p95:.1f}")
        print()
    else:
        print("--- Query count: no data ---")
        print()

    if db_times_ms:
        t_min, t_max = min(db_times_ms), max(db_times_ms)
        t_mean = sum(db_times_ms) / n_t
        t_p95 = p95(db_times_ms)
        print("--- Total DB time (ms) per dashboard load ---")
        print(f"  Loads with time: {n_t}  min={t_min:.2f}  mean={t_mean:.2f}  max={t_max:.2f}  p95={t_p95:.2f} ms")
        print()
    else:
        print("--- DB time: no data ---")
        print()

    print("Per-load snapshot (first 10):")
    for i, r in enumerate(dashboard_loads[:10], 1):
        q = r.get("queries") if r.get("queries") is not None else "-"
        t = f"{r['db_time_ms']:.2f} ms" if r.get("db_time_ms") is not None else "-"
        print(f"  {i:2d}.  queries={q}  db_time={t}")
    if len(dashboard_loads) > 10:
        print(f"  ... and {len(dashboard_loads) - 10} more")
    print()
    print("These metrics target full-page dashboard load only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
