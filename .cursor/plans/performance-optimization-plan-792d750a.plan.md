<!-- 792d750a-be82-42f3-becd-23e001924687 cb7f15a3-8b8e-4120-a849-eca5ed985f53 -->
# Performance Optimization Plan

## Problem Analysis

The app has several performance bottlenecks:

1. **No caching**: CSV files are read from disk on every request
2. **Redundant data loading**: Multiple managers reload the same data independently
3. **Heavy computations**: Complex pandas operations run on every page load
4. **Inefficient JSON parsing**: JSON columns parsed for every row on every load
5. **Multiple baseline calculations**: InstanceManager methods reload CSV multiple times

## Optimization Strategy

### Phase 1: Add In-Memory Caching (High Impact)

**Files to modify:**

- `task_aversion_app/backend/analytics.py`
- `task_aversion_app/backend/instance_manager.py`
- `task_aversion_app/backend/task_manager.py`

**Changes:**

1. Add a simple TTL-based cache decorator for `_load_instances()` and `_reload()` methods
2. Cache parsed DataFrames with 5-10 second TTL (configurable)
3. Invalidate cache on write operations (`_save()` methods)
4. Use file modification time to detect external changes

**Expected impact**: 70-90% reduction in CSV read operations

### Phase 2: Optimize Data Loading (Medium Impact)

**Files to modify:**

- `task_aversion_app/backend/analytics.py` (especially `_load_instances()`)

**Changes:**

1. Cache parsed JSON dictionaries (predicted_dict/actual_dict) instead of re-parsing
2. Lazy-load calculated columns (stress_level, net_wellbeing, etc.) only when needed
3. Use vectorized operations instead of `.apply()` where possible
4. Pre-filter data early (e.g., filter completed tasks before heavy calculations)

**Expected impact**: 30-50% faster data processing

### Phase 3: Optimize Analytics Calculations (Medium Impact)

**Files to modify:**

- `task_aversion_app/backend/analytics.py` (methods like `get_relief_summary()`, `get_dashboard_metrics()`)

**Changes:**

1. Cache expensive calculations (relief_summary, dashboard_metrics) with short TTL
2. Batch multiple baseline aversion calculations instead of calling InstanceManager repeatedly
3. Use pandas vectorized operations instead of row-by-row `.apply()`
4. Pre-compute common aggregations once per data load

**Expected impact**: 40-60% faster analytics page load

### Phase 4: Lazy Loading for Analytics Page (Low-Medium Impact)

**Files to modify:**

- `task_aversion_app/ui/analytics_page.py`

**Changes:**

1. Load critical metrics first (dashboard metrics, relief summary)
2. Load charts and heavy visualizations asynchronously or on-demand
3. Add loading indicators for better UX
4. Consider pagination or limiting data range for initial load

**Expected impact**: Perceived performance improvement, faster initial render

### Phase 5: Optimize InstanceManager Baseline Methods (Low Impact)

**Files to modify:**

- `task_aversion_app/backend/instance_manager.py`

**Changes:**

1. Cache baseline aversion calculations per task_id
2. Batch load all baseline data in one pass instead of per-task queries
3. Store computed baselines in memory with task_id as key

**Expected impact**: 50-70% reduction in redundant CSV reads for baseline calculations

## Implementation Details

### Cache Implementation Pattern

```python
from functools import lru_cache
from time import time
import os

_cache = {}
_cache_ttl = 10  # seconds

def get_cached_data(file_path, loader_func):
    """Simple TTL-based cache for file-based data."""
    mtime = os.path.getmtime(file_path)
    cache_key = (file_path, mtime)
    
    if cache_key in _cache:
        data, timestamp = _cache[cache_key]
        if time() - timestamp < _cache_ttl:
            return data
    
    data = loader_func()
    _cache[cache_key] = (data, time())
    return data
```

### Data Loading Optimization

- Parse JSON columns once and cache the parsed dictionaries
- Use `pd.read_csv()` with specific dtypes to reduce memory
- Filter data early (e.g., `df[df['completed_at'].notna()]` before heavy operations)
- Use `pd.eval()` or vectorized operations instead of `.apply()` for simple transformations

### Analytics Optimization

- Pre-compute common metrics in `_load_instances()` and store as DataFrame columns
- Cache method results with dependency tracking (invalidate when data changes)
- Batch operations: load all task data once, then compute all metrics

## Testing Strategy

1. Measure page load time before optimization
2. Add timing logs to identify slowest operations
3. Measure after each phase to validate improvements
4. Test with realistic data sizes (100-1000 task instances)

## Risk Mitigation

- Cache invalidation: Use file mtime + TTL to ensure data freshness
- Memory usage: Monitor cache size, add max cache size limits if needed
- Backward compatibility: Keep existing API, optimize internals only

## Expected Overall Impact

- **Analytics page load time**: 60-80% reduction (from ~3-5 seconds to ~1-2 seconds)
- **Memory usage**: +10-20MB for caching (acceptable on 2GB system)
- **CPU usage**: 50-70% reduction during page loads
- **Scalability**: Better performance as data grows