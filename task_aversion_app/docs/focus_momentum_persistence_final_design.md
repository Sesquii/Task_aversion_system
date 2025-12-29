# Focus, Momentum, and Persistence: Final Design

## Research Confirmation

**Focus is a mental state**, not a behavioral pattern:
- Focus = ability to concentrate on a task without distraction (cognitive/emotional state)
- Behavioral indicators (uninterrupted work, task switches) are **measures** of focus, not focus itself
- The state itself is mental/emotional, which we can measure through emotion tracking

**Conclusion:** Option A is correct - focus factor should be 100% emotion-based.

## Final Architecture

### 1. Focus Factor (Pure Mental State)
**100% emotion-based** - measures current attention state

**Components:**
- Focus-positive emotions: "focused", "concentrated", "determined", "engaged", "present", "mindful", "attentive", "absorbed"
- Focus-negative emotions: "distracted", "scattered", "unfocused", "restless", "anxious", "overwhelmed"

**Formula:**
```python
focus_factor = 0.5 + (positive_emotion_score - negative_emotion_score) * 0.5
# Range: 0.0-1.0, where 0.5 = neutral
```

**Use:** Part of **grit score** (not execution score, since it's emotion-based)

---

### 2. Momentum Factor (Behavioral Pattern)
**100% behavioral** - measures building energy through repeated action

**Components:**
1. **Task Clustering (40%):** Short gaps between completions
   - Average gap between recent task completions (last 24 hours)
   - ≤15 min = 1.0, 15-60 min = 1.0→0.5, 60-240 min = exponential decay, >240 min = 0.1

2. **Task Volume (30%):** Many tasks completed recently
   - Count tasks in last 24 hours
   - 1 task = 0.5, 3 tasks = 0.7, 5 tasks = 0.85, 10+ tasks = 1.0

3. **Template Consistency (20%):** Repeating same template
   - Count same template in last 7 days
   - 1 instance = 0.5, 2-5 instances = 0.5→0.8, 6-10 instances = 0.8→1.0, 10+ = 1.0

4. **Acceleration (10%):** Tasks getting faster
   - Compare recent task durations to earlier ones
   - If average duration decreasing = bonus, if increasing = penalty

**Formula:**
```python
momentum_factor = (
    0.4 * clustering_score +
    0.3 * volume_score +
    0.2 * consistency_score +
    0.1 * acceleration_score
)
# Range: 0.0-1.0
```

**Use:** Part of **execution score** (behavioral, not emotion-based)

**Popup Integration:**
- "You've completed 5 tasks - great momentum! Want to keep going?"
- Trigger when momentum_factor > 0.7 and task_count >= 5

---

### 3. Persistence Factor (Historical Pattern)
**100% historical** - measures continuing despite obstacles

**Components (with user-specified weights):**
1. **Obstacle Overcoming (40% - highest):** Completing despite high cognitive/emotional load
   - Compare cognitive_load + emotional_load to completion rate
   - High load + completion = high persistence
   - Formula: `obstacle_score = completion_rate * (load / 100.0)`

2. **Aversion Resistance (30%):** Completing despite high aversion
   - Compare initial_aversion to completion rate
   - High aversion + completion = high persistence
   - Formula: `aversion_score = completion_rate * (aversion / 100.0)`

3. **Task Repetition (20%):** Completing same task multiple times
   - Count completions of same template (historical, last 30 days)
   - 1 completion = 0.5, 2-5 = 0.5→0.8, 6-10 = 0.8→1.0, 10+ = 1.0

4. **Consistency (10%):** Regular completion patterns over time
   - Measure regularity of completions (variance in completion dates)
   - Lower variance = higher consistency
   - Formula: `consistency_score = 1.0 - (variance / max_variance)`

**Formula:**
```python
persistence_factor = (
    0.4 * obstacle_overcoming_score +  # Highest weight
    0.3 * aversion_resistance_score +
    0.2 * repetition_score +
    0.1 * consistency_score
)
# Range: 0.0-1.0
```

**Use:** Part of **grit score** (historical pattern, not current execution)

---

## Grit Score Restructure

**Current Grit Score:**
- Persistence multiplier (task repetition)
- Time bonus (taking longer)
- Passion factor (relief vs emotional load)

**Proposed Grit Score:**
```python
grit_score = base_score * (
    persistence_factor *      # 0.0-1.0 (continuing despite obstacles)
    focus_factor *           # 0.0-1.0 (current attention state)
    passion_factor *         # 0.0-1.0 (relief vs emotional load - existing)
    time_bonus              # 1.0+ (taking longer - existing)
)
```

**Rationale:**
- **Persistence** = historical pattern (sticking with it)
- **Focus** = current mental state (emotion-based)
- **Passion** = emotional reward (relief vs load)
- **Time bonus** = dedication (taking longer)

All are components of "grit" (perseverance + passion for long-term goals).

---

## Execution Score Structure

**Current Formula:**
```python
execution_score = base_score * (
    (1.0 + difficulty_factor) *
    (0.5 + speed_factor * 0.5) *
    (0.5 + start_speed_factor * 0.5) *
    completion_factor *
    (0.5 + focus_factor * 0.5)  # REMOVE - emotion-based, not execution
)
```

**Proposed Formula:**
```python
execution_score = base_score * (
    (1.0 + difficulty_factor) *
    (0.5 + speed_factor * 0.5) *
    (0.5 + start_speed_factor * 0.5) *
    completion_factor *
    thoroughness_factor *              # 0.5-1.3 (note-taking)
    (0.5 + momentum_factor * 0.5)      # 0.5-1.0 (behavioral pattern)
)
```

**Rationale:**
- **Execution score** = how well you executed the task (behavioral, objective)
- **Focus factor** = mental state (subjective, emotion-based) → belongs in grit score
- **Momentum factor** = behavioral pattern (objective) → belongs in execution score

---

## Implementation Plan

### Phase 1: Refactor Focus Factor
1. Remove task clustering (→ momentum factor)
2. Remove template repetition (→ persistence factor)
3. Keep only emotion-based components
4. Update to return 0.0-1.0 range

### Phase 2: Create Momentum Factor
1. Implement task clustering component
2. Implement task volume component
3. Implement template consistency component
4. Implement acceleration component
5. Combine with specified weights

### Phase 3: Create Persistence Factor
1. Implement obstacle overcoming (40% weight)
2. Implement aversion resistance (30% weight)
3. Implement task repetition (20% weight)
4. Implement consistency (10% weight)
5. Combine with specified weights

### Phase 4: Restructure Grit Score
1. Extract persistence from current grit score
2. Add focus factor to grit score
3. Keep passion factor and time bonus
4. Update formula: `grit = persistence * focus * passion * time_bonus`

### Phase 5: Update Execution Score
1. Remove focus factor from execution score
2. Add momentum factor to execution score
3. Add thoroughness factor to execution score
4. Update formula documentation

### Phase 6: Popup Integration
1. Implement momentum popup trigger
2. "You've completed 5 tasks - great momentum! Want to keep going?"
3. Trigger when momentum_factor > 0.7 and task_count >= 5

---

## Summary

| Factor | Type | Use | Components |
|--------|------|-----|------------|
| **Focus** | Mental state (emotion-based) | Grit score | Focus-positive vs focus-negative emotions |
| **Momentum** | Behavioral pattern | Execution score | Clustering (40%), Volume (30%), Consistency (20%), Acceleration (10%) |
| **Persistence** | Historical pattern | Grit score | Obstacle overcoming (40%), Aversion resistance (30%), Repetition (20%), Consistency (10%) |

**Key Decisions:**
- ✅ Focus = emotion-based only (mental state)
- ✅ Momentum = behavioral pattern (execution score)
- ✅ Persistence = historical pattern (grit score)
- ✅ Grit score = persistence + focus + passion + time_bonus
- ✅ Execution score = difficulty + speed + start_speed + completion + thoroughness + momentum
- ✅ Focus NOT in execution score (emotion-based, subjective)
