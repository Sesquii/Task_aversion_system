#!/usr/bin/env python3
"""
Parse query_log.txt and produce baseline metrics for SQL optimization.

Outputs:
  - Per path: request count, min/mean/max queries, min/mean/max DB time (ms)
  - Most frequent query patterns (helps spot N+1: same pattern repeated many times)

Usage:
  python scripts/analyze_query_baseline.py [path/to/query_log.txt]
  Default: task_aversion_app/logs/query_log.txt
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


def parse_log(path: Path) -> tuple[list[dict], Counter[str]]:
    """Parse log file. Returns (list of request dicts, Counter of normalized patterns)."""
    text = path.read_text(encoding="utf-8", errors="replace")
    pattern_counter: Counter[str] = Counter()
    requests: list[dict] = []

    # Split by separator blocks
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

            # [timestamp] METHOD /path
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

            # Query detail lines: "  1. SELECT ..."
            if re.match(r"^\s*\d+\.\s+", line):
                q = re.sub(r"^\s*\d+\.\s+", "", line)
                pattern_counter[normalize_query(q)] += 1

        if req.get("path") is not None:
            requests.append(req)

    return requests, pattern_counter


def main() -> int:
    base = Path(__file__).resolve().parent.parent
    log_path = Path(sys.argv[1]) if len(sys.argv) > 1 else base / "logs" / "query_log.txt"

    if not log_path.is_file():
        print(f"[FAIL] Log file not found: {log_path}")
        return 1

    requests, patterns = parse_log(log_path)
    if not requests:
        print("[INFO] No request entries found in log.")
        return 0

    # Per-path stats
    by_path: dict[str, list[dict]] = defaultdict(list)
    for r in requests:
        key = f"{r['method']} {r['path']}"
        by_path[key].append(r)

    def _q(r: dict) -> int:
        return r["queries"] if r.get("queries") is not None else 0

    def _t(r: dict) -> float:
        return r["db_time_ms"] if r.get("db_time_ms") is not None else 0.0

    print("=" * 80)
    print("BASELINE: Per-path stats (use to drive refactors and compare after fixes)")
    print("=" * 80)

    for path_key in sorted(by_path.keys()):
        rows = by_path[path_key]
        qs = [_q(r) for r in rows]
        ts = [_t(r) for r in rows if r.get("db_time_ms") is not None]

        q_min, q_max = (min(qs), max(qs)) if qs else (0, 0)
        q_avg = sum(qs) / len(qs) if qs else 0.0

        t_min = min(ts) if ts else 0.0
        t_max = max(ts) if ts else 0.0
        t_avg = sum(ts) / len(ts) if ts else 0.0

        print(f"\n{path_key}")
        print(f"  Requests: {len(rows)}")
        print(f"  Queries:  min={q_min} mean={q_avg:.1f} max={q_max}")
        if ts:
            print(f"  DB time:  min={t_min:.1f}ms mean={t_avg:.1f}ms max={t_max:.1f}ms")

    print("\n" + "=" * 80)
    print("Most repeated query patterns (N+1: same pattern many times)")
    print("=" * 80)

    for pat, cnt in patterns.most_common(15):
        if cnt < 2:
            break
        preview = (pat[:100] + "...") if len(pat) > 100 else pat
        print(f"  {cnt:5d}x  {preview}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
