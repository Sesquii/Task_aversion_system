# Dashboard cold load – bottlenecks (RESOLVED)

> **Status:** Main bottleneck resolved (2026-02-12). `get_relief_summary()` improved from 2.75s to 0.19s (14x faster).
> See [PERFORMANCE_OPTIMIZATION_LOG.md](PERFORMANCE_OPTIMIZATION_LOG.md) for full details.

---

# Historical: Dashboard cold load (3–5 s) – original bottlenecks

## What we fixed

- **N+1 on task_instances**: `calculate_persistence_factor` was calling `_load_instances` twice per row (repetition + consistency). We added optional `instances_df` and pass the already-loaded DataFrame from `get_relief_summary` / grit call sites. **Result**: GET / went from ~82 repeated task_instances SELECTs to ~3 per request in the query log.

## Why it’s still 3–5 s when not cached

Most of the cold load time is **Python computation**, not DB. Query log shows GET / DB time ~30–40 ms; the rest is server-side work before the response is sent.

### 1. `get_relief_summary()` (main cost when cache is cold)

Called from:

- **Monitored metrics (lazy load)** in `dashboard.py`: `lazy_load` calls `get_relief_summary()`, then `get_dashboard_metrics()`, then `get_all_scores_for_composite()` one after the other. The first one dominates when cache is cold.
- **Summary section** (`build_summary_section()`), if that path is used.

When the relief summary cache is cold, this function:

- Loads completed instances once (fast after warm cache at start of `build_dashboard`).
- Runs a **lot of per-row work** over all completed rows:
  - **Efficiency**: `completed.apply(self.calculate_efficiency_score, axis=1)` – one Python call per row.
  - **Obstacles**: `relief_data_for_obstacles.apply(_calculate_obstacles_scores_robust, axis=1)` and `_calculate_obstacles_scores_sensitive`, plus `_get_max_spike_robust` / `_get_max_spike_sensitive` on weekly data.
  - **Productivity score**: `completed.apply(lambda row: self.calculate_productivity_score(...), axis=1)`.
  - **Grit score**: `completed.apply(lambda row: self.calculate_grit_score(..., instances_df=df), axis=1)` – N+1 fixed, but still O(n) Python.
- Calls **TaskManager().get_all(user_id)** inside `get_relief_summary` to get `task_type` (dashboard already has tasks; this is duplicate work).
- Batch baseline aversions and other steps add more work.

With hundreds of completed rows, these `.apply(..., axis=1)` loops add up to seconds.

### 2. Sequential work in the same request

- `get_relief_summary()` then `get_dashboard_metrics()` then `get_all_scores_for_composite()` run one after the other in the lazy_load path. No parallelization.
- `get_dashboard_metrics()` when cold can do its own heavy work (e.g. `get_all_scores_for_composite`-style logic depending on config).

### 3. Other possible contributors

- **pg_catalog / reflection**: Query log shows many repeated `pg_catalog.pg_class.relname` queries on some loads (e.g. 18x). Worth checking if that’s per-request and if it can be reduced or cached.
- **First-time imports / one-off setup**: Usually small; only relevant if you see a big first-request vs second-request gap.

## Recommended next steps (in order of impact)

1. **Profile the cold path**
   - Add a short timing block around the main stages inside `get_relief_summary` (already partially there with the existing `print` timings). Run one cold load and note which stage dominates (e.g. efficiency apply, obstacles, productivity, grit).
   - Optionally run under `cProfile` or `py-spy` for a single GET / with cache cleared to see exact hotspots.

2. **Reduce work in `get_relief_summary`**
   - **Reuse tasks**: Avoid calling `TaskManager().get_all()` inside `get_relief_summary`; pass in a pre-fetched task list/DataFrame from the dashboard (or a shared cache keyed by `user_id`).
   - **Vectorize or batch**: Replace the heaviest `.apply(..., axis=1)` with vectorized pandas/numpy or small batches (e.g. `calculate_efficiency_score` and obstacles scores might be expressible column-wise).
   - **Limit rows for expensive metrics**: For “summary” views, consider computing only over last N days or last M completions for the slowest scores, and optionally do full history in the background or on demand.

