# Performance scripts: batch plan

Run all scripts from `task_aversion_app`: `python scripts/performance/<script>.py [args]`.

## Batch 1 — Static analysis (no DB, no app run)

No database or query log required. Scans codebase and reports query sites, call trees, indexes.

| Script | Purpose |
|--------|--------|
| `pg_query_sites_static.py` | PostgreSQL query sites; `--by-dir`, `--top` |
| `analyze_static_queries.py` | Query sites per file; `--by-dir` |
| `catalog_indexes.py` | Indexes defined in codebase |
| `index_catalog_with_usage.py` | Index catalog; optional `--live` |
| `dashboard_load_call_tree.py` | Dashboard backend call tree |
| `dashboard_elements_call_sites.py` | Dashboard elements and query sites |
| `dashboard_task_list_and_instances.py` | Task list + active instances call sites |
| `dashboard_metrics_relief_composite.py` | Metrics, composite, relief call sites |
| `dashboard_config_notes_recent.py` | Config, notes, recent call sites |
| `analytics_load_call_tree.py` | Analytics backend call tree |
| `settings_load_call_tree.py` | Settings backend call tree |
| `select_sites_by_table.py` | SELECT sites by table; `--by-dir`, `--top` |
| `select_index_coverage.py` | SELECT tables vs indexes; optional `--live` |
| `write_sites_by_operation.py` | Write sites by operation; `--by-dir` |
| `write_sites_by_table.py` | Write sites by table |
| `write_transactions_and_batching.py` | Commits and batching |
| `write_backend_call_sites.py` | Backend write call sites; `--by-module` |
| `analytics_full_page_backend_sequence.py` | Analytics page backend sequence |
| `analytics_composite_emotional_sites.py` | Composite + emotional flow sites |
| `settings_call_sites.py` | Settings call tree |
| `settings_query_sites_static.py` | Settings query sites; `--by-area` |
| `schema_overview_task_instances_tasks.py` | Schema overview; optional `--live` |
| `analytics_settings_config_reads.py` | Analytics + settings config reads |
| `n_plus_one_call_sites.py` | get_instance / _load_instances call sites (static) |
| `get_instance_loop_candidates.py` | get_instance() inside for/while (same-block); candidates for get_instances_bulk |
| `get_instances_bulk_refactor_hints.py` | every get_instance() site with refactor hint for batching |

**Quick run:** `pg_query_sites_static.py --top 25 --by-dir` then `dashboard_load_call_tree.py`, `dashboard_elements_call_sites.py`, etc.

---

## Batch 2 — Query log analysis (need query log)

Requires `ENABLE_QUERY_LOGGING=1` and at least one dashboard/analytics/settings load. Log: `logs/query_log.txt`.

| Script | Purpose |
|--------|--------|
| `analyze_query_log_bottlenecks.py` | Paths by query count/DB time; type breakdown; top patterns |
| `query_log_n_plus_one_candidates.py` | N+1 candidates per path; `--min-repeat 5 --top 20` |
| `query_log_n_plus_one_trace.py` | Code-search hints for top N+1 pattern per path |
| `query_log_sql_type_by_path.py` | Per-path SELECT/INSERT/UPDATE/DELETE counts |
| `query_log_top_patterns_by_count.py` | Top query patterns by total count across log |
| `dashboard_full_page_metrics.py` | GET / query count and DB time stats |
| `dashboard_request_query_sequence.py` | Query sequence per GET / request |
| `select_log_by_route.py` | SELECT counts and mean DB time per route |
| `analytics_query_log_routes.py` | Analytics routes from log |
| `settings_route_query_log.py` | Settings routes from log |

**Quick run:** Load app with query logging, then `analyze_query_log_bottlenecks.py`, `query_log_n_plus_one_candidates.py --min-repeat 5 --top 20`, `query_log_sql_type_by_path.py`.

---

## Batch 3 — Optimization prioritization (actionable output)

Uses query log to produce prioritized checklist and top patterns. Run after Batch 2.

| Script | Purpose |
|--------|--------|
| `optimization_priority_from_log.py` | One-page prioritized optimization checklist from log + N+1 data. Needs query log. |

**Quick run:** `optimization_priority_from_log.py [path/to/query_log.txt]`

**Batch 3 code fixes (implemented):**
- **Dashboard (GET /):** Warm Analytics instances cache at start of `build_dashboard()` so all `_load_instances` calls in the request hit cache. Stop invalidating instance caches on every build (invalidation remains on create/update/delete in InstanceManager).
- **Analytics (GET /analytics):** Warm Analytics instances cache at start of `build_analytics_page()` so all `_load_instances` in the request hit cache.

---

## Batch 4 — PostgreSQL / live DB (require DATABASE_URL)

Set `DATABASE_URL=postgresql://...` (or SQLite for some). Scripts run EXPLAIN, VACUUM, index review.

**How to run:** See **[BATCH4_RUN.md](BATCH4_RUN.md)** for prerequisite (DATABASE_URL), run order, and copy-paste commands.

| Script | Purpose |
|--------|--------|
| `pg_maintain.py` | VACUUM ANALYZE or `--analyze-only` |
| `pg_stats_and_config.py` | Server settings and table stats |
| `pg_index_review.py` | Table/index sizes and usage; `--suggest` |
| `pg_analyze_queries.py` | EXPLAIN (ANALYZE, BUFFERS) dashboard queries |
| `pg_add_performance_indexes.py` | Create composite indexes; `--dry-run` |
| `pg_explain_plan_summary.py` | EXPLAIN plan summary; `--user-id` |
| `pg_explain_analytics_queries.py` | EXPLAIN analytics queries |
| `pg_explain_scan_types.py` | One-line scan type per query |
| `pg_explain_writes.py` | EXPLAIN INSERT/UPDATE |
| `pg_vacuum_analyze_impact.py` | Tables that benefit from VACUUM |
| `pg_planner_index_locking_primer.py` | Educational; optional `--live` |
| `dashboard_select_explain_hot_path.py` | Dashboard SELECTs + EXPLAIN; `--live` |
| `index_catalog_with_usage.py --live` | Index usage from PG |
| `select_index_coverage.py --live` | Index coverage from PG |
| `schema_overview_task_instances_tasks.py --live` | Schema from information_schema |

**Quick run:** `pg_stats_and_config.py`, `pg_index_review.py --suggest`, `pg_explain_plan_summary.py --user-id 1`.

---

## Batch 5 — Run-time and educational

Require running app (HTTP) or are educational only.

| Script | Purpose |
|--------|--------|
| `dashboard_load_wall_clock.py` | HTTP GET / response time (running app) |
| `pg_planner_index_locking_primer.py` | Primer text; optional `--live` |

---

## Suggested order

1. **Batch 1** — Static scripts (no setup).
2. **Batch 2** — Enable query logging, load dashboard/analytics/settings, run log scripts.
3. **Batch 3** — Run optimization priority script for checklist.
4. **Batch 4** — When you have PostgreSQL (or SQLite), run pg_* and EXPLAIN scripts.
5. **Batch 5** — Wall-clock and primers as needed.
