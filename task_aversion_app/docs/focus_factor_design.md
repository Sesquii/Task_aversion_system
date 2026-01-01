# Focus Factor Design for Execution Score

## Overview

The focus factor measures sustained attention and task engagement patterns. It rewards completing multiple tasks with minimal idle time, maintaining focus-related emotional states, and building momentum through task volume and template consistency.

## Core Components

### 1. Task Completion Momentum (Idle Time Analysis)
**Purpose:** Rewards completing multiple tasks with little idle time between them.

**Calculation:**
- Look at recent completed tasks (within last 24 hours)
- Calculate time gaps between consecutive task completions
- Reward short gaps (high focus), penalize long gaps (low focus)

**Formula:**
```python
# For each task completion, look at time since previous completion
gap_minutes = (current_completed_at - previous_completed_at) / 60.0

# Score based on gap length:
# 0-30 min: Excellent focus (1.0)
# 30-60 min: Good focus (0.9)
# 60-120 min: Moderate focus (0.7)
# 120-240 min: Low focus (0.5)
# 240+ min: Very low focus (0.3)
# First task of day: Neutral (0.5)
```

**Weight:** 40% of focus factor

### 2. Emotion-Based Focus Indicators
**Purpose:** Uses focus-related emotions to adjust the factor.

**Focus-Positive Emotions (increase factor):**
- Focused, concentrated, determined, engaged, present, mindful, attentive, absorbed
- High values (70-100) on these emotions boost focus factor

**Focus-Negative Emotions (decrease factor):**
- Distracted, scattered, unfocused, restless, anxious, overwhelmed
- High values (70-100) on these emotions reduce focus factor

**Formula:**
```python
# Extract emotion_values from actual_dict
emotion_values = actual_dict.get('emotion_values', {})
if isinstance(emotion_values, str):
    emotion_values = json.loads(emotion_values)

# Focus-positive emotions
focus_positive = ['focused', 'concentrated', 'determined', 'engaged', 
                  'present', 'mindful', 'attentive', 'absorbed']
focus_negative = ['distracted', 'scattered', 'unfocused', 'restless', 
                  'anxious', 'overwhelmed']

# Calculate emotion score
positive_score = 0.0
negative_score = 0.0

for emotion, value in emotion_values.items():
    emotion_lower = emotion.lower()
    if emotion_lower in focus_positive:
        positive_score += float(value) / 100.0
    elif emotion_lower in focus_negative:
        negative_score += float(value) / 100.0

# Normalize: average of positive emotions minus average of negative emotions
# Range: -1.0 to 1.0, then map to 0.0-1.0 factor
emotion_factor = 0.5 + (positive_score - negative_score) * 0.5
emotion_factor = max(0.0, min(1.0, emotion_factor))
```

**Weight:** 30% of focus factor

### 3. Task Volume and Template Consistency
**Purpose:** Rewards completing many tasks, especially from the same template (building momentum).

**Calculation:**
- Count tasks completed in last 24 hours
- Count tasks from same template in last 24 hours
- Reward high volume and template consistency

**Formula:**
```python
# Get current task_id from row
current_task_id = row.get('task_id')

# Count tasks in last 24 hours
recent_tasks = df[df['completed_at_dt'] >= (now - timedelta(hours=24))]
total_recent = len(recent_tasks)

# Count tasks from same template
same_template = recent_tasks[recent_tasks['task_id'] == current_task_id]
template_count = len(same_template)

# Volume bonus: exponential growth, caps at 0.3 bonus
# 1 task = 0.0, 3 tasks = 0.1, 5 tasks = 0.2, 10+ tasks = 0.3
volume_bonus = min(0.3, 0.1 * math.log(max(1, total_recent)) / math.log(3))

# Template consistency bonus: rewards repeating same task
# 1 instance = 0.0, 2 instances = 0.1, 3 instances = 0.2, 5+ instances = 0.3
template_bonus = min(0.3, 0.1 * math.log(max(1, template_count)) / math.log(2))

# Combined volume factor: 0.5 (no bonus) to 1.1 (max bonus)
volume_factor = 0.5 + volume_bonus + template_bonus
volume_factor = max(0.5, min(1.1, volume_factor))
```

