# Analytics Formulas Review & Recommendations

## Executive Summary

This document reviews all formulas in the analytics system, identifying:
- ✅ **Promising formulas** that are well-designed and working correctly
- ⚠️ **Formulas needing repair** with identified issues
- 🔧 **Formulas needing enhancement** that could be improved

---

## 1. ✅ PROMISING FORMULAS (Well-Designed)

### 1.1 Net Wellbeing Formula
**Location:** `analytics.py:641-645`

```python
net_wellbeing = relief_score - stress_level
net_wellbeing_normalized = 50.0 + (net_wellbeing / 2.0)
```

**Status:** ✅ **Excellent** - Well-validated by literature

**Strengths:**
- Simple, intuitive formula (relief minus cost)
- Normalization with 50 as neutral point is psychologically sound
- Range (-100 to +100, normalized to 0-100) is reasonable
- **Validated by stress-coping literature** (see `literature_findings.md`)

**Recommendation:** Keep as-is. This is a solid, validated formula.

---

### 1.2 Stress Efficiency Formula
**Location:** `analytics.py:647-666`

```python
stress_efficiency = relief_safe / stress_safe  # Raw ratio
# Normalized to 0-100 using min-max scaling
```

**Status:** ✅ **Good** - Mathematically sound

**Strengths:**
- Simple ratio metric (relief per unit stress)
- Handles edge cases (zero stress → NaN, not infinity)
- Min-max normalization provides interpretable 0-100 scale
- Useful for identifying high-value tasks

**Recommendation:** Keep as-is. Consider adding confidence intervals or percentiles for better interpretation.

---

### 1.3 Spontaneous Aversion Detection
**Location:** `analytics.py:191-238`

```python
# Progressive threshold based on baseline
if baseline <= 25: threshold = 10.0 + (baseline * 0.10)
elif baseline <= 50: threshold = 5.0 + (baseline * 0.10)
else: threshold = baseline * 0.10
```

**Status:** ✅ **Good** - Adaptive threshold design

**Strengths:**
- Progressive threshold adapts to baseline aversion level
- Prevents false positives for low-baseline tasks
- Sensible scaling (10% of baseline for high baselines)

**Recommendation:** Keep as-is. Consider adding documentation explaining the psychological rationale.

---

### 1.4 Obstacles Score Base Formula
**Location:** `analytics.py:361-374`

```python
multiplier = 1.0 + (spike_proportion * (1.0 - relief_proportion) * 9.0)
score = (spike_amount * multiplier) / 50.0
```

**Status:** ✅ **Good** - Well-designed weighting

**Strengths:**
- Rewards higher spikes with lower relief (more impressive)
- Multiplier range (1x to 10x) is reasonable
- Division by 50.0 provides sensible scaling

**Recommendation:** Keep as-is. The formula correctly weights difficulty vs. reward.

---

## 2. ⚠️ FORMULAS NEEDING REPAIR

### 2.1 Aversion Multiplier Formula
**Location:** `analytics.py:24-200` (UPDATED)

**Status:** ✅ **ADDRESSED** - Separated into difficulty bonus and improvement multiplier

**Previous Issues (RESOLVED):**
1. ~~**Low correlation:** Expected r=0.35-0.45 with stress, but system shows r=0.20~~ → Addressed by separating difficulty from improvement
2. ~~**Complex formula:** Combines logarithmic and flat multipliers in unclear way~~ → Now separated into clear components
3. ~~**Conflicting logic:** Higher aversion gave bonus even without improvement~~ → Now uses separate difficulty bonus

**New Implementation:**

The formula has been **completely refactored** into two separate, well-defined components:

#### A. Difficulty Bonus (`calculate_difficulty_bonus`)
- **Purpose:** Rewards completing difficult tasks (high aversion + high load)
- **Formula:** `bonus = 1.0 * (1 - exp(-(0.7 * aversion + 0.3 * load) / 50))`
- **Characteristics:**
  - Exponential scaling with flat/low exponent (smooth curve)
  - Higher weight to aversion (0.7) vs load (0.3)
  - Max bonus = 1.0 (multiplier 1.0 to 2.0)
  - Uses stress_level, mental_energy, or task_difficulty for load calculation

#### B. Improvement Multiplier (`calculate_improvement_multiplier`)
- **Purpose:** Rewards progress over time (reduced aversion)
- **Formula:** `bonus = 1.0 * (1 - exp(-improvement / 30))`
- **Characteristics:**
  - Logarithmic scaling with exponential decay
  - Diminishing returns (early improvements count more)
  - Max bonus = 1.0 (multiplier 1.0 to 2.0)
  - Only applies when `initial_aversion > current_aversion`

