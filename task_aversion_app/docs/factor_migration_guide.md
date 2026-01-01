# Factor Migration Guide

## Overview

This guide explains how `serendipity_factor` and `disappointment_factor` are calculated and stored in the database.

## Automatic Calculation for Future Tasks

**✅ Future tasks automatically calculate and store factors when completed.**

When you complete a task instance using the database backend:
1. The system extracts `expected_relief` from the `predicted` JSON (set during initialization)
2. The system extracts `actual_relief` from the `actual` JSON (set during completion)
3. Factors are automatically calculated and stored:
   - `net_relief = actual_relief - expected_relief`
   - `serendipity_factor = max(0, net_relief)` (positive net relief = pleasant surprise)
   - `disappointment_factor = max(0, -net_relief)` (negative net relief = disappointment)

**No manual intervention needed** - this happens automatically in `_complete_instance_db()`.

## One-Time Migration for Existing Data

**Run the migration script once** to backfill factors for existing completed instances:

```bash
python task_aversion_app/migrate_factors_to_database.py
```

### Migration Script Features

- **Idempotent**: Safe to run multiple times
  - Only updates instances that are missing factors
  - Skips instances that already have factors calculated
  - Won't overwrite existing data unnecessarily

- **Automatic**: Processes all completed instances
  - Finds all instances with `is_completed = True`
  - Calculates factors from `expected_relief` and `actual_relief` in JSON
  - Handles normalization (scales 0-10 to 0-100 if needed)

- **Safe**: Error handling and reporting
  - Continues processing even if individual instances fail
  - Reports summary statistics at the end
  - Exits with error code if any critical errors occurred

### Migration Output Example

```
======================================================================
Factor Migration: Calculate and Store Serendipity/Disappointment Factors
======================================================================

1. Initializing database...
   [OK] Database initialized

2. Loading completed task instances...
   Found 65 completed instance(s)

3. Calculating and storing factors...
   Processed 10 instance(s)...
   Processed 20 instance(s)...
   ...

4. Committing changes to database...
   [OK] Changes committed

======================================================================
Migration Summary
======================================================================
Total instances processed: 65
Successfully updated: 45
Skipped (already have factors or missing data): 20
Errors: 0
======================================================================

[SUCCESS] Migration completed successfully!
```

## How It Works

### Database Schema

The `TaskInstance` model includes:
- `net_relief` (Float, nullable) - Difference between actual and expected relief
- `serendipity_factor` (Float, nullable) - Positive net relief (pleasant surprise)
- `disappointment_factor` (Float, nullable) - Negative net relief (disappointment)

### Calculation Logic

```python
# Normalize relief values (scale 0-10 to 0-100 if needed)
expected_relief = normalize(expected_relief)
actual_relief = normalize(actual_relief)

# Calculate net relief
net_relief = actual_relief - expected_relief

# Calculate factors (only positive values)
serendipity_factor = max(0.0, net_relief)      # Positive = pleasant surprise
disappointment_factor = max(0.0, -net_relief)  # Negative = disappointment (stored as positive)
```

### Storage Locations

- **Database**: Factors stored in dedicated columns for fast queries
- **CSV**: Factors calculated on-the-fly by analytics (no storage needed)

### Analytics Integration

The analytics module (`analytics.py`) uses a **hybrid approach**:
1. **First**: Try to use stored factors from database
2. **Fallback**: Calculate on-the-fly if stored values are missing

This ensures:
- ✅ Fast queries when factors are stored
- ✅ Backward compatibility with old data
- ✅ Works with both database and CSV backends

## Verification

After running the migration, verify factors are stored:

1. **Check database directly**:
   ```python
   from backend.database import get_session, TaskInstance
   
   with get_session() as session:
       instances = session.query(TaskInstance).filter(
           TaskInstance.serendipity_factor.isnot(None)
       ).limit(5).all()
       
       for instance in instances:
           print(f"{instance.instance_id}: serendipity={instance.serendipity_factor}, "
                 f"disappointment={instance.disappointment_factor}")
   ```

2. **Check factors comparison page**:
   - Navigate to Analytics → Factors Comparison
   - Should show data for instances with factors
   - Time series chart should display factors over time

3. **Complete a new task**:
   - Initialize a task with `expected_relief`
   - Complete it with `actual_relief`
   - Check database - factors should be automatically calculated and stored

## Troubleshooting

### Migration script finds 0 instances

- **Cause**: No completed instances in database
- **Solution**: Complete some tasks first, then run migration

### Factors are None after migration

- **Cause**: Missing `expected_relief` or `actual_relief` in JSON
- **Solution**: Check that tasks were initialized with expected relief and completed with actual relief

### Factors not showing in analytics

- **Cause**: Analytics might be using CSV backend or factors not calculated
- **Solution**: 
  1. Verify database backend is being used (check `DATABASE_URL` env var)
  2. Run migration script to backfill factors
  3. Check that `_load_instances()` is loading factors from database

## Summary

- ✅ **Future tasks**: Automatically calculate and store factors (no action needed)
- ✅ **Existing data**: Run migration script once to backfill
- ✅ **Migration script**: Idempotent (safe to run multiple times)
- ✅ **Analytics**: Uses stored factors with automatic fallback
