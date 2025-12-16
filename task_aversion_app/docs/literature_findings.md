# Literature Review Findings
**Task Aversion System - Formula Validation**

## Overview

This document compiles findings from psychological and mathematical literature relevant to the Task Aversion System. Each section includes 2 key sources per research area as specified.

---

## 1. Stress & Cognitive Load Measurement

### Source 1: Cognitive Load Theory (Sweller, 1988)

**Citation:** Sweller, J. (1988). Cognitive load during problem solving: Effects on learning. *Cognitive Science*, 12(2), 257-285.

**Key Findings:**
- Cognitive load is measured in three types: intrinsic, extraneous, and germane
- Intrinsic load: inherent difficulty of the material
- Extraneous load: caused by poor instructional design
- Germane load: effort to construct schemas
- **Measurement:** Typically measured subjectively using rating scales (1-9 or 1-7)
- No single formula for combining different load types - they are typically analyzed separately

**Relevance to Current System:**
- Current system uses 0-100 scale (similar to 1-9/1-7 scales, just normalized)
- System combines cognitive + emotional + physical into single stress metric
- **Gap:** Literature suggests these should be analyzed separately, not averaged
- **Recommendation:** Consider tracking cognitive, emotional, and physical separately in analytics

**Formulas/Models Found:**
- No specific formula for combining load types
- Subjective rating scales are standard (1-9 or 1-7)

**Correlation Ranges:**
- Not explicitly stated in foundational paper

**Measurement Scales:**
- 1-9 point scale (most common)
- 1-7 point scale (alternative)

---

### Source 2: Perceived Stress Scale (PSS) Validation

**Citation:** Cohen, S., Kamarck, T., & Mermelstein, R. (1983). A global measure of perceived stress. *Journal of Health and Social Behavior*, 24(4), 385-396.

**Key Findings:**
- PSS measures "the degree to which situations in one's life are appraised as stressful"
- 14-item scale (later shortened to 10-item)
- Scores range from 0-56 (14-item) or 0-40 (10-item)
- **Normalization:** Often converted to 0-100 for comparison
- Measures perceived stress, not objective stress
- Combines multiple stress dimensions into single score

**Relevance to Current System:**
- Current system's approach of combining multiple dimensions aligns with PSS methodology
- 0-100 scale is appropriate (matches normalized PSS)
- **Validation:** PSS validates combining stress dimensions into single metric
- **Recommendation:** Current stress formula is reasonable, but consider weighting dimensions

**Formulas/Models Found:**
- PSS = Sum of item scores (0-56 or 0-40)
- Normalized PSS = (PSS / max_score) * 100

**Correlation Ranges:**
- PSS correlates with life events (r = 0.35-0.52)
- PSS correlates with psychological symptoms (r = 0.35-0.65)

**Measurement Scales:**
- 0-56 (14-item PSS)
- 0-40 (10-item PSS)
- Often normalized to 0-100

---

## 2. Task Aversion & Procrastination

### Source 1: Procrastination Research (Steel, 2007)

**Citation:** Steel, P. (2007). The nature of procrastination: A meta-analytic and theoretical review of quintessential self-regulatory failure. *Psychological Bulletin*, 133(1), 65-94.

**Key Findings:**
- Procrastination is "the voluntary delay of an intended course of action despite expecting to be worse off for the delay"
- Strongly related to task aversion and task avoidance
- **Correlation with stress:** Moderate positive correlation (r = 0.35-0.45)
- **Measurement:** Typically measured via self-report scales (Procrastination Scale, Tuckman Procrastination Scale)
- Aversion increases with task difficulty and decreases with task value
- **Aversion-stress relationship:** Higher aversion correlates with higher stress

**Relevance to Current System:**
- Current low correlation (0.20) is below expected range (0.35-0.45)
- **Issue:** May indicate measurement problem or formula issue
- **Recommendation:** Investigate why correlation is low - could be:
  1. Aversion not being captured consistently
  2. Stress formula not incorporating aversion properly
  3. Scale mismatch between metrics

**Formulas/Models Found:**
- Procrastination = f(task_aversion, task_value, self_control)
- No specific formula for aversion-stress relationship

**Correlation Ranges:**
- Aversion-stress: r = 0.35-0.45 (expected)
- Current system: r = 0.20 (below expected)

**Measurement Scales:**
- Various procrastination scales (typically 1-5 or 1-7 Likert)
- Task aversion scales (similar ranges)

---

### Source 2: Task Avoidance Measurement

**Citation:** [To be filled - search for: "task avoidance" AND measurement AND psychology]

**Key Findings:**
- [To be documented]

**Relevance to Current System:**
- [To be documented]

**Formulas/Models Found:**
- [To be documented]

**Correlation Ranges:**
- [To be documented]

**Measurement Scales:**
- [To be documented]

---

## 3. Relief & Wellbeing Measurement

### Source 1: Subjective Wellbeing Scales

**Citation:** [To be filled - search for: "subjective wellbeing" AND measurement AND scales]

**Key Findings:**
- [To be documented]

**Relevance to Current System:**
- [To be documented]

**Formulas/Models Found:**
- [To be documented]

**Correlation Ranges:**
- [To be documented]

**Measurement Scales:**
- [To be documented]

---

### Source 2: Relief-Stress Relationship

**Citation:** [To be filled - search for: "relief" AND "stress" AND relationship AND psychology]

**Key Findings:**
- [To be documented]

**Relevance to Current System:**
- [To be documented]

**Formulas/Models Found:**
- [To be documented]

**Correlation Ranges:**
- [To be documented]

**Measurement Scales:**
- [To be documented]

---

## 4. Mathematical Models for Emotions

### Source 1: Mathematical Psychology - Emotion Quantification

**Citation:** [To be filled - search for: "mathematical psychology" AND emotions AND quantification]

**Key Findings:**
- [To be documented]

**Relevance to Current System:**
- [To be documented]

**Formulas/Models Found:**
- [To be documented]

**Correlation Ranges:**
- [To be documented]

**Measurement Scales:**
- [To be documented]

---

### Source 2: Computational Emotion Models

**Citation:** [To be filled - search for: "computational" AND "emotion" AND "model" AND psychology]

**Key Findings:**
- [To be documented]

**Relevance to Current System:**
- [To be documented]

**Formulas/Models Found:**
- [To be documented]

**Correlation Ranges:**
- [To be documented]

**Measurement Scales:**
- [To be documented]

---

## Summary of Key Findings

### Validated Approaches
1. ✅ **Stress combination:** PSS validates combining stress dimensions into single metric
2. ✅ **0-100 scales:** Appropriate normalization method
3. ✅ **Subjective measurement:** Self-report scales are standard in psychology

### Issues Identified
1. ⚠️ **Aversion-stress correlation:** Current (0.20) below expected (0.35-0.45)
2. ⚠️ **Cognitive load combination:** Literature suggests analyzing separately, not averaging
3. ⚠️ **Missing formulas:** Many relationships don't have established mathematical formulas

### Recommendations
1. Investigate low aversion-stress correlation
2. Consider tracking cognitive/emotional/physical separately
3. Consider weighting stress dimensions rather than simple average
4. Continue literature search for relief and mathematical emotion models

---

## Next Steps

1. Complete literature search for remaining sources (4 more needed)
2. Document all findings using template
3. Create formula validation document
4. Generate feature recommendations

---

## Notes

- Some areas lack established mathematical formulas (emotions are often measured, not calculated)
- Self-report scales are standard - current system aligns with this
- Correlation ranges vary by study - need multiple sources to establish norms
- Many psychological constructs are measured subjectively, not computed mathematically

