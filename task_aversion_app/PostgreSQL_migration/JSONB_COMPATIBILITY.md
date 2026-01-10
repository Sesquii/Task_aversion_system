# JSON vs JSONB Compatibility Guide

## Quick Answer

**You do NOT need to refactor your application code.** SQLAlchemy handles JSON/JSONB conversion automatically. Your existing code that uses Python dicts will work with both JSON and JSONB columns.

## JSON vs JSONB: What's the Difference?

### JSON (PostgreSQL)
- Text-based storage (stores exact JSON text)
- Preserves whitespace and key ordering
- **Cannot use GIN indexes** (indexing not supported)
- Slightly faster to insert (no conversion)

### JSONB (PostgreSQL - Recommended)
- Binary storage (converted from JSON)
- Normalizes whitespace and key ordering
- **Supports GIN indexes** (much faster queries)
- Slightly slower to insert (conversion overhead) but much faster queries
- Better for applications that query JSON data

### In SQLite
- SQLite doesn't distinguish between JSON and JSONB
- Both are stored as TEXT
- SQLite 3.38+ has JSON functions but no separate JSONB type
- For compatibility, we use JSON type which maps to TEXT in SQLite

## Application Code Compatibility

### ✅ No Changes Needed

**Why?** SQLAlchemy automatically handles conversion:

```python
# Your existing code works with both JSON and JSONB:
task_instance.predicted = {'expected_relief': 50}  # Python dict
task_instance.actual = {'actual_relief': 60}      # Python dict

# SQLAlchemy converts Python dict → JSON/JSONB automatically
session.add(task_instance)
session.commit()

# When reading:
predicted = task_instance.predicted  # Returns Python dict (same for JSON and JSONB)
actual = task_instance.actual        # Returns Python dict (same for JSON and JSONB)
```

**From Python's perspective, JSON and JSONB are identical** - both are Python dicts when you read them, and both accept Python dicts when you write them.

## CSV Export/Import Compatibility

### ✅ Already Compatible

Your CSV export/import code already handles this correctly:

```python
# Export (database → CSV)
def to_dict(self):
    'predicted': json.dumps(self.predicted) if isinstance(self.predicted, dict) else (self.predicted or '{}'),
    'actual': json.dumps(self.actual) if isinstance(self.actual, dict) else (self.actual or '{}'),
```

This works because:
- Database (JSONB/JSON) → Python dict → `json.dumps()` → CSV string ✅
- CSV string → `json.loads()` → Python dict → Database (JSONB/JSON) ✅

Both JSON and JSONB store the same data structure - the only difference is the internal storage format in PostgreSQL.

## Database Schema: Why Use JSONB?

**We use JSONB for PostgreSQL because:**

1. **Performance**: GIN indexes make JSON queries much faster
2. **Indexing**: Can create GIN indexes on JSONB columns (not possible with JSON)
3. **Better operators**: JSONB supports more PostgreSQL operators and functions
4. **Still compatible**: Python code treats them the same

**Example performance difference:**
```sql
-- Without index (JSON): Full table scan
SELECT * FROM task_instances WHERE predicted @> '{"expected_relief": 50}';

-- With GIN index (JSONB): Fast index lookup
CREATE INDEX USING GIN (predicted);  -- Only works on JSONB!
SELECT * FROM task_instances WHERE predicted @> '{"expected_relief": 50}';  -- Much faster!
```

## What We Changed

### 1. Database Model (`backend/database.py`)

**Before:**
```python
predicted = Column(JSON, default=dict)  # Creates JSON (not JSONB) in PostgreSQL
actual = Column(JSON, default=dict)
```

**After:**
```python
json_type = get_json_type()  # Returns JSONB for PostgreSQL, JSON for SQLite
predicted = Column(json_type, default=dict)  # Creates JSONB in PostgreSQL
actual = Column(json_type, default=dict)     # Creates JSONB in PostgreSQL
```

**Result**: Tables created with DATABASE_URL=postgresql://... will use JSONB automatically.

### 2. Migration Script 005

**Added JSON → JSONB conversion** before creating GIN indexes:
- Checks if columns are JSON (not JSONB)
- Converts them to JSONB if needed using `ALTER COLUMN ... TYPE JSONB`
- Then creates GIN indexes (which only work on JSONB)

**Why?** If you already ran migration 003 with JSON columns (before this fix), migration 005 will now convert them to JSONB automatically.

## Migration Strategy

### For New Databases

