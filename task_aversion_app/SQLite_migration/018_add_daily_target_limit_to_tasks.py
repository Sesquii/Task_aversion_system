#!/usr/bin/env python
"""
Migration 018: Add daily_target and daily_limit to tasks table (SQLite)

Adds two optional INTEGER columns to task templates:
- daily_target: desired times/day (nullable)
- daily_limit: maximum times/day (nullable)
"""
import os
import sys

# Add parent directory to path
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
    """Add daily target/limit columns to tasks table if they don't exist."""
    print("=" * 70)
    print("Migration 018: Add daily_target/daily_limit to tasks")
    print("=" * 70)
    print()

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        print("[ERROR] DATABASE_URL environment variable is not set!")
        print("Please set it before running this migration.")
        print("Example: $env:DATABASE_URL = 'sqlite:///data/task_aversion.db'  (PowerShell)")
        return False

    if not database_url.lower().startswith("sqlite"):
        print("[WARNING] This migration is designed for SQLite.")
        print(f"Current DATABASE_URL: {database_url}")
        response = input("Continue anyway? (y/N): ")
        if response.lower() != "y":
            return False

    columns_to_add = [
        {"name": "daily_target", "type": "INTEGER", "nullable": True},
        {"name": "daily_limit", "type": "INTEGER", "nullable": True},
    ]

    with get_session() as session:
        try:
            inspector = inspect(engine)
            if "tasks" not in inspector.get_table_names():
                print("[ERROR] Tasks table does not exist!")
                print("Please run migration 001 (initial schema) first.")
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
                print(f"\nErrors encountered: {len(errors)}")
                for err in errors:
                    print(f"  - {err}")
                return False

            # Verification
            print("\n" + "=" * 70)
            print("Verification")
            print("=" * 70)
            all_ok = True
            for col_def in columns_to_add:
                exists = column_exists("tasks", col_def["name"])
                status = "[OK]" if exists else "[MISSING]"
                print(f"   {status} {col_def['name']}: {'exists' if exists else 'MISSING'}")
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

