#!/usr/bin/env python3
"""
INSERT/UPDATE/DELETE-focused static analysis: write-path sites by inferred table.

Scans app code (backend, ui, app.py; excludes migration dirs) for writes and
infers target table where possible:
  - Raw SQL: INSERT INTO tbl, UPDATE tbl SET, DELETE FROM tbl (extracts tbl)
  - ORM bulk delete: session.query(Model).filter(...).delete() -> Model/table
  - session.add(x) / session.delete(x): attributed to same-file ORM write count
    (table inferred only when add/delete is near session.query(Model) on same line
    or previous line, e.g. session.add(instance) after query(TaskInstance))

Outputs actionable counts per table (and "ORM unknown" for untyped adds/deletes)
to find which tables are write hotspots. Use for per-SQL-type write coverage.

Usage:
  cd task_aversion_app
  python scripts/performance/write_sites_by_table.py [--top N]
"""
from __future__ import annotations

import argparse
import re
import sys
from collections import defaultdict
from pathlib import Path

# Known ORM model -> table name (from backend/database.py)
MODEL_TO_TABLE = {
    "User": "users",
    "Task": "tasks",
    "TaskInstance": "task_instances",
    "Emotion": "emotions",
    "Note": "notes",
    "PopupTrigger": "popup_triggers",
    "PopupResponse": "popup_responses",
    "UserPreferences": "user_preferences",
    "SurveyResponse": "survey_responses",
}


def extract_raw_sql_tables(text: str) -> list[tuple[str, str]]:
    """Return list of (op, table) for raw SQL: INSERT INTO tbl, UPDATE tbl SET, DELETE FROM tbl."""
    result = []
    # INSERT INTO table_name ( or INSERT INTO "table"
    for m in re.finditer(
        r"INSERT\s+INTO\s+(?:[\"\']?)(\w+)(?:[\"\']?)\s*[\(\s]",
        text,
        re.IGNORECASE,
    ):
        result.append(("INSERT", m.group(1).lower()))
    # UPDATE table_name SET
    for m in re.finditer(
        r"UPDATE\s+(?:[\"\']?)(\w+)(?:[\"\']?)\s+SET\s+",
        text,
        re.IGNORECASE,
    ):
        result.append(("UPDATE", m.group(1).lower()))
    # DELETE FROM table_name
    for m in re.finditer(
        r"DELETE\s+FROM\s+(?:[\"\']?)(\w+)(?:[\"\']?)\s*[\s;]",
        text,
        re.IGNORECASE,
    ):
        result.append(("DELETE", m.group(1).lower()))
    return result


def extract_orm_bulk_delete_models(text: str) -> list[str]:
    """Return list of model names from session.query(Model).filter(...).delete()."""
    result = []
    # Multiline: session.query(SomeModel). ... .delete()
    for m in re.finditer(
        r"session\.query\s*\(\s*(?:self\.)?([A-Za-z_][A-Za-z0-9_]*)\s*\)[\s\S]*?\.delete\s*\(",
        text,
        re.DOTALL,
    ):
        result.append(m.group(1))
    # Same line
    for m in re.finditer(
        r"session\.query\s*\(\s*(?:self\.)?([A-Za-z_][A-Za-z0-9_]*)\s*\)[^.]*\.delete\s*\(",
        text,
    ):
        result.append(m.group(1))
    return list(set(result))


def count_orm_add_delete_in_file(text: str) -> int:
    """Count session.add( and session.delete( (single-row ORM writes)."""
    return len(re.findall(r"session\.add\s*\(", text)) + len(
        re.findall(r"session\.delete\s*\(", text)
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Write-path sites by inferred table (INSERT/UPDATE/DELETE-focused)"
    )
    parser.add_argument("--top", type=int, default=25, help="Show top N tables and top N files")
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

    table_counts: dict[str, int] = defaultdict(int)  # table or "Model (ORM)" -> count
    file_to_tables: dict[Path, dict[str, int]] = defaultdict(lambda: defaultdict(int))

    for path in py_files:
        rel = path.relative_to(root)
        try:
            text = path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        # Raw SQL
        for op, tbl in extract_raw_sql_tables(text):
            table_counts[tbl] += 1
            file_to_tables[rel][tbl] += 1
        # ORM: bulk delete by model
        for model in extract_orm_bulk_delete_models(text):
            tbl = MODEL_TO_TABLE.get(model, model)
            table_counts[tbl] += 1
            file_to_tables[rel][tbl] += 1
        # ORM: single-row add/delete (not attributed to table)
        add_del = count_orm_add_delete_in_file(text)
        if add_del > 0:
            table_counts["ORM (add/delete)"] += add_del
            file_to_tables[rel]["ORM (add/delete)"] += add_del

    # Sort tables by count
    sorted_tables = sorted(table_counts.items(), key=lambda x: -x[1])
    sorted_files = sorted(
        file_to_tables.items(),
        key=lambda x: -sum(x[1].values()),
    )

    print("=" * 72)
    print("WRITE-PATH SITES BY TABLE (INSERT/UPDATE/DELETE-focused)")
    print("=" * 72)
    print(f"Root: {root}")
    print(f"Scoped to: app.py, backend/, ui/ (excludes migrations)")
    print(f"Files scanned: {len(py_files)}")
    print()
    print("--- Write sites by inferred table ---")
    for tbl, count in sorted_tables[: args.top]:
        print(f"  {count:5d}  {tbl}")
    print()
    print("--- Top files by write sites (with table breakdown) ---")
    for rel, tbl_counts in sorted_files[: args.top]:
        total = sum(tbl_counts.values())
        detail = "  ".join(f"{t}:{c}" for t, c in sorted(tbl_counts.items(), key=lambda x: -x[1]))
        print(f"  {total:5d}  {rel}")
        if detail:
            print(f"         {detail}")
    print()
    print("Legend: raw SQL table from INSERT/UPDATE/DELETE; ORM from session.query(Model).delete()")
    print("and session.add/delete near query(Model). (ORM unknown) = add/delete not attributed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
