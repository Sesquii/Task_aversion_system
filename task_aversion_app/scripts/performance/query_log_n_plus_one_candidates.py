#!/usr/bin/env python3
"""
Identify N+1 query candidates from the query log.

For each request in the log, finds query patterns that repeat many times
in the same request (same normalized SQL). Those are likely N+1: one query
executed in a loop. Use this to target which code paths to fix.

Requires ENABLE_QUERY_LOGGING and logs/query_log.txt.

Usage:
  cd task_aversion_app
  python scripts/performance/query_log_n_plus_one_candidates.py [path/to/query_log.txt] [--min-repeat 5] [--top 20]
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
    """Parse log file. Returns list of requests, each with path, method, query_list."""
    text = path.read_text(encoding="utf-8", errors="replace")
    requests: list[dict] = []
    blocks = re.split(r"\n={80}\n", text)

    for block in blocks:
        block = block.strip()
        if not block:
            continue
        req: dict = {"path": None, "method": "GET", "query_list": []}
        for line in block.split("\n"):
            line = line.strip()
            if not line:
                continue
            m = re.match(r"\[\d{4}-\d{2}-\d{2}[^\]]*\]\s+(GET|POST|PUT|DELETE)\s+(\S+)", line)
            if m:
                req["method"] = m.group(1)
                req["path"] = m.group(2)
                continue
            if re.match(r"^\s*\d+\.\s+", line):
                q = re.sub(r"^\s*\d+\.\s+", "", line)
                req["query_list"].append(q)
        if req.get("path") is not None:
            requests.append(req)
    return requests


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find N+1 candidates: same query repeated many times in one request"
    )
    parser.add_argument(
        "log_path",
        nargs="?",
        default=None,
        help="Path to query_log.txt (default: task_aversion_app/logs/query_log.txt)",
    )
    parser.add_argument(
        "--min-repeat",
        type=int,
        default=5,
        help="Minimum repeats in one request to flag as N+1 candidate (default 5)",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=20,
        help="Max number of patterns to show per path (default 20)",
    )
    args = parser.parse_args()

    base = Path(__file__).resolve().parent.parent.parent
    log_path = Path(args.log_path) if args.log_path else base / "logs" / "query_log.txt"
    if not log_path.is_file():
        print(f"[FAIL] Log file not found: {log_path}")
        return 1

    requests = parse_log(log_path)
    if not requests:
        print("[INFO] No request entries found in log.")
        return 0

    # Per path: for each normalized pattern, max count in any single request and total
    path_max: dict[str, dict[str, tuple[int, int]]] = defaultdict(lambda: defaultdict(lambda: (0, 0)))
    path_request_count: Counter[str] = Counter()

    for req in requests:
        key = f"{req['method']} {req['path']}"
        path_request_count[key] += 1
        query_list = req.get("query_list") or []
        if not query_list:
            continue
        within_req: Counter[str] = Counter()
        for q in query_list:
            norm = normalize_query(q)
            within_req[norm] += 1
        for norm, count in within_req.items():
            if count >= args.min_repeat:
                prev_max, prev_total = path_max[key][norm]
                path_max[key][norm] = (max(prev_max, count), prev_total + count)

    # Drop default dict for iteration
    path_max = {k: dict(v) for k, v in path_max.items() if v}

    print("=" * 72)
    print("N+1 CANDIDATES (same query repeated many times in one request)")
    print("=" * 72)
    print(f"Log: {log_path}")
    print(f"Min repeats in one request: {args.min_repeat}")
    print()

    for path_key in sorted(
        path_max.keys(),
        key=lambda p: -max((c[0] for c in path_max[p].values()), default=0),
    ):
        entries = path_max[path_key]
        sorted_entries = sorted(
            entries.items(),
            key=lambda x: -x[1][0],
        )[: args.top]
        print(f"--- {path_key} (n={path_request_count[path_key]} requests) ---")
        for norm, (max_in_req, total) in sorted_entries:
            print(f"  {max_in_req:4d}x in one request  (total in path: {total})  {norm}")
        print()

    print("[INFO] Use these patterns to search the codebase for the loop that runs this query.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
