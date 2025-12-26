---
name: SQL Logic Verification and Metrics Refinement
overview: Verify all methods work correctly with SQL database backend post-migration. Test database queries, ensure data integrity, verify SQL-specific logic, and refine existing metrics. Includes comprehensive testing strategy and validation of all CRUD operations.
todos:
  - id: verify_taskmanager_crud
    content: Verify all TaskManager CRUD operations work with database (create, get, update, delete, list)
    status: pending
  - id: verify_instancemanager_crud
    content: Verify all InstanceManager CRUD operations work with database (create, get, complete, add_prediction, start, cancel, delete)
    status: pending
  - id: verify_data_types
    content: Verify data types are stored correctly (datetime, JSON, numeric, boolean, null handling)
    status: pending
    dependencies:
      - verify_taskmanager_crud
      - verify_instancemanager_crud
  - id: verify_query_methods
    content: Verify all query methods work with database (list_active_instances, list_recent_completed, analytics queries)
    status: pending
    dependencies:
      - verify_instancemanager_crud
  - id: verify_data_integrity
    content: Verify data integrity (foreign keys, constraints, indexes, referential integrity)
    status: pending
    dependencies:
      - verify_data_types
  - id: add_missing_indexes
    content: Review and add missing database indexes for frequently queried fields
    status: pending
    dependencies:
      - verify_query_methods
  - id: optimize_queries
    content: Optimize slow queries (use SQL aggregation, batch queries, optimize JOINs)
    status: pending
    dependencies:
      - add_missing_indexes
  - id: verify_metrics_accuracy
    content: Compare database metric results to CSV results, verify calculations are identical
    status: pending
    dependencies:
      - verify_query_methods
  - id: refine_metrics_performance
    content: Refine metrics based on database performance (optimize slow calculations, use database aggregation)
    status: pending
    dependencies:
      - verify_metrics_accuracy
  - id: create_test_suite
    content: Create comprehensive test suite for SQL verification (CRUD, queries, integrity, performance)
    status: pending
    dependencies:
      - verify_data_integrity
      - optimize_queries
  - id: performance_benchmarking
    content: Benchmark query performance, compare CSV vs database, identify bottlenecks
    status: pending
    dependencies:
      - create_test_suite
  - id: documentation
    content: Document SQL-specific considerations, verification results, and optimization findings
    status: pending
    dependencies:
      - performance_benchmarking
---

# SQL Logic Verification and Metrics Refinement Plan

**Created:** 2025-01-XX

**Status:** Planning

**Priority:** High (ensures data integrity and correctness)

**Timeline:** 2-3 days

## Overview

After SQLite migration, verify all methods work correctly with SQL database backend. Test database queries, ensure data integrity, verify SQL-specific logic (indexes, foreign keys, constraints), and refine existing metrics based on database performance and accuracy.

## Current State

- ✅ SQLite migration complete
- ✅ TaskManager has dual backend (CSV/database)
- ✅ InstanceManager has dual backend (CSV/database)
- ❌ No comprehensive SQL verification testing
- ❌ SQL-specific optimizations may be missing
- ❌ Metrics may need refinement based on database performance

## Goals

1. Verify all CRUD operations work with database
2. Test all query methods with database
3. Verify data integrity (foreign keys, constraints)
4. Check SQL-specific optimizations (indexes, query performance)
5. Refine metrics based on database accuracy
6. Document SQL-specific considerations
7. Create verification test suite

## Implementation Strategy

### Phase 1: CRUD Operations Verification

**Files to test:**

- `backend/task_manager.py` - All CRUD methods
- `backend/instance_manager.py` - All CRUD methods

**Tasks:**

1. **TaskManager CRUD Verification**

- Test `create_task()` with database
- Test `get_task()` with database
- Test `update_task()` with database
- Test `delete_task()` with database
- Test `list_tasks()` with database
- Verify return formats match CSV version
- Test error handling

2. **InstanceManager CRUD Verification**

- Test `create_instance()` with database
- Test `get_instance()` with database
- Test `complete_instance()` with database
- Test `add_prediction_to_instance()` with database
- Test `start_instance()` with database
- Test `cancel_instance()` with database
- Test `delete_instance()` with database
- Verify return formats match CSV version
- Test error handling

3. **Data Type Verification**

- Verify datetime fields are stored correctly
- Verify JSON fields are parsed correctly
- Verify numeric fields are correct type
- Verify boolean fields are correct type
- Verify None/null handling

### Phase 2: Query Methods Verification

**Files to test:**

- `backend/task_manager.py` - Query methods
- `backend/instance_manager.py` - Query methods
- `backend/analytics.py` - Analytics queries

**Tasks:**

1. **TaskManager Query Verification**

- Test `list_tasks()` performance
- Test filtering and sorting
- Test with large datasets
- Verify query performance

2. **InstanceManager Query Verification**

- Test `list_active_instances()` with filters
- Test `list_recent_completed()` with limits
- Test `pause_instance()` updates
- Test query performance
- Verify indexes are used

3. **Analytics Query Verification**

- Test `get_dashboard_metrics()` with database
- Test `get_relief_summary()` with database
- Test `get_multi_attribute_trends()` with database
- Test complex aggregations
- Verify query performance
- Check for N+1 query issues

