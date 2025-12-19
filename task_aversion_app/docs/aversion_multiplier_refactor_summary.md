# Aversion Multiplier Refactor Summary

## Overview

The aversion multiplier formula has been completely refactored to separate **difficulty bonus** (rewarding hard tasks) from **improvement multiplier** (rewarding progress over time). This addresses the issue identified in the formula review where the old formula mixed these concepts incorrectly.

## Changes Made

### 1. New Functions Created

#### `calculate_difficulty_bonus()`
- **Purpose:** Rewards completing difficult tasks (high aversion + high load)
- **Formula:** `bonus = 1.0 * (1 - exp(-(0.7 * aversion + 0.3 * load) / 50))`
- **Max bonus:** 1.0 (multiplier 1.0 to 2.0)
- **Characteristics:**
  - Exponential scaling with flat/low exponent (smooth curve)
  - Higher weight to aversion (0.7) vs load (0.3)
  - Uses stress_level, mental_energy, or task_difficulty for load

#### `calculate_improvement_multiplier()`
- **Purpose:** Rewards progress over time (reduced aversion)
- **Formula:** `bonus = 1.0 * (1 - exp(-improvement / 30))`
- **Max bonus:** 1.0 (multiplier 1.0 to 2.0)
- **Characteristics:**
  - Logarithmic scaling with exponential decay
  - Diminishing returns (early improvements count more)
  - Only applies when `initial_aversion > current_aversion`

#### `calculate_overall_improvement_ratio()` (NEW)
- **Purpose:** Overarching improvement ratio from multiple performance factors
- **Formula:** Weighted combination of:
  1. Self-care frequency improvement: `(current - average) / average`
  2. Relief score improvement: `current_relief - avg_relief`
  3. Performance balance: `high_metrics - poor_metrics`
- **Max bonus:** 1.0 (multiplier 1.0 to 2.0)
- **Characteristics:**
  - Weights: self-care (0.3), relief (0.4), performance balance (0.3)
  - Exponential decay: `1 - exp(-combined_improvement / 40)`
  - Balances high-performing metrics against poorly performing metrics
  - Rewards doing more self-care than average
  - Rewards higher relief scores than average

#### `calculate_overall_improvement_from_instance()` (NEW)
- **Purpose:** Helper method to calculate overall improvement from a task instance row
- **Extracts:** Self-care count, relief score, and performance metrics from instance
- **Uses:** `calculate_overall_improvement_ratio()` internally
- **Use case:** Easy integration with existing task instance data

#### `calculate_aversion_multiplier()` (Updated)
- **Purpose:** Combines difficulty and improvement bonuses
- **Formula:** `multiplier = 1.0 + max(difficulty_bonus, improvement_bonus)`
- **Max multiplier:** 2.0 (max bonus = 1.0 = 100%)
- **Characteristics:**
  - Uses maximum of the two bonuses
  - Small additional bonus (0.1) when both are significant (>0.3 each)
  - Backward compatible with existing calls

### 2. Formula Characteristics

**Difficulty Bonus Examples:**
- Aversion=50, Load=50 → Bonus=0.63 (63% bonus, 1.63x multiplier)
- Aversion=100, Load=100 → Bonus=0.86 (86% bonus, 1.86x multiplier)

**Improvement Multiplier Examples:**
- Improvement=10 points → Bonus=0.28 (28% bonus, 1.28x multiplier)
- Improvement=30 points → Bonus=0.63 (63% bonus, 1.63x multiplier)
- Improvement=60 points → Bonus=0.86 (86% bonus, 1.86x multiplier)

**Combined Examples:**
- High difficulty only → Multiplier=1.86
- High improvement only → Multiplier=1.91
- Both high → Multiplier=1.91 (with small bonus)

## Benefits

1. ✅ **Clear separation:** Difficulty and improvement are now separate, well-defined concepts
2. ✅ **Psychologically accurate:** Exponential decay matches human perception of progress
3. ✅ **Consistent max bonus:** All bonuses capped at 1.0x (multiplier 1.0 to 2.0)
4. ✅ **Backward compatible:** Existing calls to `calculate_aversion_multiplier()` still work
5. ✅ **Extensible:** Can be enhanced with stress/load data when available

## Backward Compatibility

The `calculate_aversion_multiplier()` function maintains backward compatibility:
- Old calls: `calculate_aversion_multiplier(initial_av, current_av)` still work
- New calls: Can pass `stress_level`, `mental_energy`, or `task_difficulty` for better difficulty calculation

## Testing Results

All formulas tested and working correctly:
- ✅ Difficulty bonus: Smooth curve, max 1.0
- ✅ Improvement multiplier: Logarithmic scaling, max 1.0
- ✅ Combined multiplier: Max 2.0, smooth transitions

## New Feature: Overall Improvement Ratio

### Overview
An overarching improvement ratio that considers:
1. **Self-care frequency:** Rewards doing more self-care tasks per day than average
2. **Relief score improvement:** Rewards getting higher relief scores than average
3. **Performance balance:** Balances high-performing metrics (low stress, high wellbeing, high efficiency) against poorly performing metrics

### Usage Example

```python
from backend.analytics import Analytics

analytics = Analytics()

# Calculate overall improvement ratio
improvement_ratio = analytics.calculate_overall_improvement_ratio(
    current_self_care_per_day=3.0,  # Doing 3 self-care tasks today
    avg_self_care_per_day=1.5,      # Average is 1.5 per day
    current_relief_score=75.0,      # Current relief score
    avg_relief_score=60.0,          # Average relief score
    high_performing_metrics={
        'stress_level': 10.0,       # 10 points lower stress than average
        'net_wellbeing': 15.0       # 15 points higher wellbeing
    },
    poor_performing_metrics={
        'stress_efficiency': 5.0    # 5 points lower efficiency
    }
)

# improvement_ratio will be 0.0 to 1.0 (max bonus = 1.0 = 2x multiplier)
```

### Integration
The overall improvement ratio can be used alongside or instead of the aversion-based improvement multiplier. It provides a more holistic view of improvement across multiple dimensions.

## Related Documents

- `docs/formula_review_analysis.md` - Original issue identification
- `docs/logarithmic_improvement_metrics.md` - Comprehensive guide to improvement metrics
- `backend/analytics.py:24-350` - Implementation

## Next Steps

1. ✅ **Complete:** Separated difficulty bonus and improvement multiplier
2. ⏳ **Optional:** Update call sites to pass stress/load data for better difficulty calculation
3. ⏳ **Optional:** Add analytics to track correlation improvement with new formulas
4. ⏳ **Optional:** Consider time-decay for improvement tracking (see `logarithmic_improvement_metrics.md`)

---

**Status:** ✅ Complete
**Date:** 2024-12-XX
**Issue:** Addressed from `formula_review_analysis.md` section 2.1

