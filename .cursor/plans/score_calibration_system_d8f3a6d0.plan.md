# Score Calibration System - Comprehensive Plan

## Overview

This plan establishes a systematic, human-in-the-loop iterative process for calibrating all scores and metrics in the task aversion system. The goal is to create a unified weights architecture that can be applied across all scoring subsystems while maintaining distinct naming for future universal weights compatibility.

## Phase 1: General Analysis of Existing Scores

### 1.1 Score Inventory

**Core Scores Identified:**

1. **Productivity Score** (`calculate_productivity_score`)

- Location: `backend/analytics.py:449-610`
- Current weights/multipliers:
    - Work: 3.0x to 5.0x (smooth transition based on completion_time_ratio)
    - Self-care: multiplier = number of self-care tasks per day
    - Play: -0.003x per percentage (penalty when play > 2x work)
    - Weekly bonus/penalty: -0.01x per percentage above/below weekly average
    - Burnout penalty: exponential decay when work > 8 hours with no play

2. **Grit Score** (`calculate_grit_score`)

- Location: `backend/analytics.py:612-680`
- Current weights/multipliers:
    - Persistence multiplier: 1.0 + (completion_count - 1) * 0.1 (max 2.0x)
    - Time bonus: 1.0 + (time_ratio - 1.0) * 0.5 (when taking longer)

3. **Life Balance Score** (`get_life_balance`)

- Location: `backend/analytics.py:1489-1595`
- Current formula: `50.0 + ((work_play_ratio - 0.5) * 100.0)`
- No explicit weights (simple linear transformation)

4. **Composite Productivity Score** (`calculate_composite_productivity_score`)

- Location: `backend/analytics.py:2061-2080`
- Current weights: 40% efficiency, 40% volume, 20% consistency

5. **Overall Improvement Ratio** (`calculate_overall_improvement_ratio`)

- Location: `backend/analytics.py:126-231`
- Current weights: 30% self-care, 40% relief, 30% performance balance

6. **Aversion Multiplier System**

- Location: `backend/analytics.py:24-423`
- Difficulty bonus weights: 70% aversion, 30% load
- Improvement multiplier: exponential decay with k=30
- Combined: max(difficulty, improvement) + 0.1 bonus if both > 0.3

7. **Composite Score** (`calculate_composite_score`)

- Location: `backend/analytics.py:1979-2059`
- Currently uses equal weights (1.0) by default
- Supports custom weights per component

8. **Time Tracking Consistency Score** (`calculate_time_tracking_consistency_score`)

- Location: `backend/analytics.py:1790-1977`
- Exponential formula: `100 × (1 - exp(-tracking_coverage × 2.0))`
- No explicit weights

9. **Work Volume Score** (`get_daily_work_volume_metrics`)

- Location: `backend/analytics.py:1597-1788`
- Target: 6 hours/day (360 minutes)
- Score: `100 × (1 - exp(-avg_work_time / 180))`

10. **Obstacles Score** (`calculate_obstacles_scores`)

    - Location: `backend/analytics.py:788-931`
    - Multiple formula variants (7 different approaches)
    - Base formula: `spike_amount × multiplier / 50.0`
    - Multiplier: `1 + (spike_amount / 100) × (1 - relief_proportion) × 9`

### 1.2 Weight Patterns Analysis

**Current Weight Patterns:**

- **Hardcoded weights**: 0.3, 0.4, 0.5, 0.7 (difficulty bonus, improvement ratio, composite productivity)
- **Multipliers**: 3.0x, 5.0x (productivity), 2.0x (grit max), -0.003x (play penalty)
- **Exponential decay constants**: k=30 (improvement), k=40 (overall improvement), k=50 (difficulty bonus)
- **Linear transformations**: work_play_ratio → balance_score
- **Equal weights default**: Composite score system (1.0 for all components)

**Issues Identified:**

1. No systematic approach to weight selection
2. Weights scattered across multiple functions
3. No calibration mechanism
4. Hardcoded values without documentation of rationale
5. Inconsistent weight naming (some use percentages, some use multipliers)

## Phase 2: Score-by-Score Analysis Framework

### 2.1 Decision Matrix Template

For each score subsystem, create a decision matrix with:**Dimensions:**

1. **Purpose**: What does this score measure?
2. **Scale**: What is the output range?
3. **Inputs**: What factors contribute to this score?
4. **Current Weights**: What weights/multipliers are currently used?
5. **Calibration Criteria**: How should weights be adjusted?
6. **Sensitivity Analysis**: How sensitive is the score to weight changes?
7. **Literature Support**: Are there research-backed weight recommendations?
8. **User Feedback**: What do users expect from this score?

**Calibration Process:**

