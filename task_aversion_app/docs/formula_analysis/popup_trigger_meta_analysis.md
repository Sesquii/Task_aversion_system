# Popup Trigger Meta-Analysis: When Should We Ask Users Questions?

## Purpose

This document analyzes all potential triggers for contextual popups that can improve data accuracy, provide insights, and enhance the user experience. Popups should be **strategic, non-intrusive, and value-adding** - asking questions that help both the user and the system understand what's really happening.

## Core Principles

1. **Timing Matters**: Ask questions when context is fresh (during/right after task completion)
2. **Value Exchange**: Every popup should provide value to the user (insight, score adjustment, pattern recognition)
3. **Honesty Encouragement**: Frame questions to encourage honest self-reflection without judgment
4. **Survey Integration**: Use survey responses to personalize and prioritize popup questions
5. **Avoid Fatigue**: Don't show popups too frequently; respect user's flow state

## Data Available for Triggering

### Task Completion Data (`actual_dict`)
- `completion_percent` (0-100)
- `time_actual_minutes` vs `time_estimate_minutes`
- `actual_relief` (0-100)
- `actual_mental_energy` (0-100)
- `actual_difficulty` (0-100)
- `actual_emotional` (0-100)
- `actual_physical` (0-100)
- `emotion_values` (dict of emotion intensities)
- `notes` (free text)
- Task completion count (how many times this task has been done)

### Task Prediction Data (`predicted_dict`)
- `expected_aversion` (0-100)
- `expected_relief` (0-100)
- `expected_emotional_load` (0-100)
- `time_estimate_minutes`
- `initialization_expected_aversion` (preserved from task start)

### Behavioral Data
- Delay between creation and start (`delay_minutes`)
- Delay between start and completion
- Task cancellation rate
- Partial completion rate
- Task frequency/patterns

### Survey Data (for correlation)
- Struggles: Procrastination, Self-doubt, Motivation issues, Focus/concentration, Anxiety, Perfectionism
- Procrastination frequency (1-10 scale)
- Stress triggers: Deadlines, Unclear requirements, Too many tasks, Interruptions, Perfection pressure
- Typical stress level (1-10)
- Diagnoses (ADHD, Anxiety, Depression, etc.)

## Popup Trigger Categories

### 1. Time-Based Triggers

#### 1.1 Time Overrun (Primary Grit Trigger)
**Trigger**: `time_actual > 2.0 * time_estimate` AND `time_estimate > 0`

**Rationale**: Taking significantly longer than expected could indicate:
- Genuine grit (stuck with it despite difficulty)
- Poor focus/distraction
- Task was harder than anticipated
- Poor time estimation

**Popup Flow**:
```
Primary Question: "Did this task take extra work than expected? Be honest—have you been working with as much grit as possible? This will factor into your grit score and improve the accuracy of the application. If you haven't been focused, that's okay! The best way to improve in life is to be honest with yourself."

Branch A (Yes, I was focused):
  → "Overall, were you more frustrated or proud throughout the experience?"
  → "Did the pride you feel in completing the task outweigh the frustration you felt during it?"
  → [Optional] "What made this task take longer than expected?" (free text)

Branch B (No, I wasn't focused):
  → "Why did you struggle to complete the task?"
    - Shame
    - Confusion
    - Distraction
    - Other: [custom text]
  → [If distraction selected] "What distracted you?" (free text)
```

**Score Impact**:
- Yes + Pride > Frustration → Full grit time bonus
- Yes + Frustration > Pride → Reduced grit time bonus (still grit, but harder)
- No + Shame/Confusion → Minimal/no grit time bonus
- No + Distraction → No grit time bonus, possible productivity penalty

#### 1.2 Extreme Time Overrun
**Trigger**: `time_actual > 5.0 * time_estimate` AND `time_estimate > 0`

**Rationale**: Extreme overruns might indicate:
- Task scope creep
- Fundamental misunderstanding of task
- Severe procrastination/avoidance
- Need for task breakdown

**Popup Flow**:
```
"Wow, this took much longer than expected! What happened?"
- "The task was more complex than I thought" → Suggest task breakdown
- "I kept getting distracted" → Link to focus strategies
- "I was avoiding it" → Link to procrastination resources
- "Other reason" → Free text
```

#### 1.3 Time Underrun (Efficiency Check)
**Trigger**: `time_actual < 0.5 * time_estimate` AND `time_estimate > 0` AND `completion_percent >= 100`

**Rationale**: Finishing much faster could indicate:
- Great efficiency (positive)
- Task was easier than expected (update estimates)
- Rushed work (quality concern)

