#!/usr/bin/env python3
"""
List call sites that can cause N+1 for task_instances (get_instance / _load_instances).

Static scan: no DB or query log. Use after query_log_n_plus_one_candidates.py to know
where to fix loops. Prefer get_instances_bulk() over repeated get_instance() in loops.

Usage:
  cd task_aversion_app
  python scripts/performance/n_plus_one_call_sites.py [--by-file]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser(description="List N+1-relevant call sites (get_instance, _load_instances)")
    parser.add_argument("--by-file", action="store_true", help="Group output by file (default: same)")
    parser.parse_args()

    root = Path(__file__).resolve().parent.parent.parent
    app_dir = root / "task_aversion_app"
    if not app_dir.is_dir():
        app_dir = root

    # Skip non-source directories (avoids venv, __pycache__, etc.; prevents timeout on large trees)
    skip_dirs = {"venv", ".venv", "env", "__pycache__", ".git", "node_modules"}

    # Patterns: get_instance( or _load_instances(
    get_instance_re = re.compile(r"\.get_instance\s*\(")
    load_instances_re = re.compile(r"\._load_instances\s*\(")
    for_re = re.compile(r"\bfor\s+\w+")

    by_file: dict[str, list[tuple[int, str, str]]] = {}
    for py_path in app_dir.rglob("*.py"):
        rel = py_path.relative_to(app_dir)
        if any(part in skip_dirs for part in rel.parts):
            continue
        try:
            text = py_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # Skip full line scan if file cannot contain matches (faster on large trees)
        if "get_instance" not in text and "_load_instances" not in text:
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines, 1):
            if get_instance_re.search(line):
                block = "\n".join(lines[max(0, i - 16) : i])
                in_loop = bool(for_re.search(block))
                kind = "get_instance" + (" [LOOP? use get_instances_bulk]" if in_loop else "")
                by_file.setdefault(str(rel), []).append((i, kind, line.strip()[:80]))
            if load_instances_re.search(line) and "def _load_instances" not in line:
                by_file.setdefault(str(rel), []).append(
                    (i, "_load_instances", line.strip()[:80])
                )

    if not by_file:
        print("[INFO] No get_instance / _load_instances call sites found.")
        return 0

    print("=" * 72)
    print("N+1 RELEVANT CALL SITES (get_instance, _load_instances)")
    print("=" * 72)
    print("Use with query_log_n_plus_one_candidates.py + query_log_n_plus_one_trace.py")
    print()

    for file_path in sorted(by_file.keys()):
        entries = by_file[file_path]
        print(f"--- {file_path} ---")
        for line_no, kind, snippet in sorted(entries, key=lambda x: x[0]):
            print(f"  {line_no:5d}  {kind}")
            print(f"         {snippet}")
        print()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
