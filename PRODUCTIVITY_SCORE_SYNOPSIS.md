# Productivity Score Formula - Complete Synopsis

## Overview
The Productivity Score measures productive output based on task completion, task type, efficiency, and goal achievement. The formula combines multiple factors to reward efficient completion of meaningful work while accounting for self-care and penalizing excessive play.

## Complete Formula Structure

### Base Score
```
base_score = completion_percentage (0-100, can exceed 100% for over-completion)
```

### Task Type Multipliers

#### 1. WORK Tasks
- **Multiplier Range:** 3.0x to 5.0x (smooth transition)
- **Calculation:**
  ```
  completion_time_ratio = (completion_pct * time_estimate) / (100.0 * time_actual)
  capped_ratio = min(completion_time_ratio, 1.5)  // Cap at 1.5 to prevent extreme multipliers
  
  if capped_ratio <= 1.0:
      multiplier = 3.0
  elif capped_ratio >= 1.5:
      multiplier = 5.0
  else:
      smooth_factor = (capped_ratio - 1.0) / 0.5  // 0.0 to 1.0
      multiplier = 3.0 + (2.0 * smooth_factor)  // Smooth transition from 3.0 to 5.0
  ```
- **Burnout Penalty (Optional):**
  - Applies when weekly work > threshold (default 42 hours) AND daily work > daily cap (2x daily average)
  - Penalty: `multiplier = multiplier * (1.0 - penalty_factor * 0.5)`
  - Where `penalty_factor = 1.0 - exp(-excess_week / 300.0)` (exponential decay, capped at 50% reduction)

#### 2. SELF-CARE Tasks
- **Multiplier:** 1.0x to Nx (where N = number of self-care tasks completed that day)
- **Calculation:**
  ```
  multiplier = count of self_care_tasks_completed_today
  // First self-care task = 1.0x, second = 2.0x, third = 3.0x, etc.
  ```
- **Philosophy:** Rewards multiple self-care activities per day, encouraging consistent self-maintenance

#### 3. PLAY Tasks
- **Multiplier:** Neutral (1.0x) OR Negative Penalty (-0.003x per percentage)
- **Calculation:**
  ```
  play_work_ratio = play_time_today / work_time_today
  
  if play_work_ratio > threshold (default 2.0) OR (no work time AND play time exists):
      // Apply productivity penalty
      time_percentage = (time_actual / time_estimate) * 100.0
      multiplier = -0.003 * time_percentage  // Creates negative score
      // Max penalty: -0.3x for 100% completion = -30 score
  else:
      // No penalty: play is within acceptable ratio to work
      multiplier = 1.0  // Neutral score (just completion percentage)
  ```
- **Philosophy:** Only penalizes play when it significantly exceeds work (2x threshold). Balanced play is neutral.

### Efficiency Multiplier

**Purpose:** Adjusts score based on efficiency, accounting for both completion percentage and time relative to task's own estimate.

**Formula:**
```
completion_time_ratio = (completion_pct * time_estimate) / (100.0 * time_actual)
efficiency_ratio = completion_time_ratio
efficiency_percentage_diff = (efficiency_ratio - 1.0) * 100.0

// Curve type: 'flattened_square' (default) or 'linear'
if curve_type == 'flattened_square':
    effect = copysign((abs(efficiency_percentage_diff) ** 2) / 100.0, efficiency_percentage_diff)
    efficiency_multiplier = 1.0 - (0.01 * strength * -effect)
else:  // linear
    efficiency_multiplier = 1.0 - (0.01 * strength * -efficiency_percentage_diff)

// Cap both penalty and bonus
efficiency_multiplier = max(0.5, min(1.5, efficiency_multiplier))  // 50% reduction min, 50% bonus max
```

**Key Features:**
- Compares to task's own estimate (not weekly average)
- Accounts for completion percentage: If you take 2x longer but complete 200%, efficiency ratio = 1.0 (no penalty)
- Capped at 50% reduction (min 0.5x) and 50% increase (max 1.5x)

**Examples:**
- Task estimated 20 min, takes 20 min, 100% complete → ratio = 1.0 → multiplier = 1.0 (no change)
- Task estimated 20 min, takes 40 min, 200% complete → ratio = 1.0 → multiplier = 1.0 (no penalty!)
- Task estimated 20 min, takes 40 min, 100% complete → ratio = 0.5 → multiplier = 0.5 (50% penalty, capped)
- Task estimated 20 min, takes 10 min, 100% complete → ratio = 2.0 → multiplier = 1.5 (50% bonus)

### Goal-Based Adjustment (Optional)

**Purpose:** Provides bonus/penalty based on weekly goal achievement.

