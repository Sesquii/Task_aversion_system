---
name: Execution Score Implementation
overview: Implement execution score to reward efficient execution of difficult tasks. Addresses gap where fast, high-difficulty tasks are under-rewarded. Combines difficulty, speed, start speed, and completion quality into a single normalized score (0-100).
todos:
  - id: implement_core_method
    content: Implement calculate_execution_score() method with all four component factors (difficulty, speed, start speed, completion)
    status: pending
  - id: handle_data_extraction
    content: Extract required data from task instances (aversion, load, time estimates, datetime fields)
    status: pending
    dependencies:
      - implement_core_method
  - id: handle_edge_cases
    content: Handle missing data gracefully (missing time estimates, missing start time, invalid datetimes)
    status: pending
    dependencies:
      - handle_data_extraction
  - id: integrate_composite_score
    content: Add execution score to get_all_scores_for_composite() and composite score default weights
    status: pending
    dependencies:
      - implement_core_method
  - id: update_composite_ui
    content: Update composite score page UI to include execution score in weights and display
    status: pending
    dependencies:
      - integrate_composite_score
  - id: add_analytics_display
    content: Add execution score display to analytics page (metrics section, trends)
    status: pending
    dependencies:
      - implement_core_method
  - id: verify_sql_compatibility
    content: Test execution score with database backend, ensure datetime parsing works with SQL DateTime fields
    status: pending
    dependencies:
      - handle_data_extraction
  - id: create_unit_tests
    content: Create unit tests for execution score (ideal execution, slow execution, easy task, missing data)
    status: pending
    dependencies:
      - implement_core_method
  - id: validate_proposal_examples
    content: Validate execution score matches examples from proposal (92.5, 48.6, 62.5)
    status: pending
    dependencies:
      - implement_core_method
  - id: integration_testing
    content: Test execution score in composite score calculation and UI display with real data
    status: pending
    dependencies:
      - integrate_composite_score
      - add_analytics_display
---

# E

xecution Score Implementation Plan**Created:** 2025-01-XX**Status:** Planning**Priority:** Medium (addresses scoring gap)**Reference:** `docs/execution_score_proposal.md`

## Overview

Implement execution score to reward efficient execution of difficult tasks. This addresses a gap where:

- Fast, easy tasks get same reward as fast, hard tasks (productivity score)
- Fast completion of difficult tasks gets no recognition (grit score)
- Difficulty bonus doesn't consider speed
- No recognition for starting tasks quickly (overcoming procrastination)

## Current State

- Execution score is **not implemented** (only proposal exists)
- Fast, high-difficulty tasks are under-rewarded
- No metric combines difficulty + speed
- Start speed (procrastination resistance) is not tracked

## Goals

1. Implement `calculate_execution_score()` method in Analytics class
2. Integrate execution score into composite score system
3. Add execution score to analytics dashboard
4. Ensure SQL compatibility (works with database backend)
5. Test with sample data
6. Document implementation

## Implementation Strategy

### Phase 1: Core Implementation

**Files to modify:**

- `backend/analytics.py` - Add `calculate_execution_score()` method

**Tasks:**

1. **Implement Core Method**

- Add `calculate_execution_score()` method to Analytics class
- Implement four component factors:
    - Difficulty factor (reuse `calculate_difficulty_bonus()`)
    - Speed factor (execution efficiency)
    - Start speed factor (procrastination resistance)
    - Completion factor (quality of completion)
- Combine factors multiplicatively
- Normalize to 0-100 range

2. **Extract Required Data**

- Get task instance data (aversion, load, time estimates, etc.)
- Parse datetime fields (initialized_at, started_at, completed_at)
- Handle missing data gracefully (return neutral score)

3. **Handle Edge Cases**

- Missing time estimates → neutral speed factor
- Missing start time → use completion time as proxy
- Missing completion percent → assume 100%
- Invalid datetime strings → return neutral score

### Phase 2: Integration with Existing Systems

**Files to modify:**

- `backend/analytics.py` - Update `get_all_scores_for_composite()`
- `backend/analytics.py` - Update `calculate_composite_score()` (if needed)
- `ui/composite_score_page.py` - Add execution score to default weights

**Tasks:**

1. **Add to Composite Score**

- Include execution score in `get_all_scores_for_composite()`
- Add default weight (1.0) to composite score weights
- Ensure execution score is normalized before inclusion

2. **Update Composite Score UI**

- Add execution score to default weights dictionary
- Display execution score in composite score dashboard
- Allow users to adjust execution score weight

### Phase 3: Analytics Dashboard Integration

**Files to modify:**

- `ui/analytics_page.py` - Add execution score display
- `ui/dashboard.py` - Add execution score to dashboard (optional)

**Tasks:**

1. **Add to Analytics Page**

- Display execution score in metrics section
- Show execution score trends over time
- Add execution score to relief summary (if applicable)

2. **Add to Dashboard (Optional)**

- Display recent execution scores
- Show execution score alongside other metrics

### Phase 4: SQL Compatibility

**Files to verify:**

