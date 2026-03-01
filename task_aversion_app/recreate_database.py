#!/usr/bin/env python3
"""
Fully drop and recreate the database (not just clear tables).

Use this when a table-only reset is not enough (e.g. leftover schema state,
extensions, or permissions). All data and the database itself are removed,
then a new empty database is created and all migrations are run.

- PostgreSQL: connects to the 'postgres' DB, terminates connections to the
  target DB, DROP DATABASE, CREATE DATABASE, then runs migrations 001-017.
- SQLite: deletes the .db file from disk, then runs init_db and migrate_add_jobs.

Requires DATABASE_URL in .env or environment. Stop the app (and any other
connections to the DB) before running so connections can be terminated.

Usage:
  cd task_aversion_app
  python recreate_database.py

  python recreate_database.py --yes   # skip confirmation

  # If CREATE DATABASE fails (permission denied), create the DB as postgres then:
  python recreate_database.py --migrate-only   # run only migrations (no drop/create)
"""
import os
import re
import sys
from pathlib import Path
from typing import Tuple

_APP_ROOT = Path(__file__).resolve().parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

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


def _parse_pg_url(url: str) -> Tuple[str, str, str]:
    """Return (base_url_without_db, dbname, username). Raises ValueError if invalid."""
    url = url.strip()
    if not url.lower().startswith("postgresql"):
        raise ValueError("Not a PostgreSQL URL")
    parts = url.rstrip("/").rsplit("/", 1)
    if len(parts) != 2 or not parts[1]:
        raise ValueError("DATABASE_URL must include database name (path)")
    base, path_part = parts[0], parts[1].split("?")[0]
    dbname = path_part
    if not re.match(r"^[a-zA-Z0-9_]+$", dbname):
        raise ValueError("Database name must be alphanumeric + underscore only")
    # username is the part before ':' in netloc (user:pass@host:port)
    netloc = url.replace("postgresql://", "").split("/")[0]
    username = netloc.split("@")[0].split(":")[0] if "@" in netloc else "task_aversion_user"
    return base, dbname, username


def recreate_postgres() -> bool:
    """Drop and recreate PostgreSQL database, then run migrations 001-017."""
    from sqlalchemy import create_engine, text

    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        print("[ERROR] DATABASE_URL is not set.")
        return False

    try:
        base_url, dbname, username = _parse_pg_url(database_url)
    except ValueError as e:
        print(f"[ERROR] {e}")
        return False

    admin_url = f"{base_url}/postgres"
    print(f"Connecting to admin DB (postgres) to drop/recreate '{dbname}'...")

    try:
        engine = create_engine(
            admin_url,
            isolation_level="AUTOCOMMIT",
            pool_pre_ping=True,
        )
    except Exception as e:
        print(f"[ERROR] Could not connect to PostgreSQL: {e}")
        print("  Ensure the app (and any other clients) are not connected to the DB.")
        return False

    with engine.connect() as conn:
        print("Terminating connections to target database...")
        try:
            conn.execute(
                text(
                    "SELECT pg_terminate_backend(pid) FROM pg_stat_activity "
                    "WHERE datname = :dbname AND pid <> pg_backend_pid()"
                ),
                {"dbname": dbname},
            )
        except Exception as e:
            print(f"[WARNING] Could not terminate some connections: {e}")

        print(f"Dropping database '{dbname}'...")
        try:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{dbname}"'))
        except Exception as e:
            print(f"[ERROR] DROP DATABASE failed: {e}")
            return False
        print("[OK] Database dropped.")

        print(f"Creating database '{dbname}'...")
        try:
            conn.execute(text(f'CREATE DATABASE "{dbname}"'))
        except Exception as e:
            err_msg = str(e).lower()
            if "permission denied" in err_msg or "insufficientprivilege" in err_msg or "createdb" in err_msg:
                print("[ERROR] CREATE DATABASE failed: this user cannot create databases.")
                print("  Option A - Grant CREATEDB (no psql needed):")
                print('    Set POSTGRES_ADMIN_URL=postgresql://postgres:PASSWORD@localhost:5432/postgres then run:')
                print("    python grant_createdb.py")
                print("  Option B - If Postgres is in Docker:")
                print('    docker exec -it CONTAINER_NAME psql -U postgres -c "ALTER USER ' + username + ' CREATEDB;"')
                print("  Option C - Create the DB as postgres, then run migrations only:")
                print(f'    (Use Docker or pgAdmin to run: CREATE DATABASE "{dbname}";)')
                print("    python recreate_database.py --migrate-only")
            else:
                print(f"[ERROR] CREATE DATABASE failed: {e}")
            return False
        print("[OK] Database created.")

    engine.dispose()

    return _run_postgres_migrations()


def _run_postgres_migrations() -> bool:
    """Run PostgreSQL migrations 001-017. Used after create or with --migrate-only."""
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


def migrate_only_postgres() -> bool:
    """Run only migrations 001-017 (no drop/create). Use after creating DB as postgres."""
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url or not database_url.startswith("postgresql"):
        print("[ERROR] DATABASE_URL must be set and point to PostgreSQL.")
        return False
    print("Running migrations only (no drop/create)...")
    return _run_postgres_migrations()


def recreate_sqlite() -> bool:
    """Delete SQLite file and re-initialize via init_db + migrate_add_jobs."""
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url or "sqlite" not in database_url.lower():
        print("[ERROR] DATABASE_URL does not point to SQLite.")
        return False

    # Path is usually sqlite:///data/task_aversion.db -> data/task_aversion.db
    path_part = database_url.replace("sqlite:///", "").split("?")[0].strip("/")
    db_path = _APP_ROOT / path_part

    if db_path.exists():
        print(f"Removing SQLite file: {db_path}")
        try:
            db_path.unlink()
        except OSError as e:
            print(f"[ERROR] Could not delete file: {e}")
            print("  Close the app and any other process using the database.")
            return False
        print("[OK] File removed.")
    else:
        print("[NOTE] SQLite file not found; will create with init_db.")

    print("\nInitializing schema (init_db)...")
    try:
        from backend.database import init_db
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
        print("Set it in .env or: $env:DATABASE_URL = '...'  (PowerShell)")
        return 1

    migrate_only = "--migrate-only" in sys.argv
    if migrate_only:
        print("=" * 70)
        print("Run migrations only (no drop/create)")
        print("=" * 70)
        print(f"Database: {database_url}")
    else:
        print("=" * 70)
        print("Recreate database (DROP + CREATE, then run migrations)")
        print("=" * 70)
        print(f"Database: {database_url}")
        print("\n[WARNING] The database will be DELETED and recreated from scratch.")
        print("Stop the app before running so connections can be terminated (PostgreSQL).")
        force = "--yes" in sys.argv or "-y" in sys.argv
        if not force:
            try:
                confirm = input("Type 'yes' to continue: ").strip().lower()
            except EOFError:
                confirm = "no"
            if confirm != "yes":
                print("Aborted.")
                return 0

    if "--migrate-only" in sys.argv:
        if not database_url.startswith("postgresql"):
            print("[ERROR] --migrate-only is for PostgreSQL only.")
            return 1
        ok = migrate_only_postgres()
    elif database_url.startswith("postgresql"):
        ok = recreate_postgres()
    else:
        ok = recreate_sqlite()

    if ok:
        print("\n" + "=" * 70)
        print("[SUCCESS] Database recreated and migrations applied.")
        print("=" * 70)
        return 0
    print("\n[FAIL] Recreate failed. Fix errors above and try again.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
