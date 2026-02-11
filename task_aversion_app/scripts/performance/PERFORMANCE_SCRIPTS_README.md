# Performance analysis scripts

Scripts to **find** potential bottlenecks and **optimize** the database. Run from `task_aversion_app` directory.

**For agents adding scripts:** Read [AGENT_MASTER_INSTRUCTIONS.md](AGENT_MASTER_INSTRUCTIONS.md) first; append new script entries to this README.

**PostgreSQL is the production database.** PRAGMA is SQLite-only and does not run in production. See [PERFORMANCE_POSTGRESQL_SCOPE.md](PERFORMANCE_POSTGRESQL_SCOPE.md) for scope and a one-off PostgreSQL query-site analysis.

## Scripts

### Analysis (no DB required for static scripts)

| Script | Purpose |
|--------|--------|
| `pg_query_sites_static.py` | **PostgreSQL-focused:** count query sites in app code only (SELECT/INSERT/UPDATE/DELETE, session.query, execute). Excludes PRAGMA and migration dirs. Use `--by-dir` for per-directory totals. |
| `analyze_static_queries.py` | Count DB query sites per file (session.query, .execute, text(, SELECT, PRAGMA). Use `--by-dir` to aggregate by directory. |
| `catalog_indexes.py` | List all indexes defined in the codebase (database.py, migrations, add_database_indexes.py). |
| `index_catalog_with_usage.py` | **Indexes:** Catalog indexes from codebase and optional live usage (idx_scan, idx_tup_read). Complements catalog_indexes and pg_index_review. No DB by default; use `--live` with DATABASE_URL for PostgreSQL usage. |
| `query_log_sql_type_by_path.py` | **Query log:** Per-path breakdown by SQL type (SELECT/INSERT/UPDATE/DELETE) with counts and mean DB time. Complements analyze_query_log_bottlenecks. Needs query log. |
| `dashboard_load_call_tree.py` | List backend methods called from the dashboard (tm/im/an/user_state) and how many query sites each method contains. |
| `dashboard_elements_call_sites.py` | **Dashboard elements:** task list, active instances, dashboard metrics, composite scores, execution score, relief summary, monitored metrics config, task notes, recent/recommendations. Call-site counts in dashboard + backend query-site count per element. No DB. |
| `dashboard_task_list_and_instances.py` | **Dashboard elements:** task list (tm.get_all), active instances (im.list_active_instances). Call sites with line numbers + backend query sites. No DB. |
| `dashboard_metrics_relief_composite.py` | **Dashboard elements:** dashboard metrics, composite scores, execution score, relief summary (an.get_dashboard_metrics, get_all_scores_for_composite, get_execution_score_chunked, get_relief_summary, get_targeted_metric_values). Call sites + backend query sites. No DB. |
| `dashboard_config_notes_recent.py` | **Dashboard elements:** monitored metrics config (user_state), task notes, recent/recommendations (tm.get_task_notes*, get_recent; im.list_recent_tasks). Call sites + backend query sites. No DB. |
| `analytics_load_call_tree.py` | **Backend call tree for Analytics:** list backend methods called from Analytics UI (analytics_page, relief/factors comparison, summary) and how many query sites each method contains. Same hot-path view as dashboard. No DB. |
| `settings_load_call_tree.py` | **Backend call tree for Settings:** list backend methods called from Settings UI (settings, composite-score-weights, productivity-settings, cancellation-penalties) and how many query sites each method contains. Same hot-path view as dashboard. No DB. |
| `analyze_query_log_bottlenecks.py` | Parse `logs/query_log.txt` and report paths by query count/DB time, PRAGMA vs SELECT breakdown, and top repeated patterns. |
| `dashboard_full_page_metrics.py` | **Dashboard full-page load:** parse query log for GET / only; report per-load query count and DB time, then min/mean/max/p95. Targets page / (build_dashboard). Needs query log. |
| `dashboard_request_query_sequence.py` | **Dashboard full-page load:** from query log, print ordered sequence of queries for each GET / request to trace full request path. Targets page / (build_dashboard). Needs query log. |
| `dashboard_load_wall_clock.py` | **Dashboard full-page load:** HTTP GET to / and measure response time (wall-clock). Targets page / (build_dashboard). Needs running app. |
| `select_sites_by_table.py` | **SELECT-focused:** static scan of WHERE SELECTs appear and which tables they touch (session.query + raw SQL FROM/JOIN). Per-table and per-file counts for per-SQL-type coverage. Use `--top N` and `--by-dir`. |
| `select_log_by_route.py` | **SELECT-focused:** parse query log and report SELECT counts and mean DB time per route. Actionable counts and timings; complements analyze_query_log_bottlenecks. Needs query log (ENABLE_QUERY_LOGGING). |
| `select_index_coverage.py` | **SELECT-focused:** cross-reference tables touched by SELECTs (codebase) with indexes defined in code; report covered vs no-index tables. Optional `--live` uses PostgreSQL for current index list. No DB required by default. |
| `write_sites_by_operation.py` | **INSERT/UPDATE/DELETE-focused:** static scan of write-path sites by operation type (INSERT vs UPDATE vs DELETE, session.add/delete, raw SQL). Per-file and per-directory counts; actionable. No DB required. **Note:** UI file counts can include false positives (e.g. debug JSON with `'UPDATE'` in strings); all DB writes should go through backend. |
| `write_sites_by_table.py` | **INSERT/UPDATE/DELETE-focused:** write-path sites by inferred table (raw SQL INSERT/UPDATE/DELETE table name; ORM bulk delete and add/delete counts). Per-table and per-file breakdown. No DB required. |
| `write_transactions_and_batching.py` | **INSERT/UPDATE/DELETE-focused:** where session.commit(), add_all, bulk_insert_mappings, executemany occur; commit-per-write vs batched; commit-inside-loop hotspots. Actionable counts. No DB required. |
| `write_backend_call_sites.py` | **INSERT/UPDATE/DELETE-focused:** backend functions that contain at least one write (session.add/delete, raw INSERT/UPDATE/DELETE). Lists write-path call sites by module; use `--by-module`. No DB required. |
| `analytics_load_call_tree.py` | **Analytics page and elements:** backend call tree for /analytics (analytics_page.py, emotional flow, relief comparison, factors comparison, glossary). Lists analytics_service and user_state methods and query-site counts per method. Use `--by-module` for per-UI-file. No DB. |
| `analytics_full_page_backend_sequence.py` | **Analytics full page:** documents backend call sequence for full analytics page load (get_analytics_page_data, composite score load, get_chart_data, get_rankings_data, etc.). No DB. |
| `analytics_query_log_routes.py` | **Analytics page and routes:** query log stats for /analytics and sub-routes (emotional-flow, factors-comparison, relief-comparison, glossary). SELECT counts and mean DB time per analytics route. Needs query log. |
| `analytics_composite_emotional_sites.py` | **Analytics composite score load and emotional flow:** query-site counts for get_all_scores_for_composite, calculate_composite_score, get_emotional_flow_data in backend/analytics.py. No DB. |
| `settings_call_sites.py` | **Settings page:** backend call tree for /settings and subpages (landing, CSV import, score weights, productivity settings, cancellation penalties). Lists user_state/analytics/im/csv_import/csv_export methods called and query-site count per method. No DB required. |
| `settings_query_sites_static.py` | **Settings page:** static scan of query sites in Settings-related UI and backend files; reports per-file counts and maps files to area (landing, CSV import/export, score weights, productivity, cancellation penalties). Use `--by-area` to group by area. No DB required. |
| `settings_route_query_log.py` | **Settings page:** parse query log for /settings routes only; report per-route query count and mean DB time (settings landing, CSV, score weights, productivity, cancellation). Needs query log (ENABLE_QUERY_LOGGING). |
| `dashboard_select_explain_hot_path.py` | **Cross-cutting (SELECT + EXPLAIN for dashboard):** Parse query log for GET / SELECTs and summarize patterns; with `--live` run EXPLAIN on canonical dashboard SELECTs. Enmeshed optimization. Query log optional; needs PostgreSQL for `--live`. |
| `schema_overview_task_instances_tasks.py` | **Educational (schema overview):** Documents task_instances, tasks, user_id usage, FKs, and indexes. Static parse of database.py; optional `--live` uses PostgreSQL information_schema. No DB by default. |
| `analytics_settings_config_reads.py` | **Cross-cutting (analytics + settings config reads):** Lists backend read operations (user_state.get_*, analytics_service.get_*) used on Analytics vs Settings; shared config reads for enmeshed optimization. Static analysis; no DB. |

### PostgreSQL database optimization (require `DATABASE_URL=postgresql://...`)

| Script | Purpose |
|--------|--------|
| `pg_maintain.py` | Run `VACUUM ANALYZE` (or `ANALYZE` only with `--analyze-only`) on app tables. Improves planner stats and reclaims dead space. Run periodically or after large imports. |
| `pg_analyze_queries.py` | Run `EXPLAIN (ANALYZE, BUFFERS)` on the critical dashboard queries (load instances, list active). Use to verify index usage and spot sequential scans. |
| `pg_index_review.py` | List table sizes, all indexes with definitions, index sizes, and usage stats. Use `--suggest` for composite index suggestions. |
| `pg_stats_and_config.py` | Print key server settings (work_mem, shared_buffers, etc.) and table stats (n_live_tup, n_dead_tup, last vacuum/analyze). |
| `pg_add_performance_indexes.py` | Create optional composite indexes for dashboard hot paths (e.g. `user_id, status, is_completed, is_deleted`). Uses `CREATE INDEX CONCURRENTLY`. Run once; use `--dry-run` to preview. |
| `pg_explain_plan_summary.py` | **EXPLAIN/plan-focused:** Run EXPLAIN (FORMAT TEXT) on critical queries and summarize scan type (Seq vs Index), cost range, row estimates in a table. Per-SQL-type coverage; actionable plan data. |
| `pg_explain_analytics_queries.py` | **EXPLAIN/plan-focused:** Run EXPLAIN (ANALYZE, BUFFERS) on analytics/dashboard queries; print full plan and one-line summary (scan type, actual rows, buffers). Actionable plan data. |
| `pg_explain_scan_types.py` | **EXPLAIN/plan-focused:** One-line per query: scan type, estimated rows, cost. Quick comparison of Seq vs Index scan for critical SELECTs. Actionable plan data. |
| `pg_explain_writes.py` | **EXPLAIN/plan-focused:** Run EXPLAIN (ANALYZE) on INSERT and UPDATE on task_instances. Shows write plans and cost for per-SQL-type coverage. |
| `pg_vacuum_analyze_impact.py` | **PG ops:** Which tables benefit most from VACUUM/ANALYZE (dead-tuple ratio, stale last_analyze). Actionable priority list; use before pg_maintain. Requires PostgreSQL. |
| `pg_planner_index_locking_primer.py` | **PG ops/educational:** Primer on planner, indexes, and locking. No DB for text; use `--live` to run one EXPLAIN sample. Optional PostgreSQL. |

## Quick run

```bash
cd task_aversion_app

# Static analysis (no app run needed)
python scripts/performance/pg_query_sites_static.py --top 25 --by-dir
python scripts/performance/analyze_static_queries.py --top 25 --by-dir
python scripts/performance/catalog_indexes.py
python scripts/performance/index_catalog_with_usage.py
# Optional: python scripts/performance/index_catalog_with_usage.py --live
python scripts/performance/dashboard_load_call_tree.py
python scripts/performance/dashboard_elements_call_sites.py
python scripts/performance/dashboard_task_list_and_instances.py
python scripts/performance/dashboard_metrics_relief_composite.py
python scripts/performance/dashboard_config_notes_recent.py
python scripts/performance/analytics_load_call_tree.py
python scripts/performance/settings_load_call_tree.py

# Query log (requires at least one dashboard load with ENABLE_QUERY_LOGGING=1)
python scripts/performance/analyze_query_log_bottlenecks.py
python scripts/performance/query_log_sql_type_by_path.py
# Or: python scripts/performance/analyze_query_log_bottlenecks.py path/to/query_log.txt

# Dashboard full-page load (page /, build_dashboard): query log
python scripts/performance/dashboard_full_page_metrics.py
python scripts/performance/dashboard_request_query_sequence.py [--max-requests 3] [--normalize]
# Dashboard full-page load: wall-clock (needs running app)
python scripts/performance/dashboard_load_wall_clock.py [--url http://127.0.0.1:8080/] [--runs 5]

# SELECT-focused analysis (per-SQL-type coverage)
python scripts/performance/select_sites_by_table.py --top 25 --by-dir
python scripts/performance/select_log_by_route.py
python scripts/performance/select_index_coverage.py
# Optional: python scripts/performance/select_index_coverage.py --live

# INSERT/UPDATE/DELETE-focused (write-path) analysis (per-SQL-type coverage)
python scripts/performance/write_sites_by_operation.py --top 25 --by-dir
python scripts/performance/write_sites_by_table.py --top 25
python scripts/performance/write_transactions_and_batching.py --top 25
python scripts/performance/write_backend_call_sites.py --by-module

# Analytics page and elements (Analytics area; static, no DB)
python scripts/performance/analytics_load_call_tree.py
python scripts/performance/analytics_load_call_tree.py --by-module
python scripts/performance/analytics_full_page_backend_sequence.py
python scripts/performance/analytics_composite_emotional_sites.py
# Analytics routes in query log (needs query log)
python scripts/performance/analytics_query_log_routes.py

# Settings page (landing, CSV import, score weights, productivity, cancellation penalties)
python scripts/performance/settings_call_sites.py
python scripts/performance/settings_query_sites_static.py [--by-area]
python scripts/performance/settings_route_query_log.py

# Cross-cutting / educational (SELECT+EXPLAIN dashboard, schema overview, analytics+settings config reads)
python scripts/performance/dashboard_select_explain_hot_path.py
# Optional: python scripts/performance/dashboard_select_explain_hot_path.py path/to/query_log.txt --live --user-id 1
python scripts/performance/schema_overview_task_instances_tasks.py
# Optional: python scripts/performance/schema_overview_task_instances_tasks.py --live
python scripts/performance/analytics_settings_config_reads.py

# PostgreSQL optimization (set DATABASE_URL first)
set DATABASE_URL=postgresql://user:pass@localhost:5432/task_aversion_system
python scripts/performance/pg_stats_and_config.py
python scripts/performance/pg_index_review.py --suggest
python scripts/performance/pg_analyze_queries.py --user-id 1
python scripts/performance/pg_add_performance_indexes.py --dry-run
python scripts/performance/pg_maintain.py --analyze-only
python scripts/performance/pg_explain_plan_summary.py --user-id 1
python scripts/performance/pg_explain_analytics_queries.py --user-id 1
python scripts/performance/pg_explain_scan_types.py --user-id 1
python scripts/performance/pg_explain_writes.py --user-id 1
python scripts/performance/pg_vacuum_analyze_impact.py [--top 15]
python scripts/performance/pg_planner_index_locking_primer.py
# Optional: python scripts/performance/pg_planner_index_locking_primer.py --live [--user-id 1]
```

## Generating the query log

1. Ensure `ENABLE_QUERY_LOGGING` is set (default is 1).
2. Start the app and open the main dashboard (GET /).
3. Log is written to `task_aversion_app/logs/query_log.txt`.
4. Run `analyze_query_log_bottlenecks.py` to see per-path stats and N+1-style patterns.

Existing baseline script: `scripts/analyze_query_baseline.py` (same log format, per-path stats and repeated patterns).
