feat: Enhance Productivity Hours Goal Tracking with rolling 7-day mode and daily trends

Promote Productivity Hours Goal Tracking from experimental to production and add
significant improvements:

**New Features:**
- Rolling 7-day calculation mode (default): Tracks last 7 days continuously
  without weekly resets for more fluid productivity tracking
- Monday-based week mode with pace projection: Optional mode that projects
  weekly totals based on current daily pace, preventing early-week bias
- Daily trend visualization: Replaced weekly graphs with daily data showing
  last 90 days of productivity hours with 7-day rolling average overlay
- Week calculation mode selector: User preference to switch between rolling
  and Monday-based modes with persistence via user_state

**Backend Changes:**
- Added `calculate_rolling_7day_productivity_hours()` method to ProductivityTracker
- Added `calculate_monday_week_pace()` method for pace projection calculations
- Refactored `_calculate_productivity_hours_in_range()` helper method for code reuse
- Added `get_current_week_performance()` method with mode selection support
- Updated `compare_to_goal()` to support both calculation modes
- Added `get_daily_productivity_data()` method for daily trend data
- Added `week_calculation_mode` setting to user_state (defaults to 'rolling')

**UI Changes:**
- Changed route from /experimental/productivity-hours-goal-tracking-system to
  /goals/productivity-hours (production route under goals section)
- Added /goals landing page for goal tracking features
- Added Goals navigation button to dashboard header (top right navigation)
- Added calculation mode selector with UI toggle
- Enhanced current week display with mode-specific information and pace data
- Replaced weekly history graphs with daily trend charts (90-day window)
- Added 7-day rolling average overlay to productivity metrics trend chart
- Updated page title and descriptions to remove "experimental" labeling

**Documentation:**
- Removed from experimental landing page (promoted to production)
- Updated route references throughout codebase

**Breaking Changes:**
- Route changed: /experimental/productivity-hours-goal-tracking-system ->
  /goals/productivity-hours (update bookmarks/links if needed)

Files changed:
- backend/productivity_tracker.py
- backend/user_state.py
- ui/productivity_goals_experimental.py (route updated)
- ui/goals_page.py (new goals landing page)
- ui/experimental_landing.py
- app.py