1. Set `DATABASE_URL=postgresql://...`
2. Run migration 001 (creates schema with JSONB columns automatically)
3. Run migration 003 (creates task_instances with JSONB columns)
4. Run migration 005 (creates GIN indexes - will work because columns are already JSONB)

### For Existing Databases

If you already ran migrations with JSON (not JSONB) columns:

1. Migration 005 now automatically converts JSON → JSONB
2. Then creates GIN indexes
3. Data is preserved during conversion

**The conversion is safe**: PostgreSQL can cast JSON to JSONB without data loss:
```sql
ALTER TABLE task_instances ALTER COLUMN predicted TYPE JSONB USING predicted::JSONB;
```

## Testing

### Verify JSONB Columns

After running migrations, check column types:

```sql
SELECT column_name, data_type 
FROM information_schema.columns 
WHERE table_name = 'task_instances' 
AND column_name IN ('predicted', 'actual');
```

Should show:
```
column_name | data_type
------------+----------
predicted   | jsonb
actual      | jsonb
```

### Verify GIN Indexes

```sql
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'task_instances' 
AND indexname LIKE '%_gin';
```

Should show:
```
idx_task_instances_predicted_gin | CREATE INDEX ... USING gin (predicted)
idx_task_instances_actual_gin    | CREATE INDEX ... USING gin (actual)
```

## Additional JSONB Columns Optimized

Beyond `predicted` and `actual`, we also optimize these JSON columns for PostgreSQL:

| Table | Column | Type | GIN Index? | Use Case |
|-------|--------|------|------------|----------|
| `task_instances` | `predicted` | JSONB | ✅ Yes | Frequently queried for analytics |
| `task_instances` | `actual` | JSONB | ✅ Yes | Frequently queried for analytics |
| `tasks` | `categories` | JSONB | Optional* | May be queried for filtering |
| `tasks` | `routine_days_of_week` | JSONB | Optional* | Used in routine scheduling |
| `popup_responses` | `context` | JSONB | No | Less frequently queried |
| `user_preferences` | Various JSON fields | JSONB | No | User-specific, rarely queried directly |

*GIN indexes on `categories` and `routine_days_of_week` are optional - they can be added later if needed for performance. Migration 005 ensures these columns are JSONB (ready for future indexing).

## SQLite Compatibility

**Important:** SQLite doesn't have JSONB - it stores JSON as TEXT. This is fine for local development.

**How it works:**
- SQLAlchemy automatically maps `JSONB` → `JSON` → `TEXT` in SQLite
- Application code is identical for both databases
- CSV export/import handles both formats transparently

**For synchronization between SQLite (local) and PostgreSQL (remote):**
- See `SQLITE_POSTGRES_SYNC.md` for detailed synchronization guide
- Use CSV export/import for database-agnostic data transfer
- Schema compatibility is automatic - SQLAlchemy handles type differences

## Summary: What You Need to Know

1. **Application code**: No changes needed ✅
   - SQLAlchemy handles JSON/JSONB conversion automatically
   - Python dicts work with both types
   - Same code works for SQLite (TEXT) and PostgreSQL (JSONB)

2. **CSV export/import**: Already compatible ✅
   - Uses `json.dumps()`/`json.loads()` which works with both
   - Database-agnostic format for synchronization
   - No changes needed

3. **Database schema**: JSONB for PostgreSQL, JSON (TEXT) for SQLite ✅
   - PostgreSQL: JSONB provides better performance and enables GIN indexes
   - SQLite: JSON maps to TEXT (sufficient for development)
   - Migration 005 ensures all JSON columns are JSONB in PostgreSQL

4. **All JSON columns optimized**: ✅
   - `predicted`, `actual`: JSONB with GIN indexes (high priority)
   - `categories`, `routine_days_of_week`: JSONB (ready for future indexing)
   - Other JSON fields: JSONB for consistency and future-proofing

5. **Migration**: Automatic conversion ✅
   - Migration 005 converts all JSON → JSONB if needed
   - Checks both `task_instances` and `tasks` tables
   - No manual steps required

6. **SQLite synchronization**: Fully compatible ✅
   - SQLite uses TEXT for JSON (automatic mapping)
   - CSV export/import works seamlessly between databases
   - See `SQLITE_POSTGRES_SYNC.md` for synchronization guide

## Conclusion

**You do NOT need to refactor any application code or CSV export/import functionality.** The JSON → JSONB optimization is a database-level change that SQLAlchemy handles transparently. Your existing code works identically for both SQLite (local development) and PostgreSQL (production), with PostgreSQL getting better performance from JSONB + GIN indexes.

**All JSON columns are now optimized for PostgreSQL while maintaining full SQLite compatibility.**