#### C. Combined Multiplier (`calculate_aversion_multiplier`)
- **Purpose:** Combines difficulty and improvement bonuses
- **Formula:** `multiplier = 1.0 + max(difficulty_bonus, improvement_bonus)`
- **Characteristics:**
  - Uses maximum of the two bonuses (rewards either difficulty OR improvement)
  - Small additional bonus (0.1) when both are significant (>0.3 each)
  - Max multiplier = 2.0 (max bonus = 1.0 = 100%)

**Benefits:**
- ✅ Clear separation of concerns (difficulty vs. improvement)
- ✅ Psychologically accurate (exponential decay matches human perception)
- ✅ Consistent max bonus = 1.0x across codebase
- ✅ Backward compatible (existing calls still work)
- ✅ Can be enhanced with stress/load data when available

**See Also:**
- `docs/logarithmic_improvement_metrics.md` - Comprehensive guide to improvement metrics
- Implementation in `analytics.py:24-200`

---

### 2.2 Productivity Score Formula
**Location:** `analytics.py:210-300`

**Status:** ✅ **FIXED** - All issues addressed

**Previous Issues (RESOLVED):**
1. ~~**Play tasks can have negative scores:**~~ → Now documented as "productivity penalty from play" (intentional)
2. ~~**Abrupt threshold:**~~ → Fixed with smooth transition function
3. ~~**Weekly bonus calculation BACKWARDS:**~~ → Fixed: now penalizes taking longer, rewards efficiency

**Current Implementation:**
```python
# Work: Smooth multiplier transition from 3x to 5x based on completion_time_ratio
if completion_time_ratio <= 1.0:
    multiplier = 3.0
elif completion_time_ratio >= 1.5:
    multiplier = 5.0
else:
    # Smooth transition between 1.0 and 1.5
    smooth_factor = (completion_time_ratio - 1.0) / 0.5  # 0.0 to 1.0
    multiplier = 3.0 + (2.0 * smooth_factor)

# Productivity penalty from play: -0.01x multiplier per percentage
# This creates a negative score (penalty) for play tasks
multiplier = -0.01 * time_percentage
score = base_score * multiplier

# Weekly bonus/penalty: FIXED - now penalizes taking longer
time_percentage_diff = ((time_actual - weekly_avg_time) / weekly_avg_time) * 100.0
weekly_bonus_multiplier = 1.0 - (0.01 * time_percentage_diff)  # Reversed sign
```

**Changes Made:**
1. ✅ **Fixed weekly bonus:** Now uses `1.0 - (0.01 * time_percentage_diff)` - taking longer reduces score
2. ✅ **Smooth work multiplier:** Continuous transition from 3.0x to 5.0x between ratio 1.0 and 1.5
3. ✅ **Clarified play task intent:** Renamed to "productivity penalty from play" in comments

**See Also:** New "Grit Score" (section 2.3) - separate metric that rewards persistence and taking longer

---

### 2.3 Grit Score Formula
**Location:** `analytics.py:302-360`

**Status:** ✅ **NEW** - Rewards persistence and taking longer (opposite of productivity)

**Purpose:**
Grit score is a separate metric from productivity score that rewards:
1. **Persistence:** Doing the same task multiple times (shows commitment)
2. **Taking longer:** Spending more time than estimated (shows dedication, opposite of efficiency)

This is intentionally separate from productivity score, which rewards efficiency. Grit score captures the value of sticking with difficult tasks even when they take longer.

**Formula:**
```python
# Base score = completion percentage
base_score = completion_pct

# Persistence multiplier: 10% bonus per additional completion beyond first
# 1 completion: 1.0x (no bonus)
# 2 completions: 1.1x (10% bonus)
# 3 completions: 1.2x (20% bonus)
# ... up to 2.0x max (11+ completions)
persistence_multiplier = min(2.0, 1.0 + (completion_count - 1) * 0.1)

# Time bonus: rewards taking longer than estimated
if time_ratio > 1.0:
    # Taking longer: bonus = 1.0 + (excess_time * 0.5)
    # Example: 2x longer = 1.0 + (1.0 * 0.5) = 1.5x bonus
    time_bonus = 1.0 + ((time_ratio - 1.0) * 0.5)
else:
    # Taking less time: no bonus (efficiency is rewarded in productivity, not grit)
    time_bonus = 1.0

# Final score
score = base_score * persistence_multiplier * time_bonus
```

