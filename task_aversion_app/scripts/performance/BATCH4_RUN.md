# Batch 4: How to run (PostgreSQL required)

Batch 4 scripts need **PostgreSQL**. Set `DATABASE_URL` then run from `task_aversion_app`.

## Prerequisite

```powershell
# PowerShell: set for current session (replace with your connection string)
$env:DATABASE_URL = "postgresql://user:password@localhost:5432/task_aversion_system"
```

Or use a `.env` file in `task_aversion_app` with:
```
DATABASE_URL=postgresql://user:password@localhost:5432/task_aversion_system
```

## Run order (read-only first)

```powershell
cd task_aversion_app

# 1. Server config and table stats
python scripts/performance/pg_stats_and_config.py

# 2. Index review and suggestions
python scripts/performance/pg_index_review.py --suggest

# 3. Which tables benefit from VACUUM
python scripts/performance/pg_vacuum_analyze_impact.py

# 4. EXPLAIN plan summary (use your app user_id, e.g. 1)
python scripts/performance/pg_explain_plan_summary.py --user-id 1

# 5. One-line scan type per query
python scripts/performance/pg_explain_scan_types.py --user-id 1
```

## Optional: EXPLAIN analytics, writes, maintain

```powershell
python scripts/performance/pg_explain_analytics_queries.py --user-id 1
python scripts/performance/pg_explain_writes.py --user-id 1
# Preview index creation (no changes)
python scripts/performance/pg_add_performance_indexes.py --dry-run
# Run VACUUM ANALYZE (writes to DB)
python scripts/performance/pg_maintain.py --analyze-only
# Or full VACUUM ANALYZE
python scripts/performance/pg_maintain.py
```

## Without PostgreSQL

- **Primer (no DB):** `python scripts/performance/pg_planner_index_locking_primer.py`
- **Index catalog (codebase only):** `python scripts/performance/catalog_indexes.py`

See [BATCHES.md](BATCHES.md) for the full Batch 4 list.