### Phase 3: Data Integrity Verification

**Files to verify:**

- `backend/database.py` - Database schema
- Migration scripts

**Tasks:**

1. **Foreign Key Verification**

- Verify task_id foreign keys work
- Test cascade deletes (if configured)
- Test referential integrity

2. **Constraint Verification**

- Verify unique constraints
- Verify not-null constraints
- Verify check constraints (if any)
- Test constraint violations

3. **Index Verification**

- Verify indexes exist on frequently queried fields
- Test index usage in queries
- Verify index performance improvements

### Phase 4: SQL-Specific Optimizations

**Files to modify:**

- `backend/database.py` - Add missing indexes
- `backend/analytics.py` - Optimize queries
- `backend/task_manager.py` - Optimize queries
- `backend/instance_manager.py` - Optimize queries

**Tasks:**

1. **Add Missing Indexes**

- Review query patterns
- Add indexes on frequently filtered fields
- Add composite indexes where needed
- Test index performance

2. **Optimize Queries**

- Review slow queries
- Use SQL aggregation instead of Python loops
- Batch related queries
- Optimize JOIN operations

3. **Query Performance Testing**

- Benchmark query times
- Compare CSV vs database performance
- Identify bottlenecks
- Optimize slow queries

### Phase 5: Metrics Refinement

**Files to modify:**

- `backend/analytics.py` - Refine metric calculations

**Tasks:**

1. **Accuracy Verification**

- Compare database results to CSV results
- Verify metric calculations are identical
- Fix any discrepancies
- Document differences (if any)

2. **Performance-Based Refinement**

- Optimize slow metric calculations
- Cache expensive calculations
- Use database aggregation where possible
- Refine based on performance data

3. **Data Quality Refinement**

- Handle missing data better
- Improve null handling
- Add data validation
- Improve error messages

### Phase 6: Comprehensive Testing

**Files to create:**

- `tests/test_sql_verification.py` - SQL verification tests
- `tests/test_database_integrity.py` - Data integrity tests

**Tasks:**

1. **Create Test Suite**

- Test all CRUD operations
- Test all query methods
- Test data integrity
- Test error handling
- Test edge cases

2. **Performance Testing**

- Benchmark all operations
- Compare CSV vs database
- Test with realistic data volumes
- Identify performance regressions

3. **Regression Testing**

- Test that existing functionality still works
- Verify no data loss
- Verify calculations are correct
- Test backward compatibility

## Technical Details

### Verification Checklist

**For Each Method:**

1. ✅ Works with database backend
2. ✅ Returns same format as CSV version
3. ✅ Handles missing data correctly
4. ✅ Handles errors gracefully
5. ✅ Performance acceptable
6. ✅ Data integrity maintained
7. ✅ SQL queries are optimized

### Index Recommendations

```python
# backend/database.py - Add indexes
Index('idx_task_instances_task_id', TaskInstance.task_id),
Index('idx_task_instances_completed_at', TaskInstance.completed_at),
Index('idx_task_instances_initialized_at', TaskInstance.initialized_at),
Index('idx_task_instances_status', TaskInstance.status),
Index('idx_task_instances_is_completed', TaskInstance.is_completed),
Index('idx_emotions_task_id', Emotion.task_id),
Index('idx_emotions_created_at', Emotion.created_at),
```

### Query Optimization Patterns

**Use SQL Aggregation:**

```python
# Instead of:
instances = session.query(TaskInstance).all()
total = sum(inst.total_minutes for inst in instances)

# Use:
total = session.query(func.sum(TaskInstance.duration_minutes)).scalar()
```

**Batch Related Queries:**

```python
# Instead of N+1 queries:
for task_id in task_ids:
    instances = session.query(TaskInstance).filter_by(task_id=task_id).all()

# Use single query:
instances = session.query(TaskInstance).filter(
    TaskInstance.task_id.in_(task_ids)
).all()
```

## Testing Strategy

### Unit Tests

```python
def test_task_manager_crud_with_database():
    """Test all TaskManager CRUD operations with database."""
    # Set DATABASE_URL
    # Test create, read, update, delete
    # Verify data integrity

def test_instance_manager_crud_with_database():
    """Test all InstanceManager CRUD operations with database."""
    # Similar to above

def test_analytics_queries_with_database():
    """Test analytics queries with database."""
    # Verify results match CSV version
    # Test performance
```

### Integration Tests

1. Test full workflows (create → initialize → complete)
2. Test with realistic data volumes
3. Test concurrent operations
4. Test data migration accuracy

### Performance Tests

1. Benchmark query times
2. Compare CSV vs database
3. Test with large datasets (1000+ instances)
4. Identify slow queries

## Success Criteria

- ✅ All CRUD operations work with database
- ✅ All query methods work with database
- ✅ Data integrity maintained (foreign keys, constraints)
- ✅ Query performance acceptable (< 100ms for typical queries)
- ✅ Metrics calculations are accurate
- ✅ No data loss or corruption
- ✅ Comprehensive test suite created
- ✅ Documentation complete

## Dependencies

- SQLite migration complete
- Database schema finalized
- All methods have database implementations

## Notes

- Test with both SQLite and PostgreSQL (if available)
- Keep CSV backend as fallback during verification
- Document any SQL-specific considerations