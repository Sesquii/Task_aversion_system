#!/usr/bin/env python3
"""
Find get_instance(instance_id) call sites that are inside a loop (for/while).

These are candidates to switch to get_instances_bulk(instance_ids, user_id=...).
Static scan only; no DB or query log. Excludes def get_instance and tests that
are meant to assert per-instance behavior.

Usage:
  cd task_aversion_app
  python scripts/performance/get_instance_loop_candidates.py [--context 5] [--all]
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path


def _indent(s: str) -> int:
    """Return number of leading spaces."""
    return len(s) - len(s.lstrip())


def _find_loops_with_get_instance(
    lines: list[str], get_instance_line_indices: list[int]
) -> dict[int, tuple[str | None, int]]:
    """For each get_instance line index (0-based), if inside a for/while body, return (loop_var, for_line_1based)."""
    result: dict[int, tuple[str | None, int]] = {}
    for_line_re = re.compile(r"^\s*for\s+(\w+)\s+in\s+")
    while_re = re.compile(r"^\s*while\s+")
    for gi_idx in get_instance_line_indices:
        target_indent = _indent(lines[gi_idx])
        for i in range(gi_idx - 1, -1, -1):
            line = lines[i]
            if not line.strip():
                continue
            indent = _indent(line)
            if indent >= target_indent:
                continue
            m = for_line_re.match(line)
            if m:
                result[gi_idx] = (m.group(1), i + 1)
                break
            if while_re.match(line):
                result[gi_idx] = (None, i + 1)
                break
            break
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Find get_instance() calls inside loops (candidates for get_instances_bulk)"
    )
    parser.add_argument(
        "--context",
        type=int,
        default=8,
        help="Lines of context before each call to detect loop (default 8)",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="List all get_instance call sites; otherwise only those in loops",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent.parent
    app_dir = root / "task_aversion_app"
    if not app_dir.is_dir():
        app_dir = root

    skip_dirs = {"venv", ".venv", "env", "__pycache__", ".git", "node_modules"}
    # Only scan app code (backend, ui); exclude scripts/tests to avoid false positives
    include_parts = ("backend", "ui")
    get_instance_re = re.compile(r"\.get_instance\s*\(")

    candidates: list[tuple[str, int, bool, str | None, str, list[str]]] = []

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
        gi_indices = [
            i for i, line in enumerate(lines)
            if get_instance_re.search(line) and "def get_instance" not in line and "def _get_instance" not in line
        ]
        if not gi_indices:
            continue
        loop_map = _find_loops_with_get_instance(lines, gi_indices)
        rel_str = str(rel)
        for i in gi_indices:
            line = lines[i]
            loop_var, _for_line = loop_map.get(i, (None, 0))
            in_loop = i in loop_map
            if not in_loop and not args.all:
                continue
            context_before = lines[max(0, i - args.context) : i]
            candidates.append(
                (rel_str, i + 1, in_loop, loop_var, line.strip()[:90], context_before)
            )

    print("=" * 72)
    print("get_instance() IN LOOPS -> CANDIDATES FOR get_instances_bulk()")
    print("=" * 72)
    print("Refactor: collect instance_ids in the loop, then call get_instances_bulk(instance_ids, user_id=...) once and use the returned dict.")
    print()

    loop_only = [c for c in candidates if c[2]]
    if loop_only:
        print("--- In loop (refactor to get_instances_bulk) ---")
        for rel, line_no, _, loop_var, snippet, ctx in loop_only:
            print(f"  {rel}:{line_no}" + (f"  (loop var: {loop_var})" if loop_var else ""))
            print(f"    {snippet}")
            if ctx:
                for c in ctx[-3:]:
                    print(f"      | {c[:70]}")
            print()
    else:
        print("--- No get_instance() calls inside loops detected (--context may be too small). ---")
        print()

    if args.all and candidates:
        print("--- All get_instance() call sites ---")
        for rel, line_no, in_loop, loop_var, snippet, _ in candidates:
            tag = " [IN LOOP]" if in_loop else ""
            print(f"  {rel}:{line_no}{tag}  {snippet[:70]}")
        print()

    if loop_only:
        print("[INFO] Refactor hint: Before the loop, collect all instance_ids. Then call im.get_instances_bulk(instance_ids, user_id=...) once. In the loop, use bulk_map.get(instance_id) instead of im.get_instance(instance_id, ...).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