**Popup Flow**:
```
"Great job finishing early! How did you do it?"
- "I was really focused and efficient" → Boost productivity score
- "The task was easier than I expected" → Update time estimates
- "I might have rushed it" → Quality check follow-up
```

### 2. Completion-Based Triggers

#### 2.1 Partial Completion
**Trigger**: `completion_percent < 100` AND `completion_percent >= 50`

**Rationale**: Partial completion could indicate:
- Genuine effort but ran out of time/energy
- Got bored or distracted
- Task was too difficult
- Perfectionism (stopped when "good enough")

**Popup Flow**:
```
"Did you try your best to complete this task? Did you get bored or distracted?"

Branch A (Yes, I tried my best):
  → "What prevented you from finishing?"
    - Ran out of time
    - Ran out of energy
    - Task was too difficult
    - Other: [custom]
  → [If energy/time] "Would breaking this task into smaller pieces help?"

Branch B (No, I got bored/distracted):
  → "What distracted you?" (correlate with survey: procrastination, focus issues)
  → "Would a different approach help?" (suggest task modification)
```

**Score Impact**:
- Yes + Energy/Time → Partial grit credit, suggest task breakdown
- Yes + Too difficult → Difficulty adjustment, suggest resources
- No + Bored → Reduced grit, link to motivation strategies
- No + Distracted → No grit, productivity penalty

#### 2.2 Very Low Completion
**Trigger**: `completion_percent < 50` AND `completion_percent > 0`

**Rationale**: Very low completion might indicate:
- Task was overwhelming
- Severe avoidance/procrastination
- Task needs to be broken down
- Wrong task for current state

**Popup Flow**:
```
"This task seems overwhelming. What happened?"
- "I couldn't get started" → Procrastination analysis
- "It was too difficult" → Task breakdown suggestion
- "I wasn't in the right headspace" → Suggest rescheduling
- "Other" → Free text
```

#### 2.3 First-Time Completion with High Difficulty
**Trigger**: `completion_count == 1` AND `actual_difficulty > 70` AND `completion_percent >= 100`

**Rationale**: First-time completion of a hard task is significant grit moment

**Popup Flow**:
```
"Congratulations on completing this difficult task for the first time! How do you feel?"
- "Proud and accomplished" → High grit bonus
- "Relieved it's over" → Moderate grit bonus
- "Exhausted" → Energy consideration
- "Other" → Free text
```

### 3. Emotional/Affective Triggers

#### 3.1 Negative Net Affect Despite Completion
**Trigger**: `completion_percent >= 100` AND `actual_relief < 30` AND `actual_emotional > 70`

**Rationale**: Completing despite high negative affect shows significant grit

**Popup Flow**:
```
"You completed this task even though it was emotionally difficult. That takes real strength. How are you feeling now?"
- "Proud that I pushed through" → High grit bonus
- "Still feeling stressed/negative" → Suggest self-care
- "Mixed feelings" → Explore emotional flow
```

**Score Impact**: High grit multiplier for completing despite negative affect

#### 3.2 High Relief After Difficult Task
**Trigger**: `actual_relief > 70` AND `actual_difficulty > 60` AND `completion_percent >= 100`

**Rationale**: High relief after difficulty indicates meaningful accomplishment

**Popup Flow**:
```
"Great job! You completed a difficult task and feel good about it. What made the difference?"
- "I stuck with it even when it was hard" → Grit recognition
- "I found a better approach" → Learning moment
- "I'm just relieved it's done" → Still valuable
```

#### 3.3 Emotional Spike Pattern
**Trigger**: High `actual_emotional` compared to `expected_emotional_load` (spike > 30 points)

**Rationale**: Unexpected emotional activation might indicate:
- Task touched on sensitive topic
- External stressor
- Need for emotional support

**Popup Flow**:
```
"This task seemed more emotionally intense than expected. Are you okay?"
- "Yes, I'm fine" → Note for future reference
- "It was harder than I thought" → Emotional load adjustment
- "I need support" → Resources/suggestions
```

### 4. Behavioral Pattern Triggers

#### 4.1 High Delay Before Starting
**Trigger**: `delay_minutes > threshold` (e.g., 24 hours for non-recurring tasks)

**Rationale**: Long delays might indicate procrastination

**Popup Flow** (after completion):
```
"You waited a while before starting this task. What was going on?"
- "I was avoiding it" → Procrastination analysis (correlate with survey)
- "I was busy with other things" → Scheduling consideration
- "I wasn't sure how to start" → Task clarity check
```

#### 4.2 Repeated Cancellations
**Trigger**: Task cancelled 3+ times before completion

