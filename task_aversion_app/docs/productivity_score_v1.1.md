# Productivity Score Formula v1.1

**Version:** 1.1  
**Date:** 2025-12-27  
**Status:** ✅ Current

## Overview

The Productivity Score measures productive output based on task completion, task type, and efficiency. This version introduces a major improvement to the efficiency calculation that accounts for both completion percentage and time relative to the task's own estimate.

## Formula Components

### 1. Baseline Completion Score
- **Base score** = `completion_percentage` (0-100, can exceed 100% for over-completion)

### 2. Task Type Multipliers
- **Work tasks:** 3.0x to 5.0x (smooth transition based on completion_time_ratio)
- **Self care tasks:** 1.0x to Nx (where N = number of self care tasks completed that day)
- **Play tasks:** 0.5x (or negative penalty if play exceeds work by threshold)

### 3. Efficiency Multiplier (v1.1 - NEW)

**Purpose:** Adjusts score based on efficiency, accounting for both completion percentage and time.

**Formula:**
```python
# Calculate completion_time_ratio
completion_time_ratio = (completion_pct * time_estimate) / (100.0 * time_actual)

# Efficiency ratio = completion_time_ratio
efficiency_ratio = completion_time_ratio

# Convert to percentage difference from perfect efficiency (1.0)
efficiency_percentage_diff = (efficiency_ratio - 1.0) * 100.0

# Calculate multiplier based on curve type
if curve_type == 'flattened_square':
    effect = copysign((abs(efficiency_percentage_diff) ** 2) / 100.0, efficiency_percentage_diff)
    efficiency_multiplier = 1.0 - (0.01 * strength * effect)
else:  # linear
    efficiency_multiplier = 1.0 - (0.01 * strength * -efficiency_percentage_diff)

# Cap penalty at 50% reduction (minimum multiplier = 0.5)
efficiency_multiplier = max(0.5, efficiency_multiplier)
```

**Key Features:**
- ✅ **Compares to task's own estimate** (not weekly average across all tasks)
- ✅ **Accounts for completion percentage** - if you take 2x longer but complete 200%, efficiency ratio = 1.0 (no penalty)
- ✅ **Capped penalty and bonus** - Maximum 50% reduction (min 0.5x) and 50% increase (max 1.5x) to prevent extreme scores
- ✅ **Work multiplier also capped** - completion_time_ratio capped at 1.5 for work multiplier calculation (prevents extreme multipliers from very fast completions)
- ✅ **Supports both linear and flattened_square curve types**

**Examples:**
- Task estimated at 20 min, takes 20 min, 100% complete → ratio = 1.0 → multiplier = 1.0 (no change)
- Task estimated at 20 min, takes 40 min, 200% complete → ratio = 1.0 → multiplier = 1.0 (no penalty!)
- Task estimated at 20 min, takes 40 min, 100% complete → ratio = 0.5 → multiplier = 0.5 (50% penalty, capped)
- Task estimated at 20 min, takes 10 min, 100% complete → ratio = 2.0 → multiplier = 1.5 (50% bonus)

### 4. Goal-Based Adjustment (Optional)
- Adjusts score based on weekly goal achievement
- ±20% max adjustment based on goal completion ratio

### 5. Burnout Penalty (Optional)
- Applies when weekly work exceeds threshold AND daily work exceeds cap
- Exponential decay penalty, capped at 50% reduction

## Version History

### v1.1 (2025-12-27) - Efficiency Calculation Fix

**Changes:**
1. **Fixed efficiency comparison:** Changed from comparing to weekly average time to comparing to task's own estimate
2. **Added completion percentage accounting:** Efficiency now uses `completion_time_ratio` which accounts for both completion % and time
3. **Added penalty and bonus caps:** Maximum 50% reduction (min 0.5x) and 50% increase (max 1.5x) to prevent extreme scores
4. **Capped work multiplier calculation:** completion_time_ratio capped at 1.5 for work multiplier to prevent extreme multipliers from very fast completions
5. **Improved accuracy:** Tasks that take longer but complete more are no longer unfairly penalized

**Rationale:**
The previous version compared actual time to a weekly average across all tasks, which was problematic because:
- Different tasks have different expected durations (a 5-minute task vs a 2-hour task)
- Tasks that took longer than the weekly average got massive penalties, even if they matched their own estimate
- The calculation didn't account for completion percentage (taking 2x longer but completing 200% should be efficient, not penalized)

**Impact:**
- Productivity scores are now more accurate and fair
- Tasks are evaluated against their own estimates, not arbitrary averages
- Completion percentage is properly accounted for in efficiency calculations
- Negative scores from efficiency penalties are prevented (capped at 50% reduction)

### v1.0 (Previous)
- Initial implementation
- Compared actual time to weekly average (removed in v1.1)
- Did not account for completion percentage in efficiency calculation

## Implementation

**Location:** `backend/analytics.py:453-698`

**Key Function:**
```python
def calculate_productivity_score(
    row: pd.Series,
    self_care_tasks_per_day: Dict[str, int],
    weekly_avg_time: float = 0.0,  # Deprecated, kept for backward compatibility
    work_play_time_per_day: Optional[Dict[str, Dict[str, float]]] = None,
    play_penalty_threshold: float = 2.0,
    productivity_settings: Optional[Dict[str, any]] = None,
    weekly_work_summary: Optional[Dict[str, float]] = None,
    goal_hours_per_week: Optional[float] = None,
    weekly_productive_hours: Optional[float] = None
) -> float
```

**Note:** The `weekly_avg_time` parameter is kept for backward compatibility but is no longer used in the efficiency calculation. The efficiency multiplier now uses the task's own `time_estimate` from the `predicted_dict`.

## Related Documentation

- `docs/formula_review_analysis.md` - Comprehensive formula review and analysis
- `docs/composite_score_system.md` - How productivity score integrates with other scores
- `ui/analytics_glossary.py` - UI documentation for productivity score components

## Testing

Use the debug script to verify productivity scores:
```bash
python task_aversion_app/debug_productivity_scores.py
```

This script shows:
- Individual task productivity scores
- Breakdown by completed vs cancelled tasks
- Recent tasks (last 7 days)
- Top positive and negative scoring tasks
