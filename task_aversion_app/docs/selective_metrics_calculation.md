# Selective Metrics Calculation Strategy

## Overview

The `get_dashboard_metrics()` and `get_all_scores_for_composite()` functions currently calculate all metrics regardless of what's needed. This document outlines the strategy for making them support selective calculation.

## Current State

### `get_dashboard_metrics()`
Calculates:
- **Counts**: active, completed_7d, total_created, total_completed, completion_rate, daily_self_care_tasks, avg_daily_self_care_tasks
- **Quality**: avg_relief, avg_cognitive_load, avg_stress_level, avg_net_wellbeing, avg_net_wellbeing_normalized, avg_stress_efficiency, avg_aversion, adjusted_wellbeing, adjusted_wellbeing_normalized, thoroughness_score, thoroughness_factor
- **Time**: median_duration, avg_delay, estimation_accuracy
- **Aversion**: general_aversion_score
- **Productivity Volume**: avg_daily_work_time, work_volume_score, work_consistency_score, productivity_potential_score, work_volume_gap, composite_productivity_score, avg_base_productivity, volumetric_productivity_score, volumetric_potential_score
- **Life Balance**: work_count, play_count, balance_score, etc.

### `get_all_scores_for_composite()`
Calls `get_dashboard_metrics()` internally, then extracts:
- avg_stress_level (inverted)
- avg_net_wellbeing
- avg_stress_efficiency
- avg_relief
- work_volume_score
- work_consistency_score
- life_balance_score
- weekly_relief_score (from get_relief_summary)
- tracking_consistency_score
- completion_rate
- self_care_frequency
- execution_score (placeholder)

## Strategy

### Phase 1: Add Optional Parameter (Current)
- Add `metrics: Optional[List[str]] = None` parameter
- If `None`, calculate all (backward compatible)
- If provided, only calculate requested metrics

### Phase 2: Dependency Resolution
Create `_expand_metric_dependencies()` to handle:
- Direct dependencies (e.g., `adjusted_wellbeing` needs `avg_net_wellbeing` and `general_aversion_score`)
- Indirect dependencies (e.g., `composite_productivity_score` needs `work_volume_score`, `work_consistency_score`, `avg_base_productivity`)

### Phase 3: Conditional Calculation
Add conditional checks before expensive operations:
- `get_daily_work_volume_metrics()` - only if work_volume_score or work_consistency_score needed
- `get_life_balance()` - only if life_balance_score needed
- `calculate_thoroughness_score()` - only if thoroughness_score needed
- Productivity score calculations - only if productivity metrics needed
- Self-care calculations - only if self_care_frequency needed

### Phase 4: Result Filtering
Filter the final result dictionary to only include requested metrics.

## Implementation Notes

### Metric Naming
- Support both `'category.key'` (e.g., `'quality.avg_relief'`) and `'key'` (e.g., `'avg_relief'`)
- If just `'key'` is provided, search all categories

### Dependencies Map
```python
dependencies = {
    'adjusted_wellbeing': {'avg_net_wellbeing', 'general_aversion_score'},
    'adjusted_wellbeing_normalized': {'adjusted_wellbeing', 'avg_net_wellbeing', 'general_aversion_score'},
    'composite_productivity_score': {'work_volume_score', 'work_consistency_score', 'avg_base_productivity'},
    'volumetric_productivity_score': {'avg_base_productivity', 'work_volume_score'},
    'volumetric_potential_score': {'avg_base_productivity', 'work_volume_score'},
    'productivity_potential_score': {'avg_base_productivity', 'work_volume_score', 'work_consistency_score'},
}
```

### Expensive Operations to Conditionally Skip
1. `get_daily_work_volume_metrics(days=30)` - expensive, only needed for productivity_volume metrics
2. `get_life_balance()` - moderate cost, only needed for life_balance_score
3. `calculate_thoroughness_score()` - moderate cost, only needed for thoroughness_score
4. Productivity score calculations (iterating through all completed tasks) - expensive, only needed for productivity metrics
5. Self-care task calculations - moderate cost, only needed for self_care_frequency
6. `get_efficiency_summary()` - moderate cost, only needed for productivity_potential_score

## Example Usage

```python
# Calculate only specific metrics
metrics = analytics.get_dashboard_metrics(metrics=['quality.avg_relief', 'work_volume_score'])

# Calculate all (backward compatible)
metrics = analytics.get_dashboard_metrics()
```

## Performance Impact

- **Before**: Always calculates all metrics (~500-1000ms depending on data size)
- **After (selective)**: Only calculates requested metrics (~50-200ms for simple metrics)

## Migration Path

1. Add parameter with default `None` (backward compatible)
2. Implement dependency expansion
3. Add conditional checks for expensive operations
4. Filter results
5. Update callers to use selective calculation where beneficial

