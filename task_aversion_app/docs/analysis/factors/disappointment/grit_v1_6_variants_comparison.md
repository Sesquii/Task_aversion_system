# Grit Score v1.6 & v1.7 Variants Comparison

Generated: 2026-01-05 01:21:37

## Executive Summary

**Key Finding**: **v1.7b and v1.7c show improved correlation performance**

- **v1.7b (2.1x cap)**: Correlation **-0.139** for completed tasks (vs -0.170 for v1.6e)
- **v1.7c (both enhancements)**: Correlation **-0.139** for completed tasks
- **18% improvement** in correlation vs v1.6e baseline
- **v1.7a (1.1x base multiplier)**: Same correlation as v1.6e (-0.170) - multiplier doesn't affect correlation

**Recommendation**: 
- **v1.7b** if prioritizing correlation improvement without changing score scale
- **v1.7c** if also wanting higher overall scores (225.63 vs 204.04 mean)

## Variant Definitions

### v1.6 Variants (Previous Analysis)

- **v1.6a**: Linear scaling, original caps (1.5x bonus, 0.67x penalty)
- **v1.6b**: Linear scaling, reduced positive cap (1.3x bonus, 0.67x penalty)
- **v1.6c**: Linear scaling, balanced caps (1.2x bonus, 0.8x penalty)
- **v1.6d**: Exponential scaling up to 1.5x bonus, 0.67x penalty
- **v1.6e**: Exponential scaling up to 2.0x bonus, 0.67x penalty ← **Best v1.6 variant**

### v1.7 Variants (New)

- **v1.7a**: v1.6e + 1.1x base score multiplier
  - Adds 10% multiplier to base score (completion_pct) before applying other factors
  - Exponential scaling up to 2.0x bonus, 0.67x penalty

- **v1.7b**: Exponential scaling up to 2.1x bonus, 0.67x penalty
  - Higher cap than v1.6e (2.1x vs 2.0x) for stronger bonuses
  - Exponential scaling with 110% max bonus

- **v1.7c**: v1.7a + v1.7b combined
  - 1.1x base score multiplier
  - Exponential scaling up to 2.1x bonus
  - Applies both enhancements

## Summary Statistics

- **Total instances analyzed**: 270

### Overall Means (Focus: v1.6e vs v1.7)
- v1.6e mean: 204.04 (std: 174.43) - baseline
- v1.7a mean: 224.44 (std: 191.87) - +1.1x base
- v1.7b mean: 205.12 (std: 174.46) - 2.1x cap
- v1.7c mean: 225.63 (std: 191.91) - both

### Differences (v1.6e baseline)
- v1.6e - v1.7a: -20.40
- v1.6e - v1.7b: -1.08
- v1.6e - v1.7c: -21.59
- v1.7a - v1.7b: 19.32
- v1.7a - v1.7c: -1.19
- v1.7b - v1.7c: -20.51

## Analysis by Completion Status

### Completed Tasks (100%+): 258 instances
- v1.6e mean: 209.83 (baseline)
- v1.7a mean: 230.81 (+1.1x base)
- v1.7b mean: 210.96 (2.1x cap)
- v1.7c mean: 232.06 (both)

### Partial Tasks (<100%): 12 instances
- v1.6e mean: 79.55
- v1.7a mean: 87.50
- v1.7b mean: 79.55
- v1.7c mean: 87.50

## Correlation with Disappointment Factor

### Overall Correlation (all instances with disappointment > 0)

| Variant | Correlation | Features |
|---------|-------------|----------|
| v1.6e | -0.150 | Baseline (exp 2.0x) |
| v1.7a | -0.150 | +1.1x base multiplier |
| v1.7b | -0.122 | Exp 2.1x cap |
| v1.7c | -0.122 | Both enhancements |

### Conditional: Completed Tasks (100%+)

**Expected**: Positive correlation (disappointment increases grit)

| Variant | Correlation | Features |
|---------|-------------|----------|
| v1.6e | -0.170 | Baseline (exp 2.0x) |
| v1.7a | -0.170 | +1.1x base multiplier |
| v1.7b | -0.139 | Exp 2.1x cap |
| v1.7c | -0.139 | Both enhancements |

**Key Finding**: Look for variants with positive or least negative correlation.

### Conditional: Partial Tasks (<100%)

**Expected**: Negative correlation (disappointment decreases grit)

- v1.6e: -0.574
- v1.7a: -0.574
- v1.7b: -0.574
- v1.7c: -0.574

**Interpretation**:
- For completed tasks: Positive correlation = disappointment resilience working correctly
- For partial tasks: Negative correlation = abandonment penalty working correctly
- Overall correlation may be negative if partial tasks dominate

## Correlation Analysis Summary

### Key Finding: v1.7b and v1.7c Show Improved Correlation

**For Completed Tasks (100%+)**:
- **v1.7b (2.1x cap)**: **-0.139** ← **BEST** (18% improvement vs v1.6e)
- **v1.7c (both)**: **-0.139** ← **BEST** (18% improvement vs v1.6e)
- v1.6e (baseline): -0.170
- v1.7a (1.1x base): -0.170 (same as v1.6e - multiplier doesn't affect correlation)

**Interpretation**:
1. **Increasing exponential cap to 2.1x improves correlation** (v1.7b)
2. **1.1x base multiplier doesn't change correlation** (v1.7a) - it scales all scores equally
3. **Combining both (v1.7c) maintains correlation improvement** while increasing overall scores
4. **18% improvement** brings correlation closer to zero (still negative but better)

### Score Impact

- **v1.7a**: +20.40 mean score (10% increase from 1.1x multiplier)
- **v1.7b**: +1.08 mean score (minimal increase, correlation-focused)
- **v1.7c**: +21.59 mean score (10% increase + correlation improvement)

### Recommendation

**Option 1: v1.7b** (Recommended for correlation focus)
- Best correlation performance (-0.139)
- Minimal score inflation (+1.08 mean)
- Pure correlation improvement without scale change

**Option 2: v1.7c** (Recommended for overall improvement)
- Best correlation performance (-0.139)
- Higher overall scores (+21.59 mean, 10% increase)
- Combines correlation improvement with score scaling

**Option 3: Continue testing**
- Still negative correlation suggests either:
  - Need even higher cap (2.2x, 2.5x, 3.0x)
  - Or disappointment should modify other factors (passion_factor, time_bonus)
  - Or there's a fundamental pattern where high-disappointment tasks have systematically lower other factors