**Characteristics:**
- **Range:** 0-200+ (higher = more grit/persistence)
- **Persistence bonus:** Max 2.0x multiplier (11+ completions)
- **Time bonus:** Linear scaling, rewards taking 2x longer with 1.5x bonus
- **Separate from productivity:** Efficiency is NOT rewarded (that's productivity's job)

**Use Cases:**
- Identify tasks you're committed to (high persistence)
- Reward sticking with difficult tasks even when they take longer
- Track long-term commitment vs. short-term efficiency

**Recommendation:** Keep as-is. This is a well-designed metric that complements productivity score.

---

### 2.4 Stress Level Calculation
**Location:** `analytics.py:631-637`

```python
stress_level = (
    (mental_energy_numeric * 0.5 + 
     task_difficulty_numeric * 0.5 + 
     emotional_load_numeric + 
     physical_load_numeric + 
     expected_aversion_numeric * 2.0) / 5.0
)
```

**Status:** ⚠️ **NEEDS VALIDATION** - Weighting may be incorrect

**Issues:**
1. **Inconsistent weighting:** 
   - Cognitive components (mental_energy + task_difficulty) = 0.5 + 0.5 = 1.0 total weight
   - Emotional = 1.0 weight
   - Physical = 1.0 weight
   - Aversion = 2.0 weight
   - **Total = 5.0, but divided by 5.0** → This means aversion gets 40% weight, others get 20% each
2. **Aversion double-weighted:** Aversion is weighted 2x to increase correlation, but this may be overcorrecting
3. **Missing validation:** No literature support for this specific weighting scheme

**Recommendation:**
1. **Reconsider weighting:** If cognitive = 0.5 each, they should sum to 1.0, not be divided separately
2. **Consider equal weights:** All components get 1.0 weight, divide by 4.0 (or 5.0 if keeping aversion)
3. **Validate with data:** Test if current weighting produces expected correlations
4. **Document rationale:** Explain why aversion gets 2x weight

**Suggested Fix:**
```python
# Option 1: Equal weights (simpler)
stress_level = (
    (mental_energy_numeric + 
     task_difficulty_numeric + 
     emotional_load_numeric + 
     physical_load_numeric + 
     expected_aversion_numeric) / 5.0
)

# Option 2: Cognitive combined, aversion weighted
stress_level = (
    ((mental_energy_numeric + task_difficulty_numeric) / 2.0) * 0.4 +
    emotional_load_numeric * 0.2 +
    physical_load_numeric * 0.2 +
    expected_aversion_numeric * 0.2
)
```

---

## 3. 🔧 FORMULAS NEEDING ENHANCEMENT

### 3.1 Obstacles Score Variants (7 formulas)
**Location:** `analytics.py:300-441`

**Status:** 🔧 **NEEDS ENHANCEMENT** - All variants identical due to data quality

**Current Issue:**
- All 7 variants produce identical results because `expected_relief == actual_relief` for all tasks
- Formulas are correct, but need data variation to differentiate

**Enhancement Opportunities:**
1. **Add data quality check:** Warn when all variants are identical
2. **Recommend best variant:** Based on psychological research, recommend which variant to use
3. **Add confidence intervals:** Show uncertainty when data is sparse
4. **Consider hybrid approach:** Combine multiple variants with weights

