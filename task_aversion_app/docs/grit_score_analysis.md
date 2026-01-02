# Grit Score Formula Analysis

## Executive Summary

**CRITICAL MISMATCH FOUND:** The glossary formula for grit score is **severely outdated** and does not match the actual implementation in `analytics.py`.

### Glossary Formula (OUTDATED)
```
grit_score = difficulty_bonus * time_bonus
```

### Actual Implementation (v1.2)
```
grit_score = base_score * (
    persistence_factor_scaled *  # 0.5-1.5 range
    focus_factor_scaled *        # 0.5-1.5 range
    passion_factor *             # 0.5-1.5 range
    time_bonus                   # 1.0+ range (with difficulty weighting)
)
where:
  base_score = completion_pct
  persistence_factor_scaled = 0.5 + persistence_factor * 1.0
  focus_factor_scaled = 0.5 + focus_factor * 1.0
  passion_factor = 1.0 + passion_delta * 0.5
```

---

## Detailed Comparison

### 1. Glossary Definition (analytics_glossary.py:58-71)

**Current Glossary:**
- **Formula:** `grit_score = difficulty_bonus * time_bonus`
- **Description:** "Rewards persistence and taking on difficult tasks. Includes difficulty bonus and time bonus (for tasks taking longer than estimated)."
- **Range:** `0 - 100+`
- **Components:** Empty list (no breakdown)

**Issues:**
1. ❌ Formula is **completely wrong** - doesn't match implementation
2. ❌ Missing 3 major components: persistence_factor, focus_factor, passion_factor
3. ❌ No mention of base_score (completion_pct)
4. ❌ Time bonus description is oversimplified (missing difficulty weighting and fading)
5. ❌ Range is incorrect (actual range is 0-200+)

---

### 2. Actual Implementation (analytics.py:754-852)

**Location:** `calculate_grit_score()` method

**Full Formula Breakdown:**

#### Base Score
```python
base_score = completion_pct  # 0-100
```

#### Persistence Factor (0.5-1.5 range)
```python
persistence_factor = calculate_persistence_factor(row, task_completion_counts)
persistence_factor_scaled = 0.5 + persistence_factor * 1.0
```

**Persistence Factor Components (from `calculate_persistence_factor()`):**
1. **Obstacle Overcoming (40%):** Completing despite high cognitive/emotional load
2. **Aversion Resistance (30%):** Completing despite high aversion
3. **Task Repetition (20%):** Completing same task multiple times
4. **Consistency (10%):** Regular completion patterns over time

**Persistence Multiplier (also used):**
- Power curve growth: `1.0 + 0.015 * max(0, completion_count - 1) ** 1.001`
- Familiarity decay after 100+ completions
- Range: 1.0-5.0 (capped)

#### Focus Factor (0.5-1.5 range)
```python
focus_factor = calculate_focus_factor(row)
focus_factor_scaled = 0.5 + focus_factor * 1.0
```

**Focus Factor Components:**
- **100% emotion-based** (mental state, not behavioral)
- Focus-positive emotions: focused, concentrated, determined, engaged, flow, present, mindful, etc.
- Focus-negative emotions: distracted, scattered, overwhelmed, unfocused, restless, anxious, etc.
- Net score: `0.5 + (positive_score - negative_score) * 0.5`

#### Passion Factor (0.5-1.5 range)
```python
relief = actual_dict.get('actual_relief', 0)
emotional = actual_dict.get('actual_emotional', 0)
relief_norm = max(0.0, min(1.0, relief / 100.0))
emotional_norm = max(0.0, min(1.0, emotional / 100.0))
passion_delta = relief_norm - emotional_norm
passion_factor = 1.0 + passion_delta * 0.5
# Dampened if completion < 100%
if completion_pct < 100:
    passion_factor *= 0.9
passion_factor = max(0.5, min(1.5, passion_factor))
```

**Passion Factor Logic:**
- Positive if relief outweighs emotional load (passion/engagement)
- Negative if emotional load outweighs relief (drain)
- Dampened for incomplete tasks

#### Time Bonus (1.0+ range)
```python
if time_ratio > 1.0:
    excess = time_ratio - 1.0
    if excess <= 1.0:
        base_time_bonus = 1.0 + (excess * 0.8)  # up to 1.8x at 2x longer
    else:
        base_time_bonus = 1.8 + ((excess - 1.0) * 0.2)  # diminishing beyond 2x
    base_time_bonus = min(3.0, base_time_bonus)
    
    # Difficulty weighting (harder tasks get more credit)
    task_difficulty = actual_dict.get('task_difficulty', 50)
    difficulty_factor = max(0.0, min(1.0, task_difficulty / 100.0))
    weighted_time_bonus = 1.0 + (base_time_bonus - 1.0) * (0.5 + 0.5 * difficulty_factor)
    
    # Fade time bonus after many repetitions
    fade = 1.0 / (1.0 + max(0, completion_count - 10) / 40.0)
    time_bonus = 1.0 + (weighted_time_bonus - 1.0) * fade
else:
    time_bonus = 1.0
```

