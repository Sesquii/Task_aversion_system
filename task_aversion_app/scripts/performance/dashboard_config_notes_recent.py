#!/usr/bin/env python3
"""
Dashboard elements: monitored metrics config, task notes, recent/recommendations.

Targets: user_state.get_monitored_metrics_config, tm.get_task_notes,
tm.get_task_notes_bulk, tm.get_recent, im.list_recent_tasks. Counts call
sites in ui/dashboard.py and query sites in the corresponding backend
methods. Use to isolate load from metrics config, task notes, and
recent/recommendations sections.

Usage:
  cd task_aversion_app
  python scripts/performance/dashboard_config_notes_recent.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

# (element label, prefix, method_name)
ELEMENTS = [
    ("monitored metrics config", "user_state", "get_monitored_metrics_config"),
    ("task notes (single)", "tm", "get_task_notes"),
    ("task notes (bulk)", "tm", "get_task_notes_bulk"),
    ("recent (tasks)", "tm", "get_recent"),
    ("recent/recommendations (instances)", "im", "list_recent_tasks"),
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
    user_state_path = root / "backend" / "user_state.py"
    tm_path = root / "backend" / "task_manager.py"
    im_path = root / "backend" / "instance_manager.py"

    if not dashboard_path.is_file():
        print(f"[FAIL] Dashboard not found: {dashboard_path}")
        return 1

    try:
        dashboard_text = dashboard_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"[FAIL] Could not read dashboard: {e}")
        return 1

    us_counts = (
        extract_methods_and_query_counts(user_state_path)
        if user_state_path.is_file()
        else {}
    )
    tm_counts = (
        extract_methods_and_query_counts(tm_path) if tm_path.is_file() else {}
    )
    im_counts = (
        extract_methods_and_query_counts(im_path) if im_path.is_file() else {}
    )
    backend_counts = {
        "user_state": us_counts,
        "tm": tm_counts,
        "im": im_counts,
    }

    print("=" * 80)
    print("DASHBOARD: monitored metrics config, task notes, recent/recommendations")
    print("=" * 80)
    print(f"Dashboard: {dashboard_path.relative_to(root)}")
    print()

    print(f"{'Element':<38} {'Call sites':>10} {'Backend query sites':>20}")
    print("-" * 72)

    for label, prefix, method in ELEMENTS:
        call_count = count_pattern(dashboard_text, prefix, method)
        query_sites = backend_counts.get(prefix, {}).get(method, 0)
        print(f"{label:<38} {call_count:>10} {query_sites:>20}")

    print()
    print("[INFO] task notes (bulk) is used to avoid N+1; single get_task_notes")
    print("       is used in task notes UI. list_recent_tasks appears in many tabs.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
