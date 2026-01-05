# Experimental Module Proposal: Grit Score v1.6 Variants

## Overview

Since the preliminary analysis shows ambiguous results (very small differences between variants, unexpected negative correlations), we propose creating an experimental module to test all three variants in production.

## Module Design

### Purpose

Allow users to:
1. See grit scores from all three v1.6 variants simultaneously
2. Compare how different caps affect their scores
3. Provide feedback on which variant feels most accurate
4. Monitor patterns over time

### Implementation

#### 1. Add Variant Selection to Analytics

```python
# In analytics.py
GRIT_SCORE_VARIANT = os.getenv('GRIT_SCORE_VARIANT', 'v1_6a')  # Default to v1.6a

def calculate_grit_score(self, row, task_completion_counts):
    variant = os.getenv('GRIT_SCORE_VARIANT', 'v1_6a')
    if variant == 'v1_6b':
        return self.calculate_grit_score_v1_6b(row, task_completion_counts)
    elif variant == 'v1_6c':
        return self.calculate_grit_score_v1_6c(row, task_completion_counts)
    else:
        return self.calculate_grit_score_v1_6a(row, task_completion_counts)
```

#### 2. Create Experimental UI Page

**Location**: `task_aversion_app/ui/experimental_grit_variants.py`

**Features**:
- Side-by-side comparison of all three variants
- Show scores for recent tasks
- Highlight differences between variants
- Allow user to select preferred variant
- Show correlation analysis (disappointment vs grit by variant)

#### 3. Data Collection

Track:
- Which variant user prefers
- Which variant produces more meaningful patterns
- User feedback on score accuracy
- Long-term trends in each variant

### Usage

1. **Default**: Use v1.6a (current implementation)
2. **Experimental Mode**: Show all three variants in UI
3. **User Selection**: Allow user to choose preferred variant
4. **Monitoring**: Track which variant produces better insights

## Variant Comparison Summary

### v1.6a (Current)
- **Caps**: 1.5x bonus, 0.67x penalty
- **Pros**: Strongest reward for persistent disappointment
- **Cons**: May over-amplify high scores

### v1.6b
- **Caps**: 1.3x bonus, 0.67x penalty
- **Pros**: More moderate bonus, prevents excessive amplification
- **Cons**: Less reward for high disappointment

### v1.6c
- **Caps**: 1.2x bonus, 0.8x penalty
- **Pros**: Balanced approach, symmetric caps
- **Cons**: Weaker impact overall

## Implementation Steps

1. ✅ Create variant functions (v1.6a, v1.6b, v1.6c)
2. ✅ Run comparison analysis
3. ⏳ Create experimental UI module
4. ⏳ Add variant selection to analytics
5. ⏳ Implement data collection
6. ⏳ Monitor and analyze results

## Success Criteria

- User can see all three variants
- User can provide feedback
- System tracks which variant produces more meaningful patterns
- Clear winner emerges from usage data
