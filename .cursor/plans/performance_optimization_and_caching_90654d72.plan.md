---
name: Performance Optimization and Caching
overview: Optimize application performance by implementing caching, connection pooling improvements, and loading screens to address 5-8 second analytics load times and 2-5 second pipeline initialization delays with connection errors.
todos:
  - id: connection_pooling
    content: Enhance connection pool settings in database.py (pool_size, pool_pre_ping, pool_recycle)
    status: pending
  - id: connection_retry
    content: Implement connection retry logic with exponential backoff for task_manager and instance_manager
    status: pending
    dependencies:
      - connection_pooling
  - id: connection_warmup
    content: Add connection warmup on app startup to prevent first-connection errors
    status: pending
    dependencies:
      - connection_pooling
  - id: analytics_caching
    content: Implement caching layer for expensive analytics queries (dashboard metrics, trends, summaries)
    status: pending
  - id: query_optimization
    content: Optimize database queries in analytics.py (review N+1 queries, add indexes, use SQL aggregation)
    status: pending
  - id: analytics_loading
    content: Add loading screen to analytics page with progress indicator
    status: pending
    dependencies:
      - analytics_caching
  - id: pipeline_caching
    content: Cache frequently accessed data (task lists, active instances, user preferences)
    status: pending
  - id: dashboard_optimization
    content: Optimize dashboard initialization with lazy loading and prefetching
    status: pending
    dependencies:
      - pipeline_caching
  - id: loading_screens
    content: Implement consistent loading screens across all pages (dashboard, initialize, complete)
    status: pending
  - id: performance_testing
    content: Run performance benchmarks and load testing to validate improvements
    status: pending
    dependencies:
      - analytics_caching
      - query_optimization
      - pipeline_caching
      - loading_screens
---

# Performance Optimization and Caching Plan

**Created:** 2025-01-XX**Status:** Planning**Priority:** High (blocks user experience)

## Overview

Address performance issues identified post-SQLite migration:

- Analytics page: 5-8 seconds load time (improved from timeout, but still slow)
- Main pipeline: Connection errors on first attempt, then 2-5 seconds initialization
- Task pages: Nearly instant (good baseline to maintain)

## Goals

1. Reduce analytics page load time to < 2 seconds
2. Eliminate connection errors on first attempt
3. Reduce pipeline initialization to < 1 second
4. Implement consistent loading experience (5 seconds consistent > instant + 10 seconds inconsistent)
5. Prepare for server scaling considerations

## Implementation Strategy

### Phase 1: Connection Pooling and Error Handling

**Files to modify:**

- `backend/database.py` - Enhance connection pool configuration
- `backend/task_manager.py` - Add connection retry logic
- `backend/instance_manager.py` - Add connection retry logic

**Tasks:**

1. **Enhance connection pool settings** in `backend/database.py`:

- Increase `pool_size` from 5 to 10 for SQLite
- Set `pool_pre_ping=True` to prevent stale connections
- Add `pool_recycle=3600` for connection health
- Add connection timeout handling

2. **Implement connection retry logic**:

- Add exponential backoff retry (3 attempts) for connection errors
- Add connection health check before first use
- Log connection errors for debugging

3. **Add connection warmup**:

- Pre-establish connections on app startup
- Test connection pool health on initialization

### Phase 2: Analytics Caching

**Files to modify:**

- `backend/analytics.py` - Add caching layer
- `ui/analytics_page.py` - Add loading screen

**Tasks:**

1. **Implement caching system**:

- Use in-memory cache (Python `functools.lru_cache` or `cachetools`)
- Cache expensive analytics queries (dashboard metrics, trends, summaries)
- Cache TTL: 5 minutes for dashboard metrics, 1 minute for real-time data
- Cache invalidation on task completion/creation

2. **Optimize database queries**:

- Review `get_dashboard_metrics()` for N+1 query issues
- Add database indexes if missing (check `backend/database.py`)
- Batch load related data in single queries
- Use SQL aggregation instead of Python loops where possible

3. **Add loading screen** to analytics page:

