#!/usr/bin/env python3
"""
Catalog all database indexes defined in the codebase.

Scans:
  - backend/database.py: Column(..., index=True), Index('name', ...) in __table_args__
  - backend/add_database_indexes.py: CREATE INDEX ...
  - PostgreSQL_migration/*.py and SQLite_migration/*.py: CREATE INDEX ...

Outputs a single list of index names and target table/columns for review.
Use this to see how many indexes exist and whether any are redundant or missing.

Usage:
  cd task_aversion_app
  python scripts/performance/catalog_indexes.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from collections import defaultdict


def extract_indexes_from_content(path: Path, content: str) -> list[tuple[str, str, str]]:
    """Extract (index_name, table, columns_or_note) from file content."""
    results: list[tuple[str, str, str]] = []
    path_str = str(path)

    # CREATE INDEX IF NOT EXISTS idx_... ON table_name(col1, col2) or USING GIN (...)
    for m in re.finditer(
        r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s+ON\s+[\"']?(\w+)[\"']?\s*\(([^)]+)\)",
        content,
        re.IGNORECASE,
    ):
        name, table, cols = m.group(1), m.group(2), m.group(3).strip()
        # GIN (col) -> just col
        if "USING" in content[m.start() : m.end() + 20]:
            pass  # keep cols as-is
        results.append((name, table, cols))

    # CREATE INDEX ... USING GIN (col)
    for m in re.finditer(
        r"CREATE\s+INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s+ON\s+[\"']?(\w+)[\"']?\s+USING\s+GIN\s*\(([^)]+)\)",
        content,
        re.IGNORECASE,
    ):
        results.append((m.group(1), m.group(2), "GIN(" + m.group(3).strip() + ")"))

    # Index('idx_name', 'col1', 'col2') in Python
    for m in re.finditer(r"Index\s*\(\s*[\'\"](\w+)[\'\"]\s*,\s*([^)]+)\)", content):
        name = m.group(1)
        args = m.group(2)
        # Table from context is hard; we leave table as "model" and columns from args
        cols = re.sub(r"[\'\"\s]+", " ", args).strip()
        results.append((name, "(model)", cols))

    # index=True on Column: we infer from Column(name, ... index=True)
    for m in re.finditer(
        r"Column\s*\(\s*(\w+)\s*,.*?index\s*=\s*True",
        content,
        re.IGNORECASE | re.DOTALL,
    ):
        col = m.group(1)
        # Table: look for __tablename__ = 'X' in same file before this line
        table = "(model)"
        results.append((f"(implicit:{col})", table, col))

    return results


def main() -> int:
    root = Path(__file__).resolve().parent.parent.parent
    if not root.is_dir():
        print(f"[FAIL] Root not found: {root}")
        return 1

    # Files to scan
    candidates = [
        root / "backend" / "database.py",
        root / "backend" / "add_database_indexes.py",
    ]
    for d in ["PostgreSQL_migration", "SQLite_migration"]:
        mig_dir = root / d
        if mig_dir.is_dir():
            candidates.extend(mig_dir.glob("*.py"))

    all_entries: list[tuple[str, Path, str, str]] = []  # name, path, table, cols
    seen_names: set[str] = set()

    for path in candidates:
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for name, table, cols in extract_indexes_from_content(path, content):
            rel = path.relative_to(root)
            all_entries.append((name, rel, table, cols))
            if not name.startswith("(implicit"):
                seen_names.add(name)

    # Dedupe by (name, table) for explicit names; keep implicit per-file
    by_name: dict[str, list[tuple[Path, str, str]]] = defaultdict(list)
    for name, rel, table, cols in all_entries:
        by_name[name].append((rel, table, cols))

    print("=" * 80)
    print("INDEX CATALOG (codebase)")
    print("=" * 80)
    print(f"Root: {root}")
    print(f"Total index references: {len(all_entries)}")
    print()

    # Group explicit indexes
    explicit = [(n, items) for n, items in by_name.items() if not n.startswith("(implicit")]
    explicit.sort(key=lambda x: x[0])
    print("--- Named indexes (CREATE INDEX / Index()) ---")
    for name, items in explicit:
        for rel, table, cols in items[:3]:  # show up to 3 sources
            print(f"  {name}")
            print(f"    table: {table}  columns: {cols}")
            print(f"    source: {rel}")
        if len(items) > 3:
            print(f"    ... and {len(items) - 3} more sources")
    print()

    # Implicit (index=True on Column)
    implicit = [(n, items) for n, items in by_name.items() if n.startswith("(implicit")]
    if implicit:
        print("--- Implicit indexes (Column(..., index=True)) ---")
        for name, items in implicit:
            for rel, table, cols in items[:2]:
                print(f"  {name}  -> {cols}  in {rel}")
    print()
    print("Run this script after schema changes to keep the catalog in sync.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
