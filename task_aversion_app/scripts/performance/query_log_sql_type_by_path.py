#!/usr/bin/env python3
"""
Query log: per-path breakdown by SQL type (SELECT, INSERT, UPDATE, DELETE).

Focus: **Query log** parsing. Complements analyze_query_log_bottlenecks.py
(which reports paths by total query count and DB time, plus overall type
breakdown) by giving per-path, per-SQL-type counts. Use to see which routes
drive which kinds of statements (e.g. dashboard = mostly SELECTs; save = INSERT/UPDATE).

Outputs actionable data: for each path, counts per SQL type and mean DB time.
Requires ENABLE_QUERY_LOGGING and logs/query_log.txt. No DB required.

Usage:
  cd task_aversion_app
  python scripts/performance/query_log_sql_type_by_path.py [path/to/query_log.txt]
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
    """Parse query_log.txt. Returns list of request dicts with path, method, query_list, db_time_ms."""
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

    # path_key -> list of (type_counts dict, db_time_ms)
    path_data: dict[str, list[tuple[dict[str, int], float]]] = defaultdict(list)
    for r in requests:
        path_key = f"{r['method']} {r['path']}"
        type_counts: dict[str, int] = defaultdict(int)
        for q in r["query_list"]:
            type_counts[classify_query(q)] += 1
        db_ms = r["db_time_ms"] if r.get("db_time_ms") is not None else 0.0
        path_data[path_key].append((dict(type_counts), db_ms))

    # Aggregate per path: total count per type, mean DB time, request count
    sql_types = ["SELECT", "INSERT", "UPDATE", "DELETE", "PRAGMA", "other"]
    path_stats: list[tuple[str, int, dict[str, int], float]] = []
    for path_key, rows in path_data.items():
        n_requests = len(rows)
        total_by_type: dict[str, int] = defaultdict(int)
        for type_counts, _ in rows:
            for t, c in type_counts.items():
                total_by_type[t] += c
        times = [db_ms for _, db_ms in rows if db_ms > 0]
        mean_db = sum(times) / len(times) if times else 0.0
        total_q = sum(total_by_type.values())
        path_stats.append((path_key, n_requests, dict(total_by_type), mean_db))

    path_stats.sort(key=lambda x: (-sum(x[2].values()), -x[3]))

    print("=" * 72)
    print("QUERY LOG: SQL TYPE BY PATH (actionable counts per path)")
    print("=" * 72)
    print(f"Log: {log_path}")
    print(f"Total requests: {len(requests)}")
    print()

    print("--- Per path: request count, counts by SQL type, mean DB time (ms) ---")
    for path_key, n_req, by_type, mean_db in path_stats[:25]:
        total = sum(by_type.values())
        parts = [f"{t}={by_type.get(t, 0)}" for t in sql_types if by_type.get(t, 0) > 0]
        type_str = "  ".join(parts) if parts else "0"
        print(f"  n={n_req:4d}  total={total:5d}  mean_DB={mean_db:8.1f} ms  {path_key}")
        print(f"           {type_str}")
    print()

    # Summary table: path vs type matrix (top paths, top types)
    print("--- Summary: SELECT/INSERT/UPDATE/DELETE by path (top 15 paths) ---")
    print(f"  {'Path':<45} {'SELECT':>8} {'INSERT':>8} {'UPDATE':>8} {'DELETE':>8}")
    print("-" * 72)
    for path_key, n_req, by_type, _ in path_stats[:15]:
        short = (path_key[:43] + "..") if len(path_key) > 45 else path_key
        print(
            f"  {short:<45} {by_type.get('SELECT', 0):>8} {by_type.get('INSERT', 0):>8} "
            f"{by_type.get('UPDATE', 0):>8} {by_type.get('DELETE', 0):>8}"
        )
    print()
    print("[INFO] Focus: query log (per-path SQL type breakdown). Actionable counts.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
