#!/usr/bin/env python3
"""
Analytics page and elements: backend call tree and query-site estimates.

Targets the Analytics area: main analytics page (/analytics, ui/analytics_page.py)
and its primary elements—composite score load, emotional flow, relief comparison,
factors comparison, and glossary. Parses analytics UI files for calls to
analytics_service.* and user_state.*, then scans backend modules to count query
sites (session.query, .execute) per method. Produces a hot-path view for
analytics load.

Static analysis; no DB or live app required. Run from task_aversion_app:
  python scripts/performance/analytics_load_call_tree.py [--by-module]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from collections import defaultdict


# (prefix_in_ui, backend_key for module lookup)
ANALYTICS_PREFIXES = [
    ("analytics_service.", "analytics_service"),
    ("user_state.", "user_state"),
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
    parser = argparse.ArgumentParser(
        description="Analytics page and elements: backend call tree and query-site estimates"
    )
    parser.add_argument(
        "--by-module",
        action="store_true",
        help="Group output by source UI module (analytics_page, relief_comparison, etc.).",
    )
    args = parser.parse_args()

    ui_files: list[tuple[str, Path]] = [
        ("analytics_page (main, composite, emotional flow, charts, rankings)", ui_dir / "analytics_page.py"),
        ("factors_comparison", ui_dir / "factors_comparison_analytics.py"),
        ("relief_comparison", ui_dir / "relief_comparison_analytics.py"),
        ("analytics_glossary", ui_dir / "analytics_glossary.py"),
    ]
    unique_ui = [(label, p) for label, p in ui_files if p.is_file()]

    all_calls_list: list[dict[str, set[str]]] = []
    file_calls: dict[Path, dict[str, set[str]]] = {}
    for label, p in unique_ui:
        c = extract_backend_calls(p, ANALYTICS_PREFIXES)
        all_calls_list.append(c)
        file_calls[p] = c
    calls = merge_calls(all_calls_list)

    if not calls or all(not s for s in calls.values()):
        print("[INFO] No analytics_service/user_state calls found in Analytics UI.")
        return 0

    backend_modules = {
        "analytics_service": root / "backend" / "analytics.py",
        "user_state": root / "backend" / "user_state.py",
    }
    method_counts: dict[str, dict[str, int]] = {}
    for key, path in backend_modules.items():
        if path.is_file():
            method_counts[key] = extract_methods_and_query_counts(path)
        else:
            method_counts[key] = {}

    print("=" * 72)
    print("ANALYTICS LOAD CALL TREE (Analytics page and elements)")
    print("=" * 72)
    print("Target: Analytics page (/analytics), composite score load, emotional flow,")
    print("  relief comparison, factors comparison, glossary.")
    print()

    total_estimate = 0
    hot: list[tuple[str, str, int]] = []

    for prefix in ["analytics_service", "user_state"]:
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

    if args.by_module:
        print("--- By UI module (file) ---")
        for label, p in unique_ui:
            file_call = file_calls.get(p, {})
            if not file_call:
                continue
            print(f"  {label}: {p.name}")
            for key, methods in file_call.items():
                counts = method_counts.get(key, {})
                for m in sorted(methods):
                    c = counts.get(m, 0)
                    print(f"    {key}.{m}()  (query sites: {c})")
        print()

    print("--- Hot path (methods with at least 1 query site) ---")
    hot.sort(key=lambda x: -x[2])
    for prefix, method, c in hot[:25]:
        print(f"  {c:3d}  {prefix}.{method}()")
    print()
    print("[INFO] Total is a rough sum of per-method query sites; actual requests may")
    print("  call some methods multiple times. Static analysis only.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
