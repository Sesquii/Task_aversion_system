#!/usr/bin/env python3
"""
Index catalog with optional live usage stats (indexes + PG ops).

Focus: **Indexes** (where defined in code) and optionally **PostgreSQL** usage
(idx_scan, idx_tup_read from pg_stat_user_indexes). Complements catalog_indexes.py
(which lists definitions only) and pg_index_review.py (which lists live indexes
and sizes). This script ties codebase index definitions to live usage when
--live is used.

Outputs actionable data: index name, table, source file, columns; with --live
adds scan count and tuples read. No DB required by default; use DATABASE_URL
with --live for PostgreSQL.

Usage:
  cd task_aversion_app
  python scripts/performance/index_catalog_with_usage.py [--live]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent


def extract_indexes(root: Path) -> list[tuple[str, str, str, Path]]:
    """Extract (index_name, table, columns_or_note, path) from codebase."""
    results: list[tuple[str, str, str, Path]] = []
    candidates = [
        root / "backend" / "database.py",
        root / "backend" / "add_database_indexes.py",
    ]
    for d in ["PostgreSQL_migration", "SQLite_migration"]:
        mig_dir = root / d
        if mig_dir.is_dir():
            candidates.extend(mig_dir.glob("*.py"))

    for path in candidates:
        if not path.is_file():
            continue
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        rel = path.relative_to(root)

        # CREATE INDEX ... ON table(cols)
        for m in re.finditer(
            r"CREATE\s+(?:UNIQUE\s+)?INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s+ON\s+[\"']?(\w+)[\"']?\s*\(([^)]+)\)",
            content,
            re.IGNORECASE,
        ):
            name, table, cols = m.group(1), m.group(2), m.group(3).strip()
            results.append((name, table, cols, rel))

        # CREATE INDEX ... USING GIN
        for m in re.finditer(
            r"CREATE\s+INDEX\s+(?:IF\s+NOT\s+EXISTS\s+)?(\w+)\s+ON\s+[\"']?(\w+)[\"']?\s+USING\s+GIN\s*\(([^)]+)\)",
            content,
            re.IGNORECASE,
        ):
            results.append((m.group(1), m.group(2), "GIN(" + m.group(3).strip() + ")", rel))

        # Index('name', 'col1', 'col2')
        for m in re.finditer(r"Index\s*\(\s*['\"](\w+)['\"]\s*,\s*([^)]+)\)", content):
            name = m.group(1)
            cols = re.sub(r"['\"\s]+", " ", m.group(2)).strip()
            results.append((name, "(model)", cols, rel))

        # Column(..., index=True)
        for m in re.finditer(
            r"Column\s*\(\s*(\w+)\s*,.*?index\s*=\s*True",
            content,
            re.IGNORECASE | re.DOTALL,
        ):
            col = m.group(1)
            results.append((f"(implicit:{col})", "(model)", col, rel))

    return results


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Index catalog from codebase; optional live usage from PostgreSQL"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Query PostgreSQL for index usage (idx_scan, idx_tup_read). Requires DATABASE_URL.",
    )
    args = parser.parse_args()

    if not _ROOT.is_dir():
        print(f"[FAIL] Root not found: {_ROOT}")
        return 1

    entries = extract_indexes(_ROOT)
    # Dedupe by (name, table); keep first source
    seen: set[tuple[str, str]] = set()
    unique: list[tuple[str, str, str, Path]] = []
    for name, table, cols, rel in entries:
        key = (name, table)
        if key not in seen:
            seen.add(key)
            unique.append((name, table, cols, rel))

    usage_map: dict[tuple[str, str], tuple[int, int]] = {}  # (table, index_name) -> (idx_scan, idx_tup_read)
    if args.live:
        database_url = os.getenv("DATABASE_URL", "")
        if not database_url or not database_url.startswith("postgresql"):
            print("[FAIL] --live requires DATABASE_URL pointing to PostgreSQL.")
            return 1
        try:
            from sqlalchemy import create_engine, text
        except ImportError:
            print("[FAIL] sqlalchemy required. pip install sqlalchemy psycopg2-binary")
            return 1
        engine = create_engine(database_url, pool_pre_ping=True)
        with engine.connect() as conn:
            for row in conn.execute(
                text("""
                SELECT relname AS table_name, indexrelname AS index_name,
                       idx_scan, idx_tup_read
                FROM pg_stat_user_indexes
                WHERE schemaname = 'public'
                """)
            ):
                usage_map[(row[0], row[1])] = (row[2] or 0, row[3] or 0)

    print("=" * 72)
    print("INDEX CATALOG WITH USAGE" if args.live else "INDEX CATALOG (codebase)")
    print("=" * 72)
    print(f"Root: {_ROOT}")
    print(f"Index entries (from code): {len(unique)}")
    if args.live:
        print("Usage: idx_scan, idx_tup_read from pg_stat_user_indexes")
    print()

    # Table header
    if args.live:
        print(f"  {'Table':<22} {'Index':<42} {'Defined in':<28} Scans   Tuples_read")
    else:
        print(f"  {'Table':<22} {'Index':<42} {'Defined in':<28} Columns")
    print("-" * 72)

    for name, table, cols, rel in sorted(unique, key=lambda x: (x[1], x[0])):
        rel_str = str(rel)
        if len(rel_str) > 28:
            rel_str = "..." + rel_str[-25:]
        if args.live:
            scan, tup = usage_map.get((table, name), (None, None))
            if scan is None:
                scan_str = "-"
                tup_str = "-"
            else:
                scan_str = str(scan)
                tup_str = str(tup)
            print(f"  {table:<22} {name:<42} {rel_str:<28} {scan_str:>6} {tup_str:>12}")
        else:
            cols_short = (cols[:28] + "...") if len(cols) > 31 else cols
            print(f"  {table:<22} {name:<42} {rel_str:<28} {cols_short}")

    print()
    print("[INFO] Focus: indexes (catalog + optional usage). Run with --live for actionable usage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
