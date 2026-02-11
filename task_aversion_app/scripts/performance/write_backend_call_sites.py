#!/usr/bin/env python3
"""
INSERT/UPDATE/DELETE-focused static analysis: backend call sites that perform writes.

Scans backend modules only for functions/methods that contain at least one write:
  - session.add(, session.add_all(, session.delete(, .delete()
  - Raw SQL strings containing INSERT, UPDATE, or DELETE

Outputs actionable counts: which backend modules and which functions are write-path
hotspots. Complements dashboard_load_call_tree (read path) with write-path coverage.
Use for per-SQL-type (INSERT/UPDATE/DELETE) coverage.

Usage:
  cd task_aversion_app
  python scripts/performance/write_backend_call_sites.py [--by-module]
"""
from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path


def body_contains_write(body: str) -> bool:
    """True if body contains any write pattern."""
    if re.search(r"session\.(add|add_all|delete)\s*\(", body):
        return True
    if re.search(r"\)\.delete\s*\(", body):
        return True
    if re.search(r"[\'\"].*?(?:INSERT|UPDATE|DELETE)\s+", body, re.IGNORECASE | re.DOTALL):
        return True
    if re.search(r"text\s*\(\s*[\'\"].*?(?:INSERT|UPDATE|DELETE)\s+", body, re.IGNORECASE | re.DOTALL):
        return True
    return False


def count_writes_in_body(body: str) -> int:
    """Approximate write-site count in body (for ordering hotspots)."""
    n = 0
    n += len(re.findall(r"session\.(add|add_all|delete)\s*\(", body))
    n += len(re.findall(r"\)\.delete\s*\(", body))
    n += len(re.findall(r"INSERT\s+", body, re.IGNORECASE))
    n += len(re.findall(r"UPDATE\s+", body, re.IGNORECASE))
    n += len(re.findall(r"DELETE\s+", body, re.IGNORECASE))
    return n


def extract_functions_with_writes(module_path: Path) -> list[tuple[str, int, int]]:
    """
    Parse module and return list of (function_name, write_count, line_number).
    Only includes functions whose body contains at least one write.
    """
    try:
        lines = module_path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    result: list[tuple[str, int, int]] = []
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
            if body_contains_write(body):
                wc = count_writes_in_body(body)
                result.append((name, wc, i + 1))
            i = j
        else:
            i += 1
    return result


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Backend call sites that perform writes (INSERT/UPDATE/DELETE-focused)"
    )
    parser.add_argument(
        "--by-module",
        action="store_true",
        help="Group output by backend module (default: flat list of hotspots)",
    )
    parser.add_argument(
        "--root",
        type=str,
        default=None,
        help="Root directory (default: task_aversion_app)",
    )
    args = parser.parse_args()

    root = Path(args.root) if args.root else Path(__file__).resolve().parent.parent.parent
    backend_dir = root / "backend"
    if not backend_dir.is_dir():
        print(f"[FAIL] Backend not found: {backend_dir}")
        return 1

    py_files = sorted(backend_dir.glob("*.py"))
    all_hotspots: list[tuple[str, str, int, int]] = []  # (module, func, writes, line)

    for path in py_files:
        if path.name.startswith("__"):
            continue
        module = path.stem
        for func_name, write_count, line_no in extract_functions_with_writes(path):
            all_hotspots.append((module, func_name, write_count, line_no))

    all_hotspots.sort(key=lambda x: -x[2])

    print("=" * 72)
    print("WRITE BACKEND CALL SITES (INSERT/UPDATE/DELETE-focused)")
    print("=" * 72)
    print(f"Root: {root}")
    print(f"Scoped to: backend/*.py")
    print(f"Functions with >= 1 write site: {len(all_hotspots)}")
    print()

    if args.by_module:
        by_mod: dict[str, list[tuple[str, int, int]]] = {}
        for mod, func, wc, line in all_hotspots:
            by_mod.setdefault(mod, []).append((func, wc, line))
        print("--- By module ---")
        for mod in sorted(by_mod.keys()):
            funcs = by_mod[mod]
            total = sum(f[1] for f in funcs)
            print(f"  {mod}.py  ({len(funcs)} functions, {total} write sites)")
            for func, wc, line in sorted(funcs, key=lambda x: -x[1]):
                print(f"    {wc:3d}  {func}  (L{line})")
        print()
    else:
        print("--- Write hotspots (all backend functions with writes) ---")
        for mod, func, wc, line in all_hotspots:
            print(f"  {wc:3d}  {mod}.{func}  (L{line})")
        print()

    print("Legend: write = session.add/add_all/delete, .delete(), or raw INSERT/UPDATE/DELETE.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
