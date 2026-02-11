#!/usr/bin/env python3
"""
Map N+1 call sites to the routes/pages that can trigger them.

Static mapping: ui/dashboard.py -> GET /, ui/analytics_page.py -> GET /analytics, etc.
Backend files are attributed to all routes that use them (dashboard uses backend/analytics,
backend/instance_manager). Output: per-route list of call sites, then per-call-site routes.

Usage:
  cd task_aversion_app
  python scripts/performance/call_site_by_route.py [--route /]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from collections import defaultdict

from typing import List, Tuple

SKIP_DIRS = {"venv", ".venv", "env", "__pycache__", ".git", "node_modules"}
GET_INSTANCE_RE = re.compile(r"\.get_instance\s*\(")
LOAD_INSTANCES_RE = re.compile(r"\._load_instances\s*\(")

# UI file (or path fragment) -> primary route(s) that load it
FILE_TO_ROUTES: list[tuple[str, list[str]]] = [
    ("ui/dashboard.py", ["GET /"]),
    ("ui/analytics_page.py", ["GET /analytics"]),
    ("ui/settings_page.py", ["GET /settings"]),
    ("ui/complete_task.py", ["GET /complete-task", "POST /complete-task"]),
    ("ui/initialize_task.py", ["GET /initialize-task"]),
    ("ui/relief_comparison_analytics.py", ["GET /analytics/relief-comparison"]),
    ("ui/factors_comparison_analytics.py", ["GET /analytics/factors-comparison"]),
    ("ui/productivity_settings_page.py", ["GET /settings/productivity"]),
    ("ui/summary_page.py", ["GET /analytics/summary"]),
    ("ui/composite_score_weights_page.py", ["GET /settings/score-weights"]),
    ("ui/task_editing_manager.py", ["(used by dashboard/complete/initialize)"]),
    ("backend/analytics.py", ["GET /", "GET /analytics", "GET /settings", "GET /analytics/relief-comparison", "GET /analytics/factors-comparison", "GET /settings/productivity"]),
    ("backend/instance_manager.py", ["GET /", "GET /complete-task", "GET /initialize-task", "GET /analytics"]),
    ("backend/popup_dispatcher.py", ["(background popups)"]),
    ("backend/routine_scheduler.py", ["(scheduled jobs)"]),
]


def routes_for_file(rel_path: str) -> list[str]:
    routes: list[str] = []
    for fragment, route_list in FILE_TO_ROUTES:
        if fragment in rel_path.replace("\\", "/"):
            routes.extend(route_list)
    if not routes:
        routes = ["(other/script)"]
    return routes


def find_call_sites(app_dir: Path) -> List[Tuple[str, int, str, str]]:
    out: List[Tuple[str, int, str, str]] = []
    for py_path in sorted(app_dir.rglob("*.py")):
        rel = py_path.relative_to(app_dir)
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        try:
            text = py_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "get_instance" not in text and "_load_instances" not in text:
            continue
        lines = text.splitlines()
        rel_str = str(rel).replace("\\", "/")
        for i, line in enumerate(lines, 1):
            if GET_INSTANCE_RE.search(line):
                out.append((rel_str, i, "get_instance", line.strip()[:70]))
            elif LOAD_INSTANCES_RE.search(line) and "def _load_instances" not in line:
                out.append((rel_str, i, "_load_instances", line.strip()[:70]))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Map N+1 call sites to routes")
    parser.add_argument("--route", type=str, default=None, help="Filter to route containing this (e.g. '/' or 'analytics')")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent.parent
    app_dir = root / "task_aversion_app"
    if not app_dir.is_dir():
        app_dir = root

    sites = find_call_sites(app_dir)
    if not sites:
        print("[INFO] No get_instance / _load_instances call sites found.")
        return 0

    # Build route -> list of (file, line, kind, snippet)
    route_to_sites: dict[str, list[tuple[str, int, str, str]]] = defaultdict(list)
    for rel_path, line_no, kind, snippet in sites:
        for r in routes_for_file(rel_path):
            if args.route is None or args.route in r:
                route_to_sites[r].append((rel_path, line_no, kind, snippet))

    print("=" * 72)
    print("N+1 CALL SITES BY ROUTE")
    print("=" * 72)
    if args.route:
        print(f"Filter: route containing '{args.route}'")
    print()

    for route in sorted(route_to_sites.keys(), key=lambda x: (x.startswith("("), x)):
        entries = route_to_sites[route]
        print(f"--- {route} ({len(entries)} call sites) ---")
        for rel_path, line_no, kind, snippet in sorted(entries, key=lambda x: (x[0], x[1])):
            print(f"  {rel_path}:{line_no}  {kind}  {snippet}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