**Time Bonus Features:**
- Linear scaling up to 2x longer (1.8x bonus)
- Diminishing returns beyond 2x longer
- **Difficulty weighting:** Harder tasks get more credit for taking longer
- **Fading:** Time bonus fades after many repetitions (negligible after ~50 completions)
- Capped at 3.0x maximum

---

## Does the Formula Accurately Capture Grit?

### Grit Definition (Angela Duckworth)
Grit = **Passion** + **Perseverance** for long-term goals

### Current Formula Assessment

#### ✅ **Strengths:**

1. **Persistence Factor** - ✅ **EXCELLENT**
   - Captures obstacle overcoming (40% weight)
   - Captures aversion resistance (30% weight)
   - Captures task repetition (20% weight)
   - Captures consistency (10% weight)
   - **This directly measures perseverance**

2. **Focus Factor** - ✅ **GOOD**
   - Emotion-based mental state
   - Captures ability to concentrate despite distractions
   - **This measures mental engagement (part of passion)**

3. **Passion Factor** - ✅ **GOOD**
   - Relief vs emotional load balance
   - Positive when relief > emotional load (engagement)
   - **This measures passion/engagement**

4. **Time Bonus** - ✅ **GOOD**
   - Rewards taking longer (dedication)
   - Difficulty-weighted (harder tasks get more credit)
   - Fades with repetition (prevents gaming)
   - **This measures perseverance (sticking with it)**

5. **Base Score** - ✅ **GOOD**
   - Completion percentage
   - **This measures actual accomplishment**

#### ⚠️ **Potential Issues:**

1. **Complexity vs. Simplicity**
   - Formula is quite complex (4 factors × multiple sub-components)
   - May be difficult to understand/explain
   - **But:** Complexity is justified by comprehensive grit measurement

2. **Persistence Factor vs. Persistence Multiplier**
   - Two different persistence measures:
     - `persistence_factor` (obstacle overcoming, etc.) - used in formula
     - `persistence_multiplier` (completion count growth) - calculated but NOT used in final formula
   - **Issue:** The completion count multiplier is calculated but not applied
   - **Recommendation:** Either use it or remove it

3. **Time Bonus Fading**
   - Time bonus fades after 10+ completions
   - **Rationale:** Prevents gaming (taking longer on routine tasks)
   - **Potential issue:** May undervalue long-term persistence on routine tasks
   - **Assessment:** Probably correct - routine tasks shouldn't get time bonus

4. **Missing Long-Term Goal Component**
   - Grit is about **long-term goals**, but formula is per-task
   - **Assessment:** This is acceptable - per-task grit can aggregate to long-term grit

5. **No Consistency Over Time**
   - Formula doesn't explicitly reward consistency over weeks/months
   - **Assessment:** Persistence factor includes consistency (10%), but could be stronger

---

## Recommendations

### 1. **IMMEDIATE: Update Glossary** ⚠️ **CRITICAL**
   - Update formula to match actual implementation
   - Add all 4 components (persistence, focus, passion, time_bonus)
   - Update range to 0-200+
   - Add detailed component breakdowns

### 2. **Review Persistence Multiplier Usage** ⚠️ **CODE ISSUE**
   - **CRITICAL:** `persistence_multiplier` is calculated (lines 780-788) but **NOT USED** in final formula
   - Two different persistence measures exist:
     - `persistence_multiplier`: Based on completion count growth (1.0-5.0 range, calculated but unused)
     - `persistence_factor`: From `calculate_persistence_factor()` (0.0-1.0 range, actually used)
   - **Action Required:** 
     - Option A: Remove unused `persistence_multiplier` calculation
     - Option B: Integrate `persistence_multiplier` into final formula (combine with `persistence_factor_scaled`)
   - **Recommendation:** Option A (remove) - `persistence_factor` already captures repetition (20% weight)

### 3. **Consider Long-Term Consistency**
   - Add optional component for consistency over weeks/months
   - Could be separate metric or enhancement to persistence_factor

### 4. **Documentation**
   - Update `formula_review_analysis.md` (also outdated)
   - Add version history (v1.0 → v1.2)
   - Document rationale for each component

---

## Conclusion

### Does the Formula Accurately Capture Grit?

**YES** ✅ - The actual implementation (v1.2) is **much better** than the glossary suggests.

The formula captures:
- ✅ **Perseverance:** Persistence factor (obstacle overcoming, aversion resistance, repetition, consistency)
- ✅ **Passion:** Focus factor (mental engagement) + Passion factor (relief vs emotional load)
- ✅ **Dedication:** Time bonus (taking longer, especially on difficult tasks)
- ✅ **Accomplishment:** Base score (completion percentage)

**However:**
- ⚠️ Glossary is **severely outdated** and misleading
- ⚠️ Formula is complex but justified
- ⚠️ Persistence multiplier calculated but not used

**Overall Assessment:** The actual formula is **well-designed** and accurately captures grit. The glossary needs immediate updating to reflect reality.