**Weight:** 30% of focus factor

## Combined Focus Factor

**Formula:**
```python
focus_factor = (
    0.4 * momentum_factor +      # Task completion momentum
    0.3 * emotion_factor +       # Emotion-based focus
    0.3 * volume_factor          # Task volume and consistency
)
```

**Output Range:** 0.0 to 1.0 (can be scaled to 0.5-1.5 like thoroughness if needed)

## Integration with Execution Score

**Current Formula:**
```python
execution_score = base_score * (1.0 + difficulty_factor) * 
                  (0.5 + speed_factor * 0.5) * 
                  (0.5 + start_speed_factor * 0.5) * 
                  completion_factor
```

**Proposed Formula (with thoroughness and focus):**
```python
execution_score = base_score * (1.0 + difficulty_factor) * 
                  (0.5 + speed_factor * 0.5) * 
                  (0.5 + start_speed_factor * 0.5) * 
                  completion_factor *
                  thoroughness_factor *      # 0.5-1.3 range
                  (0.5 + focus_factor * 0.5)  # 0.5-1.0 range (scaled like speed)
```

**Alternative Formula (if user wants multiplicative):**
```python
execution_score = base_score * 
                  difficulty_factor *        # 0.0-1.0 (needs scaling)
                  speed_factor *             # 0.0-1.0 (needs scaling)
                  thoroughness_factor *      # 0.5-1.3
                  focus_factor               # 0.0-1.0 (needs scaling)
```

## Implementation Considerations

### Data Requirements
- `completed_at` timestamps for all recent tasks
- `task_id` for template matching
- `emotion_values` dictionary in actual_dict
- Access to recent task instances (last 24 hours)

### Performance
- Cache recent task queries (don't reload for every calculation)
- Consider limiting lookback window to 24-48 hours
- Use efficient pandas operations for time-based filtering

### Edge Cases
- First task of day: Use neutral momentum (0.5)
- No emotion data: Use neutral emotion factor (0.5)
- No recent tasks: Use neutral volume factor (0.5)
- Missing timestamps: Skip momentum calculation, use neutral

### Calibration
- Adjust weights (40/30/30) based on user feedback
- Tune gap thresholds (30/60/120/240 min) based on typical work patterns
- Adjust volume bonus curves based on typical task volumes

## Example Calculations

**Example 1: High Focus Session**
- Completed 3 tasks in last 2 hours (gaps: 15 min, 20 min)
- Emotion: "focused" = 85
- Same template repeated 2 times
- **Momentum:** 0.95 (short gaps)
- **Emotion:** 0.85 (high focus emotion)
- **Volume:** 0.7 (3 tasks, 2 same template)
- **Focus Factor:** 0.4*0.95 + 0.3*0.85 + 0.3*0.7 = **0.845**

**Example 2: Low Focus Session**
- Completed 1 task, previous was 4 hours ago
- Emotion: "distracted" = 70
- First task of day
- **Momentum:** 0.3 (long gap)
- **Emotion:** 0.3 (high distraction)
- **Volume:** 0.5 (only 1 task)
- **Focus Factor:** 0.4*0.3 + 0.3*0.3 + 0.3*0.5 = **0.36**

**Example 3: Moderate Focus**
- Completed 2 tasks, 45 min gap
- No focus-related emotions tracked
- Different templates
- **Momentum:** 0.8 (moderate gap)
- **Emotion:** 0.5 (neutral, no data)
- **Volume:** 0.55 (2 tasks, no template consistency)
- **Focus Factor:** 0.4*0.8 + 0.3*0.5 + 0.3*0.55 = **0.635**

## Future Enhancements

1. **Time-of-Day Patterns:** Adjust focus expectations based on circadian rhythms
2. **Task Type Weighting:** Different focus expectations for work vs self-care
3. **Session Detection:** Identify focused work sessions vs scattered activity
4. **Historical Baseline:** Compare current focus to personal baseline
5. **Context Awareness:** Adjust for breaks, meals, transitions
