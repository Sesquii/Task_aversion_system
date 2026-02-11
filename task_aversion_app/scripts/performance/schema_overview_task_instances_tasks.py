#!/usr/bin/env python3
"""
Educational: schema overview for task_instances, tasks, and user_id usage.

Documents DB architecture and SQL semantics: main tables (tasks, task_instances,
users), key columns, foreign keys, and indexes. Explains how user_id is used for
scoping and how task_instances relate to tasks. Static analysis of backend/database.py;
optional --live uses PostgreSQL information_schema for current columns/indexes.
Yields clear explanatory output for learning; no immediate optimization.

Run from task_aversion_app:
  python scripts/performance/schema_overview_task_instances_tasks.py [--live]
"""
from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def extract_table_info(database_py: Path) -> dict[str, dict]:
    """
    Parse database.py for Task, TaskInstance, User: tablename, columns, user_id, FKs, indexes.
    Returns dict keyed by class name with keys: tablename, columns, user_id_fk, indexes.
    """
    try:
        text = database_py.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return {}

    result: dict[str, dict] = {}
    for class_name in ("User", "Task", "TaskInstance"):
        # Capture full class body up to next top-level "class "
        start_pat = (
            r"class\s+"
            + re.escape(class_name)
            + r"\s*\([^)]*\)\s*:.*?__tablename__\s*=\s*['\"]([^'\"]+)['\"]"
        )
        m = re.search(start_pat, text, re.DOTALL)
        if not m:
            continue
        tablename = m.group(1)
        start_pos = m.start()
        # Find end of this class: next "\nclass " at beginning of a line
        rest = text[m.end() :]
        end_m = re.search(r"\nclass\s+\w+\s*\(", rest)
        block = text[start_pos : m.end() + (end_m.start() if end_m else len(rest))]

        columns: list[str] = []
        user_id_fk: str | None = None
        indexes: list[str] = []

        for col in re.finditer(r"(\w+)\s*=\s*Column\s*\([^)]+\)", block):
            columns.append(col.group(1))

        fk = re.search(r"user_id\s*=\s*Column\s*\([^)]*ForeignKey\s*\(\s*['\"]([^'\"]+)['\"]", block)
        if fk:
            user_id_fk = fk.group(1)

        # Index and UniqueConstraint can appear in __table_args__ anywhere in block
        for idx in re.finditer(r"Index\s*\(\s*['\"](\w+)['\"][^)]*\)", block):
            indexes.append(idx.group(1))
        for uq in re.finditer(r"UniqueConstraint\s*\([^)]+\)", block):
            indexes.append("UniqueConstraint(...)")

        result[class_name] = {
            "tablename": tablename,
            "columns": columns,
            "user_id_fk": user_id_fk,
            "indexes": indexes,
        }

        task_id_fk = re.search(r"task_id\s*=\s*Column\s*\([^)]*", block)
        if class_name == "TaskInstance" and task_id_fk:
            result[class_name]["task_id_ref"] = "tasks.task_id"

    return result


def print_static_overview(info: dict[str, dict]) -> None:
    """Print educational schema overview from static parse."""
    print("=" * 72)
    print("SCHEMA OVERVIEW: task_instances, tasks, user_id (educational)")
    print("=" * 72)
    print()
    print("Core tables (from backend/database.py):")
    print("- users: user_id (PK), email, OAuth fields. user_id is INTEGER.")
    print("- tasks: task_id (PK), name, user_id (FK -> users). Task template.")
    print("- task_instances: instance_id (PK), task_id, user_id (FK -> users),")
    print("  status, is_completed, is_deleted, completed_at, scores, etc. One row per execution.")
    print()

    for class_name in ("User", "Task", "TaskInstance"):
        if class_name not in info:
            continue
        d = info[class_name]
        print("--- %s (%s) ---" % (class_name, d["tablename"]))
        print("  Columns (sample): %s" % ", ".join(d["columns"][:12]))
        if len(d["columns"]) > 12:
            print("  ... and %d more" % (len(d["columns"]) - 12))
        if d.get("user_id_fk"):
            print("  user_id -> %s" % d["user_id_fk"])
        if d.get("task_id_ref"):
            print("  task_id -> %s" % d["task_id_ref"])
        if d.get("indexes"):
            print("  Indexes: %s" % ", ".join(d["indexes"]))
        print()

    print("SQL semantics:")
    print("- Dashboard/analytics scope by user_id: WHERE user_id = :uid")
    print("- task_instances join to tasks via task_id (no FK in DB for task_id; app-level link)")
    print("- Active instances: status NOT IN ('completed','cancelled'), is_completed=false, is_deleted=false")
    print("- Composite indexes on task_instances: status+is_completed+is_deleted, task_id+is_completed")
    print()


def run_live_overview() -> int:
    """Query PostgreSQL information_schema for tasks, task_instances, users. Returns 0 on success, 1 on failure."""
    from sqlalchemy import create_engine, text

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url or not database_url.startswith("postgresql"):
        print("[FAIL] --live requires DATABASE_URL=postgresql://...")
        return 1

    engine = create_engine(database_url, pool_pre_ping=True)
    tables = ["users", "tasks", "task_instances"]

    print("--- Live (information_schema) columns ---")
    with engine.connect() as conn:
        for table in tables:
            r = conn.execute(
                text("""
                SELECT column_name, data_type, is_nullable
                FROM information_schema.columns
                WHERE table_schema = 'public' AND table_name = :t
                ORDER BY ordinal_position
                """),
                {"t": table},
            )
            rows = list(r)
            if rows:
                print("%s: %s" % (table, ", ".join("%s (%s)" % (row[0], row[1]) for row in rows[:15])))
                if len(rows) > 15:
                    print("  ... and %d more columns" % (len(rows) - 15))
            else:
                print("%s: (table not found or empty)" % table)
    print()

    print("--- Live indexes on task_instances / tasks ---")
    with engine.connect() as conn:
        r = conn.execute(
            text("""
            SELECT tablename, indexname, indexdef
            FROM pg_indexes
            WHERE schemaname = 'public' AND tablename IN ('task_instances', 'tasks', 'users')
            ORDER BY tablename
            """),
        )
        for row in r:
            print("%s: %s" % (row[0], row[1]))
            print("  %s" % (row[2][:90] + "..." if len(row[2]) > 90 else row[2]))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Schema overview for task_instances, tasks, user_id (educational)"
    )
    parser.add_argument(
        "--live",
        action="store_true",
        help="Query PostgreSQL information_schema for columns and indexes",
    )
    args = parser.parse_args()

    base = Path(__file__).resolve().parent.parent.parent
    database_py = base / "backend" / "database.py"
    info = extract_table_info(database_py) if database_py.is_file() else {}

    print_static_overview(info)

    if args.live:
        return run_live_overview()

    return 0


if __name__ == "__main__":
    sys.exit(main())
