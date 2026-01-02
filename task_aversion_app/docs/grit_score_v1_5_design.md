# Grit Score v1.5 Design: Median vs Mean with Exponential SD Bonuses

## Overview

Version 1.5 introduces two competing implementations:
- **v1.5a (Median-based):** Uses median for thresholds (robust to outliers)
- **v1.5b (Mean-based):** Uses mean for thresholds (sensitive to outliers)

Both versions feature:
1. **Exponential SD-based bonuses** - Rewards based on standard deviations above threshold
2. **Dynamic recalibration** - Statistics calculated from historical data
3. **"Suddenly Challenging" detection** - Special bonus for routine tasks with sudden high load
4. **Load-based bonus** - Additional recognition for high cognitive/emotional load

---

## Key Design Decisions

### 1. Median vs Mean Thresholds

**Median (v1.5a):**
- **Pros:** Robust to outliers, represents "typical" value
- **Cons:** Less sensitive to changes, may miss gradual improvements
- **Use Case:** Better for stable, consistent data

**Mean (v1.5b):**
- **Pros:** Sensitive to all values, captures gradual trends
- **Cons:** Affected by outliers, may be skewed by extreme values
- **Use Case:** Better for dynamic, evolving data

**From Data:**
- Perseverance median: 0.600, mean: ~0.610
- Persistence median: 1.165, mean: ~1.3
- **Difference:** Mean is higher due to high-completion-count tasks

---

### 2. Exponential SD-Based Bonuses

**Formula:**
```python
# Calculate standard deviations above threshold
perseverance_sds = (perseverance_factor - threshold) / std
persistence_sds = (persistence_factor - threshold) / std

# Exponential bonus curve
1 SD:  2% bonus
2 SD:  5% bonus
3 SD:  10% bonus
4+ SD: 15% bonus
```

**Rationale:**
- **Exponential scaling** rewards exceptional performance disproportionately
- **SD-based** ensures bonuses scale with data distribution
- **Sub-linear synergy** (`(bonus1 * bonus2) ** 0.7`) prevents extreme values

**Example:**
- Perseverance: 0.702 (median=0.600, std=0.05) → 2.04 SD → ~5% bonus
- Persistence: 2.054 (median=1.165, std=0.3) → 2.96 SD → ~10% bonus
- Synergy: (0.05 × 0.10) ** 0.7 = 0.037 → 3.7% synergy bonus

---

### 3. "Suddenly Challenging" Scenario

**Problem:** What bonus for a task done 71 times that suddenly becomes very challenging?

**Detection:**
```python
# Compare current load to recent baseline
baseline_load = mean(recent_10_instances)
current_load = (cognitive + emotional) / 2.0

# Detect spike (2+ standard deviations above baseline)
if current_load > baseline_load + (2.0 * std):
    is_suddenly_challenging = True
```

**Bonus Structure:**
- **2 SD spike:** 5% bonus
- **3 SD spike:** 10% bonus
- **4+ SD spike:** 15% bonus

**Design Rationale:**
- **Routine tasks** (high completion count) typically have low load
- **Sudden high load** represents overcoming unexpected obstacle
- **This is impressive** - shows grit in face of unexpected challenge
- **15% max bonus** is significant but not overwhelming

**Example Scenario:**
- Task: "Task Aversion project" (71 completions, usually load=25)
- Current: load=75.5 (3x higher than baseline)
- Baseline: load=25, std=10
- Spike: (75.5 - 25) / 10 = 5.05 SD → **15% bonus** ✅

**Why This Matters:**
- Rewards **adaptability** - handling unexpected challenges
- Recognizes **resilience** - not giving up when things get hard
- Balances **routine vs challenge** - routine tasks get persistence bonus, sudden challenges get additional bonus

---

### 4. Dynamic Recalibration

**How It Works:**
1. Calculate statistics from all completed instances
2. Update thresholds and standard deviations dynamically
3. Recalibrate when anomalies occur (new data shifts distribution)

**Benefits:**
- **Adaptive** - adjusts to user's actual performance patterns
- **Self-correcting** - handles data drift over time
- **Personalized** - thresholds based on individual's data

**Implementation:**
```python
def _calculate_perseverance_persistence_stats(self, instances_df=None):
    # Load all completed instances
    # Calculate perseverance_factor and persistence_factor for each
    # Return: {'perseverance': {'mean', 'median', 'std'}, 'persistence': {...}}
```

**Caching:** Statistics can be cached for performance (recalculate periodically)

---

### 5. Load-Based Bonus

**Formula:**
```python
combined_load = (cognitive_load + emotional_load) / 2.0
load_bonus = min(0.05, combined_load / 2000.0)  # Up to 5% for load=100
```

