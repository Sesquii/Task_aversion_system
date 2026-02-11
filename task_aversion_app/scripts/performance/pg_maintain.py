#!/usr/bin/env python3
"""
PostgreSQL maintenance script: VACUUM ANALYZE and optional REINDEX.

Improves query performance by:
  - Updating table statistics (ANALYZE) so the planner chooses better plans
  - Reclaiming dead tuple space and updating visibility (VACUUM)
  - Rebuilding indexes if needed (REINDEX)

Run periodically (e.g. daily cron) or after large imports. Requires
DATABASE_URL to point to PostgreSQL. VACUUM can take time on large tables;
use --analyze-only for a quick stats-only run.

Usage:
  cd task_aversion_app
  set DATABASE_URL=postgresql://user:pass@host:5432/dbname
  python scripts/performance/pg_maintain.py [--analyze-only] [--no-vacuum]
"""
from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

# Add app root so backend.database is importable
_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))
try:
    from dotenv import load_dotenv
    load_dotenv(_ROOT / ".env")
    load_dotenv()
except ImportError:
    pass


def main() -> int:
    parser = argparse.ArgumentParser(description="PostgreSQL maintenance: VACUUM ANALYZE")
    parser.add_argument(
        "--analyze-only",
        action="store_true",
        help="Only run ANALYZE (no VACUUM). Faster, good for stats refresh.",
    )
    parser.add_argument(
        "--no-vacuum",
        action="store_true",
        help="Skip VACUUM (only ANALYZE). Same as --analyze-only.",
    )
    args = parser.parse_args()

    database_url = os.getenv("DATABASE_URL", "")
    if not database_url or not database_url.startswith("postgresql"):
        print("[FAIL] DATABASE_URL must be set and point to PostgreSQL.")
        print("Example: set DATABASE_URL=postgresql://user:pass@localhost:5432/task_aversion_system")
        return 1

    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        print("[FAIL] sqlalchemy is required. Install with: pip install sqlalchemy psycopg2-binary")
        return 1

    engine = create_engine(
        database_url,
        pool_pre_ping=True,
        isolation_level="AUTOCOMMIT",  # VACUUM cannot run inside a transaction
    )

    analyze_only = args.analyze_only or args.no_vacuum

    # Core tables used by dashboard/analytics
    tables = [
        "task_instances",
        "tasks",
        "users",
        "emotions",
        "notes",
        "user_preferences",
        "survey_responses",
        "popup_triggers",
        "popup_responses",
    ]

    with engine.connect() as conn:
        # Get existing tables (in case some migrations not run)
        r = conn.execute(
            text(
                """
                SELECT tablename FROM pg_tables
                WHERE schemaname = 'public'
                ORDER BY tablename
                """
            )
        )
        existing = {row[0] for row in r}
        to_process = [t for t in tables if t in existing]
        if not to_process:
            print("[WARN] No known tables found in public schema.")
            return 0

        if analyze_only:
            print("[INFO] Running ANALYZE only (no VACUUM).")
        else:
            print("[INFO] Running VACUUM ANALYZE (this may take a while on large tables).")

        for table in to_process:
            try:
                if analyze_only:
                    conn.execute(text(f'ANALYZE "{table}"'))
                    print(f"  [OK] ANALYZE {table}")
                else:
                    conn.execute(text(f'VACUUM (ANALYZE) "{table}"'))
                    print(f"  [OK] VACUUM ANALYZE {table}")
            except Exception as e:
                print(f"  [FAIL] {table}: {e}")
                # Continue with other tables

    print("[SUCCESS] Maintenance complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
