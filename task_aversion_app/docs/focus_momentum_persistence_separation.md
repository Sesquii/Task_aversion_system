# Focus, Momentum, and Persistence: Conceptual Separation

## Overview

These three factors measure different aspects of task execution and should be kept conceptually separate, even if they interact:

1. **Focus Factor**: Current state of attention and engagement (sustained attention, not distracted)
2. **Momentum Factor**: Building energy through repeated action (task clustering, volume, flow state)
3. **Persistence Factor**: Continuing despite obstacles (already partially in grit score, but could be separate)

## Conceptual Differences

### Focus Factor
**What it measures:** Current state of attention and engagement
- Are you focused right now? (emotion-based)
- Are you distracted? (emotion-based)
- Are you present and mindful? (emotion-based)

**Time scale:** Current task completion (snapshot)
**Key indicators:**
- Focus-positive emotions (focused, concentrated, determined, engaged, present, mindful)
- Focus-negative emotions (distracted, scattered, unfocused, restless, anxious, overwhelmed)

**Example scenarios:**
- High focus: Emotion = "focused" (90), even if it's your first task
- Low focus: Emotion = "distracted" (80), even if you've done 10 tasks

### Momentum Factor
**What it measures:** Building energy through repeated action
- Are you building momentum through task clustering?
- Are you getting into a flow state through volume?
- Are you accelerating (completing tasks faster as you go)?

**Time scale:** Recent activity pattern (last 24 hours)
**Key indicators:**
- Task clustering: Short gaps between completions
- Task volume: Many tasks completed recently
- Template consistency: Repeating same task template
- Acceleration: Tasks getting faster over time

**Example scenarios:**
- High momentum: Completed 5 tasks in last 2 hours with 15-min gaps, getting faster
- Low momentum: First task of day, or 4-hour gap since last task

### Persistence Factor
**What it measures:** Continuing despite obstacles
- Are you sticking with difficult tasks?
- Are you completing tasks despite high aversion?
- Are you maintaining effort over time?

**Time scale:** Historical pattern (days/weeks)
**Key indicators:**
- Task repetition: Completing same task multiple times
- Aversion resistance: Completing tasks despite high aversion
- Obstacle overcoming: Completing tasks despite high cognitive/emotional load
- Consistency: Regular completion patterns over time

**Example scenarios:**
- High persistence: Completed same difficult task 10 times over 2 weeks
- Low persistence: Started task 5 times but only completed once

## Current Implementation Status

### Focus Factor (✅ Implemented)
- **Location:** `calculate_focus_factor()` in `analytics.py`
- **Components:**
  1. Task clustering (40%) - **This is actually momentum!**
  2. Emotion-based indicators (20%) - **This is focus!**
  3. Task template repetition (40%) - **This is persistence!**

**Problem:** Current implementation mixes all three concepts!

### Momentum Factor (❌ Not implemented separately)
- Currently part of focus factor (task clustering component)
- Should measure: task clustering, volume, acceleration

### Persistence Factor (⚠️ Partially in grit score)
- **Location:** Grit score includes persistence multiplier
- **Current:** Rewards doing same task multiple times
- **Missing:** Aversion resistance, obstacle overcoming, consistency over time

## Proposed Separation

### Option A: Keep Focus Factor Pure, Extract Momentum

**Focus Factor (Pure):**
- **100% emotion-based** (current attention state)
- Focus-positive vs focus-negative emotions
- No time-based components
- Pure snapshot of current mental state

**Momentum Factor (New):**
- Task clustering (short gaps between completions)
- Task volume (many tasks recently)
- Template consistency (repeating same template)
- Acceleration (tasks getting faster)

**Persistence Factor (Extract from grit):**
- Task repetition (already in grit)
- Aversion resistance (completing despite high aversion)
- Obstacle overcoming (completing despite high load)
- Consistency (regular patterns)

### Option B: Keep Current Structure, Rename Components

**Focus Factor (Rename to "Engagement Factor"):**
- Task clustering (momentum component)
- Emotion-based indicators (focus component)
- Task template repetition (persistence component)
- Keep as-is but acknowledge it's a composite

**Momentum Factor (Separate):**
- Pure momentum: acceleration, velocity, clustering
- Separate from focus

**Persistence Factor (Separate):**
- Pure persistence: aversion resistance, obstacle overcoming
- Separate from grit score

### Option C: Three Separate Factors

**Focus Factor:**
- Emotion-based only (current attention state)
- 0.0-1.0 range

