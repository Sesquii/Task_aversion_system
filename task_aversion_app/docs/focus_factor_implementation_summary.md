# Focus Factor Implementation Summary

## Overview

The focus factor has been implemented as a new component of the execution score calculation. It measures sustained attention and task engagement through three key indicators:

1. **Task Clustering** (40% weight): Completing multiple tasks with little idle time
2. **Emotion-Based Indicators** (20% weight): Focus-positive vs focus-negative emotions
3. **Task Template Repetition** (40% weight): Completing same template multiple times + general volume

## Implementation Details

### Method: `calculate_focus_factor()`

**Location:** `backend/analytics.py`

**Parameters:**
- `row`: Task instance row (pandas Series or dict)
- `lookback_hours`: Hours to look back for task clustering (default: 24)
- `repetition_days`: Days to look back for repetition counting (default: 7)

**Returns:** Focus factor (0.0-1.0), where:
- 1.0 = High focus (sustained attention, focused emotions, repeated practice)
- 0.5 = Neutral (baseline, no strong indicators)
- 0.0 = Low focus (long gaps, distracted emotions, first-time tasks)

### Integration into Execution Score

The focus factor is integrated into the execution score formula as:

```python
focus_factor = self.calculate_focus_factor(row)
focus_factor_scaled = 0.5 + focus_factor * 0.5  # Scale to 0.5-1.0 range

execution_score = base_score * (
    (1.0 + difficulty_factor) *
    (0.5 + speed_factor * 0.5) *
    (0.5 + start_speed_factor * 0.5) *
    completion_factor *
    focus_factor_scaled  # NEW: Focus boost
)
```

**Current Formula Version:** 1.1 (updated from 1.0)

## Component Details

### 1. Task Clustering Score

**Purpose:** Rewards completing multiple tasks with little idle time between them.

**Calculation:**
- Looks at recent task completions within last 24 hours
- Calculates average gap between completions
- Shorter gaps = higher score

**Scoring:**
- ≤15 min gap: 1.0 (perfect)
- 15-60 min gap: 1.0 → 0.5 (linear)
- 60-240 min gap: 0.5 → 0.25 (exponential decay)
- >240 min gap: 0.1 (floor)

**Weight:** 40% of focus factor

### 2. Emotion-Based Focus Score

**Purpose:** Detects focus-positive vs focus-negative emotions.

**Focus-Positive Emotions:**
- "focused", "concentrated", "determined", "engaged", "flow", "in the zone", 
  "present", "mindful", "attentive", "alert", "sharp"

**Focus-Negative Emotions:**
- "distracted", "scattered", "overwhelmed", "frazzled", "unfocused", 
  "disengaged", "zoned out", "spaced out"

**Calculation:**
- Extracts `emotion_values` from actual or predicted dictionaries
- Sums positive emotion values (normalized 0-100)
- Sums negative emotion values (normalized 0-100)
- Net score: `0.5 + (positive - negative) * 0.5`

**Weight:** 20% of focus factor

### 3. Task Template Repetition Score

**Purpose:** Rewards repeated practice of same task template and general task completion volume.

**Components:**
- **Template Score (60%):** Counts completions of same task template in last 7 days
  - 1 completion: 0.5 (neutral)
  - 2-5 completions: 0.5 → 0.8 (linear)
  - 6-10 completions: 0.8 → 1.0 (linear)
  - 10+ completions: 1.0 (max)

- **Volume Score (40%):** Counts total task completions in last 7 days
  - 1 completion: 0.5 (neutral)
  - 2-10 completions: 0.5 → 0.8 (linear)
  - 11-20 completions: 0.8 → 1.0 (linear)
  - 20+ completions: 1.0 (max)

**Combined:** `template_score * 0.6 + volume_score * 0.4`

**Weight:** 40% of focus factor

## Formula Structure Discussion

### Current Implementation

The focus factor has been added to the **existing formula structure**:

```python
execution_score = base_score * (1.0 + difficulty_factor) * 
                  (0.5 + speed_factor * 0.5) * 
                  (0.5 + start_speed_factor * 0.5) * 
                  completion_factor *
                  (0.5 + focus_factor * 0.5)
```

### Proposed Alternative Structure

You mentioned wanting to change to:

```python
execution_score = base_score * difficulty_factor * speed_factor * 
                  thoroughness_factor * focus_factor
```

**Key Differences:**
1. **Simpler multiplicative model:** All factors are direct multipliers (0.0-1.0 or similar)
2. **No additive offsets:** Removes `(1.0 + difficulty_factor)` pattern
3. **Thoroughness factor:** Replaces or supplements `completion_factor`
4. **Unified range:** All factors use same range (likely 0.0-1.0)

**Considerations:**
- Current formula uses additive offsets to ensure factors provide "boost" rather than "penalty"
- New structure would require all factors to be calibrated to similar ranges
- `thoroughness_factor` exists as `calculate_thoroughness_factor()` but returns 0.5-1.3 range
- Need to decide if `start_speed_factor` should be merged into `speed_factor` or kept separate

**Recommendation:**
- Keep current structure for now (focus factor integrated)
- Test focus factor behavior with real data
- Consider formula restructure as separate refactoring task
- If restructuring, ensure all factors are normalized to same range (0.0-1.0)

## Testing Recommendations

1. **Test with sparse data:** First task completion (no history)
2. **Test with focused session:** Multiple tasks completed quickly
3. **Test with emotions:** Tasks with focus-positive vs focus-negative emotions
4. **Test with repetition:** Same task template completed multiple times
5. **Test edge cases:** Missing timestamps, missing emotions, missing task_id

## Future Enhancements

1. **Personalized focus hours:** Learn user's most productive times
2. **Focus decay modeling:** How focus degrades over time
3. **Context awareness:** Environmental factors (location, time of day)
4. **Focus streaks:** Consecutive days of high focus
5. **Task switching penalty:** Penalize switching between very different task types

## Files Modified

- `backend/analytics.py`: Added `calculate_focus_factor()` method, updated `calculate_execution_score()`
- `docs/focus_factor_design.md`: Design document with detailed formulas
- `docs/focus_factor_implementation_summary.md`: This file

## Related Documentation

- `docs/execution_module_v1.0.md`: Execution score formula documentation
- `docs/focus_factor_design.md`: Detailed focus factor design
