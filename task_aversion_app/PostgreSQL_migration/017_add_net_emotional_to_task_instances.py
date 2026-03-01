#!/usr/bin/env python3
"""
PostgreSQL Migration 017: Add net_emotional to task_instances.

Adds column used for emotional intensity misperception:
- net_emotional = actual_emotional - expected_emotional_load

Idempotent: skips if column already exists. Safe to run after add_factor_columns.py
(which also adds net_emotional for SQLite/local).

Prerequisites:
- task_instances table must exist
- DATABASE_URL must point to PostgreSQL (or SQLite for local add_factor_columns.py)
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

from backend.database import engine
from sqlalchemy import inspect, text


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
    """Add net_emotional to task_instances if missing. Idempotent."""
    print("=" * 70)
    print("PostgreSQL Migration 017: Add net_emotional to task_instances")
    print("=" * 70)
    print("\nAdds (if missing): net_emotional REAL (nullable)")
    print()

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        print("[ERROR] DATABASE_URL is not set.")
        return False
    if not database_url.startswith("postgresql"):
        print("[ERROR] This migration is for PostgreSQL only.")
        return False

    if not table_exists("task_instances"):
        print("[ERROR] task_instances table does not exist. Run earlier migrations first.")
        return False

    if column_exists("task_instances", "net_emotional"):
        print("[OK] Column net_emotional already exists. Skipping (idempotent).")
        return True

    with engine.connect() as conn:
        try:
            conn.execute(text(
                "ALTER TABLE task_instances ADD COLUMN net_emotional REAL"
            ))
            conn.commit()
            print("  [OK] Added net_emotional")
        except Exception as e:
            conn.rollback()
            print(f"  [FAIL] net_emotional: {e}")
            return False

    print("\n[SUCCESS] Migration 017 complete.")
    return True


if __name__ == "__main__":
    ok = migrate()
    sys.exit(0 if ok else 1)
