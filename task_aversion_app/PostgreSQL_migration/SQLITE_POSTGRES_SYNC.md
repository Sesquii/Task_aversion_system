# SQLite/PostgreSQL Synchronization Guide

## Overview

This guide explains how to synchronize data between SQLite (local development) and PostgreSQL (remote production), ensuring schema compatibility and seamless data transfer.

## Key Compatibility Points

### 1. JSON vs JSONB Handling

**SQLite:**
- SQLite doesn't have JSONB - it stores JSON as `TEXT`
- SQLAlchemy's `JSON` type maps to `TEXT` in SQLite
- JSON functions available in SQLite 3.38+ (json_extract, json_array, etc.)

**PostgreSQL:**
- PostgreSQL has both `JSON` (text) and `JSONB` (binary) types
- We use `JSONB` in PostgreSQL for better performance and indexing
- GIN indexes only work on JSONB columns

**SQLAlchemy Compatibility:**
- Our models use `get_json_type()` which returns:
  - `JSONB` for PostgreSQL (better performance, supports GIN indexes)
  - `JSON` for SQLite (maps to TEXT automatically)
- **Application code doesn't need to change** - SQLAlchemy handles conversion automatically
- Python code treats both the same way (as Python dicts/lists)

### 2. Schema Compatibility

All JSON columns are automatically compatible between SQLite and PostgreSQL:

| Column | SQLite Type | PostgreSQL Type | Application Code |
|--------|-------------|-----------------|------------------|
| `predicted` | TEXT (JSON) | JSONB | `dict` (same) |
| `actual` | TEXT (JSON) | JSONB | `dict` (same) |
| `categories` | TEXT (JSON) | JSONB | `list` (same) |
| `routine_days_of_week` | TEXT (JSON) | JSONB | `list` (same) |
| `context` | TEXT (JSON) | JSONB | `dict` (same) |
| `persistent_emotion_values` | TEXT (JSON) | JSONB | `dict` (same) |
| Other JSON fields | TEXT (JSON) | JSONB | Same types |

**Key Point:** The application code is identical for both databases - SQLAlchemy handles the type mapping automatically.

## Synchronization Strategy

### Option 1: Export/Import via CSV (Recommended)

**Export from PostgreSQL:**
```bash
cd task_aversion_app
DATABASE_URL="postgresql://user:password@host:5432/dbname" python -m backend.csv_export
# Exports all tables to CSV files in data/ directory
```

**Import to SQLite:**
```bash
cd task_aversion_app
DATABASE_URL="sqlite:///data/task_aversion.db" python migrate_csv_to_database.py
# Imports all CSV files into SQLite database
```

**Export from SQLite:**
```bash
cd task_aversion_app
DATABASE_URL="sqlite:///data/task_aversion.db" python -m backend.csv_export
```

**Import to PostgreSQL:**
```bash
cd task_aversion_app
DATABASE_URL="postgresql://user:password@host:5432/dbname" python migrate_csv_to_database.py
```

### Option 2: Direct Database Dump/Restore

**PostgreSQL → SQLite:**
Not directly supported - use CSV export/import instead.

**SQLite → PostgreSQL:**
Not directly supported - use CSV export/import instead.

**Why CSV?** It's database-agnostic and handles type conversions automatically.

### Option 3: Application-Level Sync

You can build custom sync logic using the existing export/import functions:

```python
from backend.csv_export import export_all_data_to_csv
from backend.database import get_session, Task, TaskInstance

# Export from source database
export_counts, exported_files = export_all_data_to_csv(data_dir='sync_data')

# Switch DATABASE_URL to target database
os.environ['DATABASE_URL'] = 'postgresql://...'  # or sqlite:///...

# Import to target database
from migrate_csv_to_database import migrate_all_tables
migrate_all_tables(csv_dir='sync_data')
```

## JSON Column Synchronization

### How JSON/JSONB Data is Handled

**Export (PostgreSQL JSONB → CSV):**
1. SQLAlchemy reads JSONB column → Returns Python dict/list
2. `to_dict()` method uses `json.dumps()` → Converts to JSON string
3. CSV file stores JSON string

**Import (CSV → SQLite TEXT or PostgreSQL JSONB):**
1. CSV contains JSON string
2. `json.loads()` parses JSON string → Returns Python dict/list
3. SQLAlchemy converts Python dict/list → Database type (TEXT for SQLite, JSONB for PostgreSQL)

**Key Point:** The JSON string format in CSV is compatible with both databases. SQLAlchemy handles the database-specific type conversion automatically.

