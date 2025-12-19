# Logarithmic Improvement Metrics - Meta-Analysis

## Overview

This document explores various approaches to applying logarithmic scaling to showcase improvement over time across different metrics in the task aversion system.

## Why Logarithmic Scaling?

Logarithmic scaling is ideal for improvement metrics because:
1. **Diminishing returns:** Early improvements feel more significant than later ones
2. **Prevents unbounded growth:** Natural ceiling effect
3. **Psychological accuracy:** Matches how humans perceive progress (Weber-Fechner law)
4. **Smooth transitions:** Avoids abrupt jumps in scoring

## Core Principle: Max Bonus = 1.0x

**Standard across all formulas:** Maximum bonus multiplier is 1.0x, meaning:
- Base multiplier: 1.0 (no bonus)
- Maximum multiplier: 2.0 (100% bonus = 2x total)
- Range: 1.0 to 2.0

This ensures consistency across the codebase and prevents score inflation.

---

## 1. Aversion Improvement Metrics

### Current Context
- **Initial aversion:** First-time aversion (0-100)
- **Current aversion:** Current expected aversion (0-100)
- **Improvement:** `initial_aversion - current_aversion` (can be negative)

### Formula Options

#### Option A: Logarithmic with Base 2
```python
improvement = initial_aversion - current_aversion
if improvement > 0:
    # Logarithmic: log2(1 + improvement/10)
    # Every 10 points of improvement ≈ 0.3x bonus
    improvement_multiplier = 1.0 + (math.log2(1 + improvement / 10.0) * 0.3)
else:
    improvement_multiplier = 1.0
# Clamp to 1.0 - 2.0
improvement_multiplier = max(1.0, min(2.0, improvement_multiplier))
```

**Characteristics:**
- 10 points improvement → ~1.3x (30% bonus)
- 30 points improvement → ~1.6x (60% bonus)
- 50 points improvement → ~1.8x (80% bonus)
- 100 points improvement → ~2.0x (100% bonus, max)

#### Option B: Square Root Scaling
```python
improvement = initial_aversion - current_aversion
if improvement > 0:
    # Square root: smooth, diminishing returns
    improvement_multiplier = 1.0 + (math.sqrt(improvement / 100.0))
else:
    improvement_multiplier = 1.0
# Clamp to 1.0 - 2.0
improvement_multiplier = max(1.0, min(2.0, improvement_multiplier))
```

**Characteristics:**
- 25 points improvement → ~1.5x (50% bonus)
- 50 points improvement → ~1.71x (71% bonus)
- 100 points improvement → ~2.0x (100% bonus, max)

#### Option C: Exponential Decay (Recommended)
```python
improvement = initial_aversion - current_aversion
if improvement > 0:
    # Exponential decay: 1 - exp(-improvement/k)
    # k controls steepness (lower = steeper)
    k = 30.0  # Tuning parameter
    improvement_multiplier = 1.0 + (1.0 - math.exp(-improvement / k))
else:
    improvement_multiplier = 1.0
# Clamp to 1.0 - 2.0
improvement_multiplier = max(1.0, min(2.0, improvement_multiplier))
```

**Characteristics:**
- Smooth curve, approaches 2.0 asymptotically
- 10 points → ~1.28x (28% bonus)
- 30 points → ~1.63x (63% bonus)
- 60 points → ~1.86x (86% bonus)
- 100 points → ~1.97x (97% bonus)

**Recommendation:** Option C (Exponential Decay) - smoothest, most psychologically accurate

---

## 2. Stress Reduction Improvement

### Context
- **Baseline stress:** Average stress level for task type
- **Current stress:** Current task stress level
- **Improvement:** `baseline_stress - current_stress` (reduction is positive)

### Formula
```python
stress_reduction = baseline_stress - current_stress
if stress_reduction > 0:
    # Logarithmic scaling for stress reduction
    k = 25.0  # Tuning parameter
    stress_improvement_multiplier = 1.0 + (1.0 - math.exp(-stress_reduction / k))
else:
    stress_improvement_multiplier = 1.0
# Clamp to 1.0 - 2.0
stress_improvement_multiplier = max(1.0, min(2.0, stress_improvement_multiplier))
```

