#!/usr/bin/env python3
"""
PostgreSQL Migration 014: Create jobs and job_task_mapping tables

Creates the jobs system tables for grouping tasks (Development, Upkeep, Fitness, etc.).
- jobs: job_id (PK), name, task_type, description, created_at, updated_at
- job_task_mapping: many-to-many (job_id, task_id) with FKs to jobs and tasks

PostgreSQL: uses VARCHAR/TEXT/TIMESTAMP; foreign keys with CASCADE.
Idempotent: skips if tables already exist.

Prerequisites:
- Migration 001 (tasks table) must be completed
- DATABASE_URL must point to PostgreSQL
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

from backend.database import engine, Job, JobTaskMapping
from sqlalchemy import inspect


def table_exists(table_name: str) -> bool:
    """Return True if table exists."""
    try:
        inspector = inspect(engine)
        return table_name in inspector.get_table_names()
    except Exception:
        return False


def migrate() -> bool:
    """Create jobs and job_task_mapping tables if they do not exist."""
    print("=" * 70)
    print("PostgreSQL Migration 014: Create jobs tables")
    print("=" * 70)
    print("\nCreates: jobs, job_task_mapping (for in-app jobs system).")
    print()

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url:
        print("[ERROR] DATABASE_URL is not set.")
        return False
    if not database_url.startswith("postgresql"):
        print("[ERROR] This migration is for PostgreSQL only.")
        return False
    if not table_exists("tasks"):
        print("[ERROR] tasks table does not exist. Run migration 001 first.")
        return False

    if table_exists("jobs") and table_exists("job_task_mapping"):
        print("[NOTE] jobs and job_task_mapping already exist. Skipping (idempotent).")
        return True

    try:
        if not table_exists("jobs"):
            print("Creating jobs table...")
            Job.__table__.create(engine, checkfirst=True)
            print("[OK] jobs table created.")
        else:
            print("[OK] jobs table already exists.")

        if not table_exists("job_task_mapping"):
            print("Creating job_task_mapping table...")
            JobTaskMapping.__table__.create(engine, checkfirst=True)
            print("[OK] job_task_mapping table created.")
        else:
            print("[OK] job_task_mapping table already exists.")

        # Verify
        inspector = inspect(engine)
        for tbl_name, required_cols in [
            ("jobs", ["job_id", "name", "task_type", "description", "created_at", "updated_at"]),
            ("job_task_mapping", ["job_id", "task_id", "created_at"]),
        ]:
            if not table_exists(tbl_name):
                print(f"[WARNING] {tbl_name} missing after create.")
                return False
            cols = [c["name"] for c in inspector.get_columns(tbl_name)]
            missing = [c for c in required_cols if c not in cols]
            if missing:
                print(f"[WARNING] {tbl_name} missing columns: {missing}")
                return False
            print(f"  [OK] {tbl_name}: columns verified.")

        print("\n[SUCCESS] Migration 014 complete.")
        return True
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = migrate()
    sys.exit(0 if success else 1)