**Rationale:**
- High load = more impressive completion
- Up to 5% additional bonus
- Scales linearly with load (0-100 → 0-5%)

**Combined with Synergy:**
- Base synergy: 3%
- SD-based synergy: up to 12%
- Load bonus: up to 5%
- Sudden challenge: up to 15%
- **Total max: 35%** (capped at 25% for safety)

---

## Comparison: v1.5a vs v1.5b

| Aspect | v1.5a (Median) | v1.5b (Mean) |
|--------|----------------|--------------|
| Threshold | 0.600 (median) | ~0.610 (mean) |
| Robustness | High (outlier-resistant) | Low (sensitive to outliers) |
| Sensitivity | Lower (requires more to trigger) | Higher (easier to trigger) |
| Use Case | Stable data, consistent patterns | Dynamic data, evolving patterns |
| "Both High" Count | Fewer (more selective) | More (more inclusive) |

**From Data:**
- Median threshold: 36 "both high" tasks (13.5%)
- Mean threshold: Would catch more (mean is higher)

---

## Synergy Multiplier Breakdown

**Components:**
1. **Base Synergy:** 3% minimum for "both high"
2. **SD-Based Synergy:** Up to 12% (exponential scaling)
3. **Load Bonus:** Up to 5% (high load recognition)
4. **Sudden Challenge:** Up to 15% (routine task with spike)

**Total Formula:**
```python
synergy_multiplier = 1.0 + base_synergy + synergy_component + load_bonus + challenge_bonus
# Capped at 1.25 (25% total bonus)
```

**Example Calculation:**
- Perseverance: 0.702 (2.04 SD) → 5% bonus
- Persistence: 2.054 (2.96 SD) → 10% bonus
- Synergy: (0.05 × 0.10) ** 0.7 = 3.7%
- Load: 75.5 → 3.8% bonus
- Sudden challenge: 5.05 SD spike → 15% bonus
- **Total: 1.0 + 0.03 + 0.037 + 0.038 + 0.15 = 1.255 → capped at 1.25 (25%)**

---

## Design Questions & Answers

### Q: How big should the "suddenly challenging" bonus be?

**A: 5-15% based on spike magnitude**
- **Rationale:** Significant but not overwhelming
- **2 SD spike (moderate):** 5% - recognizes unexpected challenge
- **3 SD spike (significant):** 10% - substantial obstacle overcome
- **4+ SD spike (extreme):** 15% - exceptional resilience

**Why 15% max?**
- Balances with other bonuses (total cap at 25%)
- Significant enough to be meaningful
- Not so large it dominates the score

### Q: Should it recalibrate when anomalies happen?

**A: Yes, but gradually**
- **Current:** Recalculates statistics from all data
- **Future enhancement:** Could use exponential moving average
- **Anomaly handling:** Large spikes don't immediately shift baseline (needs multiple instances)

### Q: What if you've been doing a task a long time and then something really challenging happens?

**A: This is the "suddenly challenging" scenario - gets up to 15% bonus**
- **Detection:** Compares current load to recent baseline (last 10 instances)
- **Bonus:** 2 SD = 5%, 3 SD = 10%, 4+ SD = 15%
- **Combined with:** Persistence bonus (high completion count) + synergy bonus
- **Total impact:** Can reach 25% total bonus (capped)

**Example:**
- Task: 71 completions (high persistence)
- Baseline load: 25 (routine task)
- Current load: 75.5 (sudden challenge)
- Spike: 5.05 SD → 15% sudden challenge bonus
- Plus: Persistence bonus + synergy bonus
- **Result: Significant recognition for overcoming unexpected obstacle**

---

## Testing Recommendations

1. **Compare v1.5a vs v1.5b:**
   - Which catches more "both high" cases?
   - Which produces more meaningful bonuses?
   - Which is more stable over time?

2. **Validate "suddenly challenging" detection:**
   - Test with known spike scenarios
   - Verify bonus magnitude is appropriate
   - Check that it doesn't trigger on normal variation

3. **Test dynamic recalibration:**
   - Add new data and verify thresholds update
   - Check that anomalies don't break the system
   - Validate performance (caching works)

4. **Compare with v1.3/v1.4:**
   - Do v1.5 versions produce better scores?
   - Are bonuses more meaningful?
   - Does synergy actually work now?

---

## Next Steps

1. **Run comparison script** to test both versions
2. **Analyze results** to determine which is better
3. **Tune parameters** (SD thresholds, bonus amounts) if needed
4. **Decide on final version** (v1.5a or v1.5b, or hybrid)

