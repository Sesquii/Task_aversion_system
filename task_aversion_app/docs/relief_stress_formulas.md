# Relief-Stress Relationship Formulas

## Overview

This document describes the formulas for measuring relief, stress, and their relationships. These formulas ensure that relief score is inversely correlated with stress score and provide clear differentiation between relief score and net wellbeing.

## Core Metrics

### 1. Relief Score
**Definition:** Raw measure of relief felt after task completion (0-100 scale)

**Calculation:**
- Extracted from `actual_relief` in the `actual_dict` JSON field
- Scaled from 0-10 to 0-100 if needed (for backward compatibility)
- Stored in `relief_score` CSV column (actual values only, never expected values)

**Key Points:**
- Relief score is a direct measure of how much relief you felt
- Higher values = more relief
- This is the raw input metric, not a calculated composite

### 2. Stress Level
**Definition:** Combined measure of cognitive, emotional, physical, and aversion stress

**Calculation:**
```python
stress_level = (
    (mental_energy_needed * 0.5 + task_difficulty * 0.5) +  # Cognitive
    emotional_load +                                          # Emotional
    physical_load +                                           # Physical
    expected_aversion * 2.0                                    # Aversion (weighted 2x)
) / 5.0
```

**Key Points:**
- Weighted average of stress components
- Aversion is weighted 2x to reflect its importance
- Range: 0-100

## Relationship Metrics

### 3. Net Wellbeing
**Definition:** Net benefit/cost of a task (relief minus stress)

**Formula:**
```python
net_wellbeing = relief_score - stress_level
```

**Range:** -100 to +100
- **Positive values:** Task provided more relief than stress (beneficial)
- **Negative values:** Task caused more stress than relief (costly)
- **Zero:** Neutral (relief exactly equals stress)

**Difference from Relief Score:**
- **Relief Score:** Raw measure of relief (0-100)
- **Net Wellbeing:** Relief MINUS stress, showing the NET benefit/cost
  - A task with high relief (80) but high stress (90) = -10 net wellbeing (costly)
  - A task with moderate relief (60) but low stress (30) = +30 net wellbeing (beneficial)

### 4. Net Wellbeing (Normalized)
**Definition:** Net wellbeing normalized to 0-100 scale with 50 as neutral

**Formula:**
```python
net_wellbeing_normalized = 50.0 + (net_wellbeing / 2.0)
```

**Range:** 0-100
- **50:** Neutral (relief = stress)
- **>50:** Beneficial (relief > stress)
- **<50:** Costly (stress > relief)

### 5. Stress Efficiency
**Definition:** Relief per unit of stress (efficiency ratio)

**Formula:**
```python
stress_efficiency = relief_score / stress_level
```

**Range:** 0 to infinity (normalized to 0-100 for display)
- **Higher values:** More relief per unit stress (more efficient)
- **Lower values:** Less relief per unit stress (less efficient)
- **NaN:** When stress_level is 0 or missing (avoid division by zero)

**Normalization:**
- Raw ratio is min-max normalized to 0-100 scale for visualization
- Original raw ratio stored in `stress_efficiency_raw`

**Note:** This is the preferred ratio metric. The inverse (stress/relief) was removed to avoid redundancy.

### 6. Expected Relief
**Definition:** Relief predicted before task completion (from initialization)

**Source:**
- Stored in `predicted_dict` as `expected_relief`
- Set during task initialization
- Represents your prediction of how much relief you'll feel

**Range:** 0-100

**Use Case:**
- Compare with actual relief to measure prediction accuracy
- Identify tasks where expectations don't match reality

### 7. Net Relief
**Definition:** Difference between actual and expected relief

**Formula:**
```python
net_relief = actual_relief - expected_relief
```

**Range:** -100 to +100
- **Positive values:** Actual relief exceeded expectations (pleasant surprise)
- **Negative values:** Actual relief fell short of expectations (disappointment)
- **Zero:** Actual relief matched expectations (accurate prediction)

**Interpretation:**
- **Large positive (>20):** Pleasant surprise - task was more rewarding than expected
- **Small positive (5-20):** Slightly better than expected
- **Near zero (±5):** Accurate prediction - good self-awareness
- **Small negative (-5 to -20):** Slightly worse than expected
- **Large negative (<-20):** Disappointment - task was less rewarding than expected

### 8. Serendipity Factor
**Definition:** Measures pleasant surprise when actual relief exceeds expectations

**Formula:**
```python
serendipity_factor = max(0, net_relief)
```

**Range:** 0-100
- **0:** No pleasant surprise (actual ≤ expected)
- **1-100:** Degree of pleasant surprise (actual > expected)

**Characteristics:**
- Only positive when net_relief > 0
- Zero when net_relief ≤ 0
- Represents positive emotional experience
- **Not a standalone score** - used as a factor/component in formulas
- Can be used as a bonus/multiplier in other formulas

**Use Cases:**
- Reward tasks that exceed expectations
- Boost scores for pleasant surprises
- Track positive prediction errors
- See `factors_concept.md` for formula integration patterns

### 9. Disappointment Factor
**Definition:** Measures disappointment when actual relief falls short of expectations

**Formula:**
```python
disappointment_factor = max(0, -net_relief)
```

