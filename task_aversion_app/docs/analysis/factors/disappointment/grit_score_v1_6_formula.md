# Grit Score v1.6 Formula: Exact Implementation

## Version Number

**Current Version**: v1.6 (was incorrectly marked as v1.3 in code comments)

**Reasoning**:
- v1.2: Added persistence_factor and focus_factor
- v1.3: Separate function (perseverance/persistence separation)
- v1.4: Added synergy multiplier
- v1.5a/b/c: Hybrid thresholds with SD-based bonuses (separate functions)
- **v1.6**: Added disappointment resilience to main `calculate_grit_score()` function

## Exact Formula

### Complete Formula

```
grit_score = base_score × persistence_factor_scaled × focus_factor_scaled × passion_factor × time_bonus × disappointment_resilience
```

Where:
- `base_score = completion_pct` (0-100, can exceed 100 for over-completion)
- `persistence_factor_scaled = 0.5 + persistence_factor × 1.0` (range: 0.5-1.5)
- `focus_factor_scaled = 0.5 + focus_factor × 1.0` (range: 0.5-1.5)
- `passion_factor = 1.0 + (relief_norm - emotional_norm) × 0.5` (range: 0.5-1.5)
- `time_bonus = 1.0+` (range: 1.0-3.0, difficulty-weighted, fades with repetition)
- `disappointment_resilience = 0.67-1.5` (NEW in v1.6)

### Disappointment Resilience Component

```python
disappointment_resilience = 1.0  # Default (no disappointment)

if disappointment_factor > 0:
    if completion_pct >= 100.0:
        # Persistent disappointment: reward completing despite disappointment
        disappointment_resilience = 1.0 + (disappointment_factor / 200.0)
        disappointment_resilience = min(1.5, disappointment_resilience)  # Cap at 1.5x
    else:
        # Abandonment disappointment: penalize giving up due to disappointment
        disappointment_resilience = 1.0 - (disappointment_factor / 300.0)
        disappointment_resilience = max(0.67, disappointment_resilience)  # Cap at 0.67x
```

## Design Question: Multiplicative vs Additive

### Current Implementation: **Multiplicative**

The disappointment resilience **multiplies the entire grit score**:

```
grit_score = base_score × (all_factors) × disappointment_resilience
```

**Impact**: 
- If disappointment_resilience = 1.5x, the **entire grit score** is multiplied by 1.5
- This means disappointment resilience affects the final score proportionally

### Alternative: Additive Component

Could be implemented as:

```
grit_score = base_score × (other_factors) + disappointment_bonus
```

Where `disappointment_bonus` is a fixed amount added to the score.

### Alternative: Weighted Component

Could be implemented as:

```
grit_score = base_score × (weighted_sum_of_factors)
```

Where disappointment is one factor in a weighted sum.

## Analysis: Why Multiplicative?

### Pros of Multiplicative Approach (Current)

1. **Proportional Impact**: Disappointment resilience scales with the base score
   - High-performing tasks get larger absolute bonuses
   - Low-performing tasks get smaller absolute bonuses
   - Maintains relative differences

2. **Consistent with Other Factors**: All other factors (persistence, focus, passion, time) are multiplicative
   - Maintains formula consistency
   - All factors interact multiplicatively

3. **Theoretical Alignment**: Disappointment resilience is a **modifier** of grit, not a separate component
   - It modifies how we interpret the grit demonstrated
   - Multiplicative approach reflects this interpretation

### Cons of Multiplicative Approach

1. **Amplification Effect**: High disappointment can significantly amplify already high scores
   - A task with base_score=150, all factors=1.2x, disappointment=1.5x → 150 × 1.2^4 × 1.5 = **388.8**
   - This might be too high

2. **Interaction Complexity**: Multiplicative factors interact in complex ways
   - Harder to predict final score
   - Can create unexpected interactions

### Recommendation

**Keep multiplicative approach** for consistency, but consider:

1. **Lower the cap**: Reduce max disappointment_resilience from 1.5x to 1.3x (30% bonus instead of 50%)
2. **Or use additive bonus**: Add a fixed bonus amount instead of multiplying
3. **Or weighted component**: Make disappointment a smaller weighted component

## Example Calculations

### Example 1: High Disappointment, Full Completion

**Inputs**:
- `completion_pct = 100`
- `persistence_factor_scaled = 1.2`
- `focus_factor_scaled = 1.1`
- `passion_factor = 1.0`
- `time_bonus = 1.5`
- `disappointment_factor = 60` (high disappointment)

**Calculation**:
- `disappointment_resilience = 1.0 + (60/200) = 1.3x`
- `grit_score = 100 × 1.2 × 1.1 × 1.0 × 1.5 × 1.3 = 257.4`

**Impact**: Disappointment resilience adds **30%** to the final score (257.4 vs 198 without it)

### Example 2: High Disappointment, Partial Completion

**Inputs**:
- `completion_pct = 50`
- `persistence_factor_scaled = 1.2`
- `focus_factor_scaled = 1.1`
- `passion_factor = 0.9` (reduced for partial completion)
- `time_bonus = 1.0`
- `disappointment_factor = 60`

**Calculation**:
- `disappointment_resilience = 1.0 - (60/300) = 0.8x`
- `grit_score = 50 × 1.2 × 1.1 × 0.9 × 1.0 × 0.8 = 47.5`

**Impact**: Disappointment resilience reduces score by **20%** (47.5 vs 59.4 without it)

## Proposed Changes

### Option 1: Keep Multiplicative, Lower Cap

```python
# Persistent disappointment: cap at 1.3x instead of 1.5x
disappointment_resilience = 1.0 + (disappointment_factor / 250.0)  # Slower scaling
disappointment_resilience = min(1.3, disappointment_resilience)  # Cap at 1.3x
```

### Option 2: Additive Bonus

```python
# Add fixed bonus instead of multiplying
disappointment_bonus = 0.0
if disappointment_factor > 0 and completion_pct >= 100.0:
    disappointment_bonus = min(20.0, disappointment_factor / 5.0)  # Max +20 points

grit_score = base_score × (other_factors) + disappointment_bonus
```

### Option 3: Weighted Component

```python
# Make disappointment a weighted component
disappointment_component = 0.0
if disappointment_factor > 0:
    if completion_pct >= 100.0:
        disappointment_component = (disappointment_factor / 100.0) * 0.2  # 20% weight
    else:
        disappointment_component = -(disappointment_factor / 100.0) * 0.15  # 15% penalty

grit_score = base_score × (other_factors) × (1.0 + disappointment_component)
```

## Recommendation

**Keep multiplicative approach** but **reduce the cap to 1.3x** (30% bonus) to prevent excessive amplification:

```python
if completion_pct >= 100.0:
    disappointment_resilience = 1.0 + (disappointment_factor / 250.0)  # Slower scaling
    disappointment_resilience = min(1.3, disappointment_resilience)  # Cap at 30% bonus
```

This maintains consistency with other factors while preventing excessive score inflation.

## Version History

- **v1.6** (2026-01-05): Added disappointment resilience factor (multiplicative)
  - Rewards persistent disappointment (completion >= 100%)
  - Penalizes abandonment disappointment (completion < 100%)
  - Multiplies entire grit score (consistent with other factors)