- `backend/analytics.py` - Ensure method works with database queries
- `backend/instance_manager.py` - Verify datetime fields are accessible

**Tasks:**

1. **Verify Database Compatibility**

- Test execution score calculation with database backend
- Ensure datetime parsing works with database DateTime fields
- Test with SQLite and verify PostgreSQL compatibility

2. **Handle Database-Specific Issues**

- Ensure datetime fields are properly converted
- Handle timezone issues if any
- Test with missing/null datetime values

### Phase 5: Testing and Validation

**Files to create:**

- `tests/test_execution_score.py` - Unit tests for execution score

**Tasks:**

1. **Create Test Cases**

- Test ideal execution (fast, high-difficulty, fast start, 100% completion)
- Test slow execution (slow, high-difficulty)
- Test easy task (fast, low-difficulty)
- Test missing data scenarios
- Test edge cases (very fast, very slow, etc.)

2. **Validate Examples from Proposal**

- Verify Example 1: Fast, high-difficulty → 92.5 score
- Verify Example 2: Slow, high-difficulty → 48.6 score
- Verify Example 3: Fast, easy → 62.5 score

3. **Integration Testing**

- Test execution score in composite score calculation
- Test execution score display in UI
- Test with real task instance data

## Technical Details

### Method Signature

```python
def calculate_execution_score(
    self,
    row: pd.Series,  # Task instance row (or dict from database)
    task_completion_counts: Optional[Dict[str, int]] = None
) -> float:
    """
    Calculate execution score (0-100) for efficient execution of difficult tasks.
    
    Args:
        row: Task instance with actual_dict, predicted_dict, and timing fields
        task_completion_counts: Optional dict for task completion counts (for difficulty)
    
    Returns:
        Execution score (0-100), higher = better execution
    """
```



### Component Calculations

**1. Difficulty Factor:**

```python
# Reuse existing calculate_difficulty_bonus()
predicted_dict = row.get('predicted_dict', {})
actual_dict = row.get('actual_dict', {})

current_aversion = predicted_dict.get('initial_aversion') or predicted_dict.get('aversion')
stress_level = actual_dict.get('stress_level')
mental_energy = predicted_dict.get('mental_energy_needed') or predicted_dict.get('cognitive_load')
task_difficulty = predicted_dict.get('task_difficulty')

difficulty_factor = self.calculate_difficulty_bonus(
    current_aversion=current_aversion,
    stress_level=stress_level,
    mental_energy=mental_energy,
    task_difficulty=task_difficulty
)
# Already returns 0.0-1.0, use directly
```

**2. Speed Factor:**

```python
time_actual = float(actual_dict.get('time_actual_minutes', 0) or 0)
time_estimate = float(predicted_dict.get('time_estimate_minutes', 0) or predicted_dict.get('estimate', 0) or 0)

if time_estimate > 0 and time_actual > 0:
    time_ratio = time_actual / time_estimate
    
    if time_ratio <= 0.5:
        # Very fast: 2x speed or faster → max bonus
        speed_factor = 1.0
    elif time_ratio <= 1.0:
        # Fast: completed within estimate → linear bonus
        # 0.5 → 1.0, 1.0 → 0.5
        speed_factor = 1.0 - (time_ratio - 0.5) * 1.0
    else:
        # Slow: exceeded estimate → diminishing penalty
        # 1.0 → 0.5, 2.0 → 0.25, 3.0 → 0.125
        speed_factor = 0.5 * (1.0 / time_ratio)
else:
    speed_factor = 0.5  # Neutral if no time data
```

**3. Start Speed Factor:**

```python
import pandas as pd
from datetime import datetime

initialized_at = row.get('initialized_at')
started_at = row.get('started_at')
completed_at = row.get('completed_at')

if initialized_at and completed_at:
    try:
        init_time = pd.to_datetime(initialized_at)
        complete_time = pd.to_datetime(completed_at)
        
        if started_at:
            start_time = pd.to_datetime(started_at)
            start_delay_minutes = (start_time - init_time).total_seconds() / 60.0
        else:
            # No start time: use completion time as proxy
            start_delay_minutes = (complete_time - init_time).total_seconds() / 60.0
        
        # Normalize: fast start = high score
        if start_delay_minutes <= 5:
            start_speed_factor = 1.0
        elif start_delay_minutes <= 30:
            # Linear: 5 min → 1.0, 30 min → 0.8
            start_speed_factor = 1.0 - ((start_delay_minutes - 5) / 25.0) * 0.2
        elif start_delay_minutes <= 120:
            # Linear: 30 min → 0.8, 120 min → 0.5
            start_speed_factor = 0.8 - ((start_delay_minutes - 30) / 90.0) * 0.3
        else:
            # Exponential decay: 120 min → 0.5, 480 min → ~0.125
            import math
            excess = start_delay_minutes - 120
            start_speed_factor = 0.5 * math.exp(-excess / 240.0)
    except (ValueError, TypeError):
        start_speed_factor = 0.5  # Neutral on error
else:
    start_speed_factor = 0.5  # Neutral if no timing data
```

**4. Completion Factor:**