3. **Lazy / incremental UI**
   - Show the dashboard shell and key blocks (e.g. task list, current task) immediately; load **Monitored Metrics** (and Summary if used) via a second request or timer after first paint.
   - Optionally show placeholders (“Loading…”) for metrics and fill them when `get_relief_summary` / `get_dashboard_metrics` complete.

4. **Cache and TTL**
   - Relief summary is already cached (e.g. 5 min TTL). Ensure cache key is stable (e.g. `user_id` only) and that you’re not invalidating it unnecessarily on every load. Then 3–5 s cost is only on first load or after expiry.

5. **Background prewarm**
   - After login or after first lightweight dashboard load, trigger a background task or timer that calls `get_relief_summary(user_id)` (and optionally `get_dashboard_metrics`) so the next full load is cache-warm.

## Profiling `.apply()` Calls

The `get_relief_summary()` function is instrumented with detailed profiling. Enable it at server boot:

```powershell
# Log to console
$env:PROFILE_ANALYTICS="1"; python app.py

# Log to file (recommended for analysis)
$env:PROFILE_ANALYTICS="1"; $env:PROFILE_LOG_FILE="logs/profile.log"; python app.py

# Append to existing file (for multiple runs)
$env:PROFILE_ANALYTICS="1"; $env:PROFILE_LOG_FILE="logs/profile.log"; $env:PROFILE_APPEND="1"; python app.py
```

### What gets profiled

Each `.apply()` call in `get_relief_summary()` is timed individually:
- `calculate_efficiency_score` - efficiency per completed task
- `obstacles_scores_robust` / `obstacles_scores_sensitive` - obstacles calculations
- `spike_amount_robust` / `spike_amount_sensitive` - weekly spike detection
- `time_for_work_play` - time extraction for work/play
- `time_actual_for_avg` - time for weekly average
- `calculate_productivity_score` - productivity score per task
- `calculate_grit_score` - grit score per task

### Sample output

```
[Profile 14:32:15.123] >>> START get_relief_summary
[Profile 14:32:15.456]     .apply(calculate_efficiency_score): 312.45ms (245 rows, 1.275ms/row)
[Profile 14:32:15.789]     .apply(obstacles_scores_robust): 456.78ms (198 rows, 2.307ms/row)
[Profile 14:32:16.012]     .apply(calculate_grit_score): 678.90ms (245 rows, 2.771ms/row)
[Profile 14:32:16.234] <<< END get_relief_summary: 2345.67ms total
[Profile 14:32:16.234]     Breakdown:
[Profile 14:32:16.234]       calculate_grit_score: 678.90ms (28.9%)
[Profile 14:32:16.234]       obstacles_scores_robust: 456.78ms (19.5%)
[Profile 14:32:16.234]       calculate_efficiency_score: 312.45ms (13.3%)
```

## Vectorization Plan

After profiling identifies the top bottlenecks, vectorize them one at a time:

1. Run profiling to identify top 1-2 offenders
2. Create vectorized version following two-layer pattern (see `.cursor/rules/vectorization-optimization.mdc`)
3. Test equivalence with reference implementation
4. Measure improvement with profiling
5. Repeat for next bottleneck

## Quick checks

- **Confirm relief summary is the bottleneck**: Clear relief summary cache, load dashboard once, and check the existing `[Analytics] get_relief_summary: ...ms` (and stage) prints. If that’s ~3–5 s, the above applies.
- **Wall-clock**: Run `python scripts/performance/dashboard_load_wall_clock.py` with cache cleared to get reproducible cold load time; then again after one load to see cached time.
- **Profile cold load**: Run with `PROFILE_ANALYTICS=1` and clear cache, then load dashboard. Check which `.apply()` dominates in the breakdown.

Summary: The remaining 3–5 s on cold load is mostly **CPU in `get_relief_summary`** (many `.apply` over completed rows) and **duplicate/sequential work**. Reducing per-row work and moving metrics loading to after first paint will have the biggest impact.
