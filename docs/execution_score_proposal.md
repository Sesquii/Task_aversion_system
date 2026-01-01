# Execution Score Proposal
## Addressing Under-Rewarded Fast, High-Difficulty Tasks

## Problem Analysis

### Current Scoring Gaps for Fast, High-Difficulty Tasks

#### 1. Productivity Score Limitations
**Location:** `backend/analytics.py:450-627`

**Current Behavior:**
- Work tasks: Multiplier 3.0x to 5.0x based on `completion_time_ratio`
  - Ratio = `(completion_pct * time_estimate) / (100.0 * time_actual)`
  - Fast completion (low `time_actual`) → higher ratio → up to 5.0x multiplier
- **Gap:** Fast completion is rewarded, but difficulty is NOT factored into productivity score
- A fast, easy task gets the same 5.0x multiplier as a fast, hard task

**Example:**
- Task A: Easy (aversion=20, load=30), completed in 10 min (estimated 30 min) → 5.0x multiplier
- Task B: Hard (aversion=80, load=70), completed in 10 min (estimated 30 min) → 5.0x multiplier
- **Problem:** Both get same reward despite vastly different difficulty

#### 2. Grit Score Penalizes Fast Completion
**Location:** `backend/analytics.py:628-703`

**Current Behavior:**
- Time bonus ONLY applies when `time_ratio > 1.0` (taking longer than estimated)
- Fast completion (`time_ratio < 1.0`) gets `time_bonus = 1.0` (no bonus)
- **Gap:** Fast completion of difficult tasks gets no recognition in grit score

**Example:**
- Hard task (aversion=80) completed in 15 min (estimated 60 min) → `time_ratio = 0.25` → `time_bonus = 1.0` (no bonus)
- Same hard task taking 90 min (estimated 60 min) → `time_ratio = 1.5` → `time_bonus = 1.25x` (bonus)

#### 3. Difficulty Bonus Doesn't Consider Speed
**Location:** `backend/analytics.py:24-80`

**Current Behavior:**
- `calculate_difficulty_bonus()` rewards high aversion + high load
- Formula: `bonus = 1.0 * (1 - exp(-(0.7 * aversion + 0.3 * load) / 50))`
- **Gap:** Same bonus whether task takes 5 minutes or 5 hours
- No recognition for completing difficult tasks quickly

#### 4. Missing: Start Speed Factor
**Available Data:**
- `initialized_at` - when task was initialized
- `started_at` - when task was started (optional)
- `completed_at` - when task was completed
- `delay_minutes` - calculated delay (if available)

**Gap:** No score rewards:
- Starting tasks quickly after initialization (overcoming procrastination)
- Completing tasks quickly after starting (execution efficiency)

## Proposed Solution: Execution Score

### Purpose
Reward **efficient execution of difficult tasks**, capturing:
1. **High aversion** - Task was hard to face
2. **High cognitive load** - Task required significant mental effort
3. **Fast execution** - Completed quickly relative to estimate
4. **Fast start** - Started quickly after initialization (overcoming procrastination)
5. **Clear completion** - Completed fully (100% or close)

### Orthogonality to Existing Metrics

**Execution Score is orthogonal because:**
- **Productivity Score** measures efficiency (time ratio) but ignores difficulty
- **Grit Score** rewards persistence and taking longer, opposite of execution speed
- **Difficulty Bonus** rewards difficulty but ignores speed
- **Execution Score** combines difficulty + speed (unique combination)

**Integration Strategy:**
- Execution score can be added as a **separate component** to composite score
- Default weight: 1.0 (same as other components)
- Can be used as a **multiplier** for productivity score (optional)
- Does NOT replace existing metrics, complements them

### Formula Design

#### Core Components

```python
def calculate_execution_score(
    current_aversion: Optional[float],
    stress_level: Optional[float] = None,
    mental_energy: Optional[float] = None,
    task_difficulty: Optional[float] = None,
    time_actual_minutes: Optional[float] = None,
    time_estimate_minutes: Optional[float] = None,
    completion_percent: Optional[float] = None,
    initialized_at: Optional[str] = None,
    started_at: Optional[str] = None,
    completed_at: Optional[str] = None
) -> float:
    """
    Calculate execution score (0-100) for efficient execution of difficult tasks.
    
    Components:
    1. Difficulty factor (0-1): High aversion + high load
    2. Speed factor (0-1): Fast execution relative to estimate
    3. Start speed factor (0-1): Fast start after initialization
    4. Completion factor (0-1): Full completion (100%)
    
    Formula: execution_score = base_score * difficulty_factor * speed_factor * start_speed_factor * completion_factor
    
    Returns:
        Execution score (0-100), higher = better execution
    """
```

#### Component Formulas

**1. Difficulty Factor** (reuse existing logic)
```python
# Use existing calculate_difficulty_bonus() but normalize to 0-1
difficulty_factor = calculate_difficulty_bonus(
    current_aversion=current_aversion,
    stress_level=stress_level,
    mental_energy=mental_energy,
    task_difficulty=task_difficulty
)
# Already returns 0.0-1.0, use directly
```

**2. Speed Factor** (execution efficiency)
```python
if time_estimate > 0 and time_actual > 0:
    time_ratio = time_actual / time_estimate
    
    if time_ratio <= 0.5:
        # Very fast: 2x speed or faster → max bonus
        speed_factor = 1.0
    elif time_ratio <= 1.0:
        # Fast: completed within estimate → linear bonus
        # 0.5 → 1.0, 1.0 → 0.5
        speed_factor = 1.0 - (time_ratio - 0.5) * 1.0  # 0.5 to 1.0 range
    else:
        # Slow: exceeded estimate → diminishing penalty
        # 1.0 → 0.5, 2.0 → 0.25, 3.0 → 0.125
        speed_factor = 0.5 * (1.0 / time_ratio)
else:
    speed_factor = 0.5  # Neutral if no time data
```

