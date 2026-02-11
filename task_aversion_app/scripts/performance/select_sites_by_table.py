#!/usr/bin/env python3
"""
SELECT-focused static analysis: where SELECTs appear and which tables/columns they touch.

Part of per-SQL-type coverage (SELECT). Complements analyze_static_queries.py by
breaking down SELECT usage by table and by file. Scans app code for:
  - session.query(Model) -> maps ORM model to __tablename__
  - Raw SQL strings containing SELECT -> extracts FROM/JOIN table names

Outputs actionable counts: SELECT sites per table, per file, and optional column hints
from WHERE/ON clauses. Use to prioritize which tables matter most for read-path optimization.

Usage:
  cd task_aversion_app
  python scripts/performance/select_sites_by_table.py [--top N] [--by-dir]
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path


# Model class name -> table name (from backend/database.py)
MODEL_TO_TABLE: dict[str, str] = {
    "User": "users",
    "Task": "tasks",
    "TaskInstance": "task_instances",
    "Emotion": "emotions",
    "PopupTrigger": "popup_triggers",
    "PopupResponse": "popup_responses",
    "Note": "notes",
    "UserPreferences": "user_preferences",
    "SurveyResponse": "survey_responses",
}


def extract_tables_from_sql(text: str) -> set[str]:
    """Extract table names from SQL: FROM and JOIN clauses (heuristic)."""
    tables: set[str] = set()
    # FROM table_name, FROM "table_name", JOIN table_name
    for m in re.finditer(
        r"(?:FROM|JOIN)\s+[\"']?(\w+)[\"']?(?:\s+AS\s+\w+)?(?:\s+|,|$)",
        text,
        re.IGNORECASE,
    ):
        tables.add(m.group(1).lower())
    return tables


def count_select_sites_in_file(path: Path) -> tuple[dict[str, int], dict[str, set[str]]]:
    """
    Count SELECT-only sites and which tables they touch.
    Returns (table -> count, table -> set of column hints from same line).
    """
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}, {}

    table_counts: dict[str, int] = defaultdict(int)
    table_columns: dict[str, set[str]] = defaultdict(set)

    # session.query(Model) or session.query(Model.col, ...) -> SELECT on that model's table
    for m in re.finditer(r"session\.query\s*\(\s*(\w+)", content):
        model_name = m.group(1)
        if model_name in MODEL_TO_TABLE:
            table = MODEL_TO_TABLE[model_name]
            table_counts[table] += 1
            # Optional: same line might have .filter(Model.column) -> column hint
            line = content[: m.start()].split("\n")[-1] + content[m.start() : m.end() + 80]
            for col in re.findall(r"\.(\w+)\s*(?:==|!=|\.|\)|,)", line):
                if not col.startswith("_"):
                    table_columns[table].add(col)

    # Raw SQL: line-by-line to avoid catastrophic backtracking on large files
    for line in content.splitlines():
        if not re.search(r"SELECT\s+", line, re.IGNORECASE) or not re.search(
            r"FROM\s+\w+", line, re.IGNORECASE
        ):
            continue
        if "'" in line or '"' in line:
            for t in extract_tables_from_sql(line):
                table_counts[t] += 1

    return dict(table_counts), dict(table_columns)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="SELECT-focused: static SELECT sites by table (no DB required)"
    )
    parser.add_argument("--top", type=int, default=25, help="Show top N files by SELECT sites")
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

    exclude_dirs = ("venv", ".venv", "__pycache__", "SQLite_migration", "PostgreSQL_migration")
    include_dirs = ("backend", "ui")
    py_files: list[Path] = []
    for p in root.rglob("*.py"):
        parts = p.parts
        if any(ex in parts for ex in exclude_dirs):
            continue
        rel = p.relative_to(root)
        if str(rel) == "app.py" or (rel.parts and rel.parts[0] in include_dirs):
            py_files.append(p)

    global_table_counts: dict[str, int] = defaultdict(int)
    global_table_files: dict[str, set[str]] = defaultdict(set)
    file_totals: list[tuple[Path, dict[str, int], int]] = []
    dir_totals: dict[str, int] = defaultdict(int)

    for path in py_files:
        rel = path.relative_to(root)
        table_counts, _ = count_select_sites_in_file(path)
        total = sum(table_counts.values())
        if total > 0:
            file_totals.append((rel, table_counts, total))
            for t, c in table_counts.items():
                global_table_counts[t] += c
                global_table_files[t].add(str(rel))
            if args.by_dir:
                dir_name = str(rel.parent) if rel.parent != Path(".") else "."
                dir_totals[dir_name] += total

    file_totals.sort(key=lambda x: -x[2])

    print("=" * 72)
    print("SELECT SITES BY TABLE (static; SELECT-focused)")
    print("=" * 72)
    print(f"Root: {root}")
    print(f"Files scanned: {len(py_files)}")
    print(f"Files with at least one SELECT site: {len(file_totals)}")
    print()

    # Per-table totals (actionable counts)
    print("--- SELECT site count by table ---")
    for table in sorted(global_table_counts.keys(), key=lambda t: -global_table_counts[t]):
        cnt = global_table_counts[table]
        n_files = len(global_table_files[table])
        print(f"  {cnt:5d}  {table:25s}  ({n_files} file(s))")
    print()

    if args.by_dir:
        print("--- By directory (SELECT sites) ---")
        for dir_name in sorted(dir_totals.keys(), key=lambda d: -dir_totals[d]):
            print(f"  {dir_totals[dir_name]:5d}  {dir_name}")
        print()

    print("--- Top files by SELECT site count ---")
    for rel, counts, total in file_totals[: args.top]:
        detail = "  ".join(f"{t}:{c}" for t, c in sorted(counts.items(), key=lambda x: -x[1]))
        print(f"  {total:5d}  {rel}")
        if detail:
            print(f"         {detail}")
    print()
    print("[INFO] SELECT-focused analysis for per-SQL-type coverage.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
