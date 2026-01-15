# Optimize Monitored Metrics: Fix Cache, Baseline, and Graph Loading Issues

## Summary
Fixed critical issues in the monitored metrics system where productivity score was stale until visiting the analytics page, baseline averages were identical to main values, graphs weren't loading, and zero values appeared incorrectly. Implemented proper cache invalidation, improved baseline calculations, and fixed tooltip chart rendering.

## Changes Made

### Cache Invalidation Fixes
- **Added `_invalidate_relief_summary_cache()` static method**: Allows explicit cache invalidation when productivity calculations need refresh
- **Auto-invalidate cache when analytics page loads trends**: When `get_attribute_trends()` calculates `productivity_score` for trends, it now invalidates the relief_summary cache to ensure fresh data
- **Force cache refresh in monitored metrics**: When loading `productivity_score` in monitored metrics, the cache is now invalidated before fetching data to prevent stale values
- **Validate and fix zero values**: Added detection for when `productivity_score` is zero but shouldn't be, forcing cache invalidation and recalculation

### Baseline Calculation Improvements
- **Enhanced baseline calculation logic**: Improved handling of empty or invalid history data with proper fallback logic
- **Calculate baseline from actual values**: When standard baseline calculation returns zero, now calculates from actual history values instead of defaulting to current value
- **Prevent identical averages**: Fixed issue where baseline averages were identical to main values by properly validating history data before using it

### Graph Loading Fixes
- **Fixed tooltip chart rendering**: Changed from HTML string injection to proper Plotly rendering in temporary hidden container
- **Added proper timing for chart initialization**: Charts now render with 500ms delay to ensure Plotly has time to initialize before moving to tooltip
- **Improved JavaScript chart movement**: Updated chart movement logic to properly find and move Plotly chart elements

### Data Refresh Improvements
- **Removed stale cache reliance**: Monitored metrics no longer rely on potentially stale cache for `productivity_score`
- **Always fetch fresh data for productivity_score**: Changed `get_targeted_metric_values()` to always call `get_relief_summary()` for productivity_score instead of trying to use cache
- **Cache invalidation on final render**: Added cache invalidation check in final render step to ensure fresh data

## Issues Fixed
- ✅ Productivity score now updates correctly without visiting analytics page
- ✅ Baseline averages are calculated correctly from history data (not identical to main values)
- ✅ Graphs now load properly in tooltips
- ✅ Zero values only appear when there's actually no data
- ✅ Monitored metrics refresh correctly when data changes

## Technical Details

### Cache Invalidation Implementation
- Added static method `Analytics._invalidate_relief_summary_cache()` to clear class-level cache
- Cache is invalidated in `get_attribute_trends()` when calculating `productivity_score` for trends
- Cache is invalidated before loading `productivity_score` in monitored metrics
- Cache is validated and refreshed if zero value detected when data should exist

### Baseline Calculation Logic
- Enhanced `get_baseline_value()` usage with proper validation
- Added fallback to calculate from actual history values when standard method fails
- Validates that value_key exists and has data before using baseline calculation
- Filters out zeros when calculating baseline from history values

### Chart Rendering Improvements
- Changed from `fig.to_html()` string injection to `ui.plotly()` rendering
- Creates temporary hidden container for chart initialization
- Uses JavaScript with timeout to move chart after Plotly renders
- Properly finds Plotly chart elements using querySelector

## Files Modified
- `task_aversion_app/backend/analytics.py` - Added cache invalidation method and trigger in get_attribute_trends
- `task_aversion_app/ui/dashboard.py` - Fixed cache refresh, baseline calculation, graph loading, and zero value handling

## Testing Recommendations
- Test productivity score updates immediately after completing tasks without visiting analytics page
- Test baseline averages show correct historical averages (not identical to current value)
- Test tooltip graphs load and display correctly when hovering over monitored metrics
- Test zero values only appear when there's actually no data
- Test navigating to analytics page and back - productivity score should remain correct