1. Document current implementation
2. Identify all weight parameters
3. Create test scenarios with known expected outcomes
4. Adjust weights iteratively
5. Validate against user expectations
6. Document final weights and rationale

### 2.2 Score-Specific Analysis Plans

#### Score 1: Productivity Score

**Analysis Document**: `docs/score_calibration/productivity_score_analysis.md`**Key Questions:**

- Should work multiplier (3.0x-5.0x) be configurable?
- Is play penalty (-0.003x) appropriately calibrated vs idle penalty?
- Should weekly bonus/penalty rate (-0.01x) be adjustable?
- How should burnout threshold (8 hours) and penalty scale (240 min) be determined?

**Calibration Process:**

1. Create test scenarios:

- High efficiency work (ratio > 1.5)
- Low efficiency work (ratio < 1.0)
- Balanced work/play day
- Excessive play day (play > 2x work)
- Burnout scenario (8+ hours work, no play)

2. Set expected score ranges for each scenario
3. Adjust weights to match expectations
4. Document rationale

**Weight Parameters to Calibrate:**

- `productivity_work_multiplier_min` (currently 3.0)
- `productivity_work_multiplier_max` (currently 5.0)
- `productivity_work_multiplier_transition_start` (currently 1.0)
- `productivity_work_multiplier_transition_end` (currently 1.5)
- `productivity_play_penalty_rate` (currently -0.003)
- `productivity_play_penalty_threshold` (currently 2.0)
- `productivity_weekly_bonus_rate` (currently -0.01)
- `productivity_burnout_threshold_minutes` (currently 480)
- `productivity_burnout_penalty_scale` (currently 240)
- `productivity_burnout_max_reduction` (currently 0.5)

#### Score 2: Grit Score

**Analysis Document**: `docs/score_calibration/grit_score_analysis.md`**Key Questions:**

- Is persistence multiplier growth rate (0.1 per completion) appropriate?
- Should time bonus rate (0.5) be configurable?
- What is the relationship between grit and productivity?

**Weight Parameters to Calibrate:**

- `grit_persistence_growth_rate` (currently 0.1)
- `grit_persistence_max_multiplier` (currently 2.0)
- `grit_time_bonus_rate` (currently 0.5)

#### Score 3: Life Balance Score

**Analysis Document**: `docs/score_calibration/life_balance_score_analysis.md`**Key Questions:**

- Should self-care be included in balance calculation?
- Is linear transformation (50 + (ratio - 0.5) * 100) appropriate?
- Should there be different target ratios for different users?

**Weight Parameters to Calibrate:**

- `life_balance_work_weight` (implicitly 1.0)
- `life_balance_play_weight` (implicitly 1.0)
- `life_balance_self_care_weight` (currently 0.0 - not included)
- `life_balance_target_ratio` (currently 0.5)

#### Score 4: Composite Productivity Score

**Analysis Document**: `docs/score_calibration/composite_productivity_analysis.md`**Key Questions:**

- Are current weights (40/40/20) optimal?
- Should weights be user-configurable?
- How should efficiency normalization (divide by 2) be handled?

**Weight Parameters to Calibrate:**

- `composite_productivity_efficiency_weight` (currently 0.4)
- `composite_productivity_volume_weight` (currently 0.4)
- `composite_productivity_consistency_weight` (currently 0.2)
- `composite_productivity_efficiency_normalization_factor` (currently 2.0)

#### Score 5: Overall Improvement Ratio

**Analysis Document**: `docs/score_calibration/improvement_ratio_analysis.md`**Key Questions:**

- Are weights (30/40/30) appropriate?
- Should exponential decay constant (k=40) be adjustable?
- How should performance balance weights be determined?

**Weight Parameters to Calibrate:**

- `improvement_ratio_self_care_weight` (currently 0.3)
- `improvement_ratio_relief_weight` (currently 0.4)
- `improvement_ratio_performance_weight` (currently 0.3)
- `improvement_ratio_decay_constant` (currently 40.0)
- `improvement_ratio_performance_metric_weights` (currently equal)

#### Score 6: Aversion Multiplier System

**Analysis Document**: `docs/score_calibration/aversion_multiplier_analysis.md`**Key Questions:**

- Is 70/30 split (aversion/load) optimal?
- Should exponential decay constants be configurable?
- How should difficulty and improvement bonuses be combined?

**Weight Parameters to Calibrate:**

- `aversion_difficulty_aversion_weight` (currently 0.7)
- `aversion_difficulty_load_weight` (currently 0.3)
- `aversion_difficulty_decay_constant` (currently 50.0)
- `improvement_decay_constant` (currently 30.0)
- `aversion_combined_bonus_threshold` (currently 0.3)
- `aversion_combined_bonus_amount` (currently 0.1)

#### Score 7: Composite Score