**Formula:**
```
goal_achievement_ratio = weekly_productive_hours / goal_hours_per_week

if ratio >= 1.2:
    goal_multiplier = 1.2  // 20% bonus for exceeding goal significantly
elif ratio >= 1.0:
    goal_multiplier = 1.0 + (ratio - 1.0) * 1.0  // Linear: 1.0 → 1.0, 1.2 → 1.2
elif ratio >= 0.8:
    goal_multiplier = 0.9 + (ratio - 0.8) * 0.5  // Linear: 0.8 → 0.9, 1.0 → 1.0
else:
    goal_multiplier = 0.8 + (ratio / 0.8) * 0.1  // Linear: 0.0 → 0.8, 0.8 → 0.9
    goal_multiplier = max(0.8, goal_multiplier)  // Cap at 0.8 minimum

score = score * goal_multiplier
```

**Range:** 0.8x to 1.2x (±20% max adjustment)

## Complete Formula Flow

```
1. base_score = completion_percentage

2. Apply task type multiplier:
   - WORK: multiplier = 3.0 to 5.0 (based on completion_time_ratio)
   - SELF-CARE: multiplier = count of self-care tasks that day
   - PLAY: multiplier = -0.003 * time_percentage (if play > 2x work) OR 1.0 (neutral)
   - OTHER: multiplier = 1.0
   
   score = base_score * multiplier

3. Apply burnout penalty (WORK only, if applicable):
   if weekly_work > threshold AND daily_work > daily_cap:
       penalty_factor = 1.0 - exp(-excess_week / 300.0)
       score = score * (1.0 - penalty_factor * 0.5)

4. Apply efficiency multiplier:
   efficiency_multiplier = calculate_efficiency_multiplier(completion_time_ratio)
   score = score * efficiency_multiplier

5. Apply goal-based adjustment (if goal data provided):
   goal_multiplier = calculate_goal_multiplier(goal_achievement_ratio)
   score = score * goal_multiplier

6. Return final score
```

## How Self-Care/Work/Play Factor Into Productivity

### WORK
- **Highest Priority:** 3.0x to 5.0x multiplier (highest base multiplier)
- **Efficiency Rewarded:** Faster completion with same quality = higher multiplier (up to 5.0x)
- **Burnout Protection:** Penalty applied when weekly work exceeds sustainable threshold
- **Philosophy:** Work is the primary productivity driver, but sustainability matters

### SELF-CARE
- **Cumulative Reward:** Multiplier increases with each self-care task completed per day (1x, 2x, 3x, etc.)
- **Daily Focus:** Rewards consistent daily self-maintenance, not just occasional activities
- **Philosophy:** Self-care is essential for long-term productivity; multiple activities per day are encouraged
- **No Efficiency Penalty:** Self-care tasks don't have efficiency adjustments (time spent on self-care is inherently valuable)

### PLAY
- **Conditional Impact:** 
  - **Neutral (1.0x):** When play time is within 2x of work time (balanced lifestyle)
  - **Negative Penalty:** When play significantly exceeds work (play_work_ratio > 2.0)
- **Penalty Formula:** -0.003x per percentage of time spent (max -0.3x for 100% completion)
- **Philosophy:** Play is acceptable in moderation, but excessive play relative to work reduces productivity score
- **Calibration:** Play penalty is intentionally less severe than idle time penalty (which can reduce score by 100%)

## Score Ranges

- **Work tasks:** Typically 0-500+ (base 0-100 × 3-5x multiplier × efficiency × goal)
- **Self-care tasks:** Typically 0-300+ (base 0-100 × 1-Nx multiplier, no efficiency adjustment)
- **Play tasks:** Typically -30 to 100 (negative when penalized, neutral when balanced)
- **Other tasks:** Typically 0-150 (base 0-100 × 1.0x × efficiency)

## Key Design Principles

1. **Task-Specific Evaluation:** Each task is compared to its own estimate, not arbitrary averages
2. **Completion-Aware:** Efficiency accounts for both time AND completion percentage
3. **Sustainability Focus:** Burnout penalties prevent overwork; self-care rewards prevent burnout
4. **Balanced Lifestyle:** Play is acceptable in moderation; only excessive play is penalized
5. **Capped Extremes:** All multipliers have caps to prevent unrealistic scores
6. **Goal Integration:** Optional goal-based adjustments align scores with weekly objectives

## Version Information

- **Current Version:** 1.1 (2025-12-27)
- **Key Improvement:** Efficiency now compares to task's own estimate (not weekly average) and accounts for completion percentage
- **Location:** `task_aversion_app/backend/analytics.py:474-749`
