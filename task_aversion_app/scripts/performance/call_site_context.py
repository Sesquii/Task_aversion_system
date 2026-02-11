#!/usr/bin/env python3
"""
Show code context for each N+1-relevant call site (get_instance, _load_instances).

For each call site: file, line, kind, a few lines before/after, and IN_LOOP flag.
Static scan; no DB. Use to inspect whether a call is inside a loop or one-off.

Usage:
  cd task_aversion_app
  python scripts/performance/call_site_context.py [--file path/to/file.py] [--lines 5]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

from typing import List, Tuple

# Same discovery as n_plus_one_call_sites
SKIP_DIRS = {"venv", ".venv", "env", "__pycache__", ".git", "node_modules"}
GET_INSTANCE_RE = re.compile(r"\.get_instance\s*\(")
LOAD_INSTANCES_RE = re.compile(r"\._load_instances\s*\(")
FOR_RE = re.compile(r"\bfor\s+\w+")


def find_call_sites(app_dir: Path, file_filter: str | None) -> List[Tuple[str, int, str, str]]:
    """Return list of (rel_path, line_no, kind, line_text)."""
    out: List[Tuple[str, int, str, str]] = []
    for py_path in sorted(app_dir.rglob("*.py")):
        try:
            rel = py_path.relative_to(app_dir)
        except ValueError:
            continue
        if any(part in SKIP_DIRS for part in rel.parts):
            continue
        if file_filter and file_filter not in str(rel):
            continue
        try:
            text = py_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        if "get_instance" not in text and "_load_instances" not in text:
            continue
        lines = text.splitlines()
        for i, line in enumerate(lines, 1):
            if GET_INSTANCE_RE.search(line):
                out.append((str(rel), i, "get_instance", line.strip()))
            elif LOAD_INSTANCES_RE.search(line) and "def _load_instances" not in line:
                out.append((str(rel), i, "_load_instances", line.strip()))
    return out


def main() -> int:
    parser = argparse.ArgumentParser(description="Show code context for N+1 call sites")
    parser.add_argument("--file", type=str, default=None, help="Filter to path containing this string")
    parser.add_argument("--lines", type=int, default=5, help="Lines of context before/after (default 5)")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent.parent
    app_dir = root / "task_aversion_app"
    if not app_dir.is_dir():
        app_dir = root

    sites = find_call_sites(app_dir, args.file)
    if not sites:
        print("[INFO] No get_instance / _load_instances call sites found.")
        return 0

    ctx = args.lines
    print("=" * 72)
    print("N+1 CALL SITE CONTEXT (get_instance, _load_instances)")
    print("=" * 72)
    print(f"Context: {ctx} lines before/after. Use --file <path> to filter.")
    print()

    for rel_path, line_no, kind, line_text in sites:
        full_path = app_dir / rel_path
        try:
            all_lines = full_path.read_text(encoding="utf-8", errors="replace").splitlines()
        except OSError:
            all_lines = []
        start = max(0, line_no - 1 - ctx)
        end = min(len(all_lines), line_no + ctx)
        block = all_lines[start:end]
        in_loop = False
        if kind == "get_instance":
            combined = "\n".join(all_lines[max(0, line_no - 16) : line_no])
            in_loop = bool(FOR_RE.search(combined))

        print(f"--- {rel_path}:{line_no}  {kind}" + ("  [IN_LOOP?]" if in_loop else ""))
        for j, bline in enumerate(block, start=start + 1):
            marker = ">>> " if j == line_no else "    "
            print(f"  {marker}{j:5d} | {bline[:100]}")
        print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
