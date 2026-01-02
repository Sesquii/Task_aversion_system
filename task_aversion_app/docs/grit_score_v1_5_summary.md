# Grit Score v1.5 Summary: Design Decisions

## Implementation Complete

Two competing versions have been created:
- **v1.5a (Median-based):** `calculate_grit_score_v1_5a_median()`
- **v1.5b (Mean-based):** `calculate_grit_score_v1_5b_mean()`

Both implement:
1. ✅ Median/Mean thresholds (Option 1)
2. ✅ Exponential SD-based bonuses (Option 2)
3. ✅ Dynamic recalibration
4. ✅ "Suddenly challenging" detection

---

## Design Decision: "Suddenly Challenging" Bonus

### The Scenario
**Question:** "What bonus for a task done 71 times that suddenly becomes very challenging?"

### The Answer: **5-15% bonus based on spike magnitude**

**Detection Logic:**
```python
# Compare current load to recent baseline (last 10 instances)
baseline_load = mean(recent_loads)
current_load = (cognitive + emotional) / 2.0
spike_sds = (current_load - baseline_load) / baseline_std

# Bonus structure:
2 SD spike → 5% bonus   (moderate challenge)
3 SD spike → 10% bonus  (significant challenge)
4+ SD spike → 15% bonus (extreme challenge)
```

### Why This Design?

1. **Recognizes Adaptability:** Overcoming unexpected obstacles is impressive
2. **Balances Routine vs Challenge:** 
   - Routine tasks get persistence bonus (high completion count)
   - Sudden challenges get additional bonus (spike detection)
3. **Prevents Gaming:** Only triggers on significant spikes (2+ SD)
4. **Meaningful but Not Overwhelming:** 15% max is significant but capped at 25% total

### Example from Your Data

**Task:** "Task Aversion project" (71 completions)
- **Baseline load:** ~25 (routine task)
- **Current load:** 75.5 (sudden challenge)
- **Spike:** (75.5 - 25) / 10 = 5.05 SD
- **Bonus:** 15% (extreme challenge) ✅

**Combined Bonuses:**
- Persistence bonus: ~10% (high completion count)
- Synergy bonus: ~4% (both high)
- Load bonus: ~4% (high load)
- **Sudden challenge bonus: 15%** (spike detection)
- **Total: ~33% → capped at 25%**

---

## Exponential SD-Based Bonuses

### How It Works

**Standard Deviation Calculation:**
```python
# Calculate how many SDs above threshold
perseverance_sds = (perseverance_factor - threshold) / std
persistence_sds = (persistence_factor - threshold) / std
```

**Exponential Bonus Curve:**
```
0-1 SD:  0-2% bonus   (linear)
1-2 SD:  2-5% bonus   (accelerating)
2-3 SD:  5-10% bonus  (faster)
3-4 SD:  10-15% bonus (very fast)
4+ SD:   15% bonus    (capped)
```

**Synergy Formula:**
```python
# Sub-linear to prevent extreme values
synergy = (perseverance_bonus * persistence_bonus) ** 0.7
# Cap at 12%
```

### Why Exponential?

1. **Rewards Exceptional Performance:** 3 SD is much harder than 1 SD
2. **Scales with Distribution:** Uses actual data std (adaptive)
3. **Prevents Gaming:** Hard to artificially inflate SDs
4. **Meaningful Differences:** 1 SD vs 3 SD produces noticeable bonus difference

---

## Dynamic Recalibration

### How It Works

**Statistics Calculation:**
```python
def _calculate_perseverance_persistence_stats(self):
    # Load all completed instances
    # Calculate factors for each
    # Return: {'perseverance': {'mean', 'median', 'std'}, ...}
```

**Recalibration:**
- Statistics recalculated from all historical data
- Thresholds update automatically
- Standard deviations adjust to current distribution

### Handling Anomalies

**Current Approach:**
- All data included in statistics
- Anomalies shift mean/median gradually
- Multiple anomalies needed to significantly shift thresholds

**Future Enhancement (if needed):**
- Exponential moving average (recent data weighted more)
- Outlier detection (exclude extreme values)
- Time-weighted statistics (recent completions count more)

