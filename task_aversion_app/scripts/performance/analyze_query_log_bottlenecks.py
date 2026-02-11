#!/usr/bin/env python3
"""
Parse query_log.txt and highlight potential bottlenecks.

Builds on the same log format as scripts/analyze_query_baseline.py.
Adds:
  - Paths ranked by mean/max query count and DB time (bottleneck candidates)
  - PRAGMA vs SELECT vs other query type breakdown (if present in log)
  - One-line bottleneck summary for the main dashboard path

Requires ENABLE_QUERY_LOGGING and at least one GET / (dashboard) load to be logged.

Usage:
  cd task_aversion_app
  python scripts/performance/analyze_query_log_bottlenecks.py [path/to/query_log.txt]
"""
from __future__ import annotations

import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


def normalize_query(q: str) -> str:
    """Remove param tail and collapse whitespace for pattern grouping."""
    s = re.sub(r"\s*\|\s*Params:.*$", "", q, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    return (s[:150] + "...") if len(s) > 150 else s


def parse_log(path: Path) -> tuple[list[dict], Counter[str], list[str]]:
    """Parse log file. Returns (requests, pattern_counter, list of raw query strings)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    pattern_counter: Counter[str] = Counter()
    requests: list[dict] = []
    all_queries: list[str] = []

    blocks = re.split(r"\n={80}\n", text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue

        req: dict = {"path": None, "method": "GET", "queries": None, "db_time_ms": None, "query_list": []}

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

            if re.match(r"^\s*\d+\.\s+", line):
                q = re.sub(r"^\s*\d+\.\s+", "", line)
                norm = normalize_query(q)
                pattern_counter[norm] += 1
                req["query_list"].append(q)
                all_queries.append(q)

        if req.get("path") is not None:
            requests.append(req)

    return requests, pattern_counter, all_queries


def classify_query(q: str) -> str:
    """Classify as PRAGMA, SELECT, INSERT, UPDATE, DELETE, other."""
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


def main() -> int:
    base = Path(__file__).resolve().parent.parent.parent
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else base / "logs" / "query_log.txt"

    if not log_path.is_file():
        print(f"[FAIL] Log file not found: {log_path}")
        print(f"  Generate it by loading the app with ENABLE_QUERY_LOGGING=1 and opening the dashboard.")
        return 1

    requests, patterns, all_queries = parse_log(log_path)
    if not requests:
        print("[INFO] No request entries found in log.")
        return 0

    by_path: dict[str, list[dict]] = defaultdict(list)
    for r in requests:
        key = f"{r['method']} {r['path']}"
        by_path[key].append(r)

    def _q(r: dict) -> int:
        return r["queries"] if r.get("queries") is not None else 0

    def _t(r: dict) -> float:
        return r["db_time_ms"] if r.get("db_time_ms") is not None else 0.0

    # --- Bottleneck: paths by mean queries and mean DB time ---
    path_stats: list[tuple[str, int, float, float, float]] = []
    for path_key, rows in by_path.items():
        qs = [_q(r) for r in rows]
        ts = [_t(r) for r in rows if r.get("db_time_ms") is not None]
        n = len(rows)
        mean_q = sum(qs) / n if qs else 0.0
        max_q = max(qs) if qs else 0
        mean_t = sum(ts) / len(ts) if ts else 0.0
        path_stats.append((path_key, n, mean_q, max_q, mean_t))
    path_stats.sort(key=lambda x: (-x[2], -x[4]))  # by mean queries, then mean time

    print("=" * 80)
    print("QUERY LOG BOTTLENECK ANALYSIS")
    print("=" * 80)
    print(f"Log: {log_path}")
    print(f"Total requests: {len(requests)}")
    print()

    print("--- Paths by load (mean queries, mean DB time) ---")
    for path_key, n, mean_q, max_q, mean_t in path_stats[:20]:
        print(f"  {mean_q:8.1f} mean queries  {mean_t:8.1f} ms mean DB   max_q={max_q}  n={n}  {path_key}")
    print()

    # Dashboard-specific summary
    dashboard_key = "GET /"
    if dashboard_key in by_path:
        rows = by_path[dashboard_key]
        qs = [_q(r) for r in rows]
        ts = [_t(r) for r in rows if r.get("db_time_ms") is not None]
        print("--- Dashboard (GET /) summary ---")
        print(f"  Requests: {len(rows)}")
        print(f"  Queries: min={min(qs)} mean={sum(qs)/len(qs):.1f} max={max(qs)}")
        if ts:
            print(f"  DB time:  min={min(ts):.1f}ms mean={sum(ts)/len(ts):.1f}ms max={max(ts):.1f}ms")
        print()
    else:
        print("--- Dashboard (GET /) not in log; load the main page once with query logging on. ---")
        print()

    # Query type breakdown (PRAGMA vs SELECT vs other)
    type_counts: Counter[str] = Counter()
    for q in all_queries:
        type_counts[classify_query(q)] += 1
    if type_counts:
        print("--- Query type breakdown (all requests) ---")
        for typ in ["SELECT", "PRAGMA", "INSERT", "UPDATE", "DELETE", "other"]:
            c = type_counts.get(typ, 0)
            if c > 0:
                pct = 100.0 * c / len(all_queries)
                print(f"  {typ:8s}  {c:6d}  ({pct:.1f}%)")
        print()

    print("--- Most repeated patterns (N+1 candidates) ---")
    for pat, cnt in patterns.most_common(10):
        if cnt < 2:
            break
        preview = (pat[:90] + "...") if len(pat) > 90 else pat
        print(f"  {cnt:5d}x  {preview}")
    print()
    print("Run after loading the dashboard to see current bottleneck metrics.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
