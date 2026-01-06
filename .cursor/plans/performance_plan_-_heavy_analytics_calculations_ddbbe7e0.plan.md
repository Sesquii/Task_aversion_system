---
name: Performance Plan - Heavy Analytics Calculations
overview: "Optimize heavy analytics calculations to reduce latency on dashboard/analytics pages: profiling, caching, chunking, lazy loading, and precomputation."
todos:
  - id: profile-analytics
    content: Instrument analytics hotspots (execution/composite/reco/belief) with timing logs
    status: pending
  - id: cache-aggregates
    content: Add TTL cache for task list, recent instances, common aggregates
    status: pending
  - id: chunk-long-tasks
    content: Batch or chunk long-running per-instance loops in analytics
    status: pending
    dependencies:
      - profile-analytics
  - id: lazy-load-ui
    content: Defer heavy charts in UI; add spinners and default shorter windows
    status: pending
  - id: prune-reloads
    content: Reuse loaded frames; avoid repeated full reloads; prune columns when possible
    status: pending
  - id: bench-validate
    content: Benchmark before/after; regression-check correctness vs uncached paths
    status: pending
    dependencies:
      - cache-aggregates
      - chunk-long-tasks
---

# Performance Plan - Heavy Analytics Calculations

## Overview

Reduce latency for analytics-heavy operations (dashboard/analytics pages) by profiling hotspots, adding caching, chunking long computations, lazy-loading charts, and precomputing summaries where feasible.

---

## Phase 1: Profiling & Hotspot Identification

### 1.1 Instrumentation

**Files**: `backend/analytics.py`

- Add lightweight timing around heavy methods (execution score, composite scores, recommendation pipeline, belief/state calculations if added) using existing `perf_logger` or simple `time.time()` wrappers.
- Log duration and input sizes (rows processed) to identify O(N) or worse sections.

### 1.2 Profiling Targets

- Execution score calculations (chunked variants)
- Composite/productivity score calculations
- Recommendation generation (loading all tasks + instances)
- Belief/state detection (if integrated)

Deliverable: short log summary pointing to slow sections (e.g., >300ms).

---

## Phase 2: Caching & Reuse

### 2.1 Result Caching

**Files**: `backend/analytics.py`

- Add in-memory cache with TTL (5–10 minutes) for:
- Task list
- Recent completed instances
- Pre-aggregated metrics (avg relief, avg load, productivity volumes)
- Invalidate on writes or use simple TTL.

### 2.2 Precomputation Hooks (optional)

- Precompute daily/weekly aggregates on-demand (first request) and cache result.
- Store in memory; keep CSV/DB as source of truth.

---

## Phase 3: Chunking & Batching

### 3.1 Chunk Long-Running Jobs

**Files**: `backend/analytics.py`

- For per-instance loops (scores/trends), process in batches (e.g., 200–500 rows) with interim yields.
- Reuse existing chunked execution patterns where present.

### 3.2 Vectorization First

- Prefer pandas vectorized ops over Python loops; only chunk when vectorization not feasible.

---

## Phase 4: Lazy Loading in UI

### 4.1 Deferred Charts

**Files**: `ui/analytics_page.py`, `ui/dashboard.py`

- Load heavy charts on expansion or after initial page render.
- Add spinners/“load on demand” buttons for heavy sections (correlations, multi-attribute trends).

### 4.2 Limit Default Windows

- Default to shorter time windows (e.g., 30–60 days) and let user expand range.

---

## Phase 5: Data Access Efficiency

### 5.1 Minimize Full Reloads

- Ensure `_load_instances()` isn’t repeatedly reading full datasets per chart; reuse cached frame when possible.
- Consider a thin “recent slice” function for dashboard (last 30–60 days).

### 5.2 Column Pruning

- When only a few metrics are needed, select those columns to reduce memory/CPU.

---

## Phase 6: Validation & Benchmarks

### 6.1 Bench Targets

- Dashboard initial load: target <1.5–2.0s on sample dataset.
- Analytics heavy charts: target <1.0s after cache warm.

### 6.2 Regression Checks

- Compare timings before/after caching/chunking.
- Spot-check correctness vs. uncached paths.

---

## Success Criteria

- Profiling identifies top 2–3 hotspots.
- Caching/TTL in place for common aggregates and recent instances.
- Heavy loops chunked or vectorized; no unbounded full-data scans on every request.
- UI defers heavy charts; defaults to modest windows.
- Benchmarks improved to targets or better.

---

## Notes

- Keep caching simple (in-memory, TTL). Avoid premature persistence caches.
- Maintain correctness: cache invalidation on write or rely on short TTLs.
- Prefer vectorization; chunk only where necessary.