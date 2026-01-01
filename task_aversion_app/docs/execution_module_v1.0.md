# Execution Module Formulas v1.0

**Version:** 1.0  
**Last Updated:** 2024  
**Status:** Production-Ready

## Overview

The Execution Score module rewards efficient execution of difficult tasks by combining four component factors:
1. **Difficulty Factor** - Measures task difficulty (high aversion + high cognitive load)
2. **Speed Factor** - Measures execution efficiency relative to time estimate
3. **Start Speed Factor** - Measures procrastination resistance (how quickly task was started)
4. **Completion Factor** - Measures quality of completion (full vs partial)

## Core Formula

```
execution_score = base_score × (1.0 + difficulty_factor) × 
                  (0.5 + speed_factor × 0.5) × 
                  (0.5 + start_speed_factor × 0.5) × 
                  completion_factor
```

**Where:**
- `base_score = 50.0` (neutral starting point)
- All factors range from 0.0 to 1.0 (except difficulty_factor which is added to 1.0)
- Final score is clamped to 0-100 range

## Component Formulas

### 1. Difficulty Factor

**Purpose:** Rewards completing difficult tasks (high aversion + high cognitive load)

**Formula:**
```python
difficulty_factor = 1.0 × (1 - exp(-(w_aversion × aversion + w_load × load) / k))
```

**Parameters:**
- `w_aversion = 0.7` (weight for aversion)
- `w_load = 0.3` (weight for cognitive load)
- `k = 50.0` (exponential decay constant)

**Inputs:**
- `aversion`: Current aversion value (0-100)
- `load`: Cognitive load (0-100), calculated from:
  - Preferred: `stress_level` (if available)
  - Fallback: `(mental_energy + task_difficulty) / 2.0`

**Output Range:** 0.0 to 1.0

**Characteristics:**
- Exponential scaling with smooth curve
- Higher weight to aversion (0.7) vs load (0.3)
- Approaches 1.0 at high difficulty levels
- Max bonus = 1.0 (multiplier ranges 1.0 to 2.0)

**Examples:**
- Aversion=50, Load=50 → Factor=0.63 (63% bonus)
- Aversion=100, Load=100 → Factor=0.86 (86% bonus)

**Implementation Location:** `backend/analytics.py:calculate_difficulty_bonus()`

---

### 2. Speed Factor

**Purpose:** Measures execution efficiency relative to time estimate

**Formula (Piecewise):**
```python
time_ratio = time_actual / time_estimate

if time_ratio <= 0.5:
    # Very fast: 2x speed or faster → max bonus
    speed_factor = 1.0
elif time_ratio <= 1.0:
    # Fast: completed within estimate → linear bonus
    # 0.5 → 1.0, 1.0 → 0.5
    speed_factor = 1.0 - (time_ratio - 0.5) × 1.0
else:
    # Slow: exceeded estimate → diminishing penalty
    # 1.0 → 0.5, 2.0 → 0.25, 3.0 → 0.125
    speed_factor = 0.5 × (1.0 / time_ratio)
```

**Inputs:**
- `time_actual`: Actual completion time in minutes
- `time_estimate`: Estimated completion time in minutes

**Output Range:** 0.0 to 1.0

**Characteristics:**
- Rewards fast completion (2x speed or faster = max)
- Linear bonus for completing within estimate
- Exponential decay penalty for exceeding estimate
- Neutral (0.5) if no time data available

**Examples:**
- Completed in 15 min (estimated 60 min) → Ratio=0.25 → Factor=1.0
- Completed in 30 min (estimated 60 min) → Ratio=0.5 → Factor=1.0
- Completed in 60 min (estimated 60 min) → Ratio=1.0 → Factor=0.5
- Completed in 120 min (estimated 60 min) → Ratio=2.0 → Factor=0.25

**Implementation Location:** `backend/analytics.py:calculate_execution_score()` (lines 2523-2543)

---

### 3. Start Speed Factor

**Purpose:** Measures procrastination resistance - how quickly task was started after initialization

**Formula (Piecewise):**
```python
start_delay_minutes = (started_at - initialized_at) / 60.0

if start_delay_minutes <= 5:
    start_speed_factor = 1.0
elif start_delay_minutes <= 30:
    # Linear: 5 min → 1.0, 30 min → 0.8
    start_speed_factor = 1.0 - ((start_delay_minutes - 5) / 25.0) × 0.2
elif start_delay_minutes <= 120:
    # Linear: 30 min → 0.8, 120 min → 0.5
    start_speed_factor = 0.8 - ((start_delay_minutes - 30) / 90.0) × 0.3
else:
    # Exponential decay: 120 min → 0.5, 480 min → ~0.125
    excess = start_delay_minutes - 120
    start_speed_factor = 0.5 × exp(-excess / 240.0)
```

**Inputs:**
- `initialized_at`: Timestamp when task was initialized
- `started_at`: Timestamp when task was started
- Fallback: Uses `completed_at` if `started_at` is not available

**Output Range:** 0.0 to 1.0

**Characteristics:**
- Rewards fast starts (≤5 minutes = perfect)
- Linear decay for moderate delays (5-120 minutes)
- Exponential decay for long delays (>120 minutes)
- Neutral (0.5) if no timestamp data available

