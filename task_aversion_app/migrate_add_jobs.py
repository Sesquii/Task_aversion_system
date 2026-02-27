#!/usr/bin/env python3
"""
Migration: ensure jobs tables exist so the in-app jobs system works.

Creates `jobs` and `job_task_mapping` tables if missing (via init_db).
Does not create any default jobs; users create jobs in the app and assign
tasks via the Jobs page / Assign tasks to jobs flow.

Usage:
  python migrate_add_jobs.py    # Ensure jobs schema exists (idempotent)
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def migrate_add_jobs() -> bool:
    """Ensure jobs and job_task_mapping tables exist. No default jobs created."""
    print("\n" + "=" * 70)
    print("MIGRATION: Ensure jobs tables exist (schema only)")
    print("=" * 70)

    try:
        from backend.database import init_db

        init_db()
        print("[SUCCESS] Jobs schema ready. Create jobs and assign tasks in the app.")
        return True
    except Exception as e:
        print(f"\n[ERROR] Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = migrate_add_jobs()
    sys.exit(0 if success else 1)
