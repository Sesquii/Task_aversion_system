#!/usr/bin/env python3
"""
Dashboard elements: call-site counts per primary element.

Targets dashboard primary elements: task list, active instances, dashboard
metrics, composite scores, execution score, relief summary, monitored metrics
config, task notes, recent/recommendations. Counts how many times each
element's backend method(s) are called from ui/dashboard.py and reports
backend query-site count per method. Complements dashboard_load_call_tree.py
by grouping by named element.

Usage:
  cd task_aversion_app
  python scripts/performance/dashboard_elements_call_sites.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# Element name -> list of (prefix, method) e.g. ("tm", "get_all")
ELEMENTS = [
    ("task list", [("tm", "get_all")]),
    ("active instances", [("im", "list_active_instances")]),
    ("dashboard metrics", [("an", "get_dashboard_metrics")]),
    ("composite scores", [("an", "get_all_scores_for_composite")]),
    ("execution score", [("an", "get_execution_score_chunked")]),
    (
        "relief summary",
        [("an", "get_relief_summary")],
    ),
    ("monitored metrics config", [("user_state", "get_monitored_metrics_config")]),
    ("task notes", [("tm", "get_task_notes"), ("tm", "get_task_notes_bulk")]),
    (
        "recent/recommendations",
        [("tm", "get_recent"), ("im", "list_recent_tasks")],
    ),
]


def count_pattern(text: str, prefix: str, method: str) -> int:
    """Count occurrences of prefix.method( in text."""
    pattern = re.escape(prefix + "." + method) + r"\s*\("
    return len(re.findall(pattern, text))


def count_query_sites_in_function(body: str) -> int:
    """Count session.query( and .execute( in a string (e.g. function body)."""
    return len(re.findall(r"session\.query\s*\(", body)) + len(
        re.findall(r"\.execute\s*\(\s*", body)
    )


def extract_methods_and_query_counts(module_path: Path) -> dict[str, int]:
    """For a backend module, map method_name -> query site count in that method."""
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
    if not dashboard_path.is_file():
        print(f"[FAIL] Dashboard not found: {dashboard_path}")
        return 1

    try:
        dashboard_text = dashboard_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"[FAIL] Could not read dashboard: {e}")
        return 1

    backend_modules = {
        "tm": root / "backend" / "task_manager.py",
        "im": root / "backend" / "instance_manager.py",
        "an": root / "backend" / "analytics.py",
        "user_state": root / "backend" / "user_state.py",
    }
    method_query_sites: dict[str, dict[str, int]] = {}
    for key, path in backend_modules.items():
        if path.is_file():
            method_query_sites[key] = extract_methods_and_query_counts(path)
        else:
            method_query_sites[key] = {}

    print("=" * 80)
    print("DASHBOARD ELEMENTS: call sites (dashboard) and backend query sites")
    print("=" * 80)
    print(f"Dashboard: {dashboard_path.relative_to(root)}")
    print()

    print(f"{'Element':<35} {'Call sites':>10} {'Backend query sites':>20}")
    print("-" * 70)

    for element_name, methods in ELEMENTS:
        call_count = 0
        query_sites = 0
        for prefix, method in methods:
            n = count_pattern(dashboard_text, prefix, method)
            call_count += n
            q = method_query_sites.get(prefix, {}).get(method, 0)
            query_sites += q
        print(f"{element_name:<35} {call_count:>10} {query_sites:>20}")

    print()
    print("[INFO] Call sites = occurrences in ui/dashboard.py; backend query sites")
    print("       = session.query / .execute inside each method (per method, not per call).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
