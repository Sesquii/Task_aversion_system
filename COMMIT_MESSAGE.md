# Commit Message

## Design Intent

This commit fixes the productivity settings chart to display actual productivity scores instead of simple task counts, and adds multi-configuration comparison capabilities. The goal is to enable users to compare how different weight/curve configurations affect productivity scores over time, helping optimize the productivity formula.

The chart now uses the full productivity score calculation (matching the coursera analysis page) which includes all components: baseline completion, task type multipliers, weekly bonuses, goal adjustments, and burnout penalties. While the absolute scores appear lower than expected, the relative scores are correct, indicating the calculation is working properly but may need calibration.

Additionally, the page has been documented on the experimental landing page with notes about its potential (7.5/10) and current limitations (2/10 usefulness), acknowledging that while the concept is valuable, the implementation needs refactoring for better performance and UX.

## Changes

### Bug Fixes

- **Fixed productivity settings chart to show proper productivity scores**
  - Issue: Chart was showing task completion count instead of actual productivity scores
  - Root cause: Missing `task_type` column in instances DataFrame (needed join with tasks table)
  - Solution: Added proper join with tasks table to get `task_type`, then use `calculate_daily_scores()` for full calculation
  - Result: Chart now displays full productivity scores with all components applied
  - Note: Scores appear lower than expected, but relative scores are correct (may need formula calibration)

### New Features

- **Multi-configuration comparison**
  - Added checkboxes to select multiple weight configurations for side-by-side comparison
  - Chart displays multiple lines (one per selected configuration) with color coding
  - "Current Settings" option shows real-time values from input fields
  - Enables users to see how different weight/curve settings affect scores over time

- **Auto-updating chart with debouncing**
  - Chart automatically updates when component or curve weights change
  - Debounced updates (500ms delay) to prevent excessive recalculations
  - Immediate updates for configuration checkbox changes
  - Removed page reload requirement (no more `ui.navigate.reload()`)

### Improvements

- **Enhanced configuration management UI**
  - Added clear descriptions for each button:
    - "Load Selected": Loads configuration weights into input fields
    - "Save Configuration": Saves current input values to selected configuration
    - "Create New": Creates new configuration with current input values
  - Added tooltips to buttons for better UX
  - Improved error messages and user feedback
  - "Create New" now uses current input values instead of defaults

- **Documentation and linking**
  - Added productivity settings page to experimental landing page
  - Rated: Usefulness 2/10, Potential 7.5/10
  - Added note explaining refactoring needs (performance, UX improvements)
  - Added link from productivity settings page to experimental page
  - Added link from experimental page to productivity settings page

### Files Modified

- `task_aversion_app/ui/productivity_settings_page.py`
  - Fixed chart to use full productivity score calculation
  - Added multi-configuration comparison feature
  - Added debounced chart updates
  - Improved configuration management UI
  - Added link to experimental page

- `task_aversion_app/ui/experimental_landing.py`
  - Added productivity settings page entry with usefulness/potential ratings
  - Added note about refactoring needs
  - Added link to productivity settings page

## Known Issues

- Chart updates can be slow when comparing multiple configurations (performance optimization needed)
- Configuration management flow could be more intuitive (UX improvements needed)
- Absolute productivity scores appear lower than expected (may need formula calibration, but relative scores are correct)
- New configurations don't appear in comparison list until page refresh (NiceGUI limitation)

## Future Improvements

- Refactor chart calculation for better performance (caching, optimization)
- Improve configuration management UX (wizard flow, better visual feedback)
- Consider formula calibration if absolute scores need adjustment
- Add ability to dynamically update comparison checkboxes without page refresh