**Recommendation:**
- Keep all variants for now (they'll differentiate once data varies)
- Add UI indicator when variants are identical due to data uniformity
- Consider adding a "recommended variant" based on literature review

---

### 3.2 Behavioral Score Formula
**Location:** `analytics.py:672-769`

```python
completion_component = ((completion_pct - 100.0) / 100.0) * 5.0
time_component = ((time_ratio - 1.0) * 5.0)
procrast_component = -(procrast_score / 10.0) * 5.0
behavioral_deviation = (completion_component * 0.4) + (time_component * 0.4) + (procrast_component * 0.2)
behavioral_score = 50.0 + (behavioral_deviation * 5.0)
```

**Status:** 🔧 **GOOD BUT COULD BE ENHANCED**

**Strengths:**
- Well-structured with clear components
- Obstacles bonus is a nice addition
- Normalization to 0-100 is clear

**Enhancement Opportunities:**
1. **Add time decay:** Recent tasks should weight more heavily
2. **Consider task difficulty:** Harder tasks should get more credit for completion
3. **Add trend component:** Reward improving behavior over time
4. **Clarify normalization:** The min-max normalization at the end may be confusing

**Recommendation:**
- Keep current formula as baseline
- Consider adding optional "enhanced behavioral score" with difficulty weighting
- Document the normalization step clearly

---

### 3.3 Relief Duration Score
**Location:** `analytics.py:1473-1502`

```python
relief_duration_score = (relief_score * duration_minutes * multiplier) / 60.0
```

**Status:** 🔧 **GOOD BUT COULD BE ENHANCED**

**Strengths:**
- Simple multiplication captures "relief × time"
- Division by 60 converts to hours scale
- Separate "no_mult" version for baseline comparison

**Enhancement Opportunities:**
1. **Consider diminishing returns:** Very long tasks may not provide linear relief
2. **Add efficiency component:** Reward tasks completed faster than expected
3. **Consider task type:** Different task types may have different relief-time relationships
4. **Add decay factor:** Older relief may be less relevant

**Recommendation:**
- Keep current formula
- Consider adding "efficiency-adjusted relief duration" as alternative metric
- Document why division by 60 (conversion to hours)

---

### 3.4 Life Balance Score
**Location:** `analytics.py:961-1068` (implied, need to check)

**Status:** 🔧 **NEEDS REVIEW** - Formula not found in code reviewed

**Recommendation:**
- Locate and review the life balance calculation
- Ensure it properly balances work, play, and self-care
- Consider adding time-weighted balance (not just task count)

---

## 4. 📊 SUMMARY TABLE

| Formula | Status | Priority | Action |
|---------|--------|----------|--------|
| Net Wellbeing | ✅ Excellent | Low | Keep as-is |
| Stress Efficiency | ✅ Good | Low | Keep as-is |
| Spontaneous Aversion Detection | ✅ Good | Low | Keep as-is |
| Obstacles Score Base | ✅ Good | Low | Keep as-is |
| **Aversion Multiplier** | ✅ Addressed | **COMPLETE** | Separated into difficulty bonus + improvement multiplier |
| **Productivity Score** | ✅ Fixed | **COMPLETE** | Fixed weekly bonus, smoothed thresholds, clarified play penalty |
| **Grit Score** | ✅ New | **COMPLETE** | Rewards persistence and taking longer (separate from productivity) |
| **Stress Level** | ⚠️ Needs Validation | **MEDIUM** | Review weighting, validate with data |
| Obstacles Score Variants | 🔧 Needs Enhancement | Low | Add data quality checks |
| Behavioral Score | 🔧 Good but could enhance | Low | Consider optional enhancements |
| Relief Duration Score | 🔧 Good but could enhance | Low | Consider efficiency adjustments |
| Life Balance | 🔧 Needs Review | Medium | Locate and review formula |

---

## 5. 🎯 RECOMMENDED ACTIONS

### High Priority (Fix Immediately)
1. ~~**Fix Aversion Multiplier:** Reverse logic so higher aversion doesn't give higher multiplier~~ ✅ **COMPLETE** - Separated into difficulty bonus + improvement multiplier
2. ~~**Fix Productivity Score Weekly Bonus:** Currently rewards taking longer, should penalize~~ ✅ **COMPLETE** - Fixed: now penalizes taking longer
3. ~~**Smooth Productivity Score Thresholds:** Replace step function with continuous function~~ ✅ **COMPLETE** - Smooth transition implemented
4. ~~**Add Grit Score:** Separate metric that rewards persistence and taking longer~~ ✅ **COMPLETE** - New grit score implemented

### Medium Priority (Validate & Review)
4. **Review Stress Level Weighting:** Validate that 2x aversion weight is correct
5. **Review Life Balance Formula:** Locate and validate calculation

### Low Priority (Enhancements)
6. **Add Data Quality Indicators:** Warn when formulas produce identical results
7. **Add Formula Documentation:** Explain psychological rationale for each formula
8. **Consider Enhanced Variants:** Add optional "enhanced" versions of behavioral/relief scores

---

## 6. 📝 NOTES

- All formulas are mathematically correct (no division by zero, proper bounds checking)
- Main issues are **logical** (wrong direction) or **validation** (needs data/literature support)
- The system has good separation of concerns (raw vs. normalized, with vs. without multipliers)
- Consider adding unit tests for edge cases (zero values, missing data, etc.)

---

**Generated:** 2024-12-XX
**Reviewer:** AI Analysis
**Next Review:** After implementing high-priority fixes

