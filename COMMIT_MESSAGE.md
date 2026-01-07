# Fix Cache Invalidation Issues and Improve Pause/Resume Functionality

## Summary
Fixed critical cache invalidation timing issues that caused completed and cancelled tasks to persist in the UI, and improved pause/resume functionality to preserve duration data. Implemented shared cache across all InstanceManager instances to ensure consistency.

## Changes Made

### Cache Invalidation Fixes
- **Moved cache invalidation to after database commits**: Cache was being invalidated before data was written, causing stale data to be cached. Now invalidates after commits complete.
- **Implemented shared class-level cache**: Each UI module was creating its own InstanceManager instance with separate caches, causing inconsistencies. Changed to class-level shared cache so all instances see the same data.
- **Fixed cache invalidation for all write operations**: 
  - `complete_instance` - invalidates after completion
  - `cancel_instance` - invalidates after cancellation  
  - `delete_instance` - invalidates after deletion
  - `pause_instance` - invalidates after pausing
  - `resume_instance` - invalidates after resuming
  - `start_instance` - invalidates after starting

### Pause/Resume Improvements
- **Preserved duration data across pause/resume cycles**: `time_spent_before_pause` is now properly maintained and accumulated across multiple pause/resume cycles.
- **Added cache invalidation to pause/resume operations**: Ensures duration data is immediately available after resuming.
- **Fixed UI refresh timing**: Added small delay before page reload to ensure cache invalidation completes before UI updates.

### Code Quality
- **Removed duplicate `resume_instance` function** in dashboard.py
- **Consistent cache invalidation pattern**: All database write operations now invalidate cache outside session context for reliability

## Issues Fixed
- ✅ Completed tasks now immediately removed from active tasks list
- ✅ Cancelled tasks now immediately removed from active tasks list  
- ✅ Duration data (`time_spent_before_pause`) preserved and displayed correctly after resume
- ✅ All UI modules now see consistent, up-to-date data

## Known Issues
- ⚠️ Pause functionality is still inconsistent - may need further investigation and testing

## Technical Details

### Shared Cache Implementation
- Changed instance-level cache variables to class-level:
  - `self._active_instances_cache` → `InstanceManager._shared_active_instances_cache`
  - `self._recent_completed_cache` → `InstanceManager._shared_recent_completed_cache`
- Updated `_invalidate_instance_caches()` to clear shared cache
- Updated `list_active_instances()` and `list_recently_completed()` to use shared cache

### Cache Invalidation Timing
- Moved invalidation outside database session contexts in:
  - `_complete_instance_db()`
  - `_cancel_instance_db()`
  - `_pause_instance_db()`
  - `_resume_instance_db()`
  - `_delete_instance_db()`
- Ensures cache is cleared after transaction commits and session closes

## Files Modified
- `task_aversion_app/backend/instance_manager.py` - Shared cache implementation and cache invalidation fixes
- `task_aversion_app/ui/dashboard.py` - Removed duplicate function, improved resume timing
- `task_aversion_app/ui/cancel_task.py` - Navigation improvements

## Testing Recommendations
- Test completing tasks and verify they disappear from active list immediately
- Test cancelling tasks and verify they disappear from active list immediately
- Test pausing and resuming tasks multiple times and verify duration accumulates correctly
- Test pause functionality for consistency issues
