#!/usr/bin/env python
"""
Migration 019: Add daily time and weekly count/time target/limit columns to tasks (SQLite).

Adds six optional INTEGER columns:
- daily_time_target_minutes, daily_time_limit_minutes
- weekly_count_target, weekly_count_limit
- weekly_time_target_minutes, weekly_time_limit_minutes
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import engine, get_session  # noqa: E402
from sqlalchemy import inspect, text  # noqa: E402


def column_exists(table_name: str, column_name: str) -> bool:
    """Check if a column exists in a table."""
    try:
        inspector = inspect(engine)
        columns = [col["name"] for col in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception as e:
        print(f"   [ERROR] Failed to check column existence: {e}")
        return False


def migrate() -> bool:
    """Add daily time and weekly count/time target/limit columns to tasks table if missing."""
    print("=" * 70)
    print("Migration 019: Add daily time & weekly count/time targets/limits")
    print("=" * 70)
    print()

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        print("[ERROR] DATABASE_URL environment variable is not set!")
        return False

    if not database_url.lower().startswith("sqlite"):
        print("[WARNING] This migration is designed for SQLite.")
        print(f"Current DATABASE_URL: {database_url}")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != "y":
            return False

    columns_to_add = [
        {"name": "daily_time_target_minutes", "type": "INTEGER", "nullable": True},
        {"name": "daily_time_limit_minutes", "type": "INTEGER", "nullable": True},
        {"name": "weekly_count_target", "type": "INTEGER", "nullable": True},
        {"name": "weekly_count_limit", "type": "INTEGER", "nullable": True},
        {"name": "weekly_time_target_minutes", "type": "INTEGER", "nullable": True},
        {"name": "weekly_time_limit_minutes", "type": "INTEGER", "nullable": True},
    ]

    with get_session() as session:
        try:
            inspector = inspect(engine)
            if "tasks" not in inspector.get_table_names():
                print("[ERROR] Tasks table does not exist!")
                return False

            added = 0
            skipped = 0
            errors: list[str] = []

            for col_def in columns_to_add:
                name = col_def["name"]
                if column_exists("tasks", name):
                    print(f"   [SKIP] Column '{name}' already exists")
                    skipped += 1
                    continue

                alter_sql = f"ALTER TABLE tasks ADD COLUMN {name} {col_def['type']}"
                try:
                    session.execute(text(alter_sql))
                    session.commit()
                    print(f"   [OK] Added column '{name}'")
                    added += 1
                except Exception as e:
                    session.rollback()
                    msg = f"Failed to add column '{name}': {e}"
                    print(f"   [ERROR] {msg}")
                    errors.append(msg)

            print("\n" + "=" * 70)
            print("Migration Summary")
            print("=" * 70)
            print(f"Columns added: {added}")
            print(f"Columns skipped (already exist): {skipped}")
            if errors:
                for err in errors:
                    print(f"  - {err}")
                return False

            print("\nVerification:")
            all_ok = True
            for col_def in columns_to_add:
                exists = column_exists("tasks", col_def["name"])
                status = "[OK]" if exists else "[MISSING]"
                print(f"   {status} {col_def['name']}")
                all_ok = all_ok and exists
            return all_ok
        except Exception as e:
            session.rollback()
            print(f"\n[ERROR] Migration failed: {e}")
            import traceback
            traceback.print_exc()
            return False


if __name__ == "__main__":
    ok = migrate()
    sys.exit(0 if ok else 1)
