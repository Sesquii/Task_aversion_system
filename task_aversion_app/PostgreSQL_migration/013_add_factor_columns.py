#!/usr/bin/env python3
"""
PostgreSQL Migration 013: Add serendipity_factor and disappointment_factor to task_instances

Adds columns used by analytics and InstanceManager for relief-based factors:
- serendipity_factor: max(0, net_relief) (pleasant surprise)
- disappointment_factor: max(0, -net_relief) (disappointment as positive value)

Idempotent: skips columns that already exist. Safe to run after add_factor_columns.py
or on DBs that never ran that script.

Prerequisites:
- Migration 003 (task_instances table) must be completed
- DATABASE_URL must point to PostgreSQL
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
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
    """Add factor columns if missing. Idempotent."""
    print("=" * 70)
    print("PostgreSQL Migration 013: Add factor columns to task_instances")
    print("=" * 70)
    print("\nAdds (if missing):")
    print("  - serendipity_factor REAL")
    print("  - disappointment_factor REAL")
    print()

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        print("[ERROR] DATABASE_URL is not set.")
        return False
    if not database_url.startswith("postgresql"):
        print("[ERROR] This migration is for PostgreSQL only.")
        return False

    if not table_exists("task_instances"):
        print("[ERROR] task_instances table does not exist. Run migration 003 first.")
        return False

    needs_serendipity = not column_exists("task_instances", "serendipity_factor")
    needs_disappointment = not column_exists("task_instances", "disappointment_factor")

    if not needs_serendipity and not needs_disappointment:
        print("[OK] Both columns already exist. Skipping (idempotent).")
        return True

    with engine.connect() as conn:
        if needs_serendipity:
            try:
                conn.execute(text(
                    "ALTER TABLE task_instances ADD COLUMN serendipity_factor REAL"
                ))
                conn.commit()
                print("  [OK] Added serendipity_factor")
            except Exception as e:
                conn.rollback()
                print(f"  [FAIL] serendipity_factor: {e}")
                return False
        if needs_disappointment:
            try:
                conn.execute(text(
                    "ALTER TABLE task_instances ADD COLUMN disappointment_factor REAL"
                ))
                conn.commit()
                print("  [OK] Added disappointment_factor")
            except Exception as e:
                conn.rollback()
                print(f"  [FAIL] disappointment_factor: {e}")
                return False

    print("\n[SUCCESS] Migration 013 complete.")
    return True


if __name__ == "__main__":
    ok = migrate()
    sys.exit(0 if ok else 1)