**Analysis Document**: `docs/score_calibration/composite_score_analysis.md`**Key Questions:**

- What should default weights be for each component?
- Should weights be context-dependent (e.g., different for different user goals)?
- How should component normalization be handled?

**Weight Parameters to Calibrate:**

- Default weights for all 11 components (currently all 1.0)
- Component-specific normalization factors
- Time-decay weights (future enhancement)

#### Score 8: Time Tracking Consistency Score

**Analysis Document**: `docs/score_calibration/tracking_consistency_analysis.md`**Key Questions:**

- Is exponential decay constant (2.0) appropriate?
- Should sleep cap (8 hours) be configurable?
- How should this interact with other scores?

**Weight Parameters to Calibrate:**

- `tracking_consistency_decay_constant` (currently 2.0)
- `tracking_consistency_sleep_cap_hours` (currently 8.0)

#### Score 9: Work Volume Score

**Analysis Document**: `docs/score_calibration/work_volume_analysis.md`**Key Questions:**

- Is target (6 hours/day) appropriate for all users?
- Should exponential decay constant (180) be adjustable?
- How should consistency be weighted?

**Weight Parameters to Calibrate:**

- `work_volume_target_minutes` (currently 360)
- `work_volume_decay_constant` (currently 180.0)

#### Score 10: Obstacles Score

**Analysis Document**: `docs/score_calibration/obstacles_score_analysis.md`**Key Questions:**

- Which formula variant should be primary?
- How should spike amount and relief be weighted?
- Should multiplier formula (1 + spike/100 * (1-relief) * 9) be configurable?

**Weight Parameters to Calibrate:**

- `obstacles_spike_weight` (implicitly 1.0)
- `obstacles_relief_weight` (implicitly in formula)
- `obstacles_multiplier_scale` (currently 9.0)
- `obstacles_formula_variant` (currently multiple, need to select primary)

## Phase 3: Unified Weights System Architecture

### 3.1 Weight Configuration Structure

Create a unified weight configuration system in `backend/score_weights.py`:

```python
# Weight configuration structure
SCORE_WEIGHTS_CONFIG = {
    'productivity_score': {
        'work_multiplier_min': 3.0,
        'work_multiplier_max': 5.0,
        'play_penalty_rate': -0.003,
        'weekly_bonus_rate': -0.01,
        # ... all productivity parameters
    },
    'grit_score': {
        'persistence_growth_rate': 0.1,
        'time_bonus_rate': 0.5,
        # ... all grit parameters
    },
    # ... all other scores
}
```

### 3.2 Weight Naming Convention

**Naming Pattern**: `{score_name}_{parameter_name}`**Examples:**

- `productivity_work_multiplier_min` (not `work_multiplier_min`)
- `grit_persistence_growth_rate` (not `persistence_growth_rate`)
- `life_balance_work_weight` (not `work_weight`)

**Rationale**: Prevents naming conflicts when implementing universal weights system.

### 3.3 Weight Storage

**Location**: `backend/user_state.py` (extend existing `get_score_weights`/`set_score_weights`)**Structure**:

```python
{
    'composite_score_weights': {...},  # Existing
    'productivity_score_weights': {...},  # New
    'grit_score_weights': {...},  # New
    # ... per-score weights
}
```

### 3.4 Weight Validation

Create validation functions:

- Ensure weights are within reasonable ranges
- Check for logical consistency (e.g., min < max)
- Provide default fallbacks

## Phase 4: Human-in-the-Loop Calibration Process

### 4.1 Calibration Workflow

**Step 1: Baseline Analysis**

- Document current weights
- Create test scenarios
- Measure current score outputs

**Step 2: Iterative Adjustment**

- Adjust one weight parameter at a time
- Test with scenarios
- Document impact

**Step 3: Validation**

- Compare against expected outcomes
- Check for edge cases
- Validate against user feedback

**Step 4: Documentation**

- Document final weights
- Explain rationale
- Create calibration guide

### 4.2 Calibration Tools

**Tool 1: Score Calibration Dashboard**

- Location: `ui/score_calibration_page.py`
- Features:
- View all current weights
- Adjust weights with sliders
- See real-time score calculations
- Test with sample scenarios
- Save/load weight configurations

**Tool 2: Calibration Analysis Scripts**

- Location: `scripts/calibrate_scores.py`
- Features:
- Run test scenarios
- Generate calibration reports
- Compare weight configurations
- Export calibration data

**Tool 3: Weight Comparison Tool**

- Compare different weight configurations side-by-side
- Visualize impact of weight changes
- Generate sensitivity analysis

### 4.3 Calibration Documentation

**For Each Score:**

