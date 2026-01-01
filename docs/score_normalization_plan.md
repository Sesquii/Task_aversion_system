# Score Normalization & Points vs Scores Framework

## Overview

This document outlines the plan to convert raw metrics ("points") to normalized scores (0-100 scale) that are relative to baseline performance. This makes scores more meaningful and comparable across different tasks, time periods, and users.

## Motivation

### Current Issues

1. **Raw values are absolute** - A relief of 70 means different things to different users
2. **No baseline comparison** - Can't tell if 70 is good or bad without context
3. **Inconsistent scales** - Some metrics are 0-10, others 0-100
4. **Hard to compare** - Can't easily compare performance across time periods

### Goals

1. **Normalize all scores to 0-100 scale** based on objective evaluation metrics
2. **Make scores relative to baseline performance** - 50 = baseline, 100 = excellent, 0 = poor
3. **Distinguish points from scores** - Clear naming convention
4. **Improve interpretability** - Scores should be meaningful without context

## Framework: Points vs Scores

### Points (Raw Values)

**Definition:** Unnormalized, absolute values from user input or calculations.

**Characteristics:**
- Can be any range (0-10, 0-100, etc.)
- Task-specific or absolute measurements
- Stored as-is from user input
- Used for baseline calculations

**Examples:**
- `actual_relief` (0-10 from user input)
- `stress_level` (0-100 calculated)
- `aversion_points` (raw aversion value)
- `duration_minutes` (absolute time)

**Naming Convention:**
- Use raw metric names: `actual_relief`, `stress_level`
- Or use `*_points` suffix: `relief_points`, `aversion_points`

### Scores (Normalized Values)

**Definition:** Normalized values on 0-100 scale, relative to baseline or objective criteria.

**Characteristics:**
- Always 0-100 scale
- Relative to baseline or objective metrics
- Comparable across tasks/users/time
- 50 = baseline/neutral, 100 = excellent, 0 = poor

**Examples:**
- `relief_score` (normalized relief relative to baseline)
- `stress_score` (normalized stress, inverted: lower = better)
- `aversion_score` (normalized aversion relative to baseline)
- `efficiency_score` (normalized efficiency)

**Naming Convention:**
- Use `*_score` suffix: `relief_score`, `efficiency_score`

## Normalization Approaches

### 1. Baseline-Relative Normalization (Primary)

**Use for:** Subjective metrics where personal baseline matters more than absolute values.

**Formula:**
```
score = 50 + ((current - baseline) / baseline) × 50
```

**Properties:**
- `current == baseline` → `score = 50` (neutral)
- `current == 2 × baseline` → `score = 100` (excellent)
- `current == 0` → `score = 0` (poor)
- `current == 0.5 × baseline` → `score = 25` (below average)

**Metrics to apply:**
- Relief scores → normalize against `avg_relief_score`
- Stress levels → normalize against `avg_stress_level` (inverted)
- Aversion → normalize against `baseline_aversion`
- Stress efficiency → normalize against `avg_stress_efficiency`
- Work volume → normalize against `avg_work_volume`

### 2. Objective Metric Normalization

**Use for:** Metrics with clear objective evaluation criteria.

**Formula:**
```
score = ((current - min_possible) / (optimal - min_possible)) × 100
```

**Properties:**
- `current <= min_possible` → `score = 0`
- `current >= optimal` → `score = 100`
- Linear interpolation between min and optimal

**Metrics to apply:**
- Task completion rate → optimal = 100%
- Time tracking consistency → optimal = 100% coverage
- Sleep duration → optimal = 7-8 hours
- Work consistency → optimal = daily consistency

### 3. Hybrid Normalization

**Use for:** Metrics that have both objective bounds and personal variation.

**Approach:**
1. Start with baseline-relative normalization
2. Apply objective bounds (cap at 100, floor at 0)
3. Apply penalties for impossible/undesirable values

**Metrics to apply:**
- Relief duration scores (baseline-relative, but capped by objective limits)
- Productivity scores (baseline-relative, but with objective efficiency bounds)

## Implementation Plan

### Phase 1: Foundation (Current)

