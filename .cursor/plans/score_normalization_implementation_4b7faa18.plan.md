---
name: Score Normalization Implementation
overview: Implement baseline-relative score normalization to convert raw metrics (points) to normalized 0-100 scores, making scores comparable across tasks and time periods. This establishes a framework where 50 = baseline performance, 100 = excellent, and 0 = poor.
todos:
  - id: add-normalization-functions
    content: "Add normalization utility functions to analytics.py: normalize_to_baseline(), normalize_objective_metric(), _calculate_baseline()"
    status: pending
  - id: add-relief-score-normalization
    content: Add calculate_relief_score() method to normalize relief points to baseline-relative score (0-100)
    status: pending
    dependencies:
      - add-normalization-functions
  - id: update-relief-calculations
    content: Update all relief calculations in analytics.py to use normalized relief_score instead of raw actual_relief values
    status: pending
    dependencies:
      - add-relief-score-normalization
  - id: update-data-storage
    content: Update data storage to maintain both raw relief values and normalized relief_score (backward compatibility)
    status: pending
    dependencies:
      - add-relief-score-normalization
  - id: add-normalization-tests
    content: Add unit tests for normalization functions covering edge cases (zero baseline, scale conversion, clamping)
    status: pending
    dependencies:
      - add-normalization-functions
---

# Score Normalization Implementation Plan

## Overview

Convert raw metrics ("points") to normalized scores (0-100 scale) relative to baseline performance. This makes scores meaningful and comparable: **50 = baseline, 100 = excellent (2x baseline), 0 = poor**.

## Phase 1: Add Normalization Foundation

Add core normalization utility functions to [`task_aversion_app/backend/analytics.py`](task_aversion_app/backend/analytics.py):

1. **Add `normalize_to_baseline()` static method** - Baseline-relative normalization formula: `score = 50 + ((current - baseline) / baseline) × 50`
2. **Add `normalize_objective_metric()` static method** - For metrics with objective criteria (completion rate, time tracking)
3. **Add `_calculate_baseline()` instance method** - Calculate rolling baselines with time windows (default 30 days), optional task type filtering, exclude today option
4. **Add helper for scale conversion** - Handle 0-10 to 0-100 scale conversion for relief scores

Reference: `.cursor/rules/score-normalization-baseline.mdc` for implementation patterns

## Phase 2: Relief Score Normalization (Priority 1)

Normalize relief scores to be baseline-relative:

1. **Add `calculate_relief_score()` method** to [`task_aversion_app/backend/analytics.py`](task_aversion_app/backend/analytics.py)

- Accept raw relief points (0-10 or 0-100 scale)
- Calculate baseline relief using `_calculate_baseline()`
- Normalize using `normalize_to_baseline()`
- Handle scale conversion (0-10 → 0-100)

2. **Update relief calculations** throughout [`task_aversion_app/backend/analytics.py`](task_aversion_app/backend/analytics.py):

- Find all locations using `actual_relief` or `relief_score` directly
- Replace with normalized `relief_score` using `calculate_relief_score()`
- Key methods to update: `calculate_grit_score()`, `get_relief_summary()`, any method calculating net_wellbeing or relief-based metrics

3. **Update data storage** (maintain backward compatibility):

- Store both raw values (`actual_relief`) and normalized scores (`relief_score`)
- Update CSV/database schema if needed (add `relief_score` column)
- Ensure existing code can still access raw values

## Phase 3: Stress & Aversion Normalization (Priority 2)

Extend normalization to stress and aversion metrics:

1. **Add `calculate_stress_score()` method** - Inverted normalization (lower stress = higher score)
2. **Add `calculate_aversion_score()` method** - Baseline-relative normalization
3. **Update stress/aversion calculations** - Replace raw values with normalized scores where appropriate
4. **Update UI displays** - Show normalized scores in analytics views

## Phase 4: Testing & Validation

1. **Add unit tests** for normalization functions:

- Test `normalize_to_baseline()` edge cases (baseline = 0, negative values, clamping)
- Test `calculate_relief_score()` with various scales and baselines
- Test baseline calculation with different time windows

2. **Integration tests**:

- Test with real data from database/CSV
- Verify backward compatibility (raw values still accessible)
- Test baseline stability with small sample sizes

## Key Implementation Notes

- **Naming convention**: Use `*_points` for raw values, `*_score` for normalized (0-100)
- **Backward compatibility**: Store both raw and normalized values during migration
- **Baseline calculation**: Default to 30-day rolling baseline, exclude today's data
- **Edge cases**: Handle zero baseline (return 50.0), missing data, insufficient samples
- **Clamping**: All normalized scores clamped to 0-100 range

## Files to Modify

- [`task_aversion_app/backend/analytics.py`](task_aversion_app/backend/analytics.py) - Core implementation
- [`task_aversion_app/backend/instance_manager.py`](task_aversion_app/backend/instance_manager.py) - May need schema updates
- UI files (TBD in later phases) - Update displays to show normalized scores
- Test files - Add normalization tests

## References

- `.cursor/rules/score-normalization-baseline.mdc` - Implementation patterns and rules
- `docs/score_normalization_plan.md` - Full planning document with all phases