1. **Current State Document**: Current weights and rationale
2. **Calibration Guide**: Step-by-step calibration process
3. **Test Scenarios**: Standard scenarios for validation
4. **Decision Matrix**: Completed matrix with rationale
5. **Sensitivity Analysis**: How score changes with weight adjustments

## Phase 5: Implementation Plan

### 5.1 File Structure

```javascript
task_aversion_app/
├── backend/
│   ├── score_weights.py          # NEW: Unified weight configuration
│   ├── analytics.py              # MODIFY: Use weight config
│   └── user_state.py             # MODIFY: Extend weight storage
├── ui/
│   ├── score_calibration_page.py  # NEW: Calibration dashboard
│   └── analytics_page.py          # MODIFY: Add weight display
├── scripts/
│   └── calibrate_scores.py        # NEW: Calibration analysis tools
└── docs/
    └── score_calibration/
        ├── README.md              # Overview
        ├── productivity_score_analysis.md
        ├── grit_score_analysis.md
        ├── life_balance_score_analysis.md
        ├── composite_productivity_analysis.md
        ├── improvement_ratio_analysis.md
        ├── aversion_multiplier_analysis.md
        ├── composite_score_analysis.md
        ├── tracking_consistency_analysis.md
        ├── work_volume_analysis.md
        └── obstacles_score_analysis.md
```

### 5.2 Implementation Order

1. **Phase 1**: Create weight configuration system (`score_weights.py`)
2. **Phase 2**: Refactor analytics.py to use weight config
3. **Phase 3**: Create calibration dashboard UI
4. **Phase 4**: Document each score (one at a time)
5. **Phase 5**: Calibrate each score (iterative, human-in-the-loop)
6. **Phase 6**: Create calibration analysis tools
7. **Phase 7**: Final validation and documentation

### 5.3 Compatibility with Universal Weights

**Design Principles:**

- All weight names prefixed with score name
- Weight storage structure supports per-score and universal weights
- Weight application logic separated from storage
- Future universal weights can override per-score weights

**Future Extension:**

```python
# Universal weights (future)
UNIVERSAL_WEIGHTS = {
    'efficiency': 1.5,  # Applies to all efficiency-related scores
    'volume': 1.2,     # Applies to all volume-related scores
    # ...
}
```

## Phase 6: Decision Matrix Template

### 6.1 Standard Decision Matrix

For each score, complete this matrix:| Dimension | Value | Rationale ||-----------|-------|-----------|| **Purpose** | | || **Scale** | | || **Input Factors** | | || **Current Weights** | | || **Calibration Criteria** | | || **Sensitivity** | | || **Literature Support** | | || **User Expectations** | | || **Proposed Weights** | | || **Validation Method** | | |

### 6.2 Calibration Criteria Framework

**For each weight parameter:**

1. **Range**: What are valid values?
2. **Default**: What is the starting value?
3. **Impact**: How does changing this weight affect the score?
4. **Sensitivity**: Is the score highly sensitive to this weight?
5. **Dependencies**: Does this weight depend on other weights?
6. **User Preference**: Should this be user-configurable?

## Phase 7: Iterative Calibration Schedule

### 7.1 Per-Score Calibration Sessions

**Session Structure (2-4 hours per score):**

1. **Analysis** (30 min): Review current implementation
2. **Test Scenario Creation** (30 min): Create standard test cases
3. **Baseline Measurement** (30 min): Measure current outputs
4. **Weight Adjustment** (60-120 min): Iterative adjustment
5. **Validation** (30 min): Test against scenarios
6. **Documentation** (30 min): Document final weights

**Total Time Estimate**: 4-8 hours per score × 10 scores = 40-80 hours total

### 7.2 Priority Order

1. **High Priority** (Core scores):

- Productivity Score
- Composite Score
- Life Balance Score

2. **Medium Priority** (Supporting scores):

- Grit Score
- Composite Productivity Score
- Aversion Multiplier System

3. **Lower Priority** (Specialized scores):

- Overall Improvement Ratio
- Time Tracking Consistency
- Work Volume Score
- Obstacles Score

## Phase 8: Success Criteria

### 8.1 Calibration Complete When:

1. All scores have documented weight configurations
2. All weights have clear rationale
3. Test scenarios validate expected behavior
4. Calibration dashboard is functional
5. Documentation is complete
6. Weights are stored in unified system
7. System is ready for universal weights extension

### 8.2 Quality Metrics

- **Coverage**: All 10 scores analyzed and calibrated
- **Documentation**: Complete decision matrices for all scores
- **Test Coverage**: At least 5 test scenarios per score
- **User Feedback**: Weights align with user expectations
- **Code Quality**: All weights use unified configuration system

## Next Steps

1. Review and approve this plan
2. Create `backend/score_weights.py` with initial structure
3. Begin with Productivity Score analysis (highest priority)