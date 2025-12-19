# Relief Data Storage Fix

## Problem Identified

All 7 aversion formulas were producing identical results because `expected_relief` and `actual_relief` were always the same. The root cause was a data storage issue where:

1. **Initialization** saves `expected_relief` in the `predicted` JSON
2. **`_update_attributes_from_payload`** was also writing `expected_relief` to the `relief_score` CSV column
3. **Completion** saves `actual_relief` in the `actual` JSON
4. **`_update_attributes_from_payload`** then overwrote the `relief_score` CSV column with `actual_relief`
5. **Analytics** was reading `actual_relief` from the `relief_score` CSV column (which had been overwritten)

This meant that even though `expected_relief` was correctly stored in the `predicted` JSON, the CSV column was being overwritten, and if analytics fell back to the CSV column, it would get the wrong value.

## Fixes Applied

### 1. Fixed `_update_attributes_from_payload` in `instance_manager.py`

**Before:**
```python
'relief_score': ['relief_score', 'actual_relief', 'expected_relief'],
```

**After:**
```python
# relief_score should ONLY come from actual_relief (from completion), never from expected_relief
'relief_score': ['relief_score', 'actual_relief'],
```

**Impact:** `expected_relief` is no longer written to the `relief_score` CSV column. It stays only in the `predicted` JSON.

### 2. Fixed `backfill_attributes_from_json` in `instance_manager.py`

**Before:**
```python
# In predicted section:
'relief_score': ['expected_relief', 'relief_score'],
```

**After:**
```python
# DO NOT map expected_relief to relief_score - relief_score is for actual values only
# 'relief_score': ['expected_relief', 'relief_score'],  # REMOVED
```

**Impact:** Backfill no longer writes `expected_relief` to the `relief_score` CSV column.

### 3. Fixed analytics to read `actual_relief` from `actual_dict`

**Before:**
```python
# Get actual relief from relief_score column (already populated from actual_dict)
completed['actual_relief'] = pd.to_numeric(completed['relief_score'], errors='coerce')
```

**After:**
```python
# Get actual relief from actual_dict (from completion page), not from relief_score column
def _get_actual_relief(row):
    try:
        actual_dict = row['actual_dict']
        if isinstance(actual_dict, dict):
            return actual_dict.get('actual_relief', None)
    except (KeyError, TypeError):
        pass
    # Fallback to relief_score column if actual_dict doesn't have it
    try:
        return row.get('relief_score')
    except (KeyError, TypeError):
        pass
    return None

completed['actual_relief'] = completed.apply(_get_actual_relief, axis=1)
completed['actual_relief'] = pd.to_numeric(completed['actual_relief'], errors='coerce')
```

**Impact:** Analytics now reads `actual_relief` directly from the `actual` JSON (from completion), ensuring it gets the correct value.

### 4. Fixed analytics fallback logic

**Before:**
```python
if column == 'relief_score':
    df[column] = df[column].fillna(df['actual_dict'].apply(lambda r: r.get('actual_relief')))
    df[column] = df[column].fillna(df['predicted_dict'].apply(lambda r: r.get('expected_relief')))
```

**After:**
```python
# IMPORTANT: relief_score should ONLY come from actual_relief, never from expected_relief
if column == 'relief_score':
    df[column] = df[column].fillna(df['actual_dict'].apply(lambda r: r.get('actual_relief')))
    # DO NOT use expected_relief as fallback - relief_score is for actual values only
```

**Impact:** The CSV column `relief_score` will no longer be filled with `expected_relief` as a fallback.

## Data Flow (After Fix)

### Initialization (initialize_task.py)
1. User sets `expected_relief` value
2. Saved to `predicted` JSON: `{"expected_relief": 80, ...}`
3. **NOT** written to `relief_score` CSV column

### Completion (complete_task.py)
1. User sets `actual_relief` value
2. Saved to `actual` JSON: `{"actual_relief": 75, ...}`
3. Written to `relief_score` CSV column (for backward compatibility)
4. **Does NOT** overwrite `expected_relief` in `predicted` JSON

### Analytics (analytics.py)
1. Reads `expected_relief` from `predicted_dict` (from initialization)
2. Reads `actual_relief` from `actual_dict` (from completion)
3. Calculates `net_relief = actual_relief - expected_relief`
4. Formulas now produce different results when `expected_relief ≠ actual_relief`

## Expected Behavior After Fix

- **New tasks:** Will correctly store `expected_relief` in `predicted` JSON and `actual_relief` in `actual` JSON
- **Existing tasks:** May still have identical values if they were completed before the fix
- **Formulas:** Will produce different results once there's variation in expected vs actual relief

## Testing

To verify the fix works:

1. **Create a new task** and initialize it with `expected_relief = 80`
2. **Complete the task** with `actual_relief = 75` (different value)
3. **Check analytics** - formulas should now produce different results:
   - `expected_only`: Uses 80
   - `actual_only`: Uses 75
   - `net_penalty`: Should be higher (bonus for disappointment)
   - `net_bonus`: Should be same as expected_only (no bonus)
   - `net_weighted`: Should be weighted by net_relief = -5

## Files Modified

1. `task_aversion_app/backend/instance_manager.py`
   - `_update_attributes_from_payload()` - Removed `expected_relief` from `relief_score` mapping
   - `backfill_attributes_from_json()` - Removed `expected_relief` from predicted mappings

2. `task_aversion_app/backend/analytics.py`
   - `_load_instances()` - Removed `expected_relief` fallback for `relief_score` column
   - `get_relief_summary()` - Now reads `actual_relief` from `actual_dict` instead of CSV column

## Next Steps

1. ✅ Fix applied to prevent future data mixing
2. ⏳ Existing data may need manual review/correction if needed
3. ⏳ Test with new tasks to verify formulas produce different results