---

## 3. Time Efficiency Improvement

### Context
- **Baseline time:** Average time to complete task
- **Current time:** Actual time taken
- **Improvement:** `baseline_time - current_time` (faster is positive)

### Formula
```python
time_improvement = baseline_time - current_time
if time_improvement > 0:
    # Percentage improvement
    improvement_pct = (time_improvement / baseline_time) * 100.0
    # Logarithmic scaling: log(1 + improvement_pct/10)
    k = 20.0  # Tuning parameter
    time_improvement_multiplier = 1.0 + (1.0 - math.exp(-improvement_pct / k))
else:
    time_improvement_multiplier = 1.0
# Clamp to 1.0 - 2.0
time_improvement_multiplier = max(1.0, min(2.0, time_improvement_multiplier))
```

---

## 4. Completion Rate Improvement

### Context
- **Baseline completion:** Average completion percentage
- **Current completion:** Actual completion percentage
- **Improvement:** `current_completion - baseline_completion` (higher is positive)

### Formula
```python
completion_improvement = current_completion - baseline_completion
if completion_improvement > 0:
    # Logarithmic scaling
    k = 15.0  # Tuning parameter
    completion_improvement_multiplier = 1.0 + (1.0 - math.exp(-completion_improvement / k))
else:
    completion_improvement_multiplier = 1.0
# Clamp to 1.0 - 2.0
completion_improvement_multiplier = max(1.0, min(2.0, completion_improvement_multiplier))
```

---

## 5. Composite Improvement Score

### Combining Multiple Improvement Metrics

```python
def calculate_composite_improvement(
    aversion_improvement: float,
    stress_improvement: float,
    time_improvement: float,
    completion_improvement: float,
    weights: Dict[str, float] = None
) -> float:
    """Calculate weighted composite improvement multiplier.
    
    Args:
        aversion_improvement: Aversion improvement multiplier (1.0-2.0)
        stress_improvement: Stress improvement multiplier (1.0-2.0)
        time_improvement: Time improvement multiplier (1.0-2.0)
        completion_improvement: Completion improvement multiplier (1.0-2.0)
        weights: Optional weights for each component (default: equal)
    
    Returns:
        Composite improvement multiplier (1.0-2.0)
    """
    if weights is None:
        weights = {
            'aversion': 0.4,
            'stress': 0.3,
            'time': 0.2,
            'completion': 0.1
        }
    
    # Weighted average of improvement multipliers
    composite = (
        (aversion_improvement - 1.0) * weights['aversion'] +
        (stress_improvement - 1.0) * weights['stress'] +
        (time_improvement - 1.0) * weights['time'] +
        (completion_improvement - 1.0) * weights['completion']
    )
    
    # Convert back to multiplier (1.0 + bonus)
    composite_multiplier = 1.0 + composite
    return max(1.0, min(2.0, composite_multiplier))
```

---

## 6. Time-Decay Improvement Tracking

### Tracking Improvement Over Time Windows

```python
def calculate_time_decay_improvement(
    current_value: float,
    baseline_value: float,
    days_since_baseline: int,
    half_life_days: int = 30
) -> float:
    """Calculate improvement with time decay.
    
    Recent improvements count more than old ones.
    
    Args:
        current_value: Current metric value
        baseline_value: Baseline metric value
        days_since_baseline: Days since baseline was established
        half_life_days: Days for improvement to decay to 50%
    
    Returns:
        Time-decay adjusted improvement multiplier (1.0-2.0)
    """
    improvement = baseline_value - current_value  # Assuming lower is better
    if improvement <= 0:
        return 1.0
    
    # Time decay factor: exp(-days / half_life)
    decay_factor = math.exp(-days_since_baseline / half_life_days)
    
    # Apply decay to improvement
    adjusted_improvement = improvement * decay_factor
    
    # Calculate multiplier with exponential decay formula
    k = 30.0
    improvement_multiplier = 1.0 + (1.0 - math.exp(-adjusted_improvement / k))
    
    return max(1.0, min(2.0, improvement_multiplier))
```

