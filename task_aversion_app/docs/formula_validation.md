# Formula Validation Report
**Comparing Current Formulas to Literature Findings**

## Overview

This document compares the Task Aversion System's current formulas against findings from psychological literature to validate approaches and identify needed improvements.

---

## 1. Stress Level Formula

### Current Implementation
```python
stress_level = (cognitive_load + emotional_load + physical_load) / 3.0
```

### Literature Findings

**From PSS (Perceived Stress Scale):**
- ✅ **Validated approach:** Combining multiple stress dimensions into single metric is standard
- ✅ **Scale normalization:** 0-100 scale is appropriate
- ⚠️ **Weighting:** PSS uses equal weighting, but some studies suggest different dimensions may have different impacts

**From Cognitive Load Theory:**
- ⚠️ **Separation concern:** Literature suggests cognitive, emotional, and physical loads should be analyzed separately
- ⚠️ **No standard formula:** No established formula for combining load types
- ✅ **Subjective measurement:** Self-report scales (like current 0-100) are standard

### Validation Result

**Status:** ✅ **PARTIALLY VALIDATED**

**Strengths:**
- Approach of combining dimensions aligns with PSS methodology
- 0-100 scale is appropriate
- Self-report measurement is standard

**Concerns:**
- Simple average may not reflect relative importance of dimensions
- Literature suggests analyzing dimensions separately for some purposes

**Recommendations:**
1. **Keep current formula** for overall stress metric (validated by PSS)
2. **Also track dimensions separately** in analytics for detailed analysis
3. **Consider weighted average** if research shows dimension importance differs:
   ```python
   # Potential weighted version (if literature supports):
   stress_level = (cognitive_load * 0.4 + emotional_load * 0.4 + physical_load * 0.2)
   ```
4. **Document** that dimensions can be analyzed separately when needed

---

## 2. Net Wellbeing Formula

### Current Implementation
```python
net_wellbeing = relief_score - stress_level
net_wellbeing_normalized = 50.0 + (net_wellbeing / 2.0)
```

### Literature Findings

**From Subjective Wellbeing Research:**
- [To be filled when sources are found]
- Wellbeing is often measured as relief minus cost
- Normalization to 0-100 with 50 as neutral is reasonable

**From Relief-Stress Relationship:**
- [To be filled when sources are found]
- Relief and stress are inversely related
- Net calculation (relief - stress) is logical

### Validation Result

**Status:** ⚠️ **PENDING VALIDATION**

**Strengths:**
- Logical approach (relief minus cost)
- Normalization with 50 as neutral is intuitive
- Range (-100 to +100, normalized to 0-100) is reasonable

**Concerns:**
- Need literature validation of relief-stress relationship
- May need to verify normalization formula

**Recommendations:**
1. **Continue using** until literature review complete
2. **Search for** relief-stress relationship studies
3. **Consider** if relief and stress should be weighted differently

---

## 3. Aversion Multiplier Formula

### Current Implementation
```python
# Complex logarithmic formula in analytics.py
# Uses improvement from initial_aversion
flat_multiplier = 2.0 * (current_aversion / 100.0)
if initial_aversion:
    improvement = initial_aversion - current_aversion
    logarithmic_multiplier = 2.0 ** (improvement / 10.0)
    return logarithmic_multiplier * (1.0 + flat_multiplier)
else:
    return 1.0 + flat_multiplier
```

### Literature Findings

**From Procrastination Research (Steel, 2007):**
- ⚠️ **No standard formula:** Literature doesn't provide mathematical formulas for aversion multipliers
- ✅ **Aversion measurement:** Self-report scales are standard
- ⚠️ **Aversion-stress correlation:** Expected r = 0.35-0.45, current system shows r = 0.20

**From Task Avoidance Research:**
- [To be filled when sources are found]

### Validation Result

**Status:** ⚠️ **NEEDS INVESTIGATION**

**Strengths:**
- Logarithmic approach for improvement is reasonable
- Incorporates both current aversion and improvement