### Example: Synchronizing `predicted` Column

**PostgreSQL (JSONB):**
```python
# Store
task_instance.predicted = {'expected_relief': 50}  # Python dict
session.commit()  # SQLAlchemy converts to JSONB

# Read
predicted = task_instance.predicted  # Returns Python dict
```

**SQLite (TEXT):**
```python
# Store (same code!)
task_instance.predicted = {'expected_relief': 50}  # Python dict
session.commit()  # SQLAlchemy converts to TEXT (JSON string)

# Read (same code!)
predicted = task_instance.predicted  # Returns Python dict
```

**CSV Export (both databases):**
```python
# Both produce the same CSV string
'predicted': '{"expected_relief": 50}'
```

## Best Practices

### 1. Always Use CSV for Synchronization

✅ **DO:** Use CSV export/import for data synchronization
- Database-agnostic
- Handles type conversions automatically
- Human-readable (can inspect/validate)
- Works with version control (for small datasets)

❌ **DON'T:** Try to dump/restore raw database files
- Database-specific formats
- Type incompatibilities
- Risk of data corruption

### 2. Verify Schema Compatibility

Before syncing, ensure both databases have compatible schemas:

```python
# Check PostgreSQL schema
DATABASE_URL="postgresql://..." python PostgreSQL_migration/check_migration_status.py

# Check SQLite schema (should match)
DATABASE_URL="sqlite:///..." python -c "from backend.database import init_db; init_db()"
```

### 3. Test Synchronization in Development

1. Create test data in SQLite
2. Export to CSV
3. Import to PostgreSQL (test database)
4. Verify data integrity
5. Export from PostgreSQL back to CSV
6. Compare CSVs (should match except for timestamps/user_ids)

### 4. Handle Auto-Generated Fields

**Fields that may differ between databases:**
- `user_id`: May differ if user tables are out of sync
- `created_at`: May differ slightly (millisecond precision)
- `instance_id`: Format should be consistent (`i{timestamp}`)
- `task_id`: Format should be consistent (`t{timestamp}`)

**Solution:** Use CSV export's `to_dict()` which preserves these as strings, ensuring format consistency.

### 5. Incremental Sync (Future Enhancement)

For production use, consider implementing incremental sync:
- Track last sync timestamp
- Only export records modified since last sync
- Merge with existing data (handle conflicts)

This is beyond the scope of the current export/import system but could be added as a feature.

## Troubleshooting

### Issue: JSON columns show as TEXT in PostgreSQL

**Cause:** Columns were created as JSON (not JSONB) before the JSONB update.

**Solution:**
```bash
# Run migration 005 which converts JSON → JSONB automatically
DATABASE_URL="postgresql://..." python PostgreSQL_migration/005_add_indexes_and_foreign_keys.py
```

### Issue: CSV import fails with JSON decode errors

**Cause:** CSV contains invalid JSON strings.

**Solution:**
```python
# Check CSV files for invalid JSON
import pandas as pd
import json

df = pd.read_csv('data/task_instances.csv')
for idx, row in df.iterrows():
    try:
        json.loads(row['predicted'] or '{}')
        json.loads(row['actual'] or '{}')
    except json.JSONDecodeError as e:
        print(f"Row {idx}: Invalid JSON - {e}")
```

### Issue: Data types don't match after sync

**Cause:** Schema differences between databases.

**Solution:**
1. Run migrations on both databases to ensure schema compatibility
2. Use `check_migration_status.py` to verify
3. Re-run export/import

### Issue: Foreign key constraints fail on import

**Cause:** Referenced records don't exist in target database.

**Solution:**
1. Export/import tables in dependency order:
   - Users → Tasks → TaskInstances → Other tables
2. Or temporarily disable foreign key constraints during import:
   ```python
   # PostgreSQL: ALTER TABLE ... DISABLE TRIGGER ALL
   # SQLite: PRAGMA foreign_keys = OFF
   ```

## Summary

✅ **JSON/JSONB Compatibility:** Automatic - SQLAlchemy handles conversion
✅ **Schema Compatibility:** Use migrations to keep schemas in sync
✅ **Data Synchronization:** Use CSV export/import (database-agnostic)
✅ **Application Code:** No changes needed - works with both databases

The key insight is that **SQLAlchemy abstracts away the JSON/JSONB differences** - your application code is identical for both databases. The only difference is PostgreSQL gets better performance from JSONB + GIN indexes, while SQLite stores JSON as TEXT (which is perfectly fine for development).