- Show loading spinner with "Analytics may take a few seconds to load" message
- Display progress indicator
- Load data asynchronously if possible

### Phase 3: Pipeline Optimization

**Files to modify:**

- `app.py` - Add initialization caching
- `backend/task_manager.py` - Cache task lists
- `backend/instance_manager.py` - Cache active instances

**Tasks:**

1. **Cache frequently accessed data**:

- Cache task list (invalidate on task create/update/delete)
- Cache active instances list (invalidate on instance create/complete)
- Cache user preferences (invalidate on preference change)

2. **Optimize dashboard initialization**:

- Lazy load dashboard components
- Load critical data first, secondary data after
- Prefetch data in background

3. **Add connection pooling monitoring**:

- Log pool usage for debugging
- Add metrics for connection wait times

### Phase 4: Loading Screens and UX

**Files to modify:**

- `ui/dashboard.py` - Add loading states
- `ui/analytics_page.py` - Add loading screen (already planned)
- `ui/initialize_task_page.py` - Add loading indicator
- `ui/complete_task_page.py` - Add loading indicator

**Tasks:**

1. **Implement consistent loading pattern**:

- Show loading spinner for operations > 500ms
- Display "This may take a few seconds" for known slow operations
- Disable buttons during loading to prevent double-submission

2. **Add progress indicators**:

- For analytics: Show "Loading analytics data..." with progress
- For pipeline: Show "Initializing..." with status updates

3. **Error handling improvements**:

- Show user-friendly error messages
- Add retry buttons for failed operations
- Log errors for debugging

## Technical Details

### Caching Strategy

```python
# Example caching pattern
from functools import lru_cache
from datetime import datetime, timedelta

class Analytics:
    _cache = {}
    _cache_timestamps = {}
    
    def get_dashboard_metrics(self, force_refresh=False):
        cache_key = 'dashboard_metrics'
        cache_ttl = timedelta(minutes=5)
        
        if not force_refresh and cache_key in self._cache:
            if datetime.now() - self._cache_timestamps[cache_key] < cache_ttl:
                return self._cache[cache_key]
        
        # Expensive computation
        metrics = self._compute_dashboard_metrics()
        
        self._cache[cache_key] = metrics
        self._cache_timestamps[cache_key] = datetime.now()
        return metrics
    
    def invalidate_cache(self, cache_key=None):
        if cache_key:
            self._cache.pop(cache_key, None)
        else:
            self._cache.clear()
```



### Connection Pool Configuration

```python
# backend/database.py
if DATABASE_URL.startswith('sqlite'):
    engine = create_engine(
        DATABASE_URL,
        echo=False,
        connect_args={'check_same_thread': False},
        pool_size=10,  # Increased from default 5
        pool_pre_ping=True,  # Test connections before use
        pool_recycle=3600,  # Recycle after 1 hour
    )
```



### Retry Logic Pattern

```python
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=1, max=10))
def get_task_with_retry(self, task_id):
    try:
        with self.db_session() as session:
            return session.query(self.Task).filter(Task.task_id == task_id).first()
    except OperationalError as e:
        print(f"[TaskManager] Connection error: {e}, retrying...")
        raise
```



## Testing Strategy

1. **Performance benchmarks**:

- Measure analytics load time before/after
- Measure pipeline initialization time before/after
- Track connection error frequency

2. **Load testing**:

- Test with realistic data volumes
- Test concurrent requests (if planning for server)

3. **Cache validation**:

- Verify cache invalidation works correctly
- Test cache TTL expiration
- Verify no stale data displayed

## Success Criteria

- Analytics page loads in < 2 seconds (from 5-8 seconds)
- Pipeline initialization in < 1 second (from 2-5 seconds)
- Zero connection errors on first attempt
- Consistent loading experience across all pages
- Cache hit rate > 80% for dashboard metrics

## Dependencies

- SQLite migration completed (already done)
- Database indexes may need review/addition

## Notes

- Consider using `cachetools` library for more advanced caching if `functools.lru_cache` is insufficient