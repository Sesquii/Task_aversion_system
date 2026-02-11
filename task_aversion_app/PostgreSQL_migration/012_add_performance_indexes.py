#!/usr/bin/env python3
"""
PostgreSQL Migration 012: Add performance indexes (dashboard/analytics hot paths)

Adds composite indexes recommended by pg_index_review and pg_add_performance_indexes:
- idx_task_instances_user_active: (user_id, status, is_completed, is_deleted) for
  list_active_instances and dashboard sidebar.
- idx_task_instances_user_completed_at: (user_id, completed_at) WHERE completed_at IS NOT NULL
  for _load_instances(completed_only=True) / relief summary.
- idx_taskinstance_status_completed: (status, is_completed, is_deleted) from add_database_indexes.
- idx_taskinstance_task_completed: (task_id, is_completed) from add_database_indexes.

Uses CREATE INDEX CONCURRENTLY for the first two (requires autocommit; no long table locks).
Uses CREATE INDEX IF NOT EXISTS for the last two (standard transaction).

Prerequisites:
- Migration 005 (task_instances indexes) must be completed
- DATABASE_URL must point to PostgreSQL
"""
import os
import sys
from pathlib import Path

# Add parent directory to path
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Load .env so DATABASE_URL is set when running from project root
try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
    load_dotenv()
except ImportError:
    pass

from sqlalchemy import create_engine, inspect, text


def get_engine_autocommit():
    """Engine with AUTOCOMMIT so CREATE INDEX CONCURRENTLY can run."""
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url or not database_url.startswith("postgresql"):
        return None
    return create_engine(
        database_url,
        pool_pre_ping=True,
        isolation_level="AUTOCOMMIT",
    )


def index_exists(inspector, table_name: str, index_name: str) -> bool:
    """Return True if index_name exists on table_name."""
    try:
        indexes = inspector.get_indexes(table_name)
        return any(idx["name"] == index_name for idx in indexes)
    except Exception:
        return False


def migrate():
    """Add performance indexes. Idempotent (skips if index already exists)."""
    print("=" * 70)
    print("PostgreSQL Migration 012: Add performance indexes")
    print("=" * 70)
    print("\nAdds:")
    print("  - idx_task_instances_user_active (CONCURRENTLY)")
    print("  - idx_task_instances_user_completed_at (CONCURRENTLY)")
    print("  - idx_taskinstance_status_completed")
    print("  - idx_taskinstance_task_completed")
    print()

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        print("[ERROR] DATABASE_URL is not set.")
        return False
    if not database_url.startswith("postgresql"):
        print("[ERROR] This migration is for PostgreSQL only.")
        return False

    try:
        from backend.database import engine
    except Exception as e:
        print(f"[ERROR] Could not import backend.database: {e}")
        return False

    inspector = inspect(engine)
    if "task_instances" not in inspector.get_table_names():
        print("[ERROR] task_instances table does not exist. Run migrations 001-005 first.")
        return False

    engine_autocommit = get_engine_autocommit()
    if engine_autocommit is None:
        print("[ERROR] Could not create autocommit engine (DATABASE_URL not PostgreSQL?).")
        return False

    created = 0
    skipped = 0
    errors = []

    # --- CONCURRENTLY indexes (must run outside transaction) ---
    concurrent_indexes = [
        {
            "name": "idx_task_instances_user_active",
            "sql": """CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_instances_user_active
                      ON task_instances (user_id, status, is_completed, is_deleted)""",
        },
        {
            "name": "idx_task_instances_user_completed_at",
            "sql": """CREATE INDEX CONCURRENTLY IF NOT EXISTS idx_task_instances_user_completed_at
                      ON task_instances (user_id, completed_at)
                      WHERE completed_at IS NOT NULL""",
        },
    ]

    with engine_autocommit.connect() as conn:
        for idx in concurrent_indexes:
            if index_exists(inspector, "task_instances", idx["name"]):
                print(f"  [SKIP] {idx['name']} already exists.")
                skipped += 1
                continue
            try:
                conn.execute(text(idx["sql"].replace("\n", " ").strip()))
                print(f"  [OK] Created {idx['name']}")
                created += 1
                # Refresh inspector for next check
                inspector = inspect(engine)
            except Exception as e:
                errors.append(f"{idx['name']}: {e}")
                print(f"  [FAIL] {idx['name']}: {e}")

    # --- Standard CREATE INDEX IF NOT EXISTS (can use default engine) ---
    standard_indexes = [
        (
            "idx_taskinstance_status_completed",
            "CREATE INDEX IF NOT EXISTS idx_taskinstance_status_completed "
            "ON task_instances (status, is_completed, is_deleted)",
        ),
        (
            "idx_taskinstance_task_completed",
            "CREATE INDEX IF NOT EXISTS idx_taskinstance_task_completed "
            "ON task_instances (task_id, is_completed)",
        ),
    ]

    with engine.connect() as conn:
        for index_name, create_sql in standard_indexes:
            if index_exists(inspector, "task_instances", index_name):
                print(f"  [SKIP] {index_name} already exists.")
                skipped += 1
                continue
            try:
                conn.execute(text(create_sql))
                conn.commit()
                print(f"  [OK] Created {index_name}")
                created += 1
                inspector = inspect(engine)
            except Exception as e:
                conn.rollback()
                errors.append(f"{index_name}: {e}")
                print(f"  [FAIL] {index_name}: {e}")

    if errors:
        print("\n[WARNING] Some indexes failed. Fix errors and re-run (idempotent).")
        return False
    print(f"\n[SUCCESS] Migration 012 complete. Created {created}, skipped {skipped}.")
    return True


if __name__ == "__main__":
    ok = migrate()
    sys.exit(0 if ok else 1)
