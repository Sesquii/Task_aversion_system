#!/usr/bin/env python3
"""
Backend call tree for Settings: which backend methods are called from Settings UI.

Targets backend call trees for Settings. Parses Settings UI modules
(ui/settings_page.py, ui/composite_score_weights_page.py, ui/productivity_settings_page.py,
ui/cancellation_penalties_page.py) for calls to user_state, im, and analytics,
then maps those methods to query-site counts in the backend (user_state.py,
instance_manager.py, analytics.py). Produces the same "hot path" view as
dashboard_load_call_tree: which methods are called and how many query sites each has.

Usage:
  cd task_aversion_app
  python scripts/performance/settings_load_call_tree.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from collections import defaultdict


# (prefix_in_ui, backend_key for module lookup)
SETTINGS_PREFIXES = [
    ("user_state.", "user_state"),
    ("im.", "im"),
    ("analytics.", "an"),
    ("task_manager.", "tm"),
]


def extract_backend_calls(file_path: Path, prefixes: list[tuple[str, str]]) -> dict[str, set[str]]:
    """Extract backend method names from a UI file: { backend_key: {method_name, ...}, ... }."""
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    out: dict[str, set[str]] = defaultdict(set)
    for prefix, key in prefixes:
        for m in re.finditer(re.escape(prefix) + r"(\w+)\s*\(", text):
            out[key].add(m.group(1))
    return dict(out)


def merge_calls(all_calls: list[dict[str, set[str]]]) -> dict[str, set[str]]:
    """Merge multiple call dicts: union of method sets per backend key."""
    merged: dict[str, set[str]] = defaultdict(set)
    for c in all_calls:
        for key, methods in c.items():
            merged[key].update(methods)
    return dict(merged)


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
    ui_dir = root / "ui"
    settings_ui_files = [
        ui_dir / "settings_page.py",
        ui_dir / "composite_score_weights_page.py",
        ui_dir / "productivity_settings_page.py",
        ui_dir / "cancellation_penalties_page.py",
    ]

    all_calls: list[dict[str, set[str]]] = []
    for path in settings_ui_files:
        if path.is_file():
            all_calls.append(extract_backend_calls(path, SETTINGS_PREFIXES))
    calls = merge_calls(all_calls)

    if not calls or all(not s for s in calls.values()):
        print("[INFO] No user_state/im/analytics/task_manager calls found in Settings UI.")
        return 0

    backend_modules = {
        "user_state": root / "backend" / "user_state.py",
        "im": root / "backend" / "instance_manager.py",
        "an": root / "backend" / "analytics.py",
        "tm": root / "backend" / "task_manager.py",
    }
    method_counts: dict[str, dict[str, int]] = {}
    for key, path in backend_modules.items():
        if path.is_file():
            method_counts[key] = extract_methods_and_query_counts(path)
        else:
            method_counts[key] = {}

    print("=" * 80)
    print("SETTINGS LOAD CALL TREE (backend methods + query-site estimate)")
    print("=" * 80)
    print("UI sources: " + ", ".join(p.name for p in settings_ui_files if p.is_file()))
    print()

    total_estimate = 0
    hot: list[tuple[str, str, int]] = []

    for prefix in ["user_state", "im", "an", "tm"]:
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
