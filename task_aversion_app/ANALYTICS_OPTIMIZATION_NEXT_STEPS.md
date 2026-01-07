# Analytics Optimization - Next Steps

**Context**: This document summarizes what needs to be done for analytics performance optimization. Copy this to a new agent session to continue the work.

## Current Status

### ✅ Completed (Database & Caching Phase)

1. **Backend Caching Implemented:**
   - `Analytics._load_instances()` - Cached (1,383x faster: 41ms → 0.03ms)
   - `Analytics.get_dashboard_metrics()` - Cached (295ms → instant)
   - `TaskManager.list_tasks()`, `get_all()`, `get_task()` - All cached
   - `InstanceManager.list_active_instances()`, `list_recent_completed()` - Cached
   - Cache invalidation on writes working correctly

2. **Database Indexes Added:**
   - `completed_at` indexed on TaskInstance
   - `task_type` indexed on Task
   - `created_at` indexed on both tables
   - Composite indexes: `(status, is_completed, is_deleted)` and `(task_id, is_completed)`

3. **Performance Benchmarks:**
   - Backend operations: **Massive improvements** (1000x+ faster when cached)
   - E2E Dashboard: 1,040ms → 996ms (4% faster)
   - **E2E Analytics: Still 16.5 seconds** (only 0.2% improvement)

### ⚠️ Problem Identified

**Analytics page is still very slow (16.5 seconds)** despite backend operations being 1000x faster. This suggests:

1. **Multiple sequential API calls** - Analytics page may be making many separate requests
2. **Heavy calculations not cached** - Some expensive calculations run on every request
3. **Frontend rendering overhead** - JavaScript/Plotly chart rendering may be slow
4. **No batching** - Operations may not be batched together

## What Needs to Be Done (Analytics Optimization Phase)

### Phase 1: Profiling & Hotspot Identification ✅ COMPLETED

**Goal**: Identify what's actually slow in the analytics page

**Tasks:**
1. ✅ **Add timing instrumentation** to analytics methods:
   - `get_all_scores_for_composite()` - ✅ Added
   - `calculate_time_tracking_consistency()` - ✅ Added
   - `get_dashboard_metrics()` - ✅ Added
   - `get_relief_summary()` - ✅ Added (already had timing)
   - `trend_series()` - ✅ Added
   - `attribute_distribution()` - ✅ Added
   - `get_multi_attribute_trends()` - ✅ Added
   - `get_stress_dimension_data()` - ✅ Added
   - `get_task_performance_ranking()` - ✅ Added
   - `get_stress_efficiency_leaderboard()` - ✅ Added

2. **Profile analytics page load**:
   - See "How to Find API Calls and Performance Bottlenecks" section below
   - Use browser dev tools Network tab to see page load time
   - Check console for timing logs from analytics methods
   - Identify which methods are slowest

3. **Identify calculation hotspots**:
   - Check console output for `[Analytics]` timing logs
   - Methods that take > 100ms are candidates for optimization
   - Look for methods called multiple times that could be batched

**Files modified:**
- ✅ `backend/analytics.py` - Added timing logs to all heavy methods

### Phase 2: Batching Operations

**Goal**: Reduce multiple sequential calls to single batched calls

**Tasks:**
1. **Batch `_load_instances()` calls**:
   - Analytics page likely calls `_load_instances()` multiple times
   - Cache should help, but verify it's being used
   - Consider batching multiple data requests into one

2. **Batch metric calculations**:
   - If analytics page calls multiple metric methods, combine them
   - Create a single endpoint that returns all needed metrics

3. **Reduce API round trips**:
   - Combine dashboard metrics + relief summary + composite scores into one call
   - Use single request instead of multiple sequential requests

**Files to modify:**
- `ui/analytics_page.py` - Batch API calls
- `backend/analytics.py` - Add batched methods if needed

### Phase 3: Cache Heavy Calculations

**Goal**: Cache expensive calculation results

**Tasks:**
1. **Cache calculation results**:
   - `get_all_scores_for_composite()` - Cache the result
   - `calculate_time_tracking_consistency()` - Cache with TTL
   - Any per-instance score calculations that are repeated

2. **Precompute aggregates**:
   - Daily/weekly aggregates that don't change often
   - Cache with TTL (5-10 minutes)

**Files to modify:**
- `backend/analytics.py` - Add caching to calculation methods
- Follow same pattern as existing caches (`_relief_summary_cache`, `_instances_cache_*`)

### Phase 4: Chunking & Vectorization

**Goal**: Process large datasets efficiently

**Tasks:**
1. **Chunk long-running loops**:
   - If there are per-instance loops processing 287+ instances
   - Process in batches (200-500 rows) with yields
   - Reuse existing chunked patterns if present

2. **Vectorize operations**:
   - Use pandas vectorized operations instead of Python loops
   - Only chunk when vectorization not feasible

**Files to modify:**
- `backend/analytics.py` - Optimize per-instance loops

### Phase 5: Lazy Loading in UI

**Goal**: Defer heavy operations until needed

**Tasks:**
1. **Defer heavy charts**:
   - Load charts on expansion or after initial render
   - Add spinners/"load on demand" buttons for heavy sections

2. **Limit default windows**:
   - Default to shorter time windows (30-60 days)
   - Let user expand range if needed

**Files to modify:**
- `ui/analytics_page.py` - Add lazy loading for charts
- `ui/dashboard.py` - Defer heavy analytics sections

## Key Files

### Backend
- `backend/analytics.py` - Main analytics logic (12,000+ lines)
- `backend/task_manager.py` - Task management (already optimized)
- `backend/instance_manager.py` - Instance management (already optimized)
- `backend/database.py` - Database models (indexes added)

### Frontend
- `ui/analytics_page.py` - Analytics page UI
- `ui/dashboard.py` - Dashboard page UI

### Benchmarking
- `benchmark_performance.py` - Backend benchmark script
- `benchmark_performance_playwright.py` - E2E benchmark script
- Baseline results: `benchmark_results_20260106_230347.json`
- After caching: `benchmark_results_20260106_231911.json`
- E2E baseline: `benchmark_e2e_results_20260106_230902.json`
- E2E after caching: `benchmark_e2e_results_20260106_232248.json`

## Performance Targets

**Current:**
- Analytics page: 16.5 seconds (E2E)
- Dashboard page: 1.0 second (E2E)

**Target:**
- Analytics page: **< 2 seconds** (10x improvement)
- Dashboard page: **< 1 second** (maintain current)

## Implementation Pattern

### Adding Caching (Example)

```python
# 1. Add cache variables at class level
_cache_name = None
_cache_name_time = None
_cache_ttl_seconds = 300  # 5 minutes

# 2. Check cache at start of method
import time
current_time = time.time()
if (self._cache_name is not None and 
    self._cache_name_time is not None and
    (current_time - self._cache_name_time) < self._cache_ttl_seconds):
    return self._cache_name.copy()

# 3. Load/calculate data

# 4. Store in cache before returning
self._cache_name = result.copy()
self._cache_name_time = time.time()
return result
```

### Adding Timing Logs (Example)

```python
import time
start = time.perf_counter()
# ... operation ...
duration = (time.perf_counter() - start) * 1000
print(f"[Analytics] operation_name: {duration:.2f}ms")
```

## Next Steps (Priority Order)

1. **Profile analytics page** - Use browser dev tools to see what's actually slow
2. **Add timing logs** - Instrument analytics methods to find hotspots
3. **Batch API calls** - Combine multiple requests into one
4. **Cache calculations** - Cache expensive calculation results
5. **Chunk/vectorize** - Optimize per-instance loops
6. **Lazy load UI** - Defer heavy charts until needed
7. **Re-run benchmarks** - Measure improvements

## How to Find API Calls and Performance Bottlenecks

### Understanding NiceGUI Architecture

**Important**: NiceGUI is a **server-side rendering framework**, not a traditional REST API. This means:
- Methods are called directly from Python code (not HTTP requests)
- The page is rendered on the server and sent to the browser
- There are no traditional "API endpoints" to monitor

However, you can still profile performance using these methods:

### Method 1: Check Console Output (Timing Logs)

**Where to look**: The terminal/console where you run `python app.py`

**What you'll see**: Timing logs from analytics methods:
```
[Analytics] get_dashboard_metrics: 45.23ms
[Analytics] get_all_scores_for_composite: 1234.56ms
[Analytics] calculate_time_tracking_consistency_score: 67.89ms
[Analytics] trend_series: 12.34ms
[Analytics] attribute_distribution: 23.45ms
```

