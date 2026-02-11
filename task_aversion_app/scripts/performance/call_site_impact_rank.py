#!/usr/bin/env python3
"""
Rank N+1 call sites by impact: in-loop + hot path (dashboard/analytics/settings).

Score = (in_loop + 1) * (hot_path + 1). Higher = fix first. Static scan; no DB.

Usage:
  cd task_aversion_app
  python scripts/performance/call_site_impact_rank.py [--top 30]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from typing import List, Tuple

SKIP_DIRS = {"venv", ".venv", "env", "__pycache__", ".git", "node_modules"}
GET_INSTANCE_RE = re.compile(r"\.get_instance\s*\(")
LOAD_INSTANCES_RE = re.compile(r"\._load_instances\s*\(")
FOR_RE = re.compile(r"\bfor\s+\w+")

# Path fragments that are "hot" (high traffic pages)
HOT_PATH_FRAGMENTS = (
    "ui/dashboard.py",
    "ui/analytics_page.py",
    "ui/settings_page.py",
    "ui/complete_task.py",
    "ui/initialize_task.py",
    "backend/analytics.py",
    "backend/instance_manager.py",
)


def find_sites_with_impact(app_dir: Path) -> List[Tuple[str, int, str, bool, bool]]:
    """Return (rel_path, line_no, kind, in_loop, hot_path)."""
    out: List[Tuple[str, int, str, bool, bool]] = []
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
        hot = any(f in rel_str for f in HOT_PATH_FRAGMENTS)
        for i, line in enumerate(lines, 1):
            in_loop = False
            if GET_INSTANCE_RE.search(line):
                block = "\n".join(lines[max(0, i - 16) : i])
                in_loop = bool(FOR_RE.search(block))
                out.append((rel_str, i, "get_instance", in_loop, hot))
            elif LOAD_INSTANCES_RE.search(line) and "def _load_instances" not in line:
                out.append((rel_str, i, "_load_instances", False, hot))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Rank N+1 call sites by impact")
    parser.add_argument("--top", type=int, default=50, help="Show top N by impact (default 50)")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent.parent
    app_dir = root / "task_aversion_app"
    if not app_dir.is_dir():
        app_dir = root

    sites = find_sites_with_impact(app_dir)
    if not sites:
        print("[INFO] No get_instance / _load_instances call sites found.")
        return 0

    # impact = (in_loop + 1) * (hot_path + 1)  => 1, 2, or 4
    ranked = []
    for rel_path, line_no, kind, in_loop, hot in sites:
        impact = (2 if in_loop else 1) * (2 if hot else 1)
        reason_parts = []
        if in_loop:
            reason_parts.append("loop")
        if hot:
            reason_parts.append("hot-path")
        if not reason_parts:
            reason_parts.append("cold")
        reason = "+".join(reason_parts)
        ranked.append((impact, reason, rel_path, line_no, kind, in_loop, hot))

    ranked.sort(key=lambda x: (-x[0], x[2], x[3]))
    top = ranked[: args.top]

    print("=" * 72)
    print("N+1 CALL SITES BY IMPACT (loop + hot-path)")
    print("=" * 72)
    print("Impact = (in_loop? 2:1) * (hot_path? 2:1). Fix high impact first.")
    print(f"Showing top {len(top)} of {len(ranked)}.")
    print()

    for impact, reason, rel_path, line_no, kind, in_loop, hot in top:
        flags = []
        if in_loop:
            flags.append("LOOP")
        if hot:
            flags.append("HOT")
        flag_str = " [" + ",".join(flags) + "]" if flags else ""
        print(f"  {impact}  {reason:12s}  {rel_path}:{line_no}  {kind}{flag_str}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