**Examples:**
- Started 2 min after initialization → Factor=1.0
- Started 10 min after initialization → Factor=0.96
- Started 45 min after initialization → Factor=0.72
- Started 3 hours after initialization → Factor=0.35
- Started 6 hours after initialization → Factor=0.18

**Implementation Location:** `backend/analytics.py:calculate_execution_score()` (lines 2545-2586)

---

### 4. Completion Factor

**Purpose:** Measures quality of completion (full vs partial)

**Formula (Piecewise):**
```python
completion_pct = actual_dict.get('completion_percent', 100)

if completion_pct >= 100.0:
    completion_factor = 1.0
elif completion_pct >= 90.0:
    # Near-complete: slight penalty
    completion_factor = 0.9 + (completion_pct - 90.0) / 10.0 × 0.1
elif completion_pct >= 50.0:
    # Partial: moderate penalty
    completion_factor = 0.5 + (completion_pct - 50.0) / 40.0 × 0.4
else:
    # Low completion: significant penalty
    completion_factor = completion_pct / 50.0 × 0.5
```

**Inputs:**
- `completion_percent`: Completion percentage (0-100)

**Output Range:** 0.0 to 1.0

**Characteristics:**
- Full completion (100%) = max score
- Near-complete (90-100%) = slight penalty
- Partial (50-90%) = moderate penalty
- Low completion (<50%) = significant penalty

**Examples:**
- 100% completed → Factor=1.0
- 95% completed → Factor=0.95
- 60% completed → Factor=0.6
- 25% completed → Factor=0.25

**Implementation Location:** `backend/analytics.py:calculate_execution_score()` (lines 2588-2601)

---

## Combined Execution Score Calculation

**Full Formula:**
```python
base_score = 50.0

execution_score = base_score × (
    (1.0 + difficulty_factor) ×           # 1.0-2.0 range (difficulty boost)
    (0.5 + speed_factor × 0.5) ×          # 0.5-1.0 range (speed boost)
    (0.5 + start_speed_factor × 0.5) ×    # 0.5-1.0 range (start speed boost)
    completion_factor                     # 0.0-1.0 range (completion quality)
)

# Normalize to 0-100 range
execution_score = max(0.0, min(100.0, execution_score))
```

**Example Calculations:**

**Example 1: Perfect Execution**
- Difficulty: 0.85 (very difficult task)
- Speed: 1.0 (completed 2x faster than estimate)
- Start Speed: 1.0 (started within 5 minutes)
- Completion: 1.0 (100% completed)
- **Score:** `50 × 1.85 × 1.0 × 1.0 × 1.0 = 92.5`

**Example 2: Good Execution with Delays**
- Difficulty: 0.85 (very difficult task)
- Speed: 0.75 (completed slightly faster than estimate)
- Start Speed: 0.7 (started after 45 minutes)
- Completion: 1.0 (100% completed)
- **Score:** `50 × 1.85 × 0.875 × 0.85 × 1.0 = 68.7`

**Example 3: Easy Task, Fast Execution**
- Difficulty: 0.25 (easy task)
- Speed: 1.0 (completed 2x faster than estimate)
- Start Speed: 1.0 (started within 5 minutes)
- Completion: 1.0 (100% completed)
- **Score:** `50 × 1.25 × 1.0 × 1.0 × 1.0 = 62.5`

---

## Use Cases

1. **Rewards fast completion of difficult tasks** - Combines difficulty and speed
2. **Recognizes overcoming procrastination** - Fast starts are rewarded
3. **Complements productivity score** - Productivity ignores difficulty, execution rewards it
4. **Complements grit score** - Grit rewards persistence, execution rewards speed

---

## Implementation Details

**Primary Method:** `Analytics.calculate_execution_score(row, task_completion_counts=None)`

**Location:** `backend/analytics.py:2453-2618`

**Data Sources:**
- Task instance row (pandas Series from CSV or dict from database)
- Must contain: `predicted_dict`/`actual_dict` (or `predicted`/`actual`), `initialized_at`, `started_at`, `completed_at`

**Error Handling:**
- Missing time data → neutral factors (0.5)
- Missing completion data → assumes 100% completion
- Missing aversion data → difficulty_factor = 0.0
- Invalid timestamps → neutral start_speed_factor (0.5)

---

## Version History

### v1.0 (Current)
- Initial production release
- Four-factor multiplicative model
- Exponential difficulty scaling
- Piecewise speed and start speed factors
- Piecewise completion factor
- Full integration with analytics system

---

## Related Documentation

- **Analytics Glossary:** `ui/analytics_glossary.py` (execution_score module)
- **Graphic Aids:** `scripts/graphic_aids/execution_score_*.py`
- **Proposal Document:** `docs/execution_score_proposal.md`
- **Formula Review:** `docs/formula_review_analysis.md`

---

## Notes

- All formulas are designed to be psychologically accurate (exponential decay matches human perception)
- Factors are multiplicative to ensure all components must be high for high scores
- Base score of 50 provides neutral starting point (half of max 100)
- Difficulty factor is added to 1.0 (not multiplied) to provide boost rather than penalty
- Speed and start speed factors are scaled to 0.5-1.0 range to provide boost rather than penalty
