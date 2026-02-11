#!/usr/bin/env python3
"""
Dashboard elements: dashboard metrics, composite scores, execution score, relief summary.

Targets: an.get_dashboard_metrics, an.get_all_scores_for_composite,
an.get_execution_score_chunked, relief summary (an.get_relief_summary and
get_targeted_metric_values). Counts call sites in ui/dashboard.py and
query sites in backend analytics methods. Use to quantify load from the
metrics panel and composite/execution/relief calculations.

Usage:
  cd task_aversion_app
  python scripts/performance/dashboard_metrics_relief_composite.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Element label -> (prefix, method_name)
ELEMENTS = [
    ("dashboard metrics", "an", "get_dashboard_metrics"),
    ("composite scores", "an", "get_all_scores_for_composite"),
    ("execution score", "an", "get_execution_score_chunked"),
    ("relief summary", "an", "get_relief_summary"),
]


def count_pattern(text: str, prefix: str, method: str) -> int:
    """Count occurrences of prefix.method( in text."""
    pattern = re.escape(prefix + "." + method) + r"\s*\("
    return len(re.findall(pattern, text))


def count_query_sites_in_function(body: str) -> int:
    """Count session.query( and .execute( in function body."""
    return len(re.findall(r"session\.query\s*\(", body)) + len(
        re.findall(r"\.execute\s*\(\s*", body)
    )


def extract_methods_and_query_counts(module_path: Path) -> dict[str, int]:
    """Map method_name -> query site count for backend module."""
    try:
        text = module_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    method_counts: dict[str, int] = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        line = lines[i]
        m = re.match(r"^\s*def\s+(\w+)\s*\(", line)
        if m:
            name = m.group(1)
            indent = len(line) - len(line.lstrip())
            body_lines = [line]
            j = i + 1
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
            body = "\n".join(body_lines)
            method_counts[name] = count_query_sites_in_function(body)
            i = j
        else:
            i += 1
    return method_counts


def main() -> int:
    root = Path(__file__).resolve().parent.parent.parent
    dashboard_path = root / "ui" / "dashboard.py"
    analytics_path = root / "backend" / "analytics.py"

    if not dashboard_path.is_file():
        print(f"[FAIL] Dashboard not found: {dashboard_path}")
        return 1
    if not analytics_path.is_file():
        print(f"[FAIL] Analytics module not found: {analytics_path}")
        return 1

    try:
        dashboard_text = dashboard_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"[FAIL] Could not read dashboard: {e}")
        return 1

    an_counts = extract_methods_and_query_counts(analytics_path)

    # get_targeted_metric_values is defined in dashboard.py and calls
    # get_relief_summary, get_dashboard_metrics, get_all_scores_for_composite
    targeted_calls = len(
        re.findall(r"get_targeted_metric_values\s*\(", dashboard_text)
    )

    print("=" * 80)
    print("DASHBOARD: metrics, composite scores, execution score, relief summary")
    print("=" * 80)
    print(f"Dashboard: {dashboard_path.relative_to(root)}")
    print()

    print(f"{'Element':<28} {'Call sites':>10} {'Backend query sites':>20}")
    print("-" * 62)

    for label, prefix, method in ELEMENTS:
        call_count = count_pattern(dashboard_text, prefix, method)
        query_sites = an_counts.get(method, 0)
        print(f"{label:<28} {call_count:>10} {query_sites:>20}")

    print(f"{'get_targeted_metric_values (dashboard)':<28} {targeted_calls:>10} {'(calls an.* above)':>20}")
    print()
    print("[INFO] get_targeted_metric_values is a dashboard helper that batches")
    print("       get_relief_summary, get_dashboard_metrics, get_all_scores_for_composite.")
    print("[INFO] Use query log or EXPLAIN to measure actual DB time for these paths.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
