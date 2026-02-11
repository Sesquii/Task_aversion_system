#!/usr/bin/env python3
"""
Summarize N+1 debug log: group by request_id and caller to find which path does N calls.

Requires ENABLE_N1_DEBUG=1 and at least one request (e.g. load GET /) to produce logs.

Usage:
  set ENABLE_N1_DEBUG=1, start app, load dashboard once
  cd task_aversion_app
  python scripts/performance/n1_debug_summary.py [logs/n1_debug.log]
"""
from __future__ import annotations

import sys
from collections import Counter, defaultdict
from pathlib import Path


def main() -> int:
    base = Path(__file__).resolve().parent.parent.parent
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else base / "logs" / "n1_debug.log"
    if not log_path.is_file():
        print(f"[FAIL] Log not found: {log_path}")
        print("[INFO] Set ENABLE_N1_DEBUG=1, start app, load GET / once, then run this script.")
        return 1

    lines = log_path.read_text(encoding="utf-8", errors="replace").strip().splitlines()
    # get_instance\trequest=abc\tcaller=path:123 func\t...
    # _load_instances\trequest=abc\tcaller=path:123 func\t...
    by_request: dict[str, list[tuple[str, str]]] = defaultdict(list)
    for line in lines:
        if "\t" not in line:
            continue
        parts = line.split("\t")
        kind = parts[0]
        request_id = "no-request"
        caller = "unknown"
        for p in parts[1:]:
            if p.startswith("request="):
                request_id = p.replace("request=", "")
            elif p.startswith("caller="):
                caller = p.replace("caller=", "")
        by_request[request_id].append((kind, caller))

    print("=" * 72)
    print("N+1 DEBUG SUMMARY (by request, then by caller)")
    print("=" * 72)
    print(f"Log: {log_path}")
    print()

    # Overall caller counts (across all requests) to find the hot path
    all_callers = Counter((kind, caller) for calls in by_request.values() for kind, caller in calls)
    if all_callers:
        print("--- ALL REQUESTS: callers by (kind, caller) ---")
        for (kind, caller), count in all_callers.most_common(25):
            print(f"  {count:4d}x  {kind}  {caller}")
        print()

    for req_id in sorted(by_request.keys(), key=lambda r: -len(by_request[r])):
        calls = by_request[req_id]
        total = len(calls)
        counter = Counter((kind, caller) for kind, caller in calls)
        print(f"--- request_id={req_id}  total calls={total} ---")
        for (kind, caller), count in counter.most_common(20):
            print(f"  {count:4d}x  {kind}  {caller}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