**Momentum Factor:**
- Task clustering (40%)
- Task volume (30%)
- Template consistency (20%)
- Acceleration (10%)
- 0.0-1.0 range

**Persistence Factor:**
- Task repetition (30%)
- Aversion resistance (30%)
- Obstacle overcoming (20%)
- Consistency (20%)
- 0.0-1.0 range

## Recommendation: Option A (Pure Focus, Extract Momentum)

**Rationale:**
1. **Focus should be pure:** It's a mental state, not a behavioral pattern
2. **Momentum is behavioral:** It's about patterns of action, not mental state
3. **Persistence is historical:** It's about long-term patterns, not current state
4. **Clear separation:** Each factor measures something distinct

**Implementation:**
1. **Refactor focus factor** to be 100% emotion-based
2. **Create momentum factor** with clustering, volume, consistency, acceleration
3. **Extract persistence factor** from grit score (or keep in grit, but make it explicit)

**Execution Score Formula:**
```python
execution_score = base_score * 
                  (1.0 + difficulty_factor) *
                  (0.5 + speed_factor * 0.5) *
                  (0.5 + start_speed_factor * 0.5) *
                  completion_factor *
                  thoroughness_factor *
                  (0.5 + focus_factor * 0.5) *      # Pure emotion-based
                  (0.5 + momentum_factor * 0.5) *    # Behavioral pattern
                  (0.5 + persistence_factor * 0.5)   # Historical pattern
```

## Momentum Factor Design (Proposed)

### Components

1. **Task Clustering (40%):** Short gaps between completions
   - Same as current focus factor component
   - Measures: Are you maintaining activity?

2. **Task Volume (25%):** Many tasks completed recently
   - Count tasks in last 24 hours
   - Measures: Are you building volume?

3. **Template Consistency (20%):** Repeating same template
   - Count same template in last 7 days
   - Measures: Are you building expertise?

4. **Acceleration (15%):** Tasks getting faster
   - Compare recent task durations to earlier ones
   - Measures: Are you getting more efficient?

### Formula
```python
momentum_factor = (
    0.4 * clustering_score +      # Task clustering
    0.25 * volume_score +         # Task volume
    0.2 * consistency_score +      # Template consistency
    0.15 * acceleration_score      # Getting faster
)
```

## Persistence Factor Design (Proposed)

### Components

1. **Task Repetition (30%):** Completing same task multiple times
   - Count completions of same template (historical)
   - Measures: Are you committed to this task?

2. **Aversion Resistance (30%):** Completing despite high aversion
   - Compare aversion level to completion rate
   - Measures: Are you overcoming avoidance?

3. **Obstacle Overcoming (20%):** Completing despite high load
   - Compare cognitive/emotional load to completion
   - Measures: Are you pushing through difficulty?

4. **Consistency (20%):** Regular completion patterns
   - Measure regularity of completions over time
   - Measures: Are you maintaining effort?

### Formula
```python
persistence_factor = (
    0.3 * repetition_score +      # Task repetition
    0.3 * aversion_resistance +   # Overcoming aversion
    0.2 * obstacle_overcoming +   # Pushing through load
    0.2 * consistency_score       # Regular patterns
)
```

## Additional Components (Future Popups/Recommendations)

The 4 components you mentioned could be used for recommendations:

1. **Time-of-Day Patterns:** "You're most focused at 9am - schedule important tasks then"
2. **Task Type Consistency:** "You've been doing work tasks - consider a self-care break"
3. **Duration Consistency:** "Your tasks are taking longer - are you getting stuck?"
4. **Completion Percentage Trends:** "Your completion rates are improving - keep it up!"

These could feed into:
- **Recommendations:** Suggest tasks based on patterns
- **Popups:** "You've completed 5 tasks - great momentum! Want to keep going?"
- **Insights:** "Your focus is highest in the morning"

## Next Steps

1. **Decide on separation approach** (Option A, B, or C)
2. **Refactor focus factor** to be emotion-based only
3. **Implement momentum factor** with clustering, volume, consistency, acceleration
4. **Extract/implement persistence factor** (or clarify relationship with grit score)
5. **Update execution score formula** to include all three factors
6. **Test with real data** to calibrate weights

## Questions to Answer

1. Should persistence factor be separate from grit score, or is grit score sufficient?
2. Should momentum factor include acceleration (tasks getting faster), or is that redundant with speed_factor?
3. Should focus factor be 100% emotion-based, or include some behavioral components?
4. How should these factors interact? (multiplicative, additive, weighted combination?)
