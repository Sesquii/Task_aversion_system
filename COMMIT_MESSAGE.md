# Commit Message

## Add Task Distribution Analysis Page with Interactive Filters

Add experimental task distribution visualization page showing pie charts for task template completion patterns.

### Features

- **Two pie charts:**
  - Task count distribution: Shows number of instances per task template
  - Time spent distribution: Shows total time (minutes/hours) spent per task template

- **Interactive status filters:**
  - Include Completed (default: enabled)
  - Include Cancelled (default: disabled)
  - Include Initialized (default: disabled)
  - Charts update automatically when filters change
  - Supports any combination of the three statuses

- **Statistics table:**
  - Task template name
  - Instance count and percentage
  - Time spent (hours) and percentage
  - Sortable columns

- **Future jobs system note:**
  - Added informational note explaining that the page will be refined when jobs system is implemented
  - Will support separate charts per job and per-job task breakdowns

### Technical Details

- Works with both CSV and database backends
- Handles instances with different statuses (completed, cancelled, initialized)
- Calculates time from `duration_minutes` field when available
- Gracefully handles missing data and empty states

### Files Changed

- `task_aversion_app/ui/task_distribution.py` - New experimental page
- `task_aversion_app/ui/experimental_landing.py` - Added Task Distribution link
- `task_aversion_app/app.py` - Registered route

### Route

- `/experimental/task-distribution` - Task distribution analysis page
