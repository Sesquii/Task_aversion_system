---
name: Performance Plan - CSV Reads and Database Query Efficiency
overview: Reduce IO and query overhead by minimizing CSV usage, optimizing DB queries (indexing, batching, column selection), and ensuring clean fallbacks.
todos:
  - id: audit-csv
    content: Audit remaining CSV read/write paths; prefer DB except exports/migration
    status: pending
  - id: db-indexes
    content: Add/confirm DB indexes on common filters (task_id, completed_at, task_type, is_completed)
    status: pending
  - id: prune-columns
    content: Apply column selection for list/views; avoid full row loads when not needed
    status: pending
  - id: batch-queries
    content: Eliminate N+1 by batching (IN queries) or eager loading where applicable
    status: pending
  - id: add-caches
    content: Add small in-memory caches with TTL/invalidation for task/instance list/get
    status: pending
  - id: log-bench
    content: Enable slow-query logging in dev; benchmark list/get before/after
    status: pending
    dependencies:
      - audit-csv
      - db-indexes
      - batch-queries
---

# Performance Plan - CSV Reads and Database Query Efficiency

## Overview

Reduce IO overhead by minimizing CSV reads (prefer DB), optimizing database queries (indexes, batching, column pruning), and ensuring fallbacks are safe and controlled.

---

## Phase 1: Data Access Strategy

### 1.1 Prefer DB, Minimize CSV

**Files**: `backend/task_manager.py`, `backend/instance_manager.py`

- Confirm DB is default; ensure CSV fallback only when explicitly requested (USE_CSV) or for back-compat.
- Audit any code paths still using CSV when DB is available; route them to DB.

### 1.2 Strict Mode Handling

- Ensure DISABLE_CSV_FALLBACK works: fail fast rather than silent fallback when set.

---

## Phase 2: Query Optimization

### 2.1 Indexing

**Files**: `backend/database.py` (models)

- Add/confirm indexes on frequently filtered columns:
- TaskInstance: task_id, completed_at, created_at, task_type, is_completed
- Task: task_id, task_type, created_at
- Consider composite indexes for common filters (task_type + is_completed).

### 2.2 Column Pruning

- Use column selection for list/views (avoid loading entire rows if not needed).
- In analytics/recommendations, fetch only needed fields.

### 2.3 Batch Queries / Avoid N+1

- Replace per-task queries with `IN` queries when loading many tasks/instances.
- Use joinedload/eager loading if relationships are defined.

---

## Phase 3: CSV Usage Audit

### 3.1 Identify CSV Reads

**Files**: `backend/task_manager.py`, `backend/instance_manager.py`, `backend/csv_manager.py`

- List remaining CSV read/write operations.
- Decide per use: migrate to DB, or keep only for export/backup.

### 3.2 Migration Helpers

- Keep migration scripts (`migrate_csv_to_database.py`) documented but not used at runtime.

---

## Phase 4: Caching for IO Reduction

### 4.1 Task/Instance Caches

- In managers, add simple in-memory caches (with TTL or write-invalidate) for list/get operations when appropriate.
- Avoid stale data: invalidate on writes.

---

## Phase 5: Validation & Logging

### 5.1 Logging Slow Queries

- Enable optional SQL logging for slow queries (>100ms) in dev mode.

### 5.2 Benchmarks

- Measure list/get tasks/instances with and without caching and with DB vs CSV.
- Target: list operations sub-100ms on sample dataset.

---

## Success Criteria

- Default path uses DB, CSV only when explicitly requested or for migration/export.
- Frequent filters indexed; no obvious N+1 patterns in core flows.
- Column pruning applied where only a few fields are needed.
- CSV reads minimized; caches reduce repeat IO.
- Basic benchmarks improved (sub-100ms list/get where feasible on sample data).

---

## Notes

- Keep caching simple and safe; TTL or invalidate on write.
- Avoid over-optimizing until profiling shows need.
- Maintain back-compat for migration/export, but keep runtime on DB for performance.