**Range:** 0-100
- **0:** No disappointment (actual ≥ expected)
- **1-100:** Degree of disappointment (actual < expected)

**Characteristics:**
- Only positive when net_relief < 0
- Zero when net_relief ≥ 0
- Stored as positive value for easier formula integration
- Represents negative emotional experience
- **Not a standalone score** - used as a factor/component in formulas
- Can be used as a penalty/reduction in other formulas

**Use Cases:**
- Penalize tasks that fall short of expectations
- Reduce scores for disappointments
- Track negative prediction errors
- See `factors_concept.md` for formula integration patterns

### 10. Stress-Relief Correlation Score
**Definition:** Measures how well relief and stress are inversely correlated

**Formula:**
```python
stress_relief_correlation_score = (relief_score - stress_level + 100.0) / 2.0
# Clamped to 0-100 range
```

**Range:** 0-100
- **Higher values:** Better inverse correlation (low stress + high relief)
- **Lower values:** Poor inverse correlation (high stress + low relief, or both high/low)

**Interpretation:**
- **80-100:** Excellent inverse correlation (low stress, high relief)
- **50-80:** Good inverse correlation
- **20-50:** Poor inverse correlation (stress and relief not inversely related)
- **0-20:** Very poor inverse correlation (both high or both low)

**Example:**
- Relief=80, Stress=20 → Score = (80-20+100)/2 = 80 (good inverse correlation)
- Relief=20, Stress=80 → Score = (20-80+100)/2 = 20 (poor inverse correlation)
- Relief=50, Stress=50 → Score = (50-50+100)/2 = 50 (neutral, no correlation)

## Inverse Correlation Validation

### Expected Relationship
According to stress-coping literature:
- **Expected correlation:** r = -0.40 to -0.70 (moderate to strong negative correlation)
- **Meaning:** Higher stress should be associated with higher relief potential
- **Bidirectional:** High stress → high relief potential, and vice versa

### Current Implementation
The system measures:
- **Post-task relief:** Relief after completion (matches stress-coping cycle)
- **Pre-task stress:** Stress before/during task (expected_aversion, cognitive, emotional, physical)

### Validation Formula
The `stress_relief_correlation_score` provides a per-task measure of inverse correlation:
- High score = good inverse correlation (low stress, high relief)
- Low score = poor inverse correlation (stress and relief not inversely related)

## Usage in Analytics

### Trends Section
All these metrics are available in the **Trends** section of the Analytics page:

1. **Relief Score (Actual)** - Raw actual relief values over time
2. **Expected Relief** - Predicted relief values over time
3. **Net Relief (Actual - Expected)** - Difference between actual and expected relief over time
4. **Serendipity Factor** - Pleasant surprise factors over time (positive net relief)
5. **Disappointment Factor** - Disappointment factors over time (negative net relief)
6. **Stress Level** - Combined stress values over time
7. **Net Wellbeing** - Net benefit/cost over time
8. **Net Wellbeing (Normalized)** - Normalized net wellbeing over time
9. **Stress Efficiency** - Relief per unit stress over time
10. **Stress-Relief Correlation Score** - Inverse correlation quality over time

### Relief Comparison Analytics Module
A dedicated analytics module at `/analytics/relief-comparison` provides:

1. **Summary Statistics**
   - Average expected vs actual relief
   - Mean Absolute Error (MAE) and Root Mean Square Error (RMSE) for prediction accuracy
   - Correlation between expected and actual relief

2. **Comparison Charts**
   - Scatter plot: Expected vs Actual relief with perfect prediction line
   - Time series: Expected, actual, and net relief over time
   - Distribution: Histograms of expected, actual, and net relief

3. **Pattern Analysis**
   - Categorization of tasks by prediction accuracy:
     - **Accurate Prediction:** Within 5 points
     - **Pleasant Surprise:** Actual > Expected by >20 points
     - **Disappointment:** Actual < Expected by >20 points
     - **Slightly Better/Worse:** 5-20 point differences
   - Explanations of what each pattern means
   - Actionable recommendations based on patterns

4. **Task-Level Details**
   - Table showing recent tasks with expected, actual, and net relief
   - Pattern classification for each task

## Data Consistency

### Relief Score Calculation
Relief score is calculated consistently throughout the project:

1. **Primary source:** `actual_relief` in `actual_dict` JSON (from completion page)
2. **Fallback:** `relief_score` CSV column (if JSON not available)
3. **Never use:** `expected_relief` from `predicted_dict` (that's for prediction, not actual)

### Scaling
- If relief value is 0-10, it's automatically scaled to 0-100
- All calculations assume 0-100 scale

## Recommendations

### For Task Selection
- **High Net Wellbeing:** Tasks that provide relief without excessive stress
- **High Stress Efficiency:** Tasks that maximize relief per unit stress
- **High Correlation Score:** Tasks that follow expected stress-relief pattern

### For Wellbeing Tracking
- **Net Wellbeing:** Overall benefit/cost of tasks
- **Relief Score:** Raw relief experience
- **Stress Level:** Overall stress burden

### For Pattern Analysis
- **Stress-Relief Correlation Score:** Identify tasks that don't follow expected patterns
- **Stress to Relief Ratio:** Find tasks requiring high stress for low relief
- **Trend Analysis:** Track how these relationships change over time