**Concerns:**
- **No literature validation** - formulas are not standard in psychology
- **Low correlation** with stress suggests formula or measurement issue
- **Complexity** may not be necessary if simpler approach works

**Recommendations:**
1. **Investigate low correlation** - primary concern
2. **Consider simplifying** if complex formula doesn't improve predictions
3. **Test alternatives:**
   - Simple linear: `1.0 + (current_aversion / 50.0)`
   - Improvement-based: `1.0 + (improvement / 20.0)`
4. **Document** that this is a custom formula, not from literature

---

## 4. Aversion-Stress Correlation

### Current Finding
- **Observed correlation:** r = 0.20
- **Expected correlation:** r = 0.35-0.45 (from Steel, 2007)

### Analysis

**Gap:** Correlation is 0.15-0.25 points below expected range

**Possible Causes:**
1. **Measurement issue:** Aversion not being captured consistently
2. **Formula issue:** Stress calculation doesn't properly incorporate aversion
3. **Scale mismatch:** Aversion and stress on different effective scales
4. **Data quality:** Too few aversion data points (only 8 in audit)

### Recommendations

**Priority 1: Increase Aversion Data Collection**
- Ensure all instances capture predicted aversion
- Add validation to require aversion input
- Track aversion changes over time

**Priority 2: Review Stress Formula**
- Consider if stress should include aversion component
- Test: `stress_level = (cognitive + emotional + physical + aversion) / 4.0`
- Or weighted: `stress_level = (cognitive + emotional + physical) / 3.0 + (aversion * 0.2)`

**Priority 3: Validate Scales**
- Ensure all metrics use 0-100 consistently
- Check for scale transformations that might affect correlation

**Priority 4: Collect More Data**
- Current sample (8 aversion data points) is too small
- Need more data to validate correlation

---

## 5. Relief Score Calculation

### Current Implementation
- Relief extracted from `actual_relief` in JSON
- Scaled from 0-10 to 0-100 if needed
- Used directly in calculations

### Literature Findings

**From Wellbeing Research:**
- [To be filled when sources are found]
- Relief is typically measured subjectively
- Post-task relief scales exist but vary

### Validation Result

**Status:** ⚠️ **PENDING VALIDATION**

**Recommendations:**
1. Search for post-task relief measurement scales
2. Validate 0-100 scale approach
3. Check if relief should be normalized differently

---

## Summary Table

| Formula | Status | Literature Support | Action Needed |
|---------|--------|-------------------|---------------|
| `stress_level = (cognitive + emotional + physical) / 3` | ✅ Partially Validated | PSS validates combination approach | Track dimensions separately too |
| `net_wellbeing = relief - stress` | ⚠️ Pending | Logical but needs validation | Search for relief-stress studies |
| `net_wellbeing_normalized = 50 + (net/2)` | ⚠️ Pending | Intuitive but needs validation | Validate normalization |
| Aversion multiplier (logarithmic) | ⚠️ Needs Investigation | No literature formula | Investigate low correlation |
| Aversion-stress correlation | ❌ Below Expected | Expected r=0.35-0.45, found r=0.20 | Increase data, review formula |

---

## Key Recommendations

### High Priority
1. **Investigate low aversion-stress correlation** (r=0.20 vs expected 0.35-0.45)
2. **Increase aversion data collection** (only 8 data points currently)
3. **Consider adding aversion to stress calculation** if literature supports

### Medium Priority
4. **Track stress dimensions separately** in addition to combined metric
5. **Complete literature search** for relief and wellbeing formulas
6. **Validate normalization formulas** with literature

### Low Priority
7. **Consider weighted stress formula** if research shows dimension importance differs
8. **Simplify aversion multiplier** if complex formula doesn't improve predictions

---

## Notes

- Many psychological constructs don't have established mathematical formulas
- Self-report scales are standard - current system aligns with this
- Custom formulas may be necessary where literature doesn't provide them
- Focus on measurement consistency and data quality over formula complexity

