# Factors Concept

## Overview

Factors are well-defined, measurable values that influence or modify other calculations in analytical formulas. They provide a foundation for incorporating various influences (emotional, performance, difficulty, etc.) into formulas in a consistent, interpretable way.

This document focuses on **emotional factors** (serendipity and disappointment) as a concrete example, but the concept applies broadly to any factor used in formulas.

## Core Emotional Factors

### 1. Serendipity Factor
**Definition:** Measures pleasant surprise when actual relief exceeds expectations

**Formula:**
```python
serendipity_factor = max(0, net_relief)
# Where net_relief = actual_relief - expected_relief
```

**Range:** 0-100
- **0:** No pleasant surprise (actual ≤ expected)
- **1-100:** Degree of pleasant surprise (actual > expected)

**Characteristics:**
- Only positive when net_relief > 0
- Zero when net_relief ≤ 0
- Represents positive emotional experience
- **Not a standalone score** - used as a factor/component in formulas

**Use Cases:**
- Reward tasks that exceed expectations
- Identify tasks that are more rewarding than anticipated
- Boost scores for pleasant surprises
- Track positive prediction errors

### 2. Disappointment Factor
**Definition:** Measures disappointment when actual relief falls short of expectations

**Formula:**
```python
disappointment_factor = max(0, -net_relief)
# Where net_relief = actual_relief - expected_relief
```

**Range:** 0-100
- **0:** No disappointment (actual ≥ expected)
- **1-100:** Degree of disappointment (actual < expected)

**Characteristics:**
- Only positive when net_relief < 0
- Zero when net_relief ≥ 0
- Stored as positive value for easier formula integration
- Represents negative emotional experience
- **Not a standalone score** - used as a factor/component in formulas

**Use Cases:**
- Penalize tasks that fall short of expectations
- Identify tasks that are less rewarding than anticipated
- Reduce scores for disappointments
- Track negative prediction errors

## Design Principles

### 1. Sign Separation
- **Serendipity** and **Disappointment** are separate factors
- Each defaults to zero when the wrong sign is present
- This allows independent weighting and handling in formulas

### 2. Non-Negative Values
- Both factors are always ≥ 0
- Makes them easier to use in formulas (no need to handle negative values)
- Can be used directly as multipliers, bonuses, or penalties

### 3. Interpretable Range
- Both use 0-100 scale (matching net_relief range)
- Easy to understand: 0 = none, 100 = maximum
- Can be normalized or scaled as needed

### 4. Complementary Nature
- `serendipity_factor + disappointment_factor = |net_relief|`
- When one is positive, the other is zero
- Together they capture the full emotional spectrum of prediction accuracy

### 5. Factor vs Score Distinction
- **Factor:** A value that influences or modifies other calculations (e.g., `serendipity_factor`, `disappointment_factor`, `passion_factor`, `difficulty_factor`)
- **Score:** A final calculated result (e.g., `productivity_score`, `grit_score`, `composite_score`)
- Emotional factors are **factors**, not standalone scores
- They are used as components in formulas, similar to other factors in the system

## Formula Integration Patterns

### Pattern 1: Bonus for Serendipity
Reward tasks that exceed expectations:

```python
# Example: Enhanced productivity score
base_score = calculate_base_productivity_score()
serendipity_bonus = serendipity_factor * 0.1  # 10% of serendipity factor
enhanced_score = base_score + serendipity_bonus
```

**Interpretation:** Tasks that exceed expectations get a bonus proportional to the pleasant surprise.

### Pattern 2: Penalty for Disappointment
Reduce scores for tasks that fall short:

```python
# Example: Adjusted wellbeing score
base_wellbeing = calculate_base_wellbeing()
disappointment_penalty = disappointment_factor * 0.15  # 15% of disappointment factor
adjusted_wellbeing = base_wellbeing - disappointment_penalty
```

**Interpretation:** Tasks that disappoint reduce wellbeing more than neutral tasks.

### Pattern 3: Balanced Emotional Factor
Combine both for overall emotional impact:

```python
# Example: Emotional adjustment factor
emotional_factor = 1.0 + (serendipity_factor / 200.0) - (disappointment_factor / 150.0)
# Serendipity adds up to 50% bonus, disappointment reduces up to 66%
adjusted_score = base_score * emotional_factor
```

**Interpretation:** Pleasant surprises boost scores more than disappointments reduce them (asymmetric weighting).

### Pattern 4: Conditional Enhancement
Only apply when significant:

```python
# Example: Grit score enhancement
base_grit = calculate_grit_score()
if serendipity_factor > 20:  # Significant pleasant surprise
    serendipity_multiplier = 1.0 + (serendipity_factor / 100.0)
    enhanced_grit = base_grit * serendipity_multiplier
else:
    enhanced_grit = base_grit
```

**Interpretation:** Only apply emotional adjustments when they're meaningful.

