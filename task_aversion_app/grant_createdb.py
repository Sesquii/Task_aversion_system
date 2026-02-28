#!/usr/bin/env python3
"""
Grant CREATEDB to the app database user (no psql required).

Use this when recreate_database.py fails with "permission denied to create database".
Requires a superuser connection (e.g. postgres). Reads the app user from DATABASE_URL.

Usage:
  1. Set postgres superuser URL (in .env or env):
     POSTGRES_ADMIN_URL=postgresql://postgres:YOUR_POSTGRES_PASSWORD@localhost:5432/postgres

  2. Run:
     python grant_createdb.py

  If you use Docker for PostgreSQL, you can instead run inside the container:
     docker exec -it CONTAINER_NAME psql -U postgres -c "ALTER USER task_aversion_user CREATEDB;"
  (Replace CONTAINER_NAME with your postgres container name, e.g. test-postgres-migration)
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


def _username_from_url(url: str) -> str:
    """Extract username from postgresql://user:pass@host:port/db."""
    if "://" in url:
        rest = url.split("://", 1)[1]
    else:
        rest = url
    netloc = rest.split("/")[0]
    if "@" in netloc:
        user_part = netloc.split("@")[0]
    else:
        user_part = netloc.split(":")[0]
    return user_part.split(":")[0]


def main() -> int:
    admin_url = os.getenv("POSTGRES_ADMIN_URL", "").strip()
    app_url = os.getenv("DATABASE_URL", "").strip()

    if not app_url or "postgresql" not in app_url.lower():
        print("[ERROR] DATABASE_URL not set or not PostgreSQL.")
        return 1

    username = _username_from_url(app_url)
    if not re.match(r"^[a-zA-Z0-9_]+$", username):
        print("[ERROR] Could not parse username from DATABASE_URL.")
        return 1

    if not admin_url or "postgresql" not in admin_url.lower():
        print("[INFO] POSTGRES_ADMIN_URL not set. Use one of these options:")
        print()
        print("  Option 1 - Python (set admin URL then run this script):")
        print('    $env:POSTGRES_ADMIN_URL = "postgresql://postgres:YOUR_POSTGRES_PASSWORD@localhost:5432/postgres"')
        print("    python grant_createdb.py")
        print()
        print("  Option 2 - Docker (if Postgres runs in a container):")
        print("    docker ps   # find your postgres container name")
        print(f'    docker exec -it CONTAINER_NAME psql -U postgres -c "ALTER USER {username} CREATEDB;"')
        print()
        return 1

    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        print("[ERROR] sqlalchemy required. pip install sqlalchemy psycopg2-binary")
        return 1

    engine = create_engine(admin_url, isolation_level="AUTOCOMMIT")
    try:
        with engine.connect() as conn:
            conn.execute(text(f'ALTER USER "{username}" CREATEDB'))
        print(f"[OK] CREATEDB granted to user: {username}")
        return 0
    except Exception as e:
        print(f"[ERROR] {e}")
        return 1
    finally:
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
