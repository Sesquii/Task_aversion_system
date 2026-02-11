#!/usr/bin/env python3
"""
PostgreSQL: which tables benefit most from VACUUM/ANALYZE (PG ops).

Focus: **PostgreSQL operations** (maintenance impact). Complements pg_stats_and_config.py
(table stats and config) and pg_maintain.py (runs VACUUM ANALYZE). This script
reads pg_stat_user_tables and ranks tables by dead-tuple ratio and stale stats
to produce actionable recommendations: run pg_maintain.py on high-impact tables first.

Outputs actionable data: table name, n_live_tup, n_dead_tup, dead ratio %,
last_vacuum, last_analyze, and a priority score for maintenance. Requires
DATABASE_URL pointing to PostgreSQL. Read-only.

Usage:
  cd task_aversion_app
  set DATABASE_URL=postgresql://...
  python scripts/performance/pg_vacuum_analyze_impact.py [--top N]
"""
from __future__ import annotations

import argparse
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

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
    parser = argparse.ArgumentParser(
        description="Tables that would benefit most from VACUUM/ANALYZE"
    )
    parser.add_argument(
        "--top",
        type=int,
        default=15,
        metavar="N",
        help="Show top N tables by maintenance priority (default 15)",
    )
    args = parser.parse_args()

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
        stats_sql = text("""
            SELECT
                relname,
                n_live_tup,
                n_dead_tup,
                last_vacuum,
                last_autoanalyze,
                last_analyze
            FROM pg_stat_user_tables
            WHERE schemaname = 'public'
            ORDER BY n_live_tup DESC
        """)
        rows = list(conn.execute(stats_sql))

    now = datetime.now(timezone.utc)
    # Build (table, live, dead, dead_ratio, last_vacuum, last_analyze, priority)
    # Priority: higher dead ratio + older last_analyze => run maintenance
    scored: list[tuple[str, int, int, float, str, str, float]] = []
    for row in rows:
        relname, live, dead, lv, lauto, la = row
        live = live or 0
        dead = dead or 0
        total = live + dead
        dead_ratio = (100.0 * dead / total) if total > 0 else 0.0
        last_analyze = lauto or la
        lv_str = str(lv)[:19] if lv else "never"
        la_str = str(last_analyze)[:19] if last_analyze else "never"

        # Simple priority: dead_ratio + (1 if no analyze in last 7 days, else 0)
        days_since_analyze = 999.0
        if last_analyze:
            try:
                if last_analyze.tzinfo is None:
                    last_analyze = last_analyze.replace(tzinfo=timezone.utc)
                delta = now - last_analyze
                days_since_analyze = delta.total_seconds() / 86400.0
            except (TypeError, ValueError):
                pass
        priority = dead_ratio + (10.0 if days_since_analyze > 7 else 0) + min(days_since_analyze, 30.0)
        scored.append((relname, live, dead, dead_ratio, lv_str, la_str, priority))

    scored.sort(key=lambda x: -x[6])

    print("=" * 72)
    print("VACUUM/ANALYZE IMPACT (tables to maintain first)")
    print("=" * 72)
    print("  High dead_ratio or stale last_analyze -> run pg_maintain.py")
    print()

    print(f"  {'Table':<28} {'live':>10} {'dead':>8} {'dead%':>7}  last_vacuum      last_analyze")
    print("-" * 72)
    for relname, live, dead, dead_ratio, lv_str, la_str, _ in scored[: args.top]:
        print(f"  {relname:<28} {live:>10} {dead:>8} {dead_ratio:>6.1f}%  {lv_str:>14}  {la_str}")

    print()
    print("  [INFO] Run: python scripts/performance/pg_maintain.py")
    print("  [INFO] Use --analyze-only for a quick stats-only refresh.")
    print()
    print("[SUCCESS] Focus: PG ops (VACUUM/ANALYZE impact). Actionable priorities.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
