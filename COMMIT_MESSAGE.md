# Add Daily Productivity Score with 8-Hour Idle Refresh to Monitored Metrics

## Summary
Added a new productivity metric that calculates daily productivity scores with an 8-hour idle time refresh mechanism. The metric accumulates scores throughout the day but resets after 8 hours of idle time (no task completions). This metric is now available in both the Analytics page and the Dashboard's Monitored Metrics section.

## Changes

### Backend (analytics.py)
- **New method**: `calculate_daily_productivity_score_with_idle_refresh()`
  - Calculates rolling daily productivity score that resets after 8 hours of idle time
  - For current day: Looks back to find the last 8-hour idle period and accumulates scores from that point forward
  - For historical dates: Calculates full day's score with idle refresh logic
  - Returns daily score, segments, segment count, and total tasks

- **Integration**: Added handling in `get_attribute_trends()` for `daily_productivity_score_idle_refresh`
  - Supports trend visualization in Analytics page
  - Handles both current day (rolling calculation) and historical dates

### Frontend (analytics_page.py)
- **Added to CALCULATED_METRICS**: `'Daily Productivity Score (8h Idle Refresh)'`
  - Available for selection in Analytics trends
  - Can be aggregated (sum, mean, etc.) for trend analysis

### Dashboard (dashboard.py)
- **Special handling**: Added on-demand calculation for `daily_productivity_score_idle_refresh` in monitored metrics
  - Calculates current value using `calculate_daily_productivity_score_with_idle_refresh()`
  - Retrieves historical data using `get_attribute_trends()`
  - Displays in monitored metrics cards with tooltip charts

- **Documentation**: Added comprehensive comments explaining the special handling pattern
  - Documents why special handling is needed (metrics not in standard dictionaries)
  - Provides guidance for adding similar special handling for other metrics
  - Includes examples and step-by-step instructions

## Technical Details

### How It Works
1. **Current Day Calculation**:
   - Finds the most recent task completion
   - If >8 hours since last completion, returns 0 (new segment starting)
   - Otherwise, looks backwards to find the last 8-hour idle gap
   - Includes all tasks from after that gap up to current time

2. **Historical Dates**:
   - Calculates full day's score with idle refresh logic
   - Groups tasks into segments based on 8-hour gaps
   - Sums scores across all segments for the day

3. **Integration**:
   - Available in Analytics trends (selectable in dropdown)
   - Available in Monitored Metrics (selectable in configuration dialog)
   - Both use the same calculation logic for consistency

## Benefits
- Provides a productivity metric that accounts for work patterns and idle time
- Encourages consistent daily productivity by resetting after extended breaks
- Extensible pattern for adding other calculated metrics to monitored metrics section

## Testing
- Verified metric appears in Analytics page trends
- Verified metric appears in Monitored Metrics configuration
- Verified metric calculates and displays correctly in dashboard
- Verified historical data displays in tooltip charts
