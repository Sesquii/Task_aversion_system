#!/usr/bin/env python3
"""
Produce a one-page prioritized optimization checklist from the query log.

Parses logs/query_log.txt and N+1-style repeats, then prints a numbered
checklist: path, worst repeat count, and suggested next step (e.g. run
n_plus_one_call_sites.py, fix cache, batch loads). No DB required.
Needs query log.

Usage:
  cd task_aversion_app
  python scripts/performance/optimization_priority_from_log.py [path/to/query_log.txt] [--min-repeat 5]
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path


def normalize_query(q: str, max_len: int = 120) -> str:
    """Collapse whitespace and strip params for pattern grouping."""
    s = re.sub(r"\s*\|\s*Params:.*$", "", q, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    return (s[:max_len] + "...") if len(s) > max_len else s


def parse_log(path: Path) -> list[dict]:
    """Parse log file. Returns list of requests with path, method, query_list, db_time_ms."""
    text = path.read_text(encoding="utf-8", errors="replace")
    requests: list[dict] = []
    for block in re.split(r"\n={80}\n", text):
        block = block.strip()
        if not block:
            continue
        req: dict = {
            "path": None,
            "method": "GET",
            "query_list": [],
            "db_time_ms": None,
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
    parser = argparse.ArgumentParser(
        description="Prioritized optimization checklist from query log"
    )
    parser.add_argument("log_path", nargs="?", default=None)
    parser.add_argument(
        "--min-repeat",
        type=int,
        default=5,
        help="Min repeats in one request to flag as N+1 candidate",
    )
    args = parser.parse_args()

    base = Path(__file__).resolve().parent.parent.parent
    log_path = Path(args.log_path) if args.log_path else base / "logs" / "query_log.txt"
    if not log_path.is_file():
        print(f"[FAIL] Log file not found: {log_path}")
        return 1

    requests = parse_log(log_path)
    if not requests:
        print("[INFO] No request entries in log.")
        return 0

    # Path -> (mean queries, mean db_time_ms)
    path_stats: dict[str, list[dict]] = defaultdict(list)
    for r in requests:
        key = f"{r['method']} {r['path']}"
        path_stats[key].append(r)

    # N+1 style: per path, max repeat count and pattern
    path_max_repeat: list[tuple[str, int, str, float]] = []
    for path_key, rows in path_stats.items():
        max_repeat = 0
        worst_pattern = ""
        mean_time = 0.0
        times = [r["db_time_ms"] for r in rows if r.get("db_time_ms") is not None]
        mean_time = sum(times) / len(times) if times else 0.0
        for r in rows:
            within: Counter[str] = Counter()
            for q in r.get("query_list") or []:
                within[normalize_query(q)] += 1
            for pat, cnt in within.items():
                if cnt >= args.min_repeat and cnt > max_repeat:
                    max_repeat = cnt
                    worst_pattern = pat
        if max_repeat > 0:
            path_max_repeat.append((path_key, max_repeat, worst_pattern, mean_time))

    path_max_repeat.sort(key=lambda x: -x[1])

    print("=" * 72)
    print("OPTIMIZATION PRIORITY CHECKLIST (from query log)")
    print("=" * 72)
    print(f"Log: {log_path}")
    print(f"Min repeat to flag: {args.min_repeat}")
    print()
    print("--- Prioritized by worst N+1 repeat per path ---")
    for i, (path_key, repeat, pattern, mean_t) in enumerate(path_max_repeat, 1):
        hint = "task_instances"
        if "task_instances" in pattern:
            hint = "See n_plus_one_call_sites.py; consider cache or get_instances_bulk"
        elif "pg_catalog.pg_class" in pattern:
            hint = "PostgreSQL metadata; consider caching schema or batching reflection"
        elif "PRAGMA" in pattern:
            hint = "SQLite PRAGMA; not used in production PostgreSQL"
        else:
            hint = "Run query_log_n_plus_one_trace.py for code-search hint"
        preview = pattern[:55] + "..." if len(pattern) > 55 else pattern
        print(f"  {i}. {path_key}")
        print(f"     Worst: {repeat}x in one request  mean_db_time={mean_t:.1f}ms")
        print(f"     Pattern: {preview}")
        print(f"     Next: {hint}")
        print()
    if not path_max_repeat:
        print("  No N+1 candidates above threshold. Run query_log_n_plus_one_candidates.py for details.")
    print()
    print("Follow-up: Batch 1 (n_plus_one_call_sites.py), Batch 4 (pg_explain_*) when DB available.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
