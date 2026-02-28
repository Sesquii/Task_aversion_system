#!/usr/bin/env python3
"""
Idempotent database migration runner.

Runs all pending migrations in order without dropping or recreating the database.
Safe to run multiple times: each migration script is idempotent (skips or
no-ops when already applied).

- PostgreSQL: runs 001, 002, ... N in PostgreSQL_migration/ (auto-discovered).
- SQLite: runs init_db(), migrate_add_jobs, then cross-DB migrations (e.g. 015).

Requires DATABASE_URL in .env or environment.

Usage:
  cd task_aversion_app
  python run_migrations.py
"""
import os
import re
import sys
from pathlib import Path

_APP_ROOT = Path(__file__).resolve().parent
if str(_APP_ROOT) not in sys.path:
    sys.path.insert(0, str(_APP_ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(_APP_ROOT / ".env")
    load_dotenv()
except ImportError:
    pass


def _run_script(script_path: Path, description: str) -> bool:
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


def _discover_postgres_migrations() -> list[tuple[Path, str]]:
    """Discover NNN_*.py in PostgreSQL_migration, sorted by NNN."""
    mig_dir = _APP_ROOT / "PostgreSQL_migration"
    if not mig_dir.is_dir():
        return []
    out = []
    pattern = re.compile(r"^(\d{3})_(.+)\.py$")
    for path in mig_dir.iterdir():
        if not path.is_file() or path.suffix != ".py":
            continue
        name = path.name
        if name.startswith("check_") or name == "README.md":
            continue
        m = pattern.match(name)
        if m:
            num, rest = m.group(1), m.group(2)
            desc = f"{num} {rest.replace('_', ' ')}"
            out.append((path, desc))
    out.sort(key=lambda x: x[0].name)
    return out


def run_postgres_migrations() -> bool:
    """Run all discovered PostgreSQL migrations in order. Idempotent."""
    migrations = _discover_postgres_migrations()
    if not migrations:
        print("[WARNING] No migration scripts found in PostgreSQL_migration/")
        return True
    for path, desc in migrations:
        print(f"\nRunning {desc}...")
        if not _run_script(path, desc):
            return False
    return True


def run_sqlite_migrations() -> bool:
    """Run SQLite migrations: init_db, migrate_add_jobs, then cross-DB scripts (e.g. 015). Idempotent."""
    print("\nInitializing schema (init_db)...")
    try:
        from backend.database import init_db
        init_db()
        print("[OK] Schema initialized (idempotent).")
    except Exception as e:
        print(f"[ERROR] init_db failed: {e}")
        return False

    jobs_script = _APP_ROOT / "migrate_add_jobs.py"
    if jobs_script.exists():
        print("\nRunning migrate_add_jobs...")
        if not _run_script(jobs_script, "migrate_add_jobs"):
            return False

    # Cross-DB migrations that support both PostgreSQL and SQLite (e.g. 015)
    cross_db = [
        ("015_add_due_at_to_task_instances.py", "015 Add due_at to task_instances"),
    ]
    mig_dir = _APP_ROOT / "PostgreSQL_migration"
    for filename, desc in cross_db:
        path = mig_dir / filename
        if path.exists():
            print(f"\nRunning {desc}...")
            if not _run_script(path, desc):
                return False
        else:
            print(f"[SKIP] {filename} not found (optional for SQLite)")

    return True


def main() -> int:
    database_url = os.getenv("DATABASE_URL", "").strip()
    if not database_url:
        print("[ERROR] DATABASE_URL is not set.")
        print("Set it in .env or: $env:DATABASE_URL = '...'  (PowerShell)")
        return 1

    print("=" * 70)
    print("Run migrations (idempotent)")
    print("=" * 70)
    print(f"Database: {database_url}")
    print("Each migration is safe to run multiple times.\n")

    if database_url.lower().startswith("postgresql"):
        ok = run_postgres_migrations()
    else:
        ok = run_sqlite_migrations()

    if ok:
        print("\n" + "=" * 70)
        print("[SUCCESS] All migrations applied.")
        print("=" * 70)
        return 0
    print("\n[FAIL] Migration run failed. Fix errors above and try again.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
