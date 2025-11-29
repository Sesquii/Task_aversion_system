# Data Consolidation & Fix Summary

## Problem
- Data was being stored in JSON strings (`predicted`, `actual` columns) but not extracted to individual CSV columns
- Missing values in columns like `relief_score`, `cognitive_load`, `emotional_load`, etc. even though data existed in JSON
- Data split across multiple files making it hard to track

## Solution
Consolidated to **one main file**: `task_instances.csv` which contains all raw data and is mapped to analytics inputs.

## Changes Made

### 1. Fixed Data Extraction (`instance_manager.py`)
- **`_update_attributes_from_payload()`**: Now properly maps JSON keys to CSV columns:
  - `actual_relief` → `relief_score`
  - `actual_cognitive` → `cognitive_load`
  - `actual_emotional` → `emotional_load`
  - `time_actual_minutes` → `duration_minutes`
  - And similar mappings for predicted values

- **`complete_instance()`**: Now extracts and populates all columns from the `actual` JSON payload
- **`add_prediction_to_instance()`**: Now extracts predicted values to columns

### 2. Data Backfill (`instance_manager.py`)
- Added `backfill_attributes_from_json()` method to migrate existing data
- Extracts values from JSON strings and populates empty columns
- Run with: `python -m backend.migrate_data` or `python run_backfill.py`

### 3. Updated Analytics (`analytics.py`)
- Enhanced to extract `emotional_load` and `duration_minutes` from JSON if columns are empty
- Analytics now properly handles both CSV columns and JSON fallback

## File Structure

### Main Data File
- **`task_instances.csv`**: Primary data file containing all task instance data
  - Raw JSON in `predicted` and `actual` columns (for flexibility)
  - Extracted values in individual columns (for analytics)
  - All timestamps, scores, and attributes

### Supporting Files
- **`tasks.csv`**: Task definitions/templates (keep)
- **`emotions.csv`**: Emotion list for UI (keep - used by EmotionManager)
- **`logs.csv`**: Deprecated old format (can be removed if not needed)

## Running the Migration

To backfill existing data:

```bash
cd task_aversion_app
python run_backfill.py
```

Or:

```bash
python -m backend.migrate_data
```

This will:
1. Read all instances from `task_instances.csv`
2. Extract values from JSON in `predicted` and `actual` columns
3. Populate empty attribute columns
4. Save the updated CSV

## Future Data Entry

Going forward, when you:
- **Initialize a task**: Values are extracted from `predicted` JSON to columns
- **Complete a task**: Values are extracted from `actual` JSON to columns

All data flows through `task_instances.csv` as the single source of truth.

## Notes

- The JSON columns (`predicted`, `actual`) are kept for raw data storage
- Individual columns are populated for easy analytics and filtering
- Analytics automatically falls back to JSON if columns are empty (backward compatible)
- `emotions.csv` is still used by the UI for emotion selection, so keep it

