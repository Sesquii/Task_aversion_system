#!/usr/bin/env python3
"""
Analyze dashboard load: which backend methods are called from the dashboard.

Parses ui/dashboard.py for calls to:
  tm.*, im.*, an.*, user_state.*

Then scans backend modules (task_manager, instance_manager, analytics, user_state)
to count how many query sites (session.query, .execute) each method's function
body contains. This gives a "hot path" view: methods invoked on dashboard load
that touch the DB the most.

Usage:
  cd task_aversion_app
  python scripts/performance/dashboard_load_call_tree.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from collections import defaultdict


def extract_dashboard_calls(dashboard_path: Path) -> dict[str, set[str]]:
    """Extract backend method names called from dashboard: { 'tm': {'get_all', ...}, ... }."""
    try:
        text = dashboard_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    out: dict[str, set[str]] = defaultdict(set)
    # tm.method_name( or im.method_name( or an.method_name( or user_state.method_name(
    for prefix in ["tm.", "im.", "an.", "user_state."]:
        key = prefix.rstrip(".")
        for m in re.finditer(re.escape(prefix) + r"(\w+)\s*\(", text):
            out[key].add(m.group(1))
    return dict(out)


def count_query_sites_in_function(body: str) -> int:
    """Count session.query( and .execute( in a string (e.g. function body)."""
    return len(re.findall(r"session\.query\s*\(", body)) + len(
        re.findall(r"\.execute\s*\(\s*", body)
    )


def extract_methods_and_query_counts(module_path: Path) -> dict[str, int]:
    """For a backend module, map method_name -> approximate query site count in that method."""
    try:
        text = module_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    # Heuristic: find def method_name( and take body until next def at same indent
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

    calls = extract_dashboard_calls(dashboard_path)
    if not calls:
        print("[INFO] No tm/im/an/user_state calls found in dashboard.")
        return 0

    # Backend modules
    backend_modules = {
        "tm": root / "backend" / "task_manager.py",
        "im": root / "backend" / "instance_manager.py",
        "an": root / "backend" / "analytics.py",
        "user_state": root / "backend" / "user_state.py",
    }
    method_counts: dict[str, dict[str, int]] = {}
    for key, path in backend_modules.items():
        if path.is_file():
            method_counts[key] = extract_methods_and_query_counts(path)
        else:
            method_counts[key] = {}

    print("=" * 80)
    print("DASHBOARD LOAD CALL TREE (backend methods + query-site estimate)")
    print("=" * 80)
    print(f"Dashboard: {dashboard_path.relative_to(root)}")
    print()

    total_estimate = 0
    hot: list[tuple[str, str, int]] = []  # (prefix, method, count)

    for prefix in ["tm", "im", "an", "user_state"]:
        method_set = calls.get(prefix, set())
        counts = method_counts.get(prefix, {})
        print(f"--- {prefix} ---")
        for method in sorted(method_set):
            c = counts.get(method, 0)
            if c > 0:
                hot.append((prefix, method, c))
                total_estimate += c
            print(f"  {method}  (query sites in method: {c})")
        print()

    print("--- Hot path (methods with at least 1 query site) ---")
    hot.sort(key=lambda x: -x[2])
    for prefix, method, c in hot[:25]:
        print(f"  {c:3d}  {prefix}.{method}()")
    print()
    print("(Total is a rough sum of per-method query sites; actual requests may call some methods")
    print(" multiple times or in loops, so real query count can be higher.)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
