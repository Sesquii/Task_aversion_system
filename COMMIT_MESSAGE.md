# Commit Message - PLANNING DOCUMENTS

**[PLANNING COMMIT - NO CODE CHANGES]**

## Planning Intent

This commit adds two comprehensive planning documents for performance optimization and caching infrastructure improvements. This is a **planning document only** - no code changes have been made. These plans address critical performance bottlenecks in the analytics system and establish a flexible caching framework to improve user experience.

## Plans Added

### 1. Caching System Implementation Plan
**File**: `.cursor/plans/caching_system_implementation_b3e70d55.plan.md`

A comprehensive plan to implement a flexible caching system with three storage backends (memory, file, hybrid), loading UI with progress bars, and per-page refresh strategies. The system will allow users to choose between full caching (slow initial load, fast subsequent loads) and selective loading (fast initial load, lazy-load expensive metrics).

**Key Features Planned:**
- Three cache backends: memory (fast), file (persistent), hybrid (recommended default)
- User-configurable cache modes via settings page
- Loading screen with progress bar for full cache mode (60-second timeout)
- Piecewise cache invalidation per subsystem (analytics, dashboard, summary)
- Analytics cache: 1-hour TTL with manual refresh option (no auto-invalidation on task completion)
- Dashboard metrics: Always refresh after task completion (regardless of cache)
- Summary page: Daily cache refresh (once per day on first load)

**Refresh Strategies:**
- Analytics: Manual refresh only, 1-hour TTL, stays cached even after task completion
- Dashboard: Monitored metrics refresh after every task completion
- Summary: Cache once per day, refresh on first page load of day

### 2. Optimize _load_instances() Performance Plan
**File**: `.cursor/plans/optimize_load_instances_a1b2c3d4.plan.md`

A focused optimization plan to eliminate redundant data loading and processing. The `_load_instances()` method is currently called 59 times throughout analytics.py, causing 30-80 seconds of redundant processing per analytics page load.

**Key Optimizations Planned:**
- Instance-level DataFrame caching to eliminate redundant DB/CSV reads
- Smart cache invalidation on instance/task changes
- Optimized JSON parsing using vectorized pandas operations
- Lazy column processing (only calculate derived columns when needed)
- Optional gap filtering for methods that don't require it

**Expected Performance Impact:**
- Current: 30-80 seconds for 59 calls (500-1400ms per call)
- Optimized: ~890ms for 59 calls (cache hit: <10ms per call)
- **30-90x speedup** for cached scenarios

**Time Estimate:** 8-11 hours implementation time

## Plan Structure

### Caching System Implementation
1. **Cache Manager**: Centralized cache management with three backends
2. **Loading UI Component**: Progress bar modal for full cache mode
3. **Cache Mode Selection**: Settings UI for user preference
4. **Refresh Strategies**: Per-page cache invalidation rules
5. **Analytics Integration**: Replace class-level cache with CacheManager
6. **App Initialization**: First-load decision point for cache mode

### _load_instances() Optimization
1. **Instance-Level Cache**: Store processed DataFrame with TTL
2. **Cache Invalidation**: Triggers on instance/task changes
3. **JSON Parsing Optimization**: Vectorized operations, reduce apply() overhead
4. **Lazy Column Processing**: Calculate derived columns only when needed
5. **Performance Testing**: Benchmarks and validation

## Implementation Status

**Status**: Planning phase only - no code changes made

**Next Steps**: 
- Review and approve plans
- Prioritize implementation order (suggest optimizing _load_instances() first for immediate impact)
- Begin implementation when ready

## Files Modified (Planning Documents Only)

- `.cursor/plans/caching_system_implementation_b3e70d55.plan.md` (created)
- `.cursor/plans/optimize_load_instances_a1b2c3d4.plan.md` (created)

## Notes

- Both plans can be implemented independently
- The _load_instances() optimization will provide immediate performance benefits
- The caching system can be integrated incrementally
- CacheManager system will integrate with the _load_instances() cache in future phases
- Plans include detailed time estimates, risk mitigation, and testing strategies