**How to use**:
1. Open the analytics page in your browser
2. Watch the console output
3. Identify methods taking > 100ms (these are slow)
4. Look for methods called multiple times (batching opportunity)

### Method 2: Browser Dev Tools - Network Tab

**How to access**:
1. Open Chrome/Edge/Firefox
2. Press `F12` or right-click → "Inspect"
3. Click the **Network** tab
4. Navigate to `/analytics` page

**What to look for**:
- **Page load time**: The total time to load the analytics page
- **WebSocket connections**: NiceGUI uses WebSockets for real-time updates
- **HTTP requests**: Any static assets (CSS, JS, images)

**Key metrics**:
- **DOMContentLoaded**: When HTML is parsed
- **Load**: When all resources are loaded
- **Total time**: Overall page load duration

**Example**:
- If page load is 16.5 seconds, but backend methods total 2 seconds, the problem is likely:
  - Frontend rendering (Plotly charts, UI components)
  - Multiple sequential method calls
  - Heavy JavaScript execution

### Method 3: Browser Dev Tools - Performance Tab

**How to use**:
1. Open Dev Tools (`F12`)
2. Click the **Performance** tab
3. Click the record button (circle icon)
4. Navigate to `/analytics` page
5. Wait for page to fully load
6. Click stop

**What you'll see**:
- **Timeline**: Shows when each operation happens
- **Main thread**: JavaScript execution time
- **Rendering**: Time spent rendering UI
- **Scripting**: Time spent executing JavaScript

**What to look for**:
- Long tasks (> 50ms) blocking the main thread
- Plotly chart rendering taking a long time
- Multiple sequential operations that could be parallelized

### Method 4: Check Server Logs for Method Calls

**Where**: Terminal running `python app.py`

**What to look for**:
- Methods called multiple times in sequence
- Methods taking a long time (> 100ms)
- Cache hits vs cache misses

**Example output**:
```
[Analytics] get_dashboard_metrics (cached): 0.15ms  ← Fast (cache hit)
[Analytics] get_all_scores_for_composite: 1234.56ms  ← Slow!
[Analytics] calculate_time_tracking_consistency_score: 67.89ms
[Analytics] get_relief_summary: 234.56ms
```

### Method 5: Add Page-Level Timing

To see total page load time, you can add timing to `ui/analytics_page.py`:

```python
def build_analytics_page():
    import time
    page_start = time.perf_counter()
    
    # ... existing code ...
    
    # At the end of the function:
    page_duration = (time.perf_counter() - page_start) * 1000
    print(f"[Analytics Page] Total build time: {page_duration:.2f}ms")
```

### Interpreting Results

**If backend methods are fast (< 100ms each)**:
- Problem is likely in frontend rendering
- Check Performance tab for long JavaScript tasks
- Consider lazy loading charts

**If backend methods are slow (> 100ms)**:
- Check which specific method is slow
- Look for cache misses
- Consider adding more caching
- Check for per-instance loops that could be vectorized

**If methods are called multiple times**:
- This is a batching opportunity
- Combine multiple calls into one
- See Phase 2: Batching Operations

### Quick Checklist

- [ ] Open analytics page and watch console output
- [ ] Note which methods take > 100ms
- [ ] Check if any methods are called multiple times
- [ ] Use Network tab to see total page load time
- [ ] Use Performance tab to identify frontend bottlenecks
- [ ] Document findings for Phase 2 optimization

## Notes

- ✅ Phase 1 completed: Timing instrumentation added to all analytics methods
- Backend caching is working perfectly (1000x+ improvements)
- The problem is likely in how analytics page makes requests or renders
- Focus on batching and frontend optimization first
- Use existing cache patterns as reference
- Test with real data (287 instances, 37 tasks)

## Reference Documents

- `PERFORMANCE_IMPROVEMENTS_AFTER_CACHING.md` - Results after caching
- `DATABASE_OPTIMIZATIONS_SUMMARY.md` - Database optimizations completed
- `.cursor/plans/performance_plan_-_heavy_analytics_calculations_ddbbe7e0.plan.md` - Full analytics optimization plan
- `BASELINE_PERFORMANCE_SUMMARY.md` - Original baseline measurements
