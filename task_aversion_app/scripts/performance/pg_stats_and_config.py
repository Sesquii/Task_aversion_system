#!/usr/bin/env python3
"""
PostgreSQL stats and config: key server settings and table statistics.

Prints:
  - work_mem, shared_buffers, effective_cache_size (for tuning)
  - Table row counts and last vacuum/analyze
  - Dead tuples (bloat indicator)

Use to baseline the server and decide if VACUUM ANALYZE or config changes
are needed. Read-only; no writes.

Usage:
  cd task_aversion_app
  set DATABASE_URL=postgresql://...
  python scripts/performance/pg_stats_and_config.py
"""
from __future__ import annotations

import os
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))


def main() -> int:
    database_url = os.getenv("DATABASE_URL", "")
    if not database_url or not database_url.startswith("postgresql"):
        print("[FAIL] DATABASE_URL must be set and point to PostgreSQL.")
        return 1

    try:
        from sqlalchemy import create_engine, text
    except ImportError:
        print("[FAIL] sqlalchemy required. pip install sqlalchemy psycopg2-binary")
        return 1

    engine = create_engine(database_url, pool_pre_ping=True)

    with engine.connect() as conn:
        # Key config (session or system)
        config_sql = text(
            """
            SELECT name, setting, unit
            FROM pg_settings
            WHERE name IN (
                'work_mem', 'shared_buffers', 'effective_cache_size',
                'random_page_cost', 'effective_io_concurrency',
                'max_connections', 'default_statistics_target'
            )
            ORDER BY name
            """
        )
        print("=" * 72)
        print("KEY CONFIG (pg_settings)")
        print("=" * 72)
        for row in conn.execute(config_sql):
            unit = f" {row[2]}" if row[2] else ""
            print(f"  {row[0]:28} = {row[1]}{unit}")
        print()

        # Table stats: n_live_tup, n_dead_tup, last_vacuum, last_analyze
        stats_sql = text(
            """
            SELECT
                schemaname,
                relname,
                n_live_tup,
                n_dead_tup,
                last_vacuum,
                last_autoanalyze,
                last_analyze
            FROM pg_stat_user_tables
            WHERE schemaname = 'public'
            ORDER BY n_live_tup DESC
            """
        )
        print("=" * 72)
        print("TABLE STATS (public schema)")
        print("=" * 72)
        print(
            "  table_name              n_live_tup  n_dead_tup  last_vacuum    last_analyze"
        )
        print("-" * 72)
        for row in conn.execute(stats_sql):
            _, relname, live, dead, lv, lauto, la = row
            lv_str = str(lv)[:19] if lv else "-"
            la_str = str(lauto or la)[:19] if (lauto or la) else "-"
            print(f"  {relname:24} {live:>10} {dead:>10}  {lv_str:12}  {la_str}")
        print()
        print(
            "  [INFO] High n_dead_tup or stale last_analyze -> run pg_maintain.py"
        )
        print()

    print("[SUCCESS] Stats and config complete.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
