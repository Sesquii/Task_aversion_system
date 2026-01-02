# Grit Score Formula v1.4: Synergy Multiplier

## Overview

Version 1.4 adds a **synergy multiplier** that rewards tasks with **BOTH** high perseverance (obstacle overcoming) **AND** high persistence (repeated completion). This addresses the insight that tasks showing both qualities should receive additional recognition.

---

## Synergy Multiplier Design

### Concept

Tasks that demonstrate:
- **High Perseverance:** Continuing despite obstacles (high cognitive/emotional load, high aversion)
- **High Persistence:** Repeated completion over time (high completion count)

...should receive a bonus multiplier to recognize the combination of both qualities.

### Formula

```python
# Check if both are "high" (above thresholds)
is_high_perseverance = perseverance_factor >= perseverance_threshold  # default: 0.75
is_high_persistence = persistence_factor >= persistence_threshold    # default: 2.0

if is_high_perseverance and is_high_persistence:
    # Calculate bonuses (0.0-1.0 range) based on how far above threshold
    perseverance_bonus = max(0, (perseverance_factor - threshold) / (1.0 - threshold))
    persistence_bonus = max(0, (persistence_factor - threshold) / (5.0 - threshold))
    
    # Synergy multiplier: 1.0 + (bonus_product * strength)
    synergy_multiplier = 1.0 + (perseverance_bonus * persistence_bonus * synergy_strength)
    # Default synergy_strength = 0.15 (15% max bonus)
else:
    synergy_multiplier = 1.0  # No bonus
```

### Parameters

- **perseverance_threshold:** Default 0.75 (75th percentile)
  - Tasks with perseverance_factor ≥ 0.75 are considered "high perseverance"
  
- **persistence_threshold:** Default 2.0 (approximately 25+ completions)
  - Tasks with persistence_factor ≥ 2.0 are considered "high persistence"
  
- **synergy_strength:** Default 0.15 (15% maximum bonus)
  - Controls the strength of the synergy bonus
  - Range: 0.0-0.3 recommended (0-30% bonus)

### Bonus Calculation

**Perseverance Bonus:**
- If perseverance_factor = 0.75 (threshold): bonus = 0.0
- If perseverance_factor = 1.0 (max): bonus = 1.0
- Linear interpolation between threshold and max

**Persistence Bonus:**
- If persistence_factor = 2.0 (threshold): bonus = 0.0
- If persistence_factor = 5.0 (max): bonus = 1.0
- Linear interpolation between threshold and max

**Synergy Multiplier:**
- Minimum (at threshold): 1.0 (no bonus)
- Maximum (both maxed): 1.0 + (1.0 × 1.0 × 0.15) = 1.15 (15% bonus)
- Typical (both moderately high): 1.0 + (0.5 × 0.5 × 0.15) = 1.0375 (3.75% bonus)

---

## Updated Formula (v1.4)

```python
grit_score = base_score * (
    perseverance_factor_scaled *  # 0.5-1.5 range
    focus_factor_scaled *         # 0.5-1.5 range
    passion_factor *              # 0.5-1.5 range
    time_bonus *                  # 1.0+ range
    synergy_multiplier            # 1.0-1.15 range (NEW in v1.4)
)
```

---

## Expected Impact

### Tasks with High Perseverance Only
- **Impact:** No change (synergy_multiplier = 1.0)
- **Reason:** Missing high persistence

### Tasks with High Persistence Only
- **Impact:** No change (synergy_multiplier = 1.0)
- **Reason:** Missing high perseverance

### Tasks with BOTH High Perseverance AND High Persistence
- **Impact:** 3-15% bonus depending on how high both factors are
- **Example:**
  - Perseverance = 0.80, Persistence = 2.5
  - Perseverance bonus = (0.80 - 0.75) / (1.0 - 0.75) = 0.2
  - Persistence bonus = (2.5 - 2.0) / (5.0 - 2.0) = 0.167
  - Synergy = 1.0 + (0.2 × 0.167 × 0.15) = 1.005 (0.5% bonus)
  
- **Example (higher):**
  - Perseverance = 0.90, Persistence = 3.5
  - Perseverance bonus = (0.90 - 0.75) / (1.0 - 0.75) = 0.6
  - Persistence bonus = (3.5 - 2.0) / (5.0 - 2.0) = 0.5
  - Synergy = 1.0 + (0.6 × 0.5 × 0.15) = 1.045 (4.5% bonus)

---

## Analysis Script

Use the extraction script to identify tasks in each category:

**Location:** `task_aversion_app/scripts/extract_perseverance_persistence_tasks.py`

**Usage:**
```bash
cd task_aversion_app
python scripts/extract_perseverance_persistence_tasks.py
```

**Output:**
- `data/perseverance_persistence_analysis.txt` - Analysis report
- `data/perseverance_persistence_data.csv` - All task data
- `data/high_perseverance_only_tasks.csv` - High perseverance only
- `data/high_persistence_only_tasks.csv` - High persistence only
- `data/both_high_tasks.csv` - Both high (will benefit from synergy)

---

## Rationale

### Why Synergy?

1. **Separate Qualities:** Perseverance and persistence measure different aspects of grit
   - Perseverance: Overcoming obstacles in the moment
   - Persistence: Long-term commitment over time

2. **Combined Value:** Tasks showing both qualities are particularly impressive
   - Not just overcoming obstacles once
   - Not just repeating easy tasks
   - But: Overcoming obstacles repeatedly over time

3. **Psychological Accuracy:** Grit research (Duckworth) emphasizes both passion (perseverance) and perseverance (persistence)

### Why Multiplicative Bonus?

- **Multiplicative** (perseverance_bonus × persistence_bonus) ensures:
  - Both must be high to get significant bonus
  - Bonus scales with how high both are
  - Prevents gaming (can't get bonus with just one high)

- **Synergy Strength** controls overall impact:
  - 0.15 (15%) = modest bonus, doesn't overwhelm other factors
  - Can be adjusted based on analysis results

---

## Comparison: v1.2 vs v1.3 vs v1.4

| Version | Key Feature | Persistence Factor Usage |
|---------|-------------|-------------------------|
| v1.2 | Basic formula | Calculated but NOT USED |
| v1.3 | Integrated into consistency | Used in consistency component (makes it harder to max out) |
| v1.4 | Added synergy multiplier | Used in consistency component + synergy bonus |

---

## Testing Checklist

- [ ] Run extraction script to identify task categories
- [ ] Verify synergy multiplier only applies to "both high" tasks
- [ ] Check that bonus scales appropriately with factor values
- [ ] Validate thresholds (0.75 for perseverance, 2.0 for persistence)
- [ ] Test synergy_strength parameter (0.15 default)
- [ ] Compare v1.3 vs v1.4 scores for "both high" tasks
- [ ] Ensure no bonus for "only high" tasks

---

## Future Considerations

1. **Adaptive Thresholds:** Could calculate thresholds dynamically from data (percentiles)
2. **Non-linear Synergy:** Could use exponential or power curve instead of linear
3. **Synergy Decay:** Could reduce synergy bonus for very high completion counts (routine tasks)
4. **Focus/Passion Integration:** Could include focus_factor or passion_factor in synergy calculation

---

## Notes

- **Threshold Selection:** Defaults (0.75, 2.0) are reasonable starting points but should be validated with data
- **Synergy Strength:** 0.15 (15%) is conservative - can be increased if analysis shows it's too weak
- **Backward Compatibility:** v1.2 and v1.3 implementations are preserved for comparison

