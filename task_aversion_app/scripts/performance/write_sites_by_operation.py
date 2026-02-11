#!/usr/bin/env python3
"""
INSERT/UPDATE/DELETE-focused static analysis: write-path sites by operation type.

Scans app code (backend, ui, app.py; excludes migration dirs) for write operations:
  - Raw SQL: INSERT, UPDATE, DELETE in strings
  - ORM: session.add(, session.add_all(, session.delete(, .delete() (bulk)
  - execute(text(...)) containing INSERT/UPDATE/DELETE

Outputs actionable counts per operation type (INSERT vs UPDATE vs DELETE) and per
module/file to identify write hotspots. Use for per-SQL-type coverage of writes.

Usage:
  cd task_aversion_app
  python scripts/performance/write_sites_by_operation.py [--top N] [--by-dir]
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path


def count_write_sites_in_file(path: Path) -> dict[str, int]:
    """Count write-related patterns. Returns dict of operation/category -> count."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    # Line-based for raw SQL to avoid DOTALL backtracking on large files
    def line_has_sql(line: str, keyword: str) -> bool:
        if keyword not in line.upper():
            return False
        return "'" in line or '"' in line or "text(" in line.lower()

    insert_raw = sum(1 for line in text.splitlines() if line_has_sql(line, "INSERT"))
    update_raw = sum(1 for line in text.splitlines() if line_has_sql(line, "UPDATE"))
    delete_raw = sum(1 for line in text.splitlines() if line_has_sql(line, "DELETE"))
    counts = {
        "INSERT (raw)": insert_raw,
        "UPDATE (raw)": update_raw,
        "DELETE (raw)": delete_raw,
        "session.add": len(re.findall(r"session\.add\s*\(", text)),
        "session.add_all": len(re.findall(r"session\.add_all\s*\(", text)),
        "session.delete": len(re.findall(r"session\.delete\s*\(", text)),
        "bulk .delete()": len(re.findall(r"\)\.delete\s*\(", text)),  # query().delete()
    }
    return counts


def total_writes(counts: dict[str, int]) -> int:
    """Sum of all write-site counts."""
    return sum(counts.values())


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write-path sites by operation type (INSERT/UPDATE/DELETE-focused)"
    )
    parser.add_argument("--top", type=int, default=35, help="Show top N files")
    parser.add_argument("--by-dir", action="store_true", help="Aggregate by directory")
    parser.add_argument(
        "--root",
        type=str,
        default=None,
        help="Root directory (default: task_aversion_app)",
    )
    args = parser.parse_args()

    root = Path(args.root) if args.root else Path(__file__).resolve().parent.parent.parent
    if not root.is_dir():
        print(f"[FAIL] Root not found: {root}")
        return 1

    include_dirs = ("backend", "ui")
    exclude_dirs = ("venv", ".venv", "__pycache__", "SQLite_migration", "PostgreSQL_migration")

    py_files: list[Path] = []
    for p in root.rglob("*.py"):
        parts = p.parts
        if any(ex in parts for ex in exclude_dirs):
            continue
        rel = p.relative_to(root)
        if str(rel) == "app.py" or any(rel.parts[0] == d for d in include_dirs):
            py_files.append(p)

    file_data: list[tuple[Path, dict[str, int], int]] = []
    dir_totals: dict[str, int] = defaultdict(int)
    op_totals: dict[str, int] = defaultdict(int)

    for path in py_files:
        rel = path.relative_to(root)
        counts = count_write_sites_in_file(path)
        total = total_writes(counts)
        if total > 0:
            file_data.append((rel, counts, total))
            if args.by_dir:
                dir_name = str(rel.parent) if rel.parent != Path(".") else "."
                dir_totals[dir_name] += total
            for k, v in counts.items():
                if v > 0:
                    op_totals[k] += v

    file_data.sort(key=lambda x: -x[2])

    print("=" * 72)
    print("WRITE-PATH SITES BY OPERATION (INSERT/UPDATE/DELETE-focused)")
    print("=" * 72)
    print(f"Root: {root}")
    print(f"Scoped to: app.py, backend/, ui/ (excludes migrations)")
    print(f"Files scanned: {len(py_files)}")
    print(f"Files with >= 1 write site: {len(file_data)}")
    print()
    print("--- Totals by operation type ---")
    for op in sorted(op_totals.keys(), key=lambda k: -op_totals[k]):
        print(f"  {op_totals[op]:5d}  {op}")
    print()

    if args.by_dir:
        print("--- By directory (write sites) ---")
        for dir_name in sorted(dir_totals.keys(), key=lambda d: -dir_totals[d]):
            print(f"  {dir_totals[dir_name]:5d}  {dir_name}")
        print()

    print("--- Top files by write sites ---")
    for rel, counts, total in file_data[: args.top]:
        detail = "  ".join(f"{k}:{v}" for k, v in counts.items() if v > 0)
        print(f"  {total:5d}  {rel}")
        if detail:
            print(f"         {detail}")
    print()
    print("Legend: raw SQL INSERT/UPDATE/DELETE, session.add/add_all/delete, .delete() bulk.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
