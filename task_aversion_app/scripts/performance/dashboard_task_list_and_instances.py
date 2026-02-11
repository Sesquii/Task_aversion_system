#!/usr/bin/env python3
"""
Dashboard elements: task list and active instances.

Targets: task list (tm.get_all), active instances (im.list_active_instances).
Counts call sites in ui/dashboard.py and query sites in the corresponding
backend methods. Use to isolate load from the main task table and active
instance listing.

Usage:
  cd task_aversion_app
  python scripts/performance/dashboard_task_list_and_instances.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def count_call_sites(text: str, pattern: str) -> list[tuple[int, str]]:
    """Return list of (line_number, line) for each match of prefix.method(."""
    pat = re.escape(pattern) + r"\s*\("
    results = []
    for i, line in enumerate(text.splitlines(), start=1):
        if re.search(pat, line):
            results.append((i, line.strip()))
    return results


def count_query_sites_in_function(body: str) -> int:
    """Count session.query( and .execute( in function body."""
    return len(re.findall(r"session\.query\s*\(", body)) + len(
        re.findall(r"\.execute\s*\(\s*", body)
    )


def get_method_body_and_query_count(module_path: Path, method_name: str) -> tuple[str, int]:
    """Return (method signature line, query_site_count) for method_name."""
    try:
        text = module_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ("", 0)
    lines = text.splitlines()
    for i, line in enumerate(lines):
        m = re.match(r"^\s*def\s+" + re.escape(method_name) + r"\s*\(", line)
        if m:
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
            return (line.strip(), count_query_sites_in_function(body))
    return ("", 0)


def main() -> int:
    root = Path(__file__).resolve().parent.parent.parent
    dashboard_path = root / "ui" / "dashboard.py"
    tm_path = root / "backend" / "task_manager.py"
    im_path = root / "backend" / "instance_manager.py"

    if not dashboard_path.is_file():
        print(f"[FAIL] Dashboard not found: {dashboard_path}")
        return 1
    if not tm_path.is_file() or not im_path.is_file():
        print("[FAIL] Backend modules not found.")
        return 1

    try:
        dashboard_text = dashboard_path.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        print(f"[FAIL] Could not read dashboard: {e}")
        return 1

    # Task list: tm.get_all
    task_list_calls = count_call_sites(dashboard_text, "tm.get_all")
    tm_sig, tm_queries = get_method_body_and_query_count(tm_path, "get_all")

    # Active instances: im.list_active_instances
    active_calls = count_call_sites(dashboard_text, "im.list_active_instances")
    im_sig, im_queries = get_method_body_and_query_count(
        im_path, "list_active_instances"
    )

    print("=" * 80)
    print("DASHBOARD: task list (tm.get_all) and active instances (im.list_active_instances)")
    print("=" * 80)
    print()

    print("--- Task list (tm.get_all) ---")
    print(f"  Call sites in dashboard: {len(task_list_calls)}")
    for ln, content in task_list_calls[:15]:
        short = content[:72] + "..." if len(content) > 72 else content
        print(f"    L{ln}: {short}")
    if len(task_list_calls) > 15:
        print(f"    ... and {len(task_list_calls) - 15} more")
    print(f"  Backend query sites in get_all: {tm_queries}")
    if tm_sig:
        print(f"  Method: {tm_sig[:70] + '...' if len(tm_sig) > 70 else tm_sig}")
    print()

    print("--- Active instances (im.list_active_instances) ---")
    print(f"  Call sites in dashboard: {len(active_calls)}")
    for ln, content in active_calls[:15]:
        short = content[:72] + "..." if len(content) > 72 else content
        print(f"    L{ln}: {short}")
    if len(active_calls) > 15:
        print(f"    ... and {len(active_calls) - 15} more")
    print(f"  Backend query sites in list_active_instances: {im_queries}")
    if im_sig:
        print(f"  Method: {im_sig[:70] + '...' if len(im_sig) > 70 else im_sig}")
    print()

    print("[INFO] Use pg_analyze_queries.py to EXPLAIN dashboard queries for these paths.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