**3. Start Speed Factor** (procrastination resistance)
```python
# Calculate time from initialization to start (or completion if no start)
if initialized_at and completed_at:
    init_time = pd.to_datetime(initialized_at)
    complete_time = pd.to_datetime(completed_at)
    total_delay_minutes = (complete_time - init_time).total_seconds() / 60.0
    
    if started_at:
        start_time = pd.to_datetime(started_at)
        start_delay_minutes = (start_time - init_time).total_seconds() / 60.0
    else:
        # No start time: use completion time as proxy
        start_delay_minutes = total_delay_minutes
    
    # Normalize: fast start = high score
    # Ideal: start within 5 minutes → 1.0
    # Good: start within 30 minutes → 0.8
    # Acceptable: start within 2 hours → 0.5
    # Poor: start after 2 hours → diminishing
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
        excess = start_delay_minutes - 120
        start_speed_factor = 0.5 * math.exp(-excess / 240.0)
else:
    start_speed_factor = 0.5  # Neutral if no timing data
```

**4. Completion Factor** (quality of completion)
```python
completion_pct = completion_percent or 100.0
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

#### Combined Formula

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
```

### Example Calculations

#### Example 1: Fast, High-Difficulty Task (Ideal Execution)
- Aversion: 80, Load: 70
- Time: 15 min (estimated 60 min) → `time_ratio = 0.25`
- Start delay: 5 minutes
- Completion: 100%

**Calculation:**
- `difficulty_factor = 0.85` (high difficulty)
- `speed_factor = 1.0` (very fast)
- `start_speed_factor = 1.0` (fast start)
- `completion_factor = 1.0` (full completion)
- `execution_score = 50 * (1.0 + 0.85) * (0.5 + 1.0*0.5) * (0.5 + 1.0*0.5) * 1.0`
- `execution_score = 50 * 1.85 * 1.0 * 1.0 * 1.0 = 92.5`

**Result:** High score (92.5) - rewards efficient execution of difficult task

#### Example 2: Slow, High-Difficulty Task
- Aversion: 80, Load: 70
- Time: 120 min (estimated 60 min) → `time_ratio = 2.0`
- Start delay: 180 minutes
- Completion: 100%

**Calculation:**
- `difficulty_factor = 0.85` (high difficulty)
- `speed_factor = 0.25` (slow: 2x estimate)
- `start_speed_factor = 0.4` (delayed start)
- `completion_factor = 1.0` (full completion)
- `execution_score = 50 * 1.85 * 0.75 * 0.7 * 1.0 = 48.6`

**Result:** Lower score (48.6) - difficulty recognized but speed penalized

#### Example 3: Fast, Easy Task
- Aversion: 20, Load: 30
- Time: 10 min (estimated 30 min) → `time_ratio = 0.33`
- Start delay: 5 minutes
- Completion: 100%

**Calculation:**
- `difficulty_factor = 0.25` (low difficulty)
- `speed_factor = 1.0` (very fast)
- `start_speed_factor = 1.0` (fast start)
- `completion_factor = 1.0` (full completion)
- `execution_score = 50 * 1.25 * 1.0 * 1.0 * 1.0 = 62.5`

**Result:** Moderate score (62.5) - fast but easy, so lower than difficult fast task

### Integration Points

#### 1. Add to Composite Score
```python
# In calculate_composite_score()
components = {
    'tracking_consistency_score': ...,
    'execution_score': calculate_execution_score(...),  # NEW
    # ... other components
}
```

#### 2. Optional: Multiplier for Productivity Score
```python
# Apply execution score as multiplier to productivity
execution_multiplier = 1.0 + (execution_score / 100.0) * 0.5  # 1.0-1.5x range
adjusted_productivity = productivity_score * execution_multiplier
```

#### 3. Standalone Metric
- Display in analytics dashboard
- Track over time
- Use for recommendations (prioritize tasks with high execution potential)

### Calibration Parameters

**Tunable Parameters:**
```python
EXECUTION_SCORE_CONFIG = {
    'base_score': 50.0,                    # Base points
    'difficulty_weight': 1.0,               # Weight for difficulty factor
    'speed_weight': 0.5,                   # Weight for speed factor
    'start_speed_weight': 0.5,              # Weight for start speed factor
    'completion_weight': 1.0,               # Weight for completion factor
    'fast_threshold_ratio': 0.5,            # Ratio below which = "very fast"
    'fast_start_minutes': 5,                # Start within 5 min = perfect
    'good_start_minutes': 30,               # Start within 30 min = good
    'acceptable_start_minutes': 120,        # Start within 2 hours = acceptable
}
```

### Benefits

1. **Addresses Gap:** Fast, high-difficulty tasks now get proper recognition
2. **Orthogonal:** Doesn't destabilize existing metrics
3. **Comprehensive:** Captures difficulty, speed, start speed, and completion
4. **Calibratable:** All parameters can be tuned via score calibration system
5. **Actionable:** Encourages fast starts and efficient execution

### Implementation Plan

1. **Add `calculate_execution_score()` method** to `Analytics` class
2. **Integrate with composite score** as new component
3. **Add to analytics dashboard** for visibility
4. **Calibrate parameters** using score calibration system
5. **Document** in score calibration plan

### Next Steps

1. Review and approve this proposal
2. Implement `calculate_execution_score()` function
3. Add execution score to composite score components
4. Test with sample data
5. Calibrate parameters via score calibration dashboard