**Tasks:**
1. ✅ Create normalization rule document (`.cursor/rules/score-normalization-baseline.mdc`)
2. ✅ Create planning document (this file)
3. Add normalization utility functions to `analytics.py`
4. Document current state of all metrics

**Deliverables:**
- Normalization functions
- Baseline calculation utilities
- Documentation of current metrics

### Phase 2: Relief Score Normalization (Priority 1)

**Tasks:**
1. Add `calculate_relief_score()` function to `analytics.py`
2. Update `get_relief_summary()` to calculate baseline
3. Normalize relief in all calculations
4. Update UI to display normalized relief scores
5. Store both raw and normalized values during migration

**Key Changes:**
```python
# Before
relief = float(actual_dict.get('actual_relief', 0))

# After
relief_points = float(actual_dict.get('actual_relief', 0))
avg_relief_points = self._calculate_baseline_relief(days=30)
relief_score = normalize_to_baseline(relief_points, avg_relief_points)
```

**Files to modify:**
- `backend/analytics.py` - Add normalization functions
- `backend/analytics.py` - Update relief calculations
- `ui/analytics_*.py` - Update displays
- Database/CSV schema - Store both values

### Phase 3: Stress & Aversion Normalization (Priority 2)

**Tasks:**
1. Add `calculate_stress_score()` (inverted normalization)
2. Add `calculate_aversion_score()` (baseline-relative)
3. Update all stress/aversion calculations
4. Update UI displays

### Phase 4: Efficiency & Volume Scores (Priority 3)

**Tasks:**
1. Normalize stress efficiency scores
2. Normalize work volume scores
3. Normalize work consistency scores
4. Update composite score calculations

### Phase 5: Productivity & Execution Scores (Priority 4)

**Tasks:**
1. Review execution score normalization (already uses some normalization)
2. Review productivity score normalization
3. Ensure all component scores are baseline-relative
4. Update composite scores

### Phase 6: Data Migration & Cleanup

**Tasks:**
1. Backfill normalized scores for historical data
2. Update data schema documentation
3. Migrate UI to use normalized scores exclusively
4. Remove deprecated raw score displays (optional)

## Baseline Calculation Strategy

### Time Windows

**Standard baselines:**
- **30-day baseline** - Default for most metrics (smooth, stable)
- **7-day baseline** - For recent trends (more responsive)
- **90-day baseline** - For long-term trends (very stable)

**Recommendation:** Start with 30-day baselines, allow configuration.

### Baseline Types

1. **Global baseline** - All tasks combined
   - Use for: General metrics (overall relief, stress)
   - Example: `avg_relief_score` across all tasks

2. **Task-type baseline** - Separate baseline per task type
   - Use for: Metrics that vary significantly by task type
   - Example: `avg_relief_work` vs `avg_relief_self_care`

3. **User baseline** - Separate baseline per user
   - Use for: Multi-user systems
   - Example: User-specific averages

### Implementation Pattern

```python
def calculate_baseline(self, metric_column: str, 
                      days: int = 30,
                      task_type: Optional[str] = None,
                      exclude_today: bool = True) -> float:
    """
    Calculate baseline for a metric.
    
    Args:
        metric_column: Column name with metric values
        days: Number of days to include
        task_type: Optional task type filter
        exclude_today: Whether to exclude today's data
    
    Returns:
        Baseline value (average)
    """
    cutoff_date = datetime.now() - timedelta(days=days)
    df = self._load_instances()
    completed = df[df['is_completed'] == True]
    
    if exclude_today:
        today = datetime.now().date()
        baseline_df = completed[
            (completed['completed_at_dt'] >= cutoff_date) & 
            (completed['completed_at_dt'].dt.date < today)
        ]
    else:
        baseline_df = completed[completed['completed_at_dt'] >= cutoff_date]
    
    if task_type:
        baseline_df = baseline_df[
            baseline_df['task_type'].str.lower() == task_type.lower()
        ]
    
    return baseline_df[metric_column].mean()
```

## Data Storage Strategy

### During Migration

