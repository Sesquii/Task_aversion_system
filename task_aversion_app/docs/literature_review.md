# Literature Review Framework
**Task Aversion System - Formula Validation & Feature Development**

## Overview

This document provides a structured framework for reviewing psychological and mathematical literature to:
1. Validate current formulas against established research
2. Identify gaps in current implementation
3. Discover new features and metrics to add
4. Ensure alignment with psychological measurement standards

---

## Research Questions

### 1. Stress & Cognitive Load Measurement

**Questions:**
- How is stress measured in psychological research?
- What is cognitive load theory and how is it quantified?
- How should emotional load be measured?
- What is the relationship between cognitive, emotional, and physical stress?
- Are there established formulas for combining these into a single stress metric?

**Current Implementation:**
```python
stress_level = (cognitive_load + emotional_load + physical_load) / 3.0
```

**Key Terms:**
- Cognitive Load Theory (Sweller, 1988)
- Perceived Stress Scale (PSS)
- Emotional Load
- Multi-dimensional stress models
- Stress measurement scales

**Target Sources (2 per area):**
1. Cognitive Load Theory - foundational paper
2. Stress measurement scales - validation studies

---

### 2. Task Aversion & Procrastination

**Questions:**
- How is task aversion measured in psychology?
- What is the relationship between aversion and stress?
- How do aversion levels change over time?
- What are expected correlation ranges between aversion and other metrics?
- Are there validated scales for measuring task avoidance?

**Current Implementation:**
- Aversion tracked as 0-100 scale
- Aversion multiplier formula for relief points
- Low correlation (0.20) with stress detected

**Key Terms:**
- Task Aversion
- Procrastination (Pychyl, Steel)
- Task Avoidance
- Aversion-stress correlation
- Behavioral activation

**Target Sources (2 per area):**
1. Procrastination research - Steel (2007) or Pychyl
2. Task avoidance measurement - validation studies

---

### 3. Relief & Wellbeing Measurement

**Questions:**
- How is relief measured after task completion?
- What is the relationship between relief and stress?
- How should net wellbeing be calculated?
- Are there established formulas for relief-stress relationships?
- What are expected ranges for relief scores?

**Current Implementation:**
```python
net_wellbeing = relief_score - stress_level
net_wellbeing_normalized = 50.0 + (net_wellbeing / 2.0)
```

**Key Terms:**
- Post-task relief
- Wellbeing measurement
- Relief scales
- Stress-relief relationship
- Subjective wellbeing

**Target Sources (2 per area):**
1. Wellbeing measurement - established scales
2. Relief/stress relationship - empirical studies

---

### 4. Mathematical Models for Emotions

**Questions:**
- Do psychologists use mathematical formulas for emotions?
- How are emotional states quantified?
- Are there validated computational models?
- What statistical approaches are used?
- How do researchers handle emotion measurement scales?

**Current Implementation:**
- 0-100 scales for all metrics
- Various multiplier formulas
- Correlation calculations

**Key Terms:**
- Mathematical psychology
- Emotion quantification
- Computational emotion models
- Statistical emotion analysis
- Scale validation

**Target Sources (2 per area):**
1. Mathematical psychology - foundational text
2. Emotion quantification - computational approaches

---

## Research Strategy

### Phase 1: Foundational Literature (2 sources per area = 8 sources)

**Priority Areas:**
1. **Stress & Cognitive Load** (2 sources)
   - Cognitive Load Theory paper
   - Stress measurement validation study

2. **Task Aversion** (2 sources)
   - Procrastination research (Steel or Pychyl)
   - Task avoidance measurement study

3. **Relief & Wellbeing** (2 sources)
   - Wellbeing measurement scale
   - Relief/stress relationship study

4. **Mathematical Models** (2 sources)
   - Mathematical psychology text
   - Emotion quantification paper

### Phase 2: Validation & Comparison

- Compare current formulas to literature findings
- Identify gaps and inconsistencies
- Document recommended changes

### Phase 3: Feature Recommendations

- Based on literature, suggest new metrics
- Recommend formula improvements
- Propose additional psychological constructs

---

## Source Search Strategy

### Databases to Search
1. **PubMed** - Medical/psychological research
2. **PsycINFO** - Psychology database
3. **Google Scholar** - Broad academic search
4. **ResearchGate** - Access to papers

### Search Terms by Area

**Stress & Cognitive Load:**
- "cognitive load theory" AND measurement
- "perceived stress scale" AND validation
- "emotional load" AND measurement

**Task Aversion:**
- "task aversion" AND measurement
- "procrastination" AND "task avoidance"
- "aversion" AND "stress" AND correlation

**Relief & Wellbeing:**
- "post-task relief" AND measurement
- "wellbeing" AND "stress relief"
- "subjective wellbeing" AND scales

**Mathematical Models:**
- "mathematical psychology" AND emotions
- "emotion quantification" AND computational
- "statistical" AND "emotion measurement"

---

## Documentation Template

For each source, document:

```markdown
### Source [Number]: [Title]
**Authors:** [Author names]
**Year:** [Year]
**Journal/Publication:** [Publication info]
**DOI/URL:** [Link]

**Key Findings:**
- Finding 1
- Finding 2
- Finding 3

**Relevance to Current System:**
- How it relates to current formulas
- What it suggests about our implementation
- Recommended changes

**Formulas/Models Found:**
- [Any formulas or models from the paper]

**Correlation Ranges:**
- [Expected correlation ranges if mentioned]

**Measurement Scales:**
- [Scales or measurement methods mentioned]
```

---

## Expected Outcomes

1. **Formula Validation:**
   - Confirm or refute current stress calculation
   - Validate net wellbeing formula
   - Check aversion multiplier logic

2. **Correlation Validation:**
   - Expected aversion-stress correlation range
   - Relief-stress relationship
   - Other expected correlations

3. **Feature Recommendations:**
   - New metrics to track
   - Additional psychological constructs
   - Measurement improvements

4. **Scale Validation:**
   - Confirm 0-100 scales are appropriate
   - Check if other scales are standard
   - Validate normalization approaches

---

## Timeline

- **Week 1:** Source identification and collection (8 sources)
- **Week 2:** Reading and note-taking
- **Week 3:** Analysis and comparison
- **Week 4:** Documentation and recommendations

---

## Notes

- Focus on peer-reviewed sources
- Prioritize recent research (last 20 years) but include foundational papers
- Look for validation studies and meta-analyses
- Document both supporting and conflicting evidence
- Note gaps in literature (where formulas don't exist)

