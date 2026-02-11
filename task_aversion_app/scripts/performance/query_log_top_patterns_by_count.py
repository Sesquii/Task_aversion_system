#!/usr/bin/env python3
"""
Query log: top query patterns by total count across all requests.

Shows which normalized SQL patterns run most often in the log (global view).
Complements query_log_n_plus_one_candidates.py (which focuses on per-request repeats).
No DB required. Needs query log.

Usage:
  cd task_aversion_app
  python scripts/performance/query_log_top_patterns_by_count.py [path/to/query_log.txt] [--top 25]
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import Counter
from pathlib import Path


def normalize_query(q: str, max_len: int = 100) -> str:
    """Collapse whitespace and strip params for pattern grouping."""
    s = re.sub(r"\s*\|\s*Params:.*$", "", q, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    return (s[:max_len] + "...") if len(s) > max_len else s


def parse_log(path: Path) -> list[dict]:
    """Parse log file. Returns list of requests with path, method, query_list."""
    text = path.read_text(encoding="utf-8", errors="replace")
    requests: list[dict] = []
    for block in re.split(r"\n={80}\n", text):
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
        description="Top query patterns by total count across query log"
    )
    parser.add_argument("log_path", nargs="?", default=None)
    parser.add_argument("--top", type=int, default=25, help="Number of patterns to show")
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

    pattern_counter: Counter[str] = Counter()
    for req in requests:
        for q in req.get("query_list") or []:
            pattern_counter[normalize_query(q)] += 1

    total = sum(pattern_counter.values())
    print("=" * 72)
    print("TOP QUERY PATTERNS BY TOTAL COUNT")
    print("=" * 72)
    print(f"Log: {log_path}")
    print(f"Total queries: {total}  Requests: {len(requests)}")
    print()
    for i, (pat, cnt) in enumerate(pattern_counter.most_common(args.top), 1):
        pct = 100.0 * cnt / total if total else 0
        preview = pat[:75] + "..." if len(pat) > 75 else pat
        print(f"  {cnt:6d}  ({pct:5.1f}%)  {preview}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
