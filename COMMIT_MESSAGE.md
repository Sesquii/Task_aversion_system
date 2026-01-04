# Commit Message

## Add Debugging Logs for Manual Metric Reset Issue

Added comprehensive debugging instrumentation to investigate why the manual metric reset feature (right-click context menu) is not persisting. The reset function successfully sets the value to 0.0, but it gets immediately overwritten by automatic metric updates. Issue persists and will be addressed in a future session.

### Issue Description

The manual reset feature for the "8 hour idle productivity score" metric was implemented with a right-click context menu option. When triggered, the reset function correctly sets the metric value to 0.0, but the value is immediately overwritten by `_update_metric_cards_incremental`, which recalculates the metric from the data source.

### Debugging Logs Added

- **`reset_metric_score()` function (`dashboard.py`):**
  - Logs function entry with metric_key parameter
  - Logs metric_cards state check (available keys, whether metric exists)
  - Logs card_info retrieval (whether card_info exists, available keys, value_label presence)
  - Logs value_label state before update (current value, available methods, widget type)
  - Logs value_label state after update (update method used, new value, target value)
  - Logs manually_reset flag status

- **`_update_metric_cards_incremental()` function (`dashboard.py`):**
  - Logs when update is skipped due to manually_reset flag
  - All logs use `hypothesisId: 'RESET_SCORE'` or `'UPDATE'` for easy filtering

### Attempted Fix

Implemented a `manually_reset` flag mechanism:
- Added `manually_reset: False` to metric card state initialization
- Set flag to `True` when reset is called
- Added check in `_update_metric_cards_incremental` to skip updates if flag is set
- Flag prevents automatic recalculation from overwriting manually reset values

**Status:** Fix attempted but issue persists. Further investigation needed to identify what triggers the immediate update after reset.

### Files Changed

- `task_aversion_app/ui/dashboard.py`:
  - Added comprehensive logging to `reset_metric_score()` function
  - Added `manually_reset` flag to metric card state
  - Added skip logic in `_update_metric_cards_incremental()` to respect reset flag
  - Added logging for skip events

### Next Steps

- Investigate what triggers `process_next_step` immediately after reset (logs show it runs ~1ms after reset)
- Consider alternative approaches: disable periodic refresh timer, use different state management, or implement reset at data source level
- Review NiceGUI event system to understand UI update triggers
- Analyze timing between reset and automatic update to identify root cause

### Log Analysis

Logs show:
1. Reset function successfully updates value to "0.0" (confirmed in logs)
2. `process_next_step` is triggered immediately after (~1ms later)
3. `_update_metric_cards_incremental` recalculates and overwrites the reset value
4. The manually_reset flag skip logic should prevent this, but issue persists

### Debug Log Location

All debugging logs are written to: `c:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system\.cursor\debug.log`

Filter logs using: `grep "RESET_SCORE\|UPDATE" .cursor/debug.log`