```python
completion_pct = float(actual_dict.get('completion_percent', 100) or 100)

if completion_pct >= 100.0:
    completion_factor = 1.0
elif completion_pct >= 90.0:
    # Near-complete: slight penalty
    completion_factor = 0.9 + (completion_pct - 90.0) / 10.0 * 0.1
elif completion_pct >= 50.0:
    # Partial: moderate penalty
    completion_factor = 0.5 + (completion_pct - 50.0) / 40.0 * 0.4
else:
    # Low completion: significant penalty
    completion_factor = completion_pct / 50.0 * 0.5
```

**5. Combined Formula:**

```python
# Base score: 50 points (neutral)
base_score = 50.0

# Apply factors multiplicatively (all must be high for high score)
execution_score = base_score * (
    (1.0 + difficulty_factor) *      # 1.0-2.0 range (difficulty boost)
    (0.5 + speed_factor * 0.5) *     # 0.5-1.0 range (speed boost)
    (0.5 + start_speed_factor * 0.5) *  # 0.5-1.0 range (start speed boost)
    completion_factor                # 0.0-1.0 range (completion quality)
)

# Normalize to 0-100 range
execution_score = max(0.0, min(100.0, execution_score))

return execution_score
```



### Integration with Composite Score

```python
# In get_all_scores_for_composite()
def get_all_scores_for_composite(self, days: int = 7) -> Dict[str, float]:
    # ... existing code ...
    
    # Calculate execution score for recent completions
    recent_instances = self.instance_manager.list_recent_completed(limit=100)
    execution_scores = []
    
    for instance in recent_instances:
        # Convert to Series-like object for calculate_execution_score
        execution_score = self.calculate_execution_score(instance)
        if execution_score is not None:
            execution_scores.append(execution_score)
    
    avg_execution_score = sum(execution_scores) / len(execution_scores) if execution_scores else 50.0
    
    return {
        # ... existing scores ...
        'execution_score': avg_execution_score,
    }
```



### Database Compatibility

**Handle Both CSV and Database:**

```python
def calculate_execution_score(self, row, task_completion_counts=None):
    """Works with both pandas Series (CSV) and dict (database)."""
    
    # Handle both formats
    if isinstance(row, pd.Series):
        actual_dict = row.get('actual_dict', {})
        predicted_dict = row.get('predicted_dict', {})
        initialized_at = row.get('initialized_at')
        started_at = row.get('started_at')
        completed_at = row.get('completed_at')
    else:
        # Database format (dict)
        actual_dict = row.get('actual', {}) if isinstance(row.get('actual'), dict) else {}
        predicted_dict = row.get('predicted', {}) if isinstance(row.get('predicted'), dict) else {}
        initialized_at = row.get('initialized_at')
        started_at = row.get('started_at')
        completed_at = row.get('completed_at')
    
    # Parse datetime if needed
    if isinstance(initialized_at, datetime):
        initialized_at = initialized_at.isoformat()
    # ... rest of calculation
```



## Testing Strategy

### Unit Tests

```python
# tests/test_execution_score.py

def test_ideal_execution():
    """Test fast, high-difficulty task with fast start."""
    row = create_test_row(
        aversion=80, load=70,
        time_actual=15, time_estimate=60,
        start_delay=5, completion=100
    )
    score = analytics.calculate_execution_score(row)
    assert 90 <= score <= 95  # Should be high

def test_slow_execution():
    """Test slow, high-difficulty task."""
    row = create_test_row(
        aversion=80, load=70,
        time_actual=120, time_estimate=60,
        start_delay=180, completion=100
    )
    score = analytics.calculate_execution_score(row)
    assert 40 <= score <= 55  # Should be lower

def test_easy_task():
    """Test fast, easy task."""
    row = create_test_row(
        aversion=20, load=30,
        time_actual=10, time_estimate=30,
        start_delay=5, completion=100
    )
    score = analytics.calculate_execution_score(row)
    assert 55 <= score <= 70  # Moderate (lower than difficult fast task)

def test_missing_data():
    """Test with missing time estimates."""
    row = create_test_row(
        aversion=80, load=70,
        time_actual=None, time_estimate=None,
        start_delay=5, completion=100
    )
    score = analytics.calculate_execution_score(row)
    assert score is not None  # Should return neutral score, not crash
```



### Integration Tests

1. Test execution score in composite score calculation
2. Test execution score display in UI
3. Test with real database data
4. Test with CSV data (backward compatibility)

## Success Criteria

- ✅ `calculate_execution_score()` method implemented
- ✅ Execution score integrated into composite score
- ✅ Execution score displayed in analytics dashboard
- ✅ Works with both CSV and database backends
- ✅ All test cases pass
- ✅ Examples from proposal match calculated scores
- ✅ Handles missing data gracefully
- ✅ Documentation complete

## Dependencies

- Existing `calculate_difficulty_bonus()` method (already exists)
- Task instance data with timing fields
- Database migration complete (for SQL compatibility)

## Notes

- Execution score will be included in score calibration plan later
- Can be used as multiplier for productivity score (optional future enhancement)