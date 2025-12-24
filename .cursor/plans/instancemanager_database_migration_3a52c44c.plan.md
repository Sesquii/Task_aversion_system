---
name: InstanceManager Database Migration
overview: Migrate InstanceManager from CSV-only to dual backend (CSV/database) following the TaskManager pattern. This will eliminate performance issues caused by CSV file I/O, especially with OneDrive sync.
todos:
  - id: phase1_infrastructure
    content: "Phase 1: Add database initialization, use_db flag, and helper methods (datetime, JSON parsing)"
    status: pending
  - id: phase2_crud
    content: "Phase 2: Migrate core CRUD methods (create_instance, get_instance, complete_instance, add_prediction, start_instance, cancel_instance, delete_instance)"
    status: pending
    dependencies:
      - phase1_infrastructure
  - id: phase3_queries
    content: "Phase 3: Migrate query methods (list_active_instances, list_recent_completed, pause_instance)"
    status: pending
    dependencies:
      - phase2_crud
  - id: phase4_analytics
    content: "Phase 4: Migrate analytics/statistics methods (get_previous_task_averages, get_previous_actual_averages, get_initial_aversion, has_completed_task, get_previous_aversion_average, get_baseline_aversion_*)"
    status: pending
    dependencies:
      - phase3_queries
  - id: phase5_utilities
    content: "Phase 5: Migrate utility methods (backfill_attributes_from_json, update _update_attributes_from_payload)"
    status: pending
    dependencies:
      - phase4_analytics
  - id: phase6_migration_script
    content: "Phase 6: Create data migration script (migrate_instances_csv_to_database.py)"
    status: pending
    dependencies:
      - phase2_crud
  - id: phase7_testing
    content: "Phase 7: Test all methods, verify performance improvements, test data migration"
    status: pending
    dependencies:
      - phase5_utilities
      - phase6_migration_script
---

# InstanceManager

Database Migration Plan

## Overview

Migrate `InstanceManager` from CSV-only storage to dual backend (CSV/database) following the established `TaskManager` pattern. This migration will:

- Eliminate 5-10 second delays from CSV file reads/writes
- Remove OneDrive sync file locking issues
- Provide faster queries with database indexes
- Maintain backward compatibility with CSV fallback

## Architecture Pattern

Follow the same dual-backend pattern used in `TaskManager`:

```python
class InstanceManager:
    def __init__(self):
        self.use_db = bool(os.getenv('DATABASE_URL'))
        if self.use_db:
            # Initialize database backend
        else:
            # Initialize CSV backend
    
    def some_method(self, ...):
        if self.use_db:
            return self._some_method_db(...)
        else:
            return self._some_method_csv(...)
```



## Implementation Steps

### Phase 1: Core Infrastructure

**File**: `backend/instance_manager.py`

1. **Add database initialization in `__init__`**:

- Check `DATABASE_URL` environment variable
- Import `TaskInstance` model and `get_session` from `backend.database`
- Add `self.use_db` flag and `self.db_session` reference
- Add strict mode support (DISABLE_CSV_FALLBACK) like TaskManager
- Keep CSV initialization as fallback

2. **Create helper methods**:

- `_csv_to_db_datetime(csv_str)` - Parse CSV datetime string to datetime object
- `_db_to_csv_datetime(dt)` - Format datetime object to CSV string format
- `_csv_to_db_dict(row_dict)` - Convert CSV row dict to database-compatible dict
- `_parse_json_field(json_str)` - Safe JSON parsing with fallback to empty dict

### Phase 2: Core CRUD Operations

Migrate these high-frequency methods first (used in task completion/initialization):

3. **`create_instance()`** → Split into `_create_instance_csv()` and `_create_instance_db()`

- Database: Create `TaskInstance` object, parse JSON fields, convert dates
- Return instance_id (both paths)

4. **`get_instance()`** → Split into `_get_instance_csv()` and `_get_instance_db()`

- Database: Query by instance_id, return dict using `to_dict()` method
- Maintain same return format for compatibility

5. **`complete_instance()`** → Split into `_complete_instance_csv()` and `_complete_instance_db()`

- Database: Update TaskInstance, parse actual JSON, calculate scores
- Handle datetime parsing for completed_at
- Update extracted attributes (relief_score, duration_minutes, etc.)

6. **`add_prediction_to_instance()`** → Split into `_add_prediction_csv()` and `_add_prediction_db()`

- Database: Update predicted JSON field, set initialized_at datetime
- Update extracted attributes from predicted payload

7. **`start_instance()`** → Split into `_start_instance_csv()` and `_start_instance_db()`

- Database: Update started_at datetime field

8. **`cancel_instance()`** → Split into `_cancel_instance_csv()` and `_cancel_instance_db()`

- Database: Update cancelled_at, status, actual JSON

9. **`delete_instance()`** → Split into `_delete_instance_csv()` and `_delete_instance_db()`

- Database: Query and delete TaskInstance by instance_id

### Phase 3: Query Methods

10. **`list_active_instances()`** → Split into CSV and DB versions

    - Database: Query with filters: `is_completed=False`, `is_deleted=False`, `status NOT IN ('completed', 'cancelled')`
    - Return list of dicts (use `to_dict()`)

11. **`list_recent_completed()`** → Split into CSV and DB versions

    - Database: Query where `completed_at IS NOT NULL`, order by `completed_at DESC`, limit
    - Use database index on `completed_at` for performance

12. **`ensure_instance_for_task()`** → Already calls `create_instance()`, no changes needed
13. **`pause_instance()`** → Split into CSV and DB versions

    - Database: Update status, clear started_at, update actual JSON with reason

