#!/usr/bin/env python3
"""
Full-page dashboard load: request query sequence from the query log.

Targets the main dashboard (page /, built by build_dashboard in ui/dashboard.py).
Parses logs/query_log.txt and, for each GET / request, prints the ordered sequence
of queries executed during that dashboard load. This traces the full request path
of backend DB calls for full-page dashboard load and helps correlate with the
static call tree (dashboard_load_call_tree.py).

Requires ENABLE_QUERY_LOGGING and at least one dashboard load to be logged.

Usage:
  cd task_aversion_app
  python scripts/performance/dashboard_request_query_sequence.py [path/to/query_log.txt] [--max-requests N] [--normalize]
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def normalize_query(q: str) -> str:
    """Strip param tail and collapse whitespace for pattern display."""
    s = re.sub(r"\s*\|\s*Params:.*$", "", q, flags=re.IGNORECASE)
    s = re.sub(r"\s+", " ", s).strip()
    return (s[:120] + "...") if len(s) > 120 else s


def parse_log(path: Path) -> list[dict]:
    """Parse query_log.txt; return list of request dicts with path, method, query_list."""
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

        req: dict = {"path": None, "method": "GET", "query_list": []}
        in_details = False

        for line in block.split("\n"):
            line_stripped = line.strip()
            if not line_stripped:
                continue

            m = re.match(r"\[\d{4}-\d{2}-\d{2}[^\]]*\]\s+(GET|POST|PUT|DELETE)\s+(\S+)", line_stripped)
            if m:
                req["method"] = m.group(1)
                req["path"] = m.group(2)
                in_details = False
                continue

            if "Query Details" in line_stripped:
                in_details = True
                continue

            if in_details and re.match(r"^\s*\d+\.\s+", line_stripped):
                q = re.sub(r"^\s*\d+\.\s+", "", line_stripped)
                req["query_list"].append(q)
                continue

            if line_stripped.startswith("Request ID:") or line_stripped.startswith("Queries in this request:"):
                in_details = False
                continue

        if req.get("path") is not None:
            requests.append(req)

    return requests


def main() -> int:
    base = Path(__file__).resolve().parent.parent.parent
    argv = sys.argv[1:]
    log_path: Path = base / "logs" / "query_log.txt"
    max_requests = 3
    normalize = False

    i = 0
    while i < len(argv):
        if argv[i] == "--max-requests" and i + 1 < len(argv):
            try:
                max_requests = max(1, int(argv[i + 1]))
            except ValueError:
                print("[FAIL] --max-requests requires an integer")
                return 1
            i += 2
            continue
        if argv[i] == "--normalize":
            normalize = True
            i += 1
            continue
        if not argv[i].startswith("-"):
            log_path = Path(argv[i])
            i += 1
            continue
        i += 1

    if not log_path.is_file():
        print(f"[FAIL] Log file not found: {log_path}")
        print("  Generate with ENABLE_QUERY_LOGGING=1 and load the dashboard (GET /).")
        return 1

    try:
        requests = parse_log(log_path)
    except ValueError as e:
        print(f"[FAIL] {e}")
        return 1

    dashboard_loads = [
        r for r in requests
        if (r.get("method"), r.get("path")) == ("GET", "/")
    ]

    if not dashboard_loads:
        print("[INFO] No dashboard (GET /) requests in log.")
        print("  Load the main page at least once with query logging enabled.")
        return 0

    print("=" * 80)
    print("DASHBOARD FULL-PAGE LOAD: REQUEST QUERY SEQUENCE (page /, build_dashboard)")
    print("=" * 80)
    print(f"Log: {log_path}")
    print(f"Showing first {min(max_requests, len(dashboard_loads))} dashboard load(s).")
    if normalize:
        print("Output: normalized query patterns (Params stripped, whitespace collapsed).")
    print()

    for idx, req in enumerate(dashboard_loads[:max_requests], 1):
        qlist = req.get("query_list") or []
        print(f"--- Dashboard load #{idx} ({len(qlist)} queries) ---")
        for i, q in enumerate(qlist, 1):
            display = normalize_query(q) if normalize else (q[:200] + "..." if len(q) > 200 else q)
            print(f"  {i:3d}. {display}")
        print()

    print("This sequence traces the full request path of DB calls for full-page dashboard load.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
