# Template Cache Refresh Fix

## Problem

When creating a new task template from `/create_task`, the task is created successfully but doesn't appear in the dashboard's "Task Templates" section because:

1. TaskManager cache is invalidated (✅ working)
2. Dashboard UI doesn't refresh when navigating back from `/create_task` (❌ issue)

## Solution

Implemented automatic template refresh when navigating back to dashboard after creating a task:

1. **Set refresh flag** when task is created (`ui/create_task.py`)
2. **Check flag** when dashboard loads (`ui/dashboard.py`)
3. **Force refresh** if flag is set
4. **Clear flag** after refresh

## Implementation Details

### 1. Task Creation (`ui/create_task.py`)

When a task is successfully created:
```python
# Signal dashboard to refresh templates
from nicegui import app
app.storage.general['refresh_templates'] = True
ui.navigate.to('/')
```

### 2. Dashboard Load (`ui/dashboard.py`)

When dashboard loads, check for refresh flag:
```python
# Check if templates need refresh (e.g., after creating a new task)
needs_refresh = app.storage.general.get('refresh_templates', False)
if needs_refresh:
    print("[Dashboard] Templates refresh flag detected, will force refresh after initial load")
    app.storage.general.pop('refresh_templates', None)  # Clear flag
    # Schedule refresh after initial load completes
    def force_refresh_after_load():
        print("[Dashboard] Force refreshing templates after task creation")
        refresh_templates()
    ui.timer(1.0, force_refresh_after_load, once=True)
```

## How It Works

1. User creates task → TaskManager invalidates cache → Flag set in storage
2. User navigates to `/` → Dashboard loads
3. Dashboard checks flag → If set, schedules refresh after 1 second
4. Refresh executes → Templates reload from database (fresh data)
5. Flag cleared → Ready for next task creation

## Cache Invalidation Chain

```
create_task()
  ↓
TaskManager.create_task()
  ↓
_invalidate_task_caches()  ← Clears TaskManager cache
  ↓
Set refresh_templates flag
  ↓
Navigate to dashboard
  ↓
Dashboard checks flag
  ↓
refresh_templates()
  ↓
tm.get_all()  ← Gets fresh data (cache was invalidated)
  ↓
Templates displayed with new task
```

## Testing

1. Create a new task template
2. Navigate back to dashboard
3. **Expected:** New task appears in "Task Templates" section immediately
4. **Verify:** No manual refresh needed

## Related Functions

- `TaskManager._invalidate_task_caches()` - Invalidates TaskManager cache
- `refresh_templates()` - Refreshes dashboard template display
- `app.storage.general['refresh_templates']` - Flag for refresh signal

## Notes

- Flag is stored in `app.storage.general` (server-side, shared across all users)
- Refresh is scheduled with 1 second delay to ensure dashboard container is ready
- Flag is cleared immediately after detection to prevent duplicate refreshes
- Other operations (edit, copy, delete) already call `refresh_templates()` directly
