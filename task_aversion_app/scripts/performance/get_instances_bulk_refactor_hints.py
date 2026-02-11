#!/usr/bin/env python3
"""
List every get_instance(instance_id) call site with refactor hints for get_instances_bulk.

Use when the same code path is invoked many times with different instance_ids (e.g. one
call per card or per timer). Refactor: caller collects instance_ids, calls
get_instances_bulk(instance_ids, user_id=...) once, then passes instance dict or uses
bulk_map.get(instance_id) inside the loop.

Usage:
  cd task_aversion_app
  python scripts/performance/get_instances_bulk_refactor_hints.py [--include-backend]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="List get_instance() call sites with refactor hints for get_instances_bulk"
    )
    parser.add_argument(
        "--include-backend",
        action="store_true",
        help="Include backend (instance_manager) call sites; default is UI only",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent.parent
    app_dir = root / "task_aversion_app"
    if not app_dir.is_dir():
        app_dir = root

    skip_dirs = {"venv", ".venv", "env", "__pycache__", ".git", "node_modules"}
    include_parts = ("backend", "ui") if args.include_backend else ("ui",)
    get_instance_re = re.compile(r"\.get_instance\s*\(\s*([^,)]+)\s*[,)]")

    sites: list[tuple[str, int, str, str]] = []

    for py_path in sorted(app_dir.rglob("*.py")):
        rel = py_path.relative_to(app_dir)
        if any(part in skip_dirs for part in rel.parts):
            continue
        if not rel.parts or rel.parts[0] not in include_parts:
            continue
        try:
            text = py_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "get_instance" not in text:
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines):
            if "def get_instance" in line or "def _get_instance" in line:
                continue
            m = get_instance_re.search(line)
            if not m:
                continue
            arg0 = m.group(1).strip()
            sites.append((str(rel), i + 1, line.strip()[:75], arg0))

    print("=" * 72)
    print("get_instance() -> get_instances_bulk() REFACTOR HINTS")
    print("=" * 72)
    print("If the caller has a list of instance_ids, call get_instances_bulk(instance_ids, user_id=...) once.")
    print("Then use bulk_map.get(instance_id) instead of get_instance(instance_id, ...) in the loop.")
    print()
    for rel, line_no, snippet, arg0 in sites:
        print(f"  {rel}:{line_no}")
        print(f"    arg: {arg0}  ->  use bulk_map.get({arg0}) after get_instances_bulk([...], user_id=...)")
        print(f"    {snippet}")
        print()
    if sites:
        print("[INFO] Run get_instance_loop_candidates.py to find same-block for/while loops.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