### Pattern 5: Emotional Resilience
Track how disappointment affects future performance:

```python
# Example: Disappointment impact on future tasks
recent_disappointment = calculate_recent_disappointment_avg()
resilience_factor = 1.0 - (recent_disappointment / 200.0)  # Up to 50% reduction
future_task_adjustment = base_score * resilience_factor
```

**Interpretation:** Recent disappointments may reduce motivation for similar tasks.

## Example: Enhanced Grit Score

Here's how emotional factors could enhance the existing grit score:

```python
def calculate_enhanced_grit_score(row, task_completion_counts):
    """Grit score with emotional variable integration."""
    # Base grit score (existing calculation)
    base_grit = calculate_grit_score(row, task_completion_counts)
    
    # Get emotional variables (factors, not standalone scores)
    serendipity = row.get('serendipity_factor', 0.0)
    disappointment = row.get('disappointment_factor', 0.0)
    
    # Emotional adjustment
    # Serendipity boosts grit (pleasant surprises increase commitment)
    serendipity_bonus = serendipity * 0.05  # 5% of serendipity factor
    
    # Disappointment reduces grit (disappointments reduce commitment)
    disappointment_penalty = disappointment * 0.08  # 8% of disappointment factor
    
    # Apply emotional factors
    emotional_adjustment = serendipity_bonus - disappointment_penalty
    enhanced_grit = base_grit + emotional_adjustment
    
    return max(0.0, enhanced_grit)
```

**Rationale:**
- Pleasant surprises increase commitment (serendipity bonus)
- Disappointments reduce commitment (disappointment penalty)
- Asymmetric weighting: disappointments have stronger impact

## Example: Enhanced Wellbeing Score

```python
def calculate_emotional_wellbeing(relief_score, stress_level, serendipity, disappointment):
    """Wellbeing with emotional variable integration."""
    # Base net wellbeing
    base_wellbeing = relief_score - stress_level
    
    # Emotional adjustments
    # Serendipity enhances wellbeing (pleasant surprises feel good)
    serendipity_boost = serendipity * 0.3  # 30% of serendipity factor
    
    # Disappointment reduces wellbeing (disappointments feel bad)
    disappointment_cost = disappointment * 0.4  # 40% of disappointment factor
    
    # Emotional wellbeing
    emotional_wellbeing = base_wellbeing + serendipity_boost - disappointment_cost
    
    return emotional_wellbeing
```

**Rationale:**
- Serendipity adds to wellbeing (positive emotional experience)
- Disappointment subtracts from wellbeing (negative emotional experience)
- Disappointment has stronger impact (loss aversion)

## Integration Guidelines

### 1. Start Conservative
- Use small weights initially (0.05-0.15)
- Test impact before increasing
- Monitor for unintended effects

### 2. Consider Context
- Some formulas may benefit more from emotional factors than others
- Productivity scores might use serendipity differently than wellbeing scores
- Consider task type and user goals

### 3. Maintain Balance
- Don't let emotional factors dominate base calculations
- Keep base scores meaningful without emotional adjustments
- Emotional factors should enhance, not replace, core metrics

### 4. Document Rationale
- Explain why emotional factors are included
- Document weights and their justification
- Track how emotional adjustments affect overall scores

### 5. Test Asymmetry
- Consider whether serendipity and disappointment should have equal weights
- Loss aversion suggests disappointments may have stronger impact
- Test different weight ratios to find optimal balance

## Other Factors in the System

This concept extends beyond emotional factors. The system uses various factors:

### Performance Factors
- `passion_factor`: Relief vs emotional load (used in grit score)
- `difficulty_factor`: Task difficulty weighting
- `improvement_multiplier`: Progress over time
- `persistence_multiplier`: Task repetition bonus

### Adjustment Factors
- `penalty_factor`: Reductions for negative outcomes
- `smooth_factor`: Transition smoothing
- `time_bonus`: Time-based adjustments

### Pattern
All factors follow similar principles:
- They influence or modify other calculations
- They are not standalone scores
- They can be combined, weighted, or conditionally applied
- They should be well-documented and justified

## Future Extensions

### Additional Emotional Factors
This concept can be extended to other emotional dimensions:

1. **Anticipation Factor:** Based on expected relief before task
2. **Satisfaction Factor:** Based on actual relief after task
3. **Regret Factor:** Based on tasks not completed
4. **Pride Factor:** Based on overcoming obstacles
5. **Anxiety Factor:** Based on stress before task

### Factor Combinations
- **Emotional Balance:** `serendipity_factor - disappointment_factor` (net emotional impact)
- **Emotional Volatility:** `serendipity_factor + disappointment_factor` (total emotional variation)
- **Emotional Consistency:** `1 - (volatility / 100)` (how consistent predictions are)

## References

- See `relief_stress_formulas.md` for net relief calculation
- See `analytics.py` for implementation details
- See `relief_comparison_analytics.py` for visualization
