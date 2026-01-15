# Database Queries Without user_id Filter

This document lists all functions that query the database but do NOT filter by `user_id`. These queries may expose data across users and should be reviewed for security and data isolation.

## Summary

**Total functions found: 20**

## Detailed List

### 1. `backend/csv_export.py`

**Purpose:** Export utility (intentional - exports all data)
- **Function:** `export_all_data_to_csv()`
  - Line 51: `session.query(Task).all()` - No user_id filter
  - Line 70: `session.query(TaskInstance).all()` - No user_id filter
  - Line 92: `session.query(Emotion).all()` - No user_id filter (Emotion table doesn't have user_id)
  - Line 107: `session.query(PopupTrigger).all()` - No user_id filter
  - Line 123: `session.query(PopupResponse).all()` - No user_id filter
  - Line 139: `session.query(Note).all()` - No user_id filter
  - Line 154: `session.query(SurveyResponse).all()` - No user_id filter

**Note:** This is intentional for export functionality, but should be documented.

---

### 2. `backend/notes_manager.py`

**Function:** `get_all_notes()`
- Line 155: `session.query(self.Note).order_by(self.Note.timestamp.desc()).all()` - No user_id filter
- **Issue:** Returns all notes from all users

**Function:** `delete_note()`
- Line 171: `session.query(self.Note).filter(self.Note.note_id == note_id).first()` - No user_id filter
- **Issue:** Can delete notes from any user if note_id is known

**Function:** `_initialize_default_note()`
- Line 106: `session.query(self.Note).count()` - No user_id filter
- **Issue:** Counts all notes, not per-user

---

### 3. `backend/instance_manager.py`

**Function:** `_list_cancelled_instances_db()`
- Line 927-930: Queries `TaskInstance` without user_id filter
- **Issue:** Returns cancelled instances from all users
- **Location:** `backend/instance_manager.py:923`

**Function:** `_get_instance_db()`
- Line 979-981: Queries `TaskInstance` by instance_id without user_id filter
- **Note:** Has post-query user_id verification (line 954-960), but query itself doesn't filter
- **Location:** `backend/instance_manager.py:974`

**Function:** `_backfill_attributes_from_json_db()`
- Line 2302: `session.query(self.TaskInstance).all()` - No user_id filter
- **Issue:** Processes all instances from all users
- **Location:** `backend/instance_manager.py:2302`

**Function:** `_get_previous_actual_averages_db()`
- Line 2677-2680: Queries `TaskInstance` by task_id without user_id filter
- **Issue:** Averages include data from all users for the same task_id
- **Location:** `backend/instance_manager.py:2672`

**Function:** `_get_initial_aversion_db()`
- Line 2787-2790: Queries `TaskInstance` by task_id without user_id filter
- **Issue:** Gets initial aversion from any user's first instance of the task
- **Location:** `backend/instance_manager.py:2780`

**Function:** `_get_previous_aversion_average_db()`
- Line 2929-2932: Queries `TaskInstance` by task_id without user_id filter
- **Issue:** Averages aversion from all users for the same task_id
- **Location:** `backend/instance_manager.py:2924`

**Function:** `_get_baseline_aversion_robust_db()`
- Line 3025-3028: Queries `TaskInstance` by task_id without user_id filter
- **Issue:** Calculates baseline from all users' instances
- **Location:** `backend/instance_manager.py:3019`

**Function:** `_get_batch_baseline_aversions_db()`
- Line 3094-3097: Queries `TaskInstance` for multiple task_ids without user_id filter
- **Issue:** Batch loads baseline aversions from all users
- **Location:** `backend/instance_manager.py:3083`

**Function:** `_get_baseline_aversion_sensitive_db()`
- Line 3292-3295: Queries `TaskInstance` by task_id without user_id filter
- **Issue:** Calculates sensitive baseline from all users' instances
- **Location:** `backend/instance_manager.py:3286`

---

### 4. `backend/task_manager.py`

**Function:** `_update_task_db()`
- Line 525: `session.query(self.Task).filter(self.Task.task_id == task_id).first()` - No user_id filter
- **Issue:** Can update tasks from any user if task_id is known
- **Note:** Method signature accepts `user_id` parameter but doesn't use it in the query
- **Location:** `backend/task_manager.py:521`

---

### 5. `backend/analytics.py`

**Function:** `_load_instances_from_db()` (or similar)
- Line 2658-2663: `session.query(TaskInstance).all()` - No user_id filter (when `completed_only=False`)
- **Issue:** Loads all instances from all users
- **Location:** `backend/analytics.py:2658`

---

### 6. `backend/productivity_tracker.py`

**Function:** `_get_completed_instances()`
- Line 316-319: Queries `TaskInstance` without user_id filter
- **Issue:** Gets completed instances from all users
- **Location:** `backend/productivity_tracker.py:276`

---

### 7. `backend/csv_import.py`

**Purpose:** Import utility (intentional - imports all data)
- **Function:** Various import functions
  - Line 441: `session.query(Task).all()` - No user_id filter
  - Line 677: `session.query(TaskInstance).all()` - No user_id filter
  - Line 916: `session.query(Emotion).all()` - No user_id filter
  - Line 1000: `session.query(Note).all()` - No user_id filter
  - Line 1267: `session.query(SurveyResponse).all()` - No user_id filter

**Note:** This is intentional for import functionality, but should be documented.

---

### 8. `backend/auth.py`

**Function:** `get_or_create_user_from_oauth()`
- Line 307: `session.query(User).filter(User.google_id == google_id).first()` - No user_id filter (but filters by google_id)
- Line 339: `session.query(User).filter(User.email == email).first()` - No user_id filter (but filters by email)
- **Note:** These are user lookup functions, so user_id filter doesn't apply. However, they query the User table which doesn't need user_id filtering.

---

## Functions That DO Filter by user_id (For Reference)

These functions correctly filter by user_id:
- `backend/task_manager.py`: `_get_task_db()`, `_list_tasks_db()`, `_get_all_db()`, `_find_by_name_db()`, `_append_task_notes_db()`, `_get_task_notes_db()`, `_delete_by_id_db()`
- `backend/instance_manager.py`: `_get_instances_by_task_id_db()`, `_list_active_instances_db()`, `_get_previous_task_averages_db()`
- `backend/popup_state.py`: All functions filter by user_id
- `ui/plotly_data_charts.py`: Filters by user_id='default' (hardcoded)

---

## Recommendations

1. **High Priority (Security Risk):**
   - `notes_manager.py`: `get_all_notes()`, `delete_note()`
   - `instance_manager.py`: `_list_cancelled_instances_db()`, `_get_instance_db()` (add filter before query)
   - `task_manager.py`: `_update_task_db()` (add user_id filter)

2. **Medium Priority (Data Isolation):**
   - `instance_manager.py`: All baseline/aversion calculation methods should filter by user_id
   - `analytics.py`: `_load_instances_from_db()` should filter by user_id
   - `productivity_tracker.py`: `_get_completed_instances()` should filter by user_id

3. **Low Priority (Documentation):**
   - `csv_export.py`: Document that export intentionally includes all users
   - `csv_import.py`: Document that import intentionally includes all users

---

## Notes

- Some functions accept `user_id` as a parameter but don't use it in the query (e.g., `_update_task_db()`)
- Some functions have post-query user_id verification but should filter at query time for better security
- Export/import utilities are intentionally querying all data, but this should be clearly documented
- Emotion table doesn't have user_id (it's a shared reference table), so queries are acceptable