**Popup Flow** (on next attempt):
```
"You've cancelled this task a few times. What's making it hard?"
- "It's too overwhelming" → Task breakdown
- "I keep avoiding it" → Procrastination support
- "I'm not sure it's the right task" → Task review
```

#### 4.3 Rapid Task Completion (Possible Rushing)
**Trigger**: Multiple tasks completed in very short time (< 5 min each) with low relief

**Popup Flow**:
```
"You've completed several tasks quickly. Are you rushing through them?"
- "No, they were quick tasks" → OK
- "Yes, I'm trying to get through my list" → Quality vs. quantity discussion
```

### 5. Survey-Correlated Triggers

#### 5.1 Procrastination Pattern Match
**Trigger**: User marked "Procrastination" in struggles AND `delay_minutes > threshold` AND `time_actual > 2 * time_estimate`

**Popup Flow**:
```
[Personalized based on survey]
"You mentioned struggling with procrastination. Did that play a role here?"
- "Yes, I kept putting it off" → Procrastination-specific follow-up
- "No, this was different" → Explore what was different
```

#### 5.2 Perfectionism Pattern Match
**Trigger**: User marked "Perfectionism" in struggles AND `time_actual > 2 * time_estimate` AND `completion_percent >= 100`

**Popup Flow**:
```
"You mentioned struggling with perfectionism. Did that affect how long this took?"
- "Yes, I kept redoing things" → Perfectionism-specific support
- "No, it was just difficult" → OK
```

#### 5.3 Anxiety Pattern Match
**Trigger**: User marked "Anxiety" in struggles AND `actual_emotional > 70` AND `completion_percent >= 100`

**Popup Flow**:
```
"You mentioned anxiety. Did that make this task harder?"
- "Yes, I was anxious throughout" → Anxiety-specific support
- "No, this was different" → OK
```

### 6. Data Quality Triggers

#### 6.1 Missing Critical Data
**Trigger**: `actual_relief` is missing/0 AND `completion_percent >= 100`

**Popup Flow**:
```
"Quick question: How much relief do you feel now that this is done?" (0-100 slider)
[Light touch, don't make it feel like work]
```

#### 6.2 Inconsistent Data Patterns
**Trigger**: `actual_relief > 80` AND `actual_emotional > 80` (contradictory: high relief + high emotional load)

**Popup Flow**:
```
"Interesting pattern: You felt both high relief and high emotional load. Can you help us understand?"
- "I'm relieved it's done but it was stressful" → Makes sense
- "That doesn't seem right" → Data correction opportunity
```

## Popup Frequency Management

### Cooldown Rules
- **Same trigger type**: Don't show same trigger within 24 hours
- **Any popup**: Maximum 1 popup per task completion
- **Daily limit**: Maximum 3 popups per day (user-configurable)

### Priority System
1. **High Priority**: Time overrun (grit), negative affect despite completion (grit), first-time difficult completion
2. **Medium Priority**: Partial completion, emotional spikes, survey-correlated patterns
3. **Low Priority**: Data quality checks, efficiency confirmations

### User Preferences
- Allow users to disable specific popup types
- "Don't ask me about this again" option for each popup type
- Frequency slider: "Ask me questions: Never / Rarely / Sometimes / Often"

## Implementation Strategy

### Phase 1: Core Grit Popups
- Time overrun popup (2x threshold)
- Partial completion popup
- Negative affect despite completion popup

### Phase 2: Survey Integration
- Correlate popup triggers with survey responses
- Personalize questions based on user's struggles

### Phase 3: Advanced Patterns
- Behavioral pattern detection
- Data quality improvements
- Emotional flow analysis

## Score Impact Framework

Each popup response should influence scores appropriately:

| Response Type | Grit Impact | Productivity Impact | Notes |
|--------------|-------------|---------------------|-------|
| Focused + Pride > Frustration | High bonus | Neutral | True grit |
| Focused + Frustration > Pride | Moderate bonus | Neutral | Hard but pushed through |
| Distracted/Not focused | No bonus | Penalty | Not grit, poor productivity |
| Shame/Confusion | Minimal bonus | Neutral | Acknowledged struggle |
| Partial + Best effort | Partial bonus | Neutral | Partial grit |
| Partial + Bored/Distracted | No bonus | Penalty | Not grit |

## Next Steps

1. **Create popup rule document** (separate file) that defines the technical implementation
2. **Design UI components** for popup dialogs (NiceGUI modal system)
3. **Implement popup trigger system** in `complete_task.py`
4. **Add survey correlation logic** to personalize popups
5. **Create popup response storage** (new field in task_instances or separate table)
6. **Update grit score calculation** to use popup responses

