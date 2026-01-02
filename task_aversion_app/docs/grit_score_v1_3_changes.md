# Grit Score Formula v1.3 Changes

## Overview

Version 1.3 of the grit score formula addresses the issue where `persistence_multiplier` (completion count based) was calculated but not used in the final formula. This version:

1. **Renames factors for clarity:**
   - `persistence_factor` (from `calculate_persistence_factor()`) → `perseverance_factor`
   - `persistence_multiplier` (completion count) → `persistence_factor`

2. **Integrates persistence_factor into consistency component:**
   - Makes consistency harder to max out for tasks with many completions
   - Scales consistency score by persistence_factor (1.0-5.0 range → 1.0-1.5 scaling)

3. **Preserves v1.2 implementation:**
   - Original `calculate_grit_score()` remains unchanged (v1.2)
   - New `calculate_grit_score_v1_3()` implements the updated formula

---

## Factor Naming Rationale

### Perseverance Factor (formerly persistence_factor)
- **Definition:** Continuing despite obstacles
- **Components:**
  - Obstacle overcoming (40%): Completing despite high cognitive/emotional load
  - Aversion resistance (30%): Completing despite high aversion
  - Task repetition (20%): Completing same task multiple times
  - Consistency (10%): Regular completion patterns over time
- **Range:** 0.0-1.0 (scaled to 0.5-1.5 in formula)

### Persistence Factor (formerly persistence_multiplier)
- **Definition:** Completion count multiplier (power curve with familiarity decay)
- **Formula:** `1.0 + 0.015 * (completion_count - 1) ** 1.001` with decay after 100+ completions
- **Range:** 1.0-5.0
- **Purpose:** Rewards repeated completion over time

---

## Changes in v1.3

### 1. Consistency Component Integration

**v1.2 (Original):**
```python
# Consistency score based on variance in completion timing
consistency_score = 1.0 - min(1.0, variance / max_variance)
```

**v1.3 (Updated):**
```python
# Consistency score scaled by persistence_factor
base_consistency = 1.0 - min(1.0, variance / max_variance)
persistence_factor_scaled = 1.0 + (persistence_factor - 1.0) * 0.125  # 1.0→1.0, 5.0→1.5
consistency_score = base_consistency / persistence_factor_scaled
```

**Effect:**
- Tasks with 1 completion: persistence_factor = 1.0 → no scaling (same as v1.2)
- Tasks with 10 completions: persistence_factor ≈ 1.22 → consistency_score reduced by ~2.5%
- Tasks with 50 completions: persistence_factor ≈ 2.6 → consistency_score reduced by ~13%
- Tasks with 100+ completions: persistence_factor ≈ 4.1 → consistency_score reduced by ~28%

**Rationale:**
- Makes consistency harder to max out for tasks with many completions
- Prevents routine tasks from getting maximum consistency score too easily
- Rewards both consistency AND high completion count (persistence)

### 2. Method Names

**v1.2:**
- `calculate_grit_score()` - main method
- `calculate_persistence_factor()` - obstacle overcoming factor

**v1.3:**
- `calculate_grit_score()` - unchanged (v1.2 implementation)
- `calculate_grit_score_v1_3()` - new v1.3 implementation
- `calculate_perseverance_factor_v1_3()` - renamed from `calculate_persistence_factor()`

---

## Formula Comparison

### v1.2 Formula
```python
grit_score = base_score * (
    persistence_factor_scaled *  # 0.5-1.5 (obstacle overcoming)
    focus_factor_scaled *        # 0.5-1.5 (mental engagement)
    passion_factor *             # 0.5-1.5 (relief vs emotional load)
    time_bonus                   # 1.0+ (taking longer)
)
# Note: persistence_multiplier calculated but NOT USED
```

### v1.3 Formula
```python
# Calculate persistence_factor (completion count multiplier)
persistence_factor = calculate_persistence_factor(completion_count)  # 1.0-5.0

# Calculate perseverance_factor (obstacle overcoming) with persistence_factor integration
perseverance_factor = calculate_perseverance_factor_v1_3(
    row, 
    persistence_factor=persistence_factor  # Used in consistency component
)  # 0.0-1.0

grit_score = base_score * (
    perseverance_factor_scaled *  # 0.5-1.5 (obstacle overcoming, consistency scaled)
    focus_factor_scaled *        # 0.5-1.5 (mental engagement)
    passion_factor *             # 0.5-1.5 (relief vs emotional load)
    time_bonus                   # 1.0+ (taking longer)
)
```

---

## Expected Impact

### Tasks with Low Completion Count (1-3)
- **Impact:** Minimal change
- **Reason:** persistence_factor ≈ 1.0, so consistency scaling is negligible
- **Expected difference:** < 1% change in grit score

### Tasks with Medium Completion Count (4-10)
- **Impact:** Small decrease in consistency component
- **Reason:** persistence_factor ≈ 1.1-1.3, so consistency_score reduced by 1-3%
- **Expected difference:** 1-3% decrease in grit score

### Tasks with High Completion Count (11-50)
- **Impact:** Moderate decrease in consistency component
- **Reason:** persistence_factor ≈ 1.3-2.6, so consistency_score reduced by 3-13%
- **Expected difference:** 0.3-1.3% decrease in grit score (consistency is only 10% weight)

### Tasks with Very High Completion Count (50+)
- **Impact:** Larger decrease in consistency component
- **Reason:** persistence_factor ≈ 2.6-5.0, so consistency_score reduced by 13-28%
- **Expected difference:** 1.3-2.8% decrease in grit score (consistency is only 10% weight)

---

## Analysis Script

A script has been created to compare v1.2 and v1.3 with real data:

**Location:** `task_aversion_app/scripts/analyze_grit_score_formulas.py`

**Usage:**
```bash
cd task_aversion_app
python scripts/analyze_grit_score_formulas.py
```

**Output:**
- Console report with summary statistics
- `data/grit_score_comparison_report.txt` - Detailed analysis report
- `data/grit_score_comparison_results.csv` - Per-instance comparison data

**Report Includes:**
- Summary statistics (mean, median, min, max, std) for both versions
- Difference analysis (increased/decreased/unchanged counts)
- Completion count analysis (grouped by ranges)
- Correlation analysis
- Key insights and recommendations

---

## Migration Path

### Current State
- `calculate_grit_score()` uses v1.2 formula (unchanged)
- `calculate_grit_score_v1_3()` implements v1.3 formula (new)

### Recommended Steps
1. **Run analysis script** to compare v1.2 vs v1.3 with real data
2. **Review results** to ensure v1.3 better captures grit
3. **Validate** that persistence_factor integration works as intended
4. **Decide** whether to adopt v1.3 as the default
5. **If adopting:** Replace `calculate_grit_score()` with v1.3 implementation

### Backward Compatibility
- v1.2 implementation is preserved
- Can switch between versions by calling appropriate method
- No breaking changes to existing code

---

## Testing Checklist

- [ ] Run analysis script with real data
- [ ] Verify persistence_factor is calculated correctly (1.0-5.0 range)
- [ ] Verify consistency_score scaling works as expected
- [ ] Check that high completion count tasks show expected decrease
- [ ] Verify low completion count tasks show minimal change
- [ ] Review correlation between completion_count and difference
- [ ] Validate that overall formula still captures grit accurately

---

## Notes

- **Consistency weight:** Only 10% of perseverance_factor, so impact is modest
- **Scaling factor:** 0.125 chosen to provide meaningful but not excessive scaling
- **Familiarity decay:** Persistence_factor already includes decay after 100+ completions
- **Future consideration:** May want to adjust scaling factor based on analysis results

