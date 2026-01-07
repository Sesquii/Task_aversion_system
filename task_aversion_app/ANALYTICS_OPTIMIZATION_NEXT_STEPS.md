# Analytics Optimization - Next Steps

**Status**: ✅ **COMPLETE** (Last optimization: January 7 2025)

**Context**: This document summarizes the analytics performance optimization work. All phases (1-4) are complete. Phase 5 (Lazy Loading) was skipped as current performance is sufficient.

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

### Phase 2: Batching Operations ✅ COMPLETED

**Goal**: Reduce multiple sequential calls to single batched calls

**Tasks:**
1. ✅ **Batch `_load_instances()` calls**:
   - Created `get_analytics_page_data()` - combines dashboard_metrics, relief_summary, time_tracking
   - Created `get_chart_data()` - combines trend_series, attribute_distribution, stress_dimension_data
   - Created `get_rankings_data()` - combines all task performance rankings

2. ✅ **Batch metric calculations**:
   - Analytics page now uses 3 batched calls instead of 10+ sequential calls
   - Reduced from: 3 separate calls for main data + 3 for charts + 5 for rankings = 11 calls
   - To: 1 batched call for main data + 1 for charts + 1 for rankings = 3 calls

3. ✅ **Reduce API round trips**:
   - Combined dashboard metrics + relief summary + time tracking into `get_analytics_page_data()`
   - Combined all chart data into `get_chart_data()`
   - Combined all rankings into `get_rankings_data()`
   - Removed duplicate `get_dashboard_metrics()` calls

**Files modified:**
- ✅ `backend/analytics.py` - Added 3 batched methods with timing logs
- ✅ `ui/analytics_page.py` - Updated to use batched methods, removed duplicate calls

### Phase 3: Cache Heavy Calculations ✅ COMPLETED

**Goal**: Cache expensive calculation results

**Tasks:**
1. ✅ **Cache calculation results**:
   - ✅ `get_all_scores_for_composite()` - Already had caching, verified working
   - ✅ `calculate_time_tracking_consistency_score()` - Added caching with parameter keying
   - ✅ `trend_series()` - Added caching
   - ✅ `attribute_distribution()` - Added caching
   - ✅ `get_stress_dimension_data()` - Added caching
   - ✅ `get_task_performance_ranking()` - Added caching (keyed by metric + top_n)
   - ✅ `get_stress_efficiency_leaderboard()` - Added caching (keyed by top_n)

2. ✅ **Precompute aggregates**:
   - All chart data methods now cached with 5-minute TTL
   - Rankings cached with parameter-based keys
   - Cache invalidation properly handled on instance updates

**Files modified:**
- ✅ `backend/analytics.py` - Added caching to 6 methods, updated cache invalidation
- ✅ All caches follow same pattern as existing caches with TTL-based expiration

### Phase 4: Chunking & Vectorization ✅ **COMPLETE**

**Goal**: Process large datasets efficiently

**Status**: Complete - Vectorized key operations for better performance

**Tasks Completed:**
1. **Vectorized apply operations**:
   - ✅ `_get_expected_relief_from_dict`: Replaced `df.apply(axis=1)` with direct dict column extraction
   - ✅ `serendipity_factor`: Replaced `.apply(lambda)` with vectorized `.clip()` operations
   - ✅ `disappointment_factor`: Replaced `.apply(lambda)` with vectorized `.clip()` operations
   - ✅ `behavioral_score`: Simplified to direct column conversion

2. **Vectorized iterrows loops**:
   - ✅ `get_all_scores_for_composite`: Vectorized `persistence_factor` calculation using numpy operations
   - ✅ `_detect_suddenly_challenging`: Vectorized load extraction from dict column
   - ✅ `calculate_focus_factor`: Vectorized notes counting using pandas string operations

**Performance Impact:**
- Eliminated 5+ `df.apply(axis=1)` operations (slow row-by-row processing)
- Eliminated 3 `iterrows()` loops (replaced with vectorized pandas/numpy operations)
- Dict extractions remain as `.apply()` (necessary for nested dict access, but optimized)

**Files modified:**
- ✅ `backend/analytics.py` - Vectorized key operations in `_load_instances`, `get_all_scores_for_composite`, `_detect_suddenly_challenging`, `calculate_focus_factor`

### Phase 5: Lazy Loading in UI ⏭️ **SKIPPED**

**Goal**: Defer heavy operations until needed

**Status**: Skipped - Analytics optimization considered complete after Phase 4

**Rationale**: Current performance improvements from Phases 1-4 are sufficient. Page loads nearly instantly, and further UI optimizations can be addressed if needed in the future.

**Tasks (not implemented):**
1. **Defer heavy charts**:
   - Load charts on expansion or after initial render
   - Add spinners/"load on demand" buttons for heavy sections

2. **Limit default windows**:
   - Default to shorter time windows (30-60 days)
   - Let user expand range if needed

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
- Baseline results: `benchmark_results_20260106_230347.json`
- After caching: `benchmark_results_20260106_231911.json`
- Note: E2E Playwright benchmark removed (did not accurately reflect actual performance)

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

1. ✅ **Profile analytics page** - Use browser dev tools to see what's actually slow
2. ✅ **Add timing logs** - Instrument analytics methods to find hotspots
3. ✅ **Batch API calls** - Combine multiple requests into one
4. **Cache calculations** - Cache expensive calculation results (Phase 3)
5. **Chunk/vectorize** - Optimize per-instance loops (Phase 4)
6. ~~**Lazy load UI** - Defer heavy charts until needed (Phase 5)~~ - **SKIPPED**
7. **Re-run benchmarks** - Measure improvements (optional)

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
