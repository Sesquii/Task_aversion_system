#!/usr/bin/env python3
"""
Suggest code search targets for N+1 patterns from the query log.

Reads the same log as query_log_n_plus_one_candidates.py and prints
suggested grep/search commands for the top repeated pattern per path.
Use after running query_log_n_plus_one_candidates.py to trace the source.

Requires ENABLE_QUERY_LOGGING and logs/query_log.txt.

Usage:
  cd task_aversion_app
  python scripts/performance/query_log_n_plus_one_trace.py [path/to/query_log.txt]
"""
from __future__ import annotations

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
    base = Path(__file__).resolve().parent.parent.parent
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else base / "logs" / "query_log.txt"
    if not log_path.is_file():
        print(f"[FAIL] Log file not found: {log_path}")
        return 1

    requests = parse_log(log_path)
    if not requests:
        print("[INFO] No request entries found in log.")
        return 0

    min_repeat = 5
    path_max: dict[str, dict[str, tuple[int, int]]] = defaultdict(
        lambda: defaultdict(lambda: (0, 0))
    )

    for req in requests:
        key = f"{req['method']} {req['path']}"
        query_list = req.get("query_list") or []
        if not query_list:
            continue
        within_req: Counter[str] = Counter()
        for q in query_list:
            norm = normalize_query(q)
            within_req[norm] += 1
        for norm, count in within_req.items():
            if count >= min_repeat:
                prev_max, prev_total = path_max[key][norm]
                path_max[key][norm] = (max(prev_max, count), prev_total + count)

    path_max = {k: dict(v) for k, v in path_max.items() if v}
    if not path_max:
        print("[INFO] No N+1 candidates (min repeat 5) in log.")
        return 0

    # Build search hints for the worst pattern per path
    print("=" * 72)
    print("N+1 TRACE: suggested code search for top pattern per path")
    print("=" * 72)
    print(f"Log: {log_path}")
    print()

    for path_key in sorted(
        path_max.keys(),
        key=lambda p: -max((c[0] for c in path_max[p].values()), default=0),
    ):
        entries = path_max[path_key]
        if not entries:
            continue
        norm, (max_in_req, _total) = max(entries.items(), key=lambda x: x[1][0])
        # Suggest search terms from the normalized query
        if "task_instances" in norm and "SELECT" in norm:
            hint = (
                "Likely _load_instances (Analytics) or get_instance/get_instances_bulk (InstanceManager). "
                "Search: _load_instances( | get_instance( | session.query(TaskInstance)"
            )
        elif "pg_catalog.pg_class" in norm:
            hint = "PostgreSQL metadata (e.g. reflection). Search: pg_class | inspect | get_columns"
        elif "PRAGMA" in norm:
            hint = "SQLite PRAGMA (table_info). Search: table_info | PRAGMA"
        else:
            hint = "Search codebase for the table/entity name in the query."
        print(f"--- {path_key} (worst: {max_in_req}x) ---")
        print(f"  Pattern: {norm[:80]}...")
        print(f"  [TRACE] {hint}")
        print()

    return 0


if __name__ == "__main__":
    sys.exit(main())