---

## 7. Relative Improvement (Percentile-Based)

### Comparing to Population Distribution

```python
def calculate_percentile_improvement(
    current_value: float,
    baseline_value: float,
    population_values: List[float]
) -> float:
    """Calculate improvement based on percentile ranking.
    
    Args:
        current_value: Current metric value
        baseline_value: Baseline metric value
        population_values: All values in population for comparison
    
    Returns:
        Percentile-based improvement multiplier (1.0-2.0)
    """
    # Calculate percentiles
    baseline_percentile = percentile(baseline_value, population_values)
    current_percentile = percentile(current_value, population_values)
    
    # Improvement in percentile points
    percentile_improvement = current_percentile - baseline_percentile
    
    if percentile_improvement <= 0:
        return 1.0
    
    # Logarithmic scaling of percentile improvement
    k = 20.0
    improvement_multiplier = 1.0 + (1.0 - math.exp(-percentile_improvement / k))
    
    return max(1.0, min(2.0, improvement_multiplier))
```

---

## 8. Streak-Based Improvement

### Rewarding Consistent Improvement

```python
def calculate_streak_improvement(
    improvement_streak: int,
    avg_improvement_per_task: float
) -> float:
    """Calculate bonus for consistent improvement streak.
    
    Args:
        improvement_streak: Number of consecutive tasks with improvement
        avg_improvement_per_task: Average improvement per task in streak
    
    Returns:
        Streak-based improvement multiplier (1.0-2.0)
    """
    if improvement_streak <= 0:
        return 1.0
    
    # Base improvement from average
    k = 30.0
    base_multiplier = 1.0 + (1.0 - math.exp(-avg_improvement_per_task / k))
    
    # Streak bonus: logarithmic scaling
    streak_bonus = math.log(1 + improvement_streak) / math.log(10)  # log10
    streak_multiplier = 1.0 + (streak_bonus * 0.1)  # Max 10% bonus from streak
    
    # Combine (multiplicative)
    total_multiplier = base_multiplier * streak_multiplier
    
    return max(1.0, min(2.0, total_multiplier))
```

---

## Implementation Recommendations

### Priority 1: Aversion Improvement (Current Focus)
- **Use:** Exponential decay formula (Option C)
- **Tuning parameter k:** 30.0 (adjust based on data)
- **Max bonus:** 1.0x (multiplier 1.0 to 2.0)

### Priority 2: Composite Improvement
- Combine aversion, stress, time, and completion improvements
- Weighted average with aversion getting highest weight (0.4)

### Priority 3: Time-Decay Tracking
- Track improvement over time windows
- Recent improvements count more

### Priority 4: Streak-Based Bonuses
- Reward consistent improvement
- Add small bonus for streaks

---

## Testing & Validation

### Test Cases

1. **No improvement:** `improvement = 0` → multiplier = 1.0
2. **Small improvement:** `improvement = 10` → multiplier ≈ 1.28
3. **Medium improvement:** `improvement = 30` → multiplier ≈ 1.63
4. **Large improvement:** `improvement = 60` → multiplier ≈ 1.86
5. **Maximum improvement:** `improvement = 100` → multiplier ≈ 1.97 (approaches 2.0)

### Validation Criteria

- ✅ Maximum multiplier = 2.0 (never exceeds)
- ✅ Minimum multiplier = 1.0 (never below)
- ✅ Smooth curve (no abrupt jumps)
- ✅ Diminishing returns (early improvements count more)
- ✅ Psychologically accurate (matches human perception)

---

## Future Enhancements

1. **Adaptive tuning:** Adjust k parameter based on user's improvement patterns
2. **Personalized baselines:** Use individual baselines instead of population averages
3. **Context-aware scaling:** Different formulas for different task types
4. **Machine learning:** Learn optimal scaling from user behavior data

---

**Last Updated:** 2024-12-XX
**Status:** Active Design Document

