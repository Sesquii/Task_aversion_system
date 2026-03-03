#!/usr/bin/env python3
"""
Database reset script: drop all tables and re-run migrations from scratch.

Use this when you need a clean database (e.g. after schema issues or to verify
analytics/data behavior). All data will be permanently deleted.
For a full DROP DATABASE + CREATE DATABASE (not just tables), use recreate_database.py.

Supports:
- PostgreSQL: drops all tables, then runs migrations 001-017 (includes jobs).
- SQLite: drops all tables, then runs init_db() and migrate_add_jobs.

Requires DATABASE_URL in environment (set in .env or export/set before running).

Usage:
  cd task_aversion_app
  python reset_database.py

  # Skip confirmation prompt (e.g. for scripts):
  python reset_database.py --yes

  # Or with explicit DATABASE_URL (PowerShell):
  $env:DATABASE_URL = "postgresql://user:password@localhost:5432/task_aversion_test"
  python reset_database.py
"""
import os
import sys
from pathlib import Path

# App root (task_aversion_app)
_APP_ROOT = Path(__file__).resolve().parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

# Load .env so DATABASE_URL is set; on VPS also try .env.production
try:
    from dotenv import load_dotenv
    load_dotenv(_APP_ROOT / ".env")
    load_dotenv()
    if not os.getenv("DATABASE_URL"):
        load_dotenv(_APP_ROOT / ".env.production")
except ImportError:
    pass


def run_script(script_path: Path, description: str) -> bool:
    """Run a Python migration script; return True on success."""
    import subprocess
    env = os.environ.copy()
    if not env.get("DATABASE_URL") and os.getenv("DATABASE_URL"):
        env["DATABASE_URL"] = os.getenv("DATABASE_URL")
    result = subprocess.run(
        [sys.executable, str(script_path)],
        cwd=str(_APP_ROOT),
        env=env,
        capture_output=False,
    )
    if result.returncode != 0:
        print(f"[FAIL] {description} exited with code {result.returncode}")
        return False
    return True


def reset_postgres() -> bool:
    """Drop all tables and run PostgreSQL migrations 001-017 (includes jobs)."""
    from backend.database import Base, engine

    print("Dropping all tables...")
    try:
        Base.metadata.drop_all(bind=engine)
        print("[OK] All tables dropped.")
    except Exception as e:
        print(f"[ERROR] Failed to drop tables: {e}")
        return False

    migrations = [
        ("001_initial_schema.py", "001 Initial schema"),
        ("002_add_routine_scheduling_fields.py", "002 Routine scheduling fields"),
        ("003_create_task_instances_table.py", "003 Task instances table"),
        ("004_create_emotions_table.py", "004 Emotions table"),
        ("005_add_indexes_and_foreign_keys.py", "005 Indexes and foreign keys"),
        ("006_add_notes_column.py", "006 Notes column"),
        ("007_create_user_preferences_table.py", "007 User preferences table"),
        ("008_create_survey_responses_table.py", "008 Survey responses table"),
        ("009_create_users_table.py", "009 Users table"),
        ("010_add_user_id_foreign_keys.py", "010 User ID foreign keys"),
        ("011_add_user_id_to_emotions.py", "011 User ID on emotions"),
        ("012_add_performance_indexes.py", "012 Performance indexes"),
        ("013_add_factor_columns.py", "013 Factor columns"),
        ("014_create_jobs_tables.py", "014 Jobs tables"),
        ("015_add_due_at_to_task_instances.py", "015 Add due_at to task_instances"),
        ("016_add_timezone_to_user_preferences.py", "016 Add timezone to user_preferences"),
        ("017_add_net_emotional_to_task_instances.py", "017 Add net_emotional to task_instances"),
        ("018_add_hour12_to_user_preferences.py", "018 Add hour12 to user_preferences"),
    ]
    mig_dir = _APP_ROOT / "PostgreSQL_migration"
    for filename, desc in migrations:
        path = mig_dir / filename
        if not path.exists():
            print(f"[WARNING] Migration script not found: {path}")
            continue
        print(f"\nRunning {desc}...")
        if not run_script(path, desc):
            return False

    return True


def reset_sqlite() -> bool:
    """Drop all tables and re-initialize SQLite via init_db()."""
    from backend.database import Base, engine, init_db

    print("Dropping all tables...")
    try:
        Base.metadata.drop_all(bind=engine)
        print("[OK] All tables dropped.")
    except Exception as e:
        print(f"[ERROR] Failed to drop tables: {e}")
        return False

    print("\nInitializing schema (init_db)...")
    try:
        init_db()
        print("[OK] Schema initialized.")
    except Exception as e:
        print(f"[ERROR] init_db failed: {e}")
        return False

    jobs_script = _APP_ROOT / "migrate_add_jobs.py"
    if jobs_script.exists():
        print("\nRunning migrate_add_jobs...")
        if not run_script(jobs_script, "migrate_add_jobs"):
            return False

    return True


def main() -> int:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        print("[ERROR] DATABASE_URL is not set.")
        print("Set it in .env or run: $env:DATABASE_URL = 'postgresql://...'  (PowerShell)")
        return 1

    print("=" * 70)
    print("Database reset (drop all tables and re-run migrations)")
    print("=" * 70)
    print(f"Database: {database_url}")
    print("\n[WARNING] All data will be permanently deleted.")
    force = "--yes" in sys.argv or "-y" in sys.argv
    if not force:
        try:
            confirm = input("Type 'yes' to continue: ").strip().lower()
        except EOFError:
            confirm = "no"
        if confirm != "yes":
            print("Aborted.")
            return 0

    if database_url.startswith("postgresql"):
        ok = reset_postgres()
    else:
        ok = reset_sqlite()

    if ok:
        print("\n" + "=" * 70)
        print("[SUCCESS] Database reset complete.")
        print("=" * 70)
        return 0
    print("\n[FAIL] Reset failed. Fix errors above and try again.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
