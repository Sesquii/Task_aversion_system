#!/usr/bin/env python3
"""
One-off static analysis: PostgreSQL-relevant query sites only (no PRAGMA).

Scans app code (backend, ui, app.py; excludes SQLite/PostgreSQL migration dirs)
for query sites that run when DATABASE_URL is PostgreSQL:
  - session.query(, .execute(, execute(text(
  - Raw SQL strings: SELECT, INSERT, UPDATE, DELETE

PRAGMA is reported separately; it is SQLite-only and does not run in production.
Use this to scope performance work on the final PostgreSQL deployment.

Usage:
  cd task_aversion_app
  python scripts/performance/pg_query_sites_static.py [--top N] [--by-dir]
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path


def count_in_file(path: Path) -> dict[str, int]:
    """Count query-related patterns. Returns dict of pattern -> count.

    Uses line-by-line regex for SQL-in-strings to avoid ReDoS (catastrophic
    backtracking) from patterns like .*?...*? on large files.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}
    lines = text.splitlines()
    counts = {
        "session.query": len(re.findall(r"session\.query\s*\(", text)),
        "execute": len(re.findall(r"\.execute\s*\(\s*", text))
        + len(re.findall(r"execute\s*\(\s*text\s*\(|conn\.execute\s*\(", text)),
        "SELECT": 0,
        "INSERT": 0,
        "UPDATE": 0,
        "DELETE": 0,
        "PRAGMA": len(re.findall(r"PRAGMA\s+", text, re.IGNORECASE)),
    }
    # Count SQL keywords inside string-like contexts line-by-line to avoid
    # catastrophic backtracking (ReDoS) from .*? with re.DOTALL on whole file.
    for line in lines:
        if re.search(r"[\'\"].*SELECT\s+", line, re.IGNORECASE) or re.search(
            r"SELECT\s+.*[\'\"].*\)", line, re.IGNORECASE
        ):
            counts["SELECT"] += 1
        counts["INSERT"] += len(re.findall(r"[\'\"].*?INSERT\s+", line, re.IGNORECASE)) + len(
            re.findall(r"text\s*\(\s*[\'\"].*?INSERT\s+", line, re.IGNORECASE)
        )
        counts["UPDATE"] += len(re.findall(r"[\'\"].*?UPDATE\s+", line, re.IGNORECASE)) + len(
            re.findall(r"text\s*\(\s*[\'\"].*?UPDATE\s+", line, re.IGNORECASE)
        )
        counts["DELETE"] += len(re.findall(r"[\'\"].*?DELETE\s+", line, re.IGNORECASE)) + len(
            re.findall(r"text\s*\(\s*[\'\"].*?DELETE\s+", line, re.IGNORECASE)
        )
    return counts


def pg_relevant_total(counts: dict[str, int]) -> int:
    """Sum of counts that run on PostgreSQL (exclude PRAGMA)."""
    return (
        counts.get("session.query", 0)
        + counts.get("execute", 0)
        + counts.get("SELECT", 0)
        + counts.get("INSERT", 0)
        + counts.get("UPDATE", 0)
        + counts.get("DELETE", 0)
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="PostgreSQL-relevant query sites (static; no DB required)"
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

    # Directories that run when app uses PostgreSQL (exclude migration one-offs)
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
    # Include scripts/performance for completeness
    for p in (root / "scripts" / "performance").rglob("*.py"):
        if p.suffix == ".py" and "__pycache__" not in p.parts:
            if p not in py_files:
                py_files.append(p)

    file_counts: list[tuple[Path, dict[str, int], int]] = []
    dir_totals: dict[str, int] = defaultdict(int)
    pragma_total = 0

    for path in py_files:
        rel = path.relative_to(root)
        counts = count_in_file(path)
        pg_total = pg_relevant_total(counts)
        pragma_total += counts.get("PRAGMA", 0)
        if pg_total > 0 or counts.get("PRAGMA", 0) > 0:
            file_counts.append((rel, counts, pg_total))
            if args.by_dir:
                dir_name = str(rel.parent) if rel.parent != Path(".") else "."
                dir_totals[dir_name] += pg_total

    file_counts.sort(key=lambda x: -x[2])

    print("=" * 72)
    print("POSTGRESQL-RELEVANT QUERY SITES (static; PRAGMA excluded)")
    print("=" * 72)
    print(f"Root: {root}")
    print(f"Scoped to: app.py, backend/, ui/, scripts/performance/")
    print(f"Excluded: SQLite_migration, PostgreSQL_migration")
    print(f"Files scanned: {len(py_files)}")
    print(f"Files with >= 1 PostgreSQL-relevant site: {len([f for f in file_counts if f[2] > 0])}")
    if pragma_total > 0:
        print(f"[INFO] PRAGMA (SQLite-only) sites in scoped files: {pragma_total}")
    print()

    if args.by_dir:
        print("--- By directory (PostgreSQL-relevant sites) ---")
        for dir_name in sorted(dir_totals.keys(), key=lambda d: -dir_totals[d]):
            print(f"  {dir_totals[dir_name]:5d}  {dir_name}")
        print()

    print("--- Top files by PostgreSQL-relevant query sites ---")
    for rel, counts, total in file_counts[: args.top]:
        if total == 0:
            continue
        detail = "  ".join(f"{k}:{v}" for k, v in counts.items() if v > 0 and k != "PRAGMA")
        pragma_n = counts.get("PRAGMA", 0)
        suffix = f"  (PRAGMA:{pragma_n})" if pragma_n else ""
        print(f"  {total:5d}  {rel}{suffix}")
        if detail:
            print(f"         {detail}")
    print()
    print("Legend: session.query, execute, SELECT/INSERT/UPDATE/DELETE in SQL strings.")
    print("PRAGMA is SQLite-only; see PERFORMANCE_POSTGRESQL_SCOPE.md.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
