# Commit Message

## Design Intent

This commit adds two new experimental analysis tools to provide data-driven insights into task patterns and productivity tradeoffs. The goal is to help users understand their actual behavior patterns rather than relying on assumptions, enabling more informed decision-making about task prioritization and time allocation.

The Coursera Analysis tool directly addresses the user's need to understand how specific tasks (like Coursera) impact overall productivity metrics, while the Productivity vs Grit Tradeoff tool explores the relationship between efficiency-focused metrics and persistence-focused metrics across all tasks. Both tools use existing analytics calculations to provide concrete, visual comparisons that can challenge or confirm user assumptions about their work patterns.

Additionally, usefulness ratings have been added to all experimental features to provide transparency about which features are most valuable based on actual usage patterns, helping users prioritize which experimental tools to explore.

## Changes

### New Features

- **Coursera Analysis (`/experimental/coursera-analysis`)**
  - Compare productivity scores on days with vs without Coursera
  - Analyze time spent on Coursera and track completion patterns
  - Visual charts showing productivity trends and Coursera time distribution
  - Detailed instance list with metrics
  - Usefulness rating: 9/10

- **Productivity vs Grit Tradeoff Analysis (`/experimental/productivity-grit-tradeoff`)**
  - Scatter plot visualization of productivity vs grit scores across all tasks
  - Quadrant analysis (High Both, High Prod/Low Grit, Low Prod/High Grit, Low Both)
  - Correlation analysis between efficiency and persistence metrics
  - Task categorization and sorting by productivity/grit differences
  - Usefulness rating: 6/10

### Bug Fixes

- Fixed pandas indexing error in `calculate_daily_scores()` method
  - Issue: Boolean Series indexing misalignment when using `DataFrame.get()` with default values
  - Solution: Changed to direct column access with proper index alignment checks
  - Affects both `self_care_per_day` and `work_play_time` calculations

### Improvements

- Updated experimental landing page with usefulness ratings for all features
  - Formula Baseline Charts: 0/10 (with note about implementation vs concept)
  - Formula Control System: 4/10
  - Coursera Analysis: 9/10
  - Productivity vs Grit Tradeoff: 6/10

### Files Modified

- `task_aversion_app/ui/coursera_analysis.py` (new)
- `task_aversion_app/ui/productivity_grit_tradeoff.py` (new)
- `task_aversion_app/ui/experimental_landing.py` (updated)
- `task_aversion_app/app.py` (updated - registered new pages)
- `task_aversion_app/backend/analytics.py` (bug fix)
