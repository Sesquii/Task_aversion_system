#!/usr/bin/env python3
"""
Analytics composite score load and emotional flow: backend methods and query sites.

Targets the Analytics area elements: (1) composite score load (get_all_scores_for_composite,
calculate_composite_score, and their call sites in backend/analytics.py), (2) emotional
flow (get_emotional_flow_data and its call sites). Statically lists these methods and
counts query sites (session.query, .execute) in each for actionable bottleneck hints.

Static analysis; no DB or live app required. Run from task_aversion_app:
  python scripts/performance/analytics_composite_emotional_sites.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def count_query_sites_in_function(body: str) -> int:
    """Count session.query( and .execute( in a string (function body)."""
    return len(re.findall(r"session\.query\s*\(", body)) + len(
        re.findall(r"\.execute\s*\(\s*", body)
    )


def get_function_body(lines: list[str], def_index: int) -> tuple[str, int]:
    """Return (body_string, next_line_index). Body from def line to next same-level def."""
    line = lines[def_index]
    m = re.match(r"^\s*def\s+\w+", line)
    if not m:
        return "", def_index + 1
    indent = len(line) - len(line.lstrip())
    body_lines = [line]
    j = def_index + 1
    while j < len(lines):
        next_line = lines[j]
        if next_line.strip() == "":
            body_lines.append(next_line)
            j += 1
            continue
        next_indent = len(next_line) - len(next_line.lstrip())
        if next_line.strip().startswith("def ") and next_indent <= indent:
            break
        body_lines.append(next_line)
        j += 1
    return "\n".join(body_lines), j


def extract_analytics_method_sites(analytics_path: Path) -> dict[str, int]:
    """Map Analytics method name -> query site count for methods we care about."""
    target_methods = {
        "get_all_scores_for_composite",
        "calculate_composite_score",
        "get_emotional_flow_data",
    }
    try:
        text = analytics_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    lines = text.splitlines()
    result: dict[str, int] = {}
    i = 0
    while i < len(lines):
        m = re.match(r"^\s*def\s+(\w+)\s*\(", lines[i])
        if m:
            name = m.group(1)
            body, i = get_function_body(lines, i)
            if name in target_methods:
                result[name] = count_query_sites_in_function(body)
        else:
            i += 1
    return result


def main() -> int:
    root = Path(__file__).resolve().parent.parent.parent
    analytics_py = root / "backend" / "analytics.py"
    if not analytics_py.is_file():
        print(f"[FAIL] Not found: {analytics_py}")
        return 1

    sites = extract_analytics_method_sites(analytics_py)
    print("=" * 72)
    print("ANALYTICS COMPOSITE SCORE LOAD AND EMOTIONAL FLOW (query sites)")
    print("=" * 72)
    print("Target: composite score load (get_all_scores_for_composite, calculate_composite_score),")
    print("  emotional flow (get_emotional_flow_data).")
    print()
    print("--- Composite score load ---")
    for name in ("get_all_scores_for_composite", "calculate_composite_score"):
        c = sites.get(name, 0)
        print(f"  Analytics.{name}():  {c} query sites")
    print("--- Emotional flow ---")
    c = sites.get("get_emotional_flow_data", 0)
    print(f"  Analytics.get_emotional_flow_data():  {c} query sites")
    print()
    print("[INFO] Static scan of backend/analytics.py only. High counts may indicate")
    print("  N+1 or multiple round-trips; consider batching or caching.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
