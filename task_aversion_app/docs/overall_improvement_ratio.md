# Overall Improvement Ratio - Implementation Guide

## Overview

The **Overall Improvement Ratio** is an overarching improvement metric that rewards improvements across multiple dimensions:
1. **Self-care frequency** - Doing more self-care tasks per day than average
2. **Relief score** - Getting higher relief scores than average
3. **Performance balance** - High-performing metrics balanced against poorly performing metrics

This provides a holistic view of improvement that goes beyond just aversion reduction.

## Formula

```python
improvement_ratio = 1.0 * (1 - exp(-combined_improvement / 40))
```

Where `combined_improvement` is a weighted average of:
- Self-care improvement (30% weight)
- Relief improvement (40% weight)
- Performance balance (30% weight)

**Max bonus:** 1.0 (multiplier 1.0 to 2.0)

## Components

### 1. Self-Care Frequency Improvement

```python
self_care_improvement = (current - average) / average
# Only positive improvements count (doing more than average)
# Normalized to 0-100 range (capped at 200% improvement = 2x average)
```

**Example:**
- Current: 3.0 self-care tasks/day
- Average: 1.5 self-care tasks/day
- Improvement: (3.0 - 1.5) / 1.5 = 100% improvement
- Normalized: 100.0 (capped)

### 2. Relief Score Improvement

```python
relief_improvement = current_relief - avg_relief
# Only positive improvements count (higher relief than average)
# Already in 0-100 range
```

**Example:**
- Current: 80.0 relief score
- Average: 60.0 relief score
- Improvement: 20.0 points

### 3. Performance Balance

```python
performance_balance = high_score - poor_score + 50.0
# Normalized to 0-100 range
# high_score = weighted average of high-performing metrics
# poor_score = weighted average of poor-performing metrics
```

**High-Performing Metrics:**
- Lower stress than average
- Higher net wellbeing than average
- Higher stress efficiency than average

**Poor-Performing Metrics:**
- Higher stress than average
- Lower net wellbeing than average
- Lower stress efficiency than average

## Usage

### Basic Usage

```python
from backend.analytics import Analytics

analytics = Analytics()

improvement_ratio = analytics.calculate_overall_improvement_ratio(
    current_self_care_per_day=3.0,
    avg_self_care_per_day=1.5,
    current_relief_score=75.0,
    avg_relief_score=60.0
)
# Returns: 0.0 to 1.0 (max bonus = 1.0 = 2x multiplier)
```

### With Performance Metrics

```python
improvement_ratio = analytics.calculate_overall_improvement_ratio(
    current_self_care_per_day=3.0,
    avg_self_care_per_day=1.5,
    current_relief_score=80.0,
    avg_relief_score=60.0,
    high_performing_metrics={
        'stress_level': 10.0,      # 10 points lower stress
        'net_wellbeing': 15.0      # 15 points higher wellbeing
    },
    poor_performing_metrics={
        'stress_efficiency': 5.0   # 5 points lower efficiency
    }
)
```

### From Task Instance

```python
# Helper method that extracts data from a task instance
improvement_ratio = analytics.calculate_overall_improvement_from_instance(
    row=task_instance_row,
    avg_self_care_per_day=1.5,
    avg_relief_score=60.0,
    completed_instances=all_completed_instances_df
)
```

## Test Results

| Scenario | Self-Care | Relief | Performance | Result |
|----------|-----------|--------|-------------|--------|
| High self-care only | 3.0 vs 1.5 | 60.0 vs 60.0 | None | 0.59 (59% bonus) |
| High relief only | 1.5 vs 1.5 | 80.0 vs 60.0 | None | 0.18 (18% bonus) |
| Both high + metrics | 3.0 vs 1.5 | 80.0 vs 60.0 | Balanced | 0.75 (75% bonus) |
| No improvement | 1.0 vs 1.5 | 50.0 vs 60.0 | None | 0.0 (no bonus) |

## Integration with Improvement Multiplier

The overall improvement ratio can be used alongside or instead of the aversion-based improvement multiplier:

```python
# Option 1: Use aversion-based improvement (existing)
improvement_bonus = Analytics.calculate_improvement_multiplier(
    initial_aversion=100,
    current_aversion=70
)

# Option 2: Use overall improvement ratio (new)
overall_improvement = analytics.calculate_overall_improvement_ratio(
    current_self_care_per_day=3.0,
    avg_self_care_per_day=1.5,
    current_relief_score=75.0,
    avg_relief_score=60.0
)

# Option 3: Use maximum of both
combined_improvement = max(improvement_bonus, overall_improvement)
```

## Benefits

1. ✅ **Holistic view:** Considers multiple improvement dimensions
2. ✅ **Self-care focus:** Rewards consistent self-care habits
3. ✅ **Relief tracking:** Rewards higher relief scores
4. ✅ **Performance balance:** Balances good vs poor metrics
5. ✅ **Consistent max bonus:** Capped at 1.0 (multiplier 1.0 to 2.0)
6. ✅ **Smooth scaling:** Exponential decay for natural curve

## Future Enhancements

1. **Time-decay:** Recent improvements count more than old ones
2. **Streak bonuses:** Reward consistent improvement over time
3. **Personalized baselines:** Use individual baselines instead of population averages
4. **Adaptive weights:** Adjust weights based on user's priorities

---

**Status:** ✅ Implemented
**Location:** `backend/analytics.py:124-280`
**Related:** `docs/aversion_multiplier_refactor_summary.md`