### Example: Anomaly Impact

**Scenario:** Task suddenly becomes very challenging (load spikes from 25 to 75)

**Impact on Statistics:**
- **Mean:** Shifts slightly (one data point)
- **Median:** Unaffected (robust to outliers) ✅
- **Std:** Increases slightly (more variation)

**Result:**
- **v1.5a (Median):** Threshold stable, bonus still applies
- **v1.5b (Mean):** Threshold shifts slightly, may affect future bonuses

---

## Comparison: Median vs Mean

### From Your Data

**Statistics:**
- Perseverance median: 0.600, mean: ~0.610
- Persistence median: 1.165, mean: ~1.3

**"Both High" Tasks:**
- With median threshold: 36 tasks (13.5%)
- With mean threshold: Would be more (mean is higher)

### Which Is Better?

**Median (v1.5a) - Recommended:**
- ✅ Robust to outliers (anomalies don't break it)
- ✅ Represents "typical" performance
- ✅ More stable over time
- ✅ Better for "suddenly challenging" detection (baseline doesn't shift)

**Mean (v1.5b):**
- ✅ Sensitive to all values
- ✅ Captures gradual improvements
- ⚠️ Affected by outliers
- ⚠️ May shift with anomalies

**Recommendation:** Start with **v1.5a (median)** - more robust and stable.

---

## Total Bonus Structure

### Components

1. **Base Synergy:** 3% (minimum for "both high")
2. **SD-Based Synergy:** Up to 12% (exponential scaling)
3. **Load Bonus:** Up to 5% (high load recognition)
4. **Sudden Challenge:** Up to 15% (routine task with spike)

### Total Cap

**Maximum Total Bonus: 25%** (safety cap)

**Example Calculation:**
```
Base synergy:        3.0%
SD synergy:          4.0%  (perseverance 2 SD × persistence 3 SD)
Load bonus:          3.8%  (load = 75.5)
Sudden challenge:   15.0% (5 SD spike)
─────────────────────────
Total:              25.8% → capped at 25.0%
```

---

## Testing Plan

### 1. Compare v1.5a vs v1.5b

**Metrics:**
- Number of "both high" tasks caught
- Average synergy bonus magnitude
- Stability over time (recalculate with new data)

### 2. Validate "Suddenly Challenging"

**Test Cases:**
- Routine task (71 completions) with load spike (25 → 75)
- Verify detection triggers (2+ SD)
- Check bonus magnitude (5-15%)
- Ensure it doesn't trigger on normal variation

### 3. Test Dynamic Recalibration

**Scenarios:**
- Add new "both high" task → verify thresholds update
- Add anomaly → verify median stable, mean shifts
- Recalculate statistics → verify bonuses adjust

### 4. Compare with Previous Versions

**Versions to Compare:**
- v1.3 (baseline)
- v1.4 (threshold-based, didn't work)
- v1.5a (median, exponential SD)
- v1.5b (mean, exponential SD)

**Questions:**
- Do v1.5 versions produce meaningful bonuses?
- Is synergy actually working now?
- Which version (a or b) is better?

---

## Next Steps

1. **Run comparison script** (create script to test both versions)
2. **Analyze results** to determine which is better
3. **Tune parameters** if needed (SD thresholds, bonus amounts)
4. **Decide on final version** (v1.5a, v1.5b, or hybrid)

---

## Key Takeaways

1. **"Suddenly Challenging" Bonus:** 5-15% based on spike magnitude (2-4+ SD)
2. **Exponential SD Bonuses:** Rewards exceptional performance disproportionately
3. **Dynamic Recalibration:** Statistics update from historical data
4. **Median vs Mean:** Median is more robust, mean is more sensitive
5. **Total Cap:** 25% maximum bonus (safety limit)

The design addresses your question: **"How big should the bonus be for a routine task that suddenly becomes challenging?"** 

**Answer: Up to 15% bonus, combined with other bonuses can reach 25% total - significant recognition for overcoming unexpected obstacles while maintaining long-term commitment.**

