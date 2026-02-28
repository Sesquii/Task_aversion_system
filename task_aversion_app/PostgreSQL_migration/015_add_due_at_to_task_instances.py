#!/usr/bin/env python3
"""
Migration 015: Add due_at to task_instances.

Adds optional due_at (datetime) column for instance-level deadlines.
Overdue = now > due_at. Used by urgency score system.

Idempotent: safe to run multiple times (checks for column first).
Supports both PostgreSQL and SQLite (uses TIMESTAMP vs DATETIME as appropriate).
Does not modify or backfill existing rows; new column is NULL for all existing rows.
"""
import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
    load_dotenv()
except ImportError:
    pass

from sqlalchemy import inspect, text
from backend.database import engine


def table_exists(table_name: str) -> bool:
    """Return True if table exists."""
    try:
        inspector = inspect(engine)
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def column_exists(table_name: str, column_name: str) -> bool:
    """Return True if column exists on table."""
    try:
        inspector = inspect(engine)
        columns = [c["name"] for c in inspector.get_columns(table_name)]
        return column_name in columns
    except Exception:
        return False


def migrate():
    """Add due_at to task_instances if missing. Idempotent; no data changes."""
    print("=" * 70)
    print("Migration 015: Add due_at to task_instances")
    print("=" * 70)

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        print("[ERROR] DATABASE_URL not set")
        return False

    if not table_exists("task_instances"):
        print("[ERROR] task_instances table does not exist. Run earlier migrations first.")
        return False

    if column_exists("task_instances", "due_at"):
        print("[OK] Column due_at already exists. Skipping (idempotent).")
        return True

    # PostgreSQL: TIMESTAMP WITHOUT TIME ZONE (nullable); SQLite: DATETIME
    # Idempotency is ensured by column_exists() check above (no ADD COLUMN IF NOT EXISTS needed).
    if database_url.startswith("postgresql"):
        stmt = "ALTER TABLE task_instances ADD COLUMN due_at TIMESTAMP WITHOUT TIME ZONE"
    else:
        # SQLite: DATETIME; no IF NOT EXISTS for column in older SQLite
        stmt = "ALTER TABLE task_instances ADD COLUMN due_at DATETIME"

    try:
        with engine.connect() as conn:
            conn.execute(text(stmt))
            conn.commit()
        print("[OK] Column due_at added to task_instances (existing rows unchanged, due_at=NULL)")
        return True
    except Exception as e:
        print(f"[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