### Phase 4: Analytics/Statistics Methods

These methods do complex filtering and aggregation - database will be much faster:

14. **`get_previous_task_averages()`** → Split into CSV and DB versions

    - Database: Query by task_id, filter by initialized_at IS NOT NULL
    - Parse predicted JSON from database JSON field
    - Aggregate values in Python (or use SQL aggregation if possible)

15. **`get_previous_actual_averages()`** → Split into CSV and DB versions

    - Database: Query by task_id, filter by completed_at IS NOT NULL
    - Parse actual JSON from database JSON field
    - Aggregate values

16. **`get_initial_aversion()`** → Split into CSV and DB versions

    - Database: Query most recent completed instance for task_id
    - Extract expected_aversion from predicted JSON

17. **`has_completed_task()`** → Split into CSV and DB versions

    - Database: Simple count query: `WHERE task_id=X AND is_completed=True`

18. **`get_previous_aversion_average()`** → Split into CSV and DB versions

    - Database: Query completed instances, extract aversion from predicted JSON

19. **`get_baseline_aversion_robust()`** → Split into CSV and DB versions

    - Database: Complex query with multiple filters
    - Aggregate aversion values

20. **`get_baseline_aversion_sensitive()`** → Split into CSV and DB versions

    - Database: Similar to robust but different filtering logic

### Phase 5: Utility Methods

21. **`backfill_attributes_from_json()`** → Split into CSV and DB versions

    - Database: Query all instances, parse JSON fields, update extracted columns
    - Use batch update for performance

22. **`_update_attributes_from_payload()`** → Keep as shared helper

    - Works with both CSV (pandas DataFrame) and database (TaskInstance object)
    - May need slight modification to handle both data structures

### Phase 6: Data Migration Script

**New File**: `migrate_instances_csv_to_database.py`

23. **Create migration script** (similar to `migrate_csv_to_database.py`):

    - Load all instances from CSV
    - Parse datetime strings to datetime objects
    - Parse JSON strings to dicts
    - Convert empty strings to None for nullable fields
    - Batch insert into database
    - Handle duplicates (skip if instance_id already exists)
    - Verify row counts match

### Phase 7: Testing & Verification

24. **Test each migrated method**:

    - Test database path with DATABASE_URL set
    - Test CSV fallback path without DATABASE_URL
    - Verify return formats match (dict structure)
    - Test error handling and fallback behavior

25. **Performance testing**:

    - Run performance comparison script
    - Verify database queries are faster than CSV reads
    - Test with existing data volume

## Key Implementation Details

### Date/Time Handling

CSV stores dates as strings: `"2024-01-15 14:30"`Database stores dates as `DateTime` objectsConversion pattern (from TaskManager):

```python
def _csv_to_db_datetime(self, csv_str):
    if not csv_str or csv_str.strip() == '':
        return None
    try:
        return datetime.strptime(csv_str.strip(), "%Y-%m-%d %H:%M")
    except (ValueError, TypeError):
        return None

def _db_to_csv_datetime(self, dt):
    return dt.strftime("%Y-%m-%d %H:%M") if dt else ''
```



### JSON Field Handling

CSV stores JSON as strings: `'{"expected_relief": 5, ...}'`Database stores JSON as dict (SQLAlchemy JSON type)Conversion pattern:

```python
def _parse_json_field(self, json_str):
    if not json_str or json_str.strip() == '':
        return {}
    try:
        parsed = json.loads(json_str)
        return parsed if isinstance(parsed, dict) else {}
    except (json.JSONDecodeError, TypeError):
        return {}
```



### Numeric Field Handling

CSV stores numbers as strings: `"5.5"` or `""` (empty)Database stores as `Float` or `Integer`, `None` for emptyConversion pattern:

```python
def _csv_to_db_float(self, csv_str):
    if not csv_str or csv_str.strip() == '':
        return None
    try:
        return float(csv_str)
    except (ValueError, TypeError):
        return None
```



### Boolean Field Handling

CSV stores as strings: `"True"` or `"False"`Database stores as booleanConversion:

```python
is_completed = str(row.get('is_completed', 'False')).lower() == 'true'
```



## Files to Modify

- `backend/instance_manager.py` - Main implementation (large file, ~970 lines)

## New Files

- `migrate_instances_csv_to_database.py` - Data migration script

## Dependencies

- `backend/database.py` - TaskInstance model already exists
- `backend/task_manager.py` - Reference implementation for dual-backend pattern

## Testing Strategy

1. **Unit tests per method**: Test CSV and DB paths separately
2. **Integration tests**: Test full workflows (create → initialize → complete)
3. **Performance tests**: Compare CSV vs DB query times
4. **Data migration tests**: Verify all CSV data migrates correctly

## Migration Order

1. Phase 1: Infrastructure (allows testing setup)
2. Phase 2: Core CRUD (highest impact on performance)
3. Phase 3: Query methods (moderate impact)
4. Phase 4: Analytics methods (lower frequency, but complex)
5. Phase 5: Utility methods
6. Phase 6: Data migration script
7. Phase 7: Testing

## Risk Mitigation

- Keep CSV backend fully functional as fallback
- Database errors fall back to CSV (unless strict mode enabled)
- Migration script preserves CSV as backup
- Test each phase before moving to next
- Maintain exact same method signatures and return formats

## Success Criteria

- All InstanceManager methods work with database backend
- Performance improvement: < 100ms for typical operations (vs 5-10s currently)
- No breaking changes to existing UI or analytics code