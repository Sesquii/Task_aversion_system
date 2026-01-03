# Add Search Bar to Initialized Tasks

## Summary
Added search functionality to the initialized tasks section in the dashboard. Users can now search for initialized tasks by task name, description, task notes, and pause notes. The search bar uses debounced input (300ms delay) to prevent excessive filtering during typing.

## Changes

### Dashboard (dashboard.py)
- **New function**: `refresh_initialized_tasks(search_query=None)`
  - Filters initialized tasks by task name, description, task notes, and pause notes
  - Re-renders filtered tasks in 2-column layout
  - Handles empty states with appropriate messages
  - Includes retry logic if containers aren't ready

- **Search bar UI component**:
  - Added search input for initialized tasks with debounced event handling
  - Uses 300ms debounce timer to reduce refresh frequency during typing
  - Search handler checks container existence before executing

- **Global state management**:
  - Added `initialized_tasks_container` global variable for container reference
  - Added `initialized_search_input_ref` global variable for search input reference
  - Container is created synchronously before refresh calls

## Technical Details

### Search Functionality
- **Initialized Tasks Search**:
  - Searches in: task name, description, task-level notes, pause notes
  - Case-insensitive substring matching
  - Updates in real-time with 300ms debounce

### Implementation Pattern
- Follows same pattern as existing task templates search and recommendation system search
- Uses debounced `update:model-value` events to prevent refresh on every keystroke
- Handlers are attached immediately after input creation to ensure proper binding
- Includes error handling and retry logic for edge cases

## Known Issues
- **Initial Load Bug**: Search bar may not work correctly on the first page load due to multiple page re-renders during initialization. The page renders multiple times (likely due to monitored metrics section), creating new UI elements each time. While handlers are attached immediately to the current inputs, there may still be timing issues where the final rendered inputs don't have handlers attached. Manual page refresh resolves the issue and search bar works correctly after refresh.

## Testing
- Verified search works correctly after manual page refresh
- Verified search filters initialized tasks by name, description, notes, and pause notes
- Verified debouncing prevents excessive refreshes during typing
- Verified empty states display correctly when no matches found
