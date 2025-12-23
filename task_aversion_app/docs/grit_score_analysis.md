# Grit Score Formula Analysis & Improvement Recommendations

## Current Formula Overview

The grit score measures **persistence and dedication** - the ability to stick with tasks even when they take longer than expected. It's intentionally separate from productivity score, which rewards efficiency.

### Current Formula Components

```python
base_score = completion_pct  # 0-100
persistence_multiplier = min(2.0, 1.0 + (completion_count - 1) * 0.1)  # 1.0x to 2.0x
time_bonus = 1.0 + ((time_ratio - 1.0) * 0.5) if time_ratio > 1.0 else 1.0  # 1.0x to unlimited
final_score = base_score * persistence_multiplier * time_bonus
```

## Design Intent Analysis

Based on the formula structure, the design intent appears to be:

1. **Reward Repetition**: Doing the same task multiple times shows commitment and habit formation
2. **Reward Perseverance**: Taking longer than estimated suggests you didn't give up when it got hard
3. **Separate from Efficiency**: Grit is about dedication, not speed (that's productivity's job)

**The core psychological concept**: Grit = passion + perseverance for long-term goals (Angela Duckworth's definition). Your formula captures:
- **Perseverance**: Persistence multiplier (doing it repeatedly)
- **Passion**: Time bonus (sticking with it even when it takes longer)

## Strengths of Current Formula

1. ✅ **Clear separation from productivity**: Doesn't reward efficiency, which is correct
2. ✅ **Persistence recognition**: Rewards repeated task completion (habit formation)
3. ✅ **Time bonus logic**: Taking longer can indicate dedication, not just poor planning
4. ✅ **Completion percentage base**: Partially completed tasks get partial credit (fair)

## Issues & Limitations

### 1. **Persistence Multiplier Cap is Too Low**

**Problem**: After 11 completions, additional completions provide zero benefit. Someone who completes a task 50 times gets the same persistence bonus as someone who completes it 11 times.

**Example**:
- 11 completions: 2.0x multiplier
- 50 completions: 2.0x multiplier (same!)

**Impact**: The formula doesn't distinguish between moderate persistence (11x) and extreme persistence (50x+). This might be intentional to prevent infinite growth, but it loses information.

**Recommendation**: Use a logarithmic or square-root scaling instead of a hard cap:
```python
# Option A: Logarithmic (diminishing returns, no hard cap)
persistence_multiplier = 1.0 + (math.log(completion_count) * 0.3)
# 1x: 1.0, 2x: 1.21, 5x: 1.48, 11x: 1.72, 50x: 2.17

# Option B: Square root (smoother than log, still capped)
persistence_multiplier = 1.0 + (math.sqrt(completion_count - 1) * 0.15)
# 1x: 1.0, 2x: 1.15, 5x: 1.30, 11x: 1.47, 50x: 2.06

# Option C: Keep cap but raise it
persistence_multiplier = min(3.0, 1.0 + (completion_count - 1) * 0.1)
# 1x: 1.0, 11x: 2.0, 21x: 3.0 (cap at 21 completions)
```

### 2. **Time Bonus Doesn't Consider Task Difficulty**

**Problem**: Taking 2x longer on an easy task (e.g., "wash dishes") gets the same bonus as taking 2x longer on a hard task (e.g., "write research paper"). The former might indicate poor time management, while the latter might indicate genuine grit.

**Example**:
- Easy task (difficulty=20): 2x longer = 1.5x bonus
- Hard task (difficulty=80): 2x longer = 1.5x bonus (same!)

**Impact**: The formula doesn't distinguish between "taking longer because task is hard" (grit) vs "taking longer because of poor planning" (not grit).

**Recommendation**: Weight time bonus by task difficulty:
```python
# Get task difficulty (0-100)
task_difficulty = float(actual_dict.get('task_difficulty', 50) or 
                        predicted_dict.get('task_difficulty', 50) or 50)
difficulty_factor = task_difficulty / 100.0  # 0.0 to 1.0

if time_ratio > 1.0:
    # Base time bonus
    base_time_bonus = 1.0 + ((time_ratio - 1.0) * 0.5)
    # Weight by difficulty: harder tasks get more credit for taking longer
    time_bonus = 1.0 + (base_time_bonus - 1.0) * (0.5 + 0.5 * difficulty_factor)
    # Easy task (difficulty=20): 2x longer = 1.3x bonus
    # Hard task (difficulty=80): 2x longer = 1.7x bonus
else:
    time_bonus = 1.0
```

### 3. **Time Bonus Has No Upper Bound**

**Problem**: Taking 10x longer gets a 5.5x time bonus, which can dominate the score. This might reward procrastination or poor planning rather than grit.

**Example**:
- Task estimated 30 min, takes 5 hours (10x): time_bonus = 5.5x
- This could indicate poor planning, not grit

**Recommendation**: Cap time bonus or use diminishing returns:
```python
if time_ratio > 1.0:
    excess_ratio = time_ratio - 1.0
    # Diminishing returns: first 2x gets full credit, beyond that gets less
    if excess_ratio <= 1.0:  # Up to 2x longer
        time_bonus = 1.0 + (excess_ratio * 0.5)
    else:  # Beyond 2x longer
        # Additional time gets diminishing returns
        additional_excess = excess_ratio - 1.0
        time_bonus = 1.5 + (additional_excess * 0.2)  # Slower growth
    # Cap at reasonable maximum (e.g., 3.0x for taking 8x longer)
    time_bonus = min(3.0, time_bonus)
else:
    time_bonus = 1.0
```

### 4. **No Consideration of Improvement Over Time**

**Problem**: The formula treats all completions equally. If someone gets faster over time (showing skill development), that's not recognized. However, this might be intentional since grit is about persistence, not improvement.

**Alternative perspective**: If grit = passion + perseverance, then showing improvement (getting better at a task you keep doing) could be part of grit.

**Recommendation**: This is optional - the current design is fine if grit is purely about persistence. But if you want to reward improvement:
```python
# Calculate average time ratio across all previous completions
# If current time_ratio is better than average, add small bonus
# This rewards "getting better at something you persist with"
```

### 5. **Partial Completion Still Gets High Score**

**Problem**: A task completed at 50% can still get a high grit score if it's been done many times and took a long time. This might be intentional (partial credit for partial effort), but it could also reward incomplete work.

**Example**:
- Task at 50% completion, done 10 times, took 2x longer
- Score = 50 * 1.9 * 1.5 = 142.5 (high score for incomplete work)

**Recommendation**: This is probably fine - partial completion with persistence still shows grit. But you could add a minimum completion threshold:
```python
# Only apply persistence multiplier if completion >= 80%
if completion_pct >= 80:
    persistence_multiplier = min(2.0, 1.0 + (completion_count - 1) * 0.1)
else:
    # Reduce persistence bonus for partial completions
    persistence_multiplier = min(1.5, 1.0 + (completion_count - 1) * 0.05)
```

## Recommended Improved Formula

Here's a suggested improved formula that addresses the main issues:

```python
def calculate_grit_score(self, row: pd.Series, task_completion_counts: Dict[str, int]) -> float:
    """Calculate grit score that rewards persistence and dedication.
    
    Improvements:
    1. Logarithmic persistence scaling (no hard cap, diminishing returns)
    2. Difficulty-weighted time bonus (harder tasks get more credit)
    3. Capped time bonus with diminishing returns (prevents extreme values)
    """
    try:
        actual_dict = row.get('actual_dict', {})
        predicted_dict = row.get('predicted_dict', {})
        task_id = row.get('task_id', '')
        
        if not isinstance(actual_dict, dict) or not isinstance(predicted_dict, dict):
            return 0.0
        
        # Get completion percentage and time data
        completion_pct = float(actual_dict.get('completion_percent', 100) or 100)
        time_actual = float(actual_dict.get('time_actual_minutes', 0) or 0)
        time_estimate = float(predicted_dict.get('time_estimate_minutes', 0) or 
                              predicted_dict.get('estimate', 0) or 0)
        
        # Get task difficulty (for weighting time bonus)
        task_difficulty = float(actual_dict.get('task_difficulty', 50) or 
                                predicted_dict.get('task_difficulty', 50) or 50)
        difficulty_factor = max(0.0, min(1.0, task_difficulty / 100.0))
        
        # Base score is completion percentage
        base_score = completion_pct
        
        # IMPROVEMENT 1: Logarithmic persistence multiplier (no hard cap)
        completion_count = task_completion_counts.get(task_id, 1)
        if completion_count <= 1:
            persistence_multiplier = 1.0
        else:
            # Logarithmic scaling: diminishing returns but no hard cap
            # 1x: 1.0, 2x: 1.21, 5x: 1.48, 11x: 1.72, 50x: 2.17
            persistence_multiplier = 1.0 + (math.log(completion_count) * 0.3)
            # Optional: Soft cap at 3.0x for very high counts
            persistence_multiplier = min(3.0, persistence_multiplier)
        
        # IMPROVEMENT 2 & 3: Difficulty-weighted time bonus with diminishing returns
        if time_estimate > 0 and time_actual > 0:
            time_ratio = time_actual / time_estimate
            if time_ratio > 1.0:
                excess_ratio = time_ratio - 1.0
                
                # Base time bonus with diminishing returns
                if excess_ratio <= 1.0:  # Up to 2x longer
                    base_time_bonus = 1.0 + (excess_ratio * 0.5)
                else:  # Beyond 2x longer
                    additional_excess = excess_ratio - 1.0
                    base_time_bonus = 1.5 + (additional_excess * 0.2)
                
                # Cap at 3.0x maximum
                base_time_bonus = min(3.0, base_time_bonus)
                
                # Weight by difficulty: harder tasks get more credit
                # Easy task (difficulty=20): time_bonus closer to 1.0
                # Hard task (difficulty=80): time_bonus gets full value
                time_bonus = 1.0 + (base_time_bonus - 1.0) * (0.5 + 0.5 * difficulty_factor)
            else:
                time_bonus = 1.0
        else:
            time_bonus = 1.0
        
        # Final score = base * persistence * time_bonus
        score = base_score * persistence_multiplier * time_bonus
        
        return score
    
    except (KeyError, TypeError, ValueError, AttributeError) as e:
        return 0.0
```

## Comparison: Current vs. Improved

| Scenario | Current Formula | Improved Formula | Rationale |
|----------|----------------|------------------|-----------|
| Easy task, 2x longer, 5 completions | 100 * 1.4 * 1.5 = 210 | 100 * 1.48 * 1.25 = 185 | Harder tasks get more credit for taking longer |
| Hard task, 2x longer, 5 completions | 100 * 1.4 * 1.5 = 210 | 100 * 1.48 * 1.75 = 259 | Difficulty weighting rewards genuine grit |
| Task, 10x longer, 2 completions | 100 * 1.1 * 5.5 = 605 | 100 * 1.21 * 2.5 = 303 | Capped time bonus prevents extreme values |
| Task, 50 completions | 100 * 2.0 * 1.0 = 200 | 100 * 2.17 * 1.0 = 217 | Logarithmic scaling recognizes extreme persistence |

## Alternative Formula (If You Want to Reward Improvement)

If you want grit to also recognize improvement over time:

```python
# Calculate improvement bonus (optional)
# Compare current time_ratio to average time_ratio for this task
# If getting faster over time, add small bonus (shows skill development)

avg_time_ratio = calculate_average_time_ratio(task_id)  # From previous instances
if avg_time_ratio > 0 and time_ratio < avg_time_ratio:
    # Getting faster = improving = part of grit
    improvement_factor = (avg_time_ratio - time_ratio) / avg_time_ratio
    improvement_bonus = 1.0 + (improvement_factor * 0.2)  # Max 1.2x
else:
    improvement_bonus = 1.0

score = base_score * persistence_multiplier * time_bonus * improvement_bonus
```

## Recommendation

**Keep the current formula's core design** (persistence + time bonus), but implement these improvements:

1. ✅ **Use logarithmic persistence scaling** (addresses issue #1)
2. ✅ **Add difficulty-weighted time bonus** (addresses issue #2)
3. ✅ **Cap time bonus with diminishing returns** (addresses issue #3)

**Don't change**:
- Base score = completion percentage (fair for partial work)
- Separate from productivity (correct design)
- Time bonus only for taking longer (correct for grit concept)

The improved formula maintains your design intent while making it more nuanced and preventing edge cases from dominating the score.