**Store both values:**
- Raw values: `actual_relief`, `relief_points` (for backward compatibility)
- Normalized scores: `relief_score` (new column)

**Database schema:**
```sql
-- Existing columns (keep)
actual_relief REAL  -- Raw relief value

-- New columns (add)
relief_score REAL  -- Normalized relief score (0-100)
```

### After Migration

**Option 1:** Keep both (recommended)
- Allows recalculation if normalization changes
- Enables both absolute and relative views

**Option 2:** Store only normalized
- Cleaner schema
- Requires raw value reconstruction if needed

## UI Updates

### Display Strategy

**Show normalized scores by default:**
- Relief Score: 75/100 (relative to your baseline of 60)
- Stress Score: 35/100 (inverted: lower is better)
- Efficiency Score: 82/100 (relative to your baseline)

**Optional tooltips/info:**
- "Your baseline relief is 60. Current: 75 (25% above baseline)"
- "Raw value: 7.5/10"

### Migration Path

1. **Phase 1:** Show both raw and normalized (dual display)
2. **Phase 2:** Show normalized by default, raw in tooltip
3. **Phase 3:** Show only normalized (with baseline context)

## Testing Strategy

### Unit Tests

```python
def test_normalize_to_baseline():
    """Test baseline-relative normalization."""
    # At baseline
    assert normalize_to_baseline(50.0, 50.0) == 50.0
    
    # 2x baseline = 100
    assert normalize_to_baseline(100.0, 50.0) == 100.0
    
    # Zero = 0
    assert normalize_to_baseline(0.0, 50.0) == 0.0
    
    # Half baseline = 25
    assert normalize_to_baseline(25.0, 50.0) == 25.0

def test_relief_score_normalization():
    """Test relief score normalization."""
    relief_points = 7.5  # Raw value (0-10 scale)
    avg_relief_points = 6.0  # Baseline
    
    relief_score = calculate_relief_score(relief_points, avg_relief_points)
    # Expected: 75 points normalized, 60 baseline → score should be ~62.5
    assert 60 < relief_score < 65
```

### Integration Tests

1. Test baseline calculations with real data
2. Test normalization across different time windows
3. Test edge cases (zero baseline, missing data)
4. Test task-type-specific baselines

## Success Criteria

1. ✅ All scores normalized to 0-100 scale
2. ✅ Scores relative to baseline (50 = baseline)
3. ✅ Clear distinction between points and scores in naming
4. ✅ Backward compatibility maintained
5. ✅ UI displays normalized scores
6. ✅ Documentation complete
7. ✅ Tests passing

## Risks & Mitigations

### Risk 1: Baseline Instability

**Issue:** Small sample sizes lead to unstable baselines

**Mitigation:**
- Use minimum sample sizes (e.g., require 10+ data points)
- Fall back to global baseline if insufficient data
- Use longer time windows (30+ days) for stability

### Risk 2: Baseline Drift

**Issue:** User's baseline changes over time (improvement), making old scores incomparable

**Mitigation:**
- Use rolling baselines (always relative to recent performance)
- Document baseline calculation methodology
- Consider baseline versioning for historical comparisons

### Risk 3: Negative Scores

**Issue:** Current performance below baseline can result in negative scores

**Mitigation:**
- Clamp scores to 0-100 range
- Ensure baseline-relative formula handles this correctly

### Risk 4: Breaking Changes

**Issue:** Normalization changes existing score calculations

**Mitigation:**
- Maintain backward compatibility during migration
- Store both raw and normalized values
- Gradual migration (phase-by-phase)

## Next Steps

1. **Review this plan** - Get feedback on approach
2. **Implement Phase 1** - Add normalization functions
3. **Implement Phase 2** - Relief score normalization (priority)
4. **Test thoroughly** - Ensure backward compatibility
5. **Document** - Update API docs and user guides
6. **Iterate** - Apply to other metrics based on results

## References

- `.cursor/rules/score-normalization-baseline.mdc` - Implementation rules
- `docs/execution_module_v1.0.md` - Execution score patterns
- `docs/composite_score_system.md` - Composite score normalization
- `docs/overall_improvement_ratio.md` - Improvement-based scoring
