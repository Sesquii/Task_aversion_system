---
name: Score Calibration and Points System Integration
overview: Combined plan that calibrates each score one at a time, then immediately implements the corresponding points system for that score. This piecewise approach ensures points are built on stable, calibrated formulas and avoids rework. Integrates score calibration workflow with points vs scores differentiation.
todos:
  - id: infrastructure_database
    content: Set up database schema for points tracking and score weights (UserPoints, ScoreWeights tables)
    status: pending
  - id: infrastructure_points_manager
    content: Create PointsManager class for points management (add_points, get_points, etc.)
    status: pending
    dependencies:
      - infrastructure_database
  - id: infrastructure_score_weights
    content: Create ScoreWeights unified weight configuration system
    status: pending
    dependencies:
      - infrastructure_database
  - id: infrastructure_calibration_tools
    content: Create calibration dashboard UI and analysis scripts
    status: pending
    dependencies:
      - infrastructure_score_weights
  - id: productivity_calibration
    content: "Calibrate productivity score: analyze, create test scenarios, adjust weights, document"
    status: pending
    dependencies:
      - infrastructure_calibration_tools
  - id: productivity_points
    content: "Implement productivity points system: extract raw value, create calculation, store in DB, update UI"
    status: pending
    dependencies:
      - productivity_calibration
      - infrastructure_points_manager
  - id: grit_calibration
    content: "Calibrate grit score: analyze, create test scenarios, adjust weights, document"
    status: pending
    dependencies:
      - productivity_points
  - id: grit_points
    content: "Implement grit points system: extract raw value, create calculation, store in DB, update UI"
    status: pending
    dependencies:
      - grit_calibration
      - infrastructure_points_manager
  - id: relief_calibration
    content: "Calibrate relief score: analyze, create test scenarios, adjust weights, document"
    status: pending
    dependencies:
      - grit_points
  - id: relief_points
    content: "Implement relief points system: extract raw value, create calculation, store in DB, update UI"
    status: pending
    dependencies:
      - relief_calibration
      - infrastructure_points_manager
  - id: execution_implementation
    content: Implement execution score from proposal, then calibrate weights
    status: pending
    dependencies:
      - relief_points
  - id: execution_points
    content: "Implement execution points system: extract raw value, create calculation, store in DB, update UI"
    status: pending
    dependencies:
      - execution_implementation
      - infrastructure_points_manager
  - id: composite_calibration
    content: "Calibrate composite score: analyze component weights, create test scenarios, adjust, document"
    status: pending
    dependencies:
      - execution_points
  - id: composite_points
    content: Implement composite points as sum of component points, store in DB, update UI
    status: pending
    dependencies:
      - composite_calibration
      - infrastructure_points_manager
  - id: secondary_scores
    content: Calibrate and implement points for remaining scores (life balance, stress efficiency, tracking, work volume, obstacles)
    status: pending
    dependencies:
      - composite_points
---

# Score Calibration and Points System Integration Plan

**Created:** 2025-01-XX

**Status:** Planning

**Priority:** Medium (improves metric accuracy and tracking)

**Timeline:** 40-80 hours (4-8 hours per score × 10 scores)

## Overview

This plan combines score calibration and points system implementation into a single, piecewise workflow. For each score:

1. **Calibrate** the score formula and weights
2. **Implement** the corresponding points system
3. **Move on** to the next score

This ensures:

- Points are built on stable, calibrated formulas
- No rework when formulas change
- Incremental progress (one score at a time)
- Both systems evolve together

## Current State

- All metrics are "scores" normalized to 0-100
- No systematic calibration process
- No cumulative points tracking
- Weights are hardcoded and scattered
- No distinction between raw performance and normalized comparison

## Goals

1. Calibrate all 10 scores systematically
2. Create corresponding points systems for each score
3. Make points cumulative (grow over time)
4. Keep scores normalized (0-100 for comparison)
5. Create unified weight configuration system
6. Build calibration dashboard UI
7. Document all decisions and rationale

## Piecewise Workflow Pattern

### For Each Score:

**Step 1: Analysis (30 min)**

- Review current implementation
- Document current weights and formulas
- Identify all parameters to calibrate

**Step 2: Calibration (60-120 min)**

- Create test scenarios
- Measure baseline outputs
- Adjust weights iteratively
- Validate against expectations

**Step 3: Points Implementation (60-90 min)**

- Extract raw calculation value (before normalization)
- Create points calculation method
- Add points storage to database
- Update UI to display points

**Step 4: Documentation (30 min)**

- Document calibrated weights and rationale
- Document points calculation method
- Update decision matrix
- Create test scenarios

**Total per Score:** 3-4 hours

## Score-by-Score Implementation

### Score 1: Productivity Score

**Priority:** High (core metric)**Calibration Tasks:**

1. Document current implementation (`calculate_productivity_score`)
2. Identify weight parameters:

- `productivity_work_multiplier_min` (currently 3.0)
- `productivity_work_multiplier_max` (currently 5.0)
- `productivity_play_penalty_rate` (currently -0.003)
- `productivity_weekly_bonus_rate` (currently -0.01)
- `productivity_burnout_threshold_minutes` (currently 480)

3. Create test scenarios (high efficiency, low efficiency, burnout, etc.)
4. Calibrate weights iteratively
5. Document final weights

**Points Implementation Tasks:**

1. Extract raw productivity value (before normalization to 0-100)
2. Create `calculate_productivity_points()` method
3. Store points in database (add to `user_points` table)
4. Update UI to show: "Productivity: 1,234 points (Score: 85/100)"
5. Test points accumulation

**Deliverable:** Calibrated productivity score + working points system---

### Score 2: Grit Score

**Priority:** High (core metric)**Calibration Tasks:**

1. Document current implementation (`calculate_grit_score`)
2. Identify weight parameters:

- `grit_persistence_growth_rate` (currently 0.1)
- `grit_persistence_max_multiplier` (currently 2.0)
- `grit_time_bonus_rate` (currently 0.5)

3. Create test scenarios (first completion, 10th completion, slow completion, etc.)
4. Calibrate weights iteratively
5. Document final weights

**Points Implementation Tasks:**

1. Extract raw grit value (before normalization)
2. Create `calculate_grit_points()` method
3. Store points in database
4. Update UI to show points and score
5. Test points accumulation

**Deliverable:** Calibrated grit score + working points system---

### Score 3: Relief Score

**Priority:** High (core metric)**Calibration Tasks:**

1. Document current relief score calculations
2. Identify normalization parameters
3. Create test scenarios (high relief, low relief, duration variations)
4. Calibrate normalization if needed
5. Document final approach

**Points Implementation Tasks:**

1. Extract raw relief value (relief × duration, etc.)
2. Create `calculate_relief_points()` method
3. Store points in database
4. Update UI to show points and score
5. Test points accumulation

**Deliverable:** Calibrated relief score + working points system---

### Score 4: Execution Score

**Priority:** High (to be implemented)**Calibration Tasks:**

1. Implement execution score (from execution_score_proposal.md)
2. Calibrate component weights:

- Difficulty factor weight
- Speed factor weight
- Start speed factor weight
- Completion factor weight

3. Create test scenarios
4. Calibrate weights iteratively
5. Document final weights

**Points Implementation Tasks:**

1. Extract raw execution value (before normalization)
2. Create `calculate_execution_points()` method
3. Store points in database
4. Update UI to show points and score
5. Test points accumulation

**Deliverable:** Implemented + calibrated execution score + working points system---

### Score 5: Composite Score

**Priority:** Medium (aggregate metric)**Calibration Tasks:**

1. Document current implementation (`calculate_composite_score`)
2. Calibrate default weights for all components
3. Create test scenarios (various component combinations)
4. Calibrate component weights iteratively
5. Document final default weights

**Points Implementation Tasks:**

1. Calculate composite points as sum of component points
2. Create `calculate_composite_points()` method
3. Store points in database
4. Update UI to show points and score
5. Test points accumulation

**Deliverable:** Calibrated composite score + working points system---

### Score 6: Life Balance Score

**Priority:** Medium**Calibration Tasks:**

1. Document current implementation (`get_life_balance`)
2. Identify if self-care should be included
3. Calibrate target ratio
4. Create test scenarios
5. Document final approach

**Points Implementation Tasks:**

1. Extract raw balance value
2. Create `calculate_life_balance_points()` method
3. Store points in database
4. Update UI
5. Test

**Deliverable:** Calibrated life balance score + working points system---

### Score 7: Stress Efficiency Score

**Priority:** Medium**Calibration Tasks:**

1. Document current implementation
2. Calibrate normalization if needed
3. Create test scenarios
4. Document final approach

**Points Implementation Tasks:**

1. Extract raw efficiency value
2. Create `calculate_stress_efficiency_points()` method
3. Store points in database
4. Update UI
5. Test

**Deliverable:** Calibrated stress efficiency score + working points system---

### Score 8: Time Tracking Consistency Score

**Priority:** Medium**Calibration Tasks:**

1. Document current implementation (`calculate_time_tracking_consistency_score`)
2. Calibrate exponential decay constant (currently 2.0)
3. Calibrate sleep cap (currently 8 hours)
4. Create test scenarios
5. Document final approach

**Points Implementation Tasks:**

1. Extract raw tracking value
2. Create `calculate_tracking_consistency_points()` method
3. Store points in database
4. Update UI
5. Test

**Deliverable:** Calibrated tracking consistency score + working points system---

### Score 9: Work Volume Score

**Priority:** Lower**Calibration Tasks:**

1. Document current implementation (`get_daily_work_volume_metrics`)
2. Calibrate target (currently 360 minutes)
3. Calibrate decay constant (currently 180)
4. Create test scenarios
5. Document final approach

**Points Implementation Tasks:**

1. Extract raw volume value
2. Create `calculate_work_volume_points()` method
3. Store points in database
4. Update UI
5. Test

**Deliverable:** Calibrated work volume score + working points system---

### Score 10: Obstacles Score

**Priority:** Lower**Calibration Tasks:**

1. Document current implementation (`calculate_obstacles_scores`)
2. Select primary formula variant
3. Calibrate spike/relief weights
4. Calibrate multiplier scale (currently 9.0)
5. Create test scenarios
6. Document final approach

**Points Implementation Tasks:**

1. Extract raw obstacles value
2. Create `calculate_obstacles_points()` method
3. Store points in database
4. Update UI
5. Test

**Deliverable:** Calibrated obstacles score + working points system

## Infrastructure Setup (Do Once)

### Phase 1: Database Schema

**Files to create/modify:**

- `backend/database.py` - Add points tracking tables
- `SQLite_migration/006_add_points_tracking.py` - Migration script

**Tasks:**

1. Create `UserPoints` table for cumulative points storage
2. Create `PointsConfig` table for per-metric configuration
3. Create `ScoreWeights` table for calibrated weights storage
4. Run migration script

### Phase 2: Core Infrastructure

**Files to create:**

- `backend/points_manager.py` - Points management class
- `backend/score_weights.py` - Unified weight configuration system

**Tasks:**

1. Create `PointsManager` class with:

- `add_points(user_id, metric_name, points)`
- `get_points(user_id, metric_name)`
- `get_all_points(user_id)`

2. Create `ScoreWeights` class with:

- Weight storage and retrieval
- Weight validation
- Default weight management

### Phase 3: Calibration Tools

**Files to create:**

- `ui/score_calibration_page.py` - Calibration dashboard
- `scripts/calibrate_scores.py` - Calibration analysis tools

**Tasks:**

1. Create calibration dashboard UI
2. Create calibration analysis scripts
3. Create test scenario framework

## Implementation Order

### Week 1: Infrastructure + Core Scores

**Day 1-2: Infrastructure**

- Set up database schema
- Create PointsManager
- Create ScoreWeights system
- Create calibration dashboard skeleton

**Day 3-4: Productivity Score**

- Calibrate productivity score
- Implement productivity points
- Test and document

**Day 5: Grit Score**

- Calibrate grit score
- Implement grit points
- Test and document

### Week 2: Core Scores Continued

**Day 1: Relief Score**

- Calibrate relief score
- Implement relief points
- Test and document

**Day 2-3: Execution Score**

- Implement execution score (from proposal)
- Calibrate execution score
- Implement execution points
- Test and document

**Day 4: Composite Score**

- Calibrate composite score weights
- Implement composite points
- Test and document

### Week 3: Secondary Scores

**Day 1: Life Balance Score**

- Calibrate and implement points

**Day 2: Stress Efficiency Score**

- Calibrate and implement points

**Day 3: Time Tracking Consistency Score**

- Calibrate and implement points

**Day 4: Work Volume Score**

- Calibrate and implement points

**Day 5: Obstacles Score**

- Calibrate and implement points

## Technical Details

### Points Calculation Pattern

```python
def calculate_productivity_with_points(self, row, ...):
    """Calculate both productivity score and points."""
    
    # Calculate raw productivity value (not normalized)
    raw_productivity = completion_pct * multiplier * bonus
    
    # Calculate points (cumulative, not normalized, can exceed 100)
    productivity_points = raw_productivity
    
    # Calculate score (normalized 0-100)
    productivity_score = min(100.0, raw_productivity)
    
    # Store points
    points_manager.add_points(user_id, 'productivity', productivity_points)
    
    return {
        'productivity_score': productivity_score,
        'productivity_points': productivity_points
    }
```

### Weight Configuration Pattern

```python
# backend/score_weights.py
PRODUCTIVITY_WEIGHTS = {
    'work_multiplier_min': 3.0,  # Calibrated value
    'work_multiplier_max': 5.0,  # Calibrated value
    'play_penalty_rate': -0.003,  # Calibrated value
    # ... all calibrated parameters
}

# Load from database or use defaults
def get_productivity_weights(user_id: str) -> Dict:
    user_weights = user_state.get_score_weights(user_id)
    return user_weights.get('productivity', PRODUCTIVITY_WEIGHTS)
```

### Database Schema

```python
class UserPoints(Base):
    __tablename__ = 'user_points'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    metric_name = Column(String, nullable=False)  # 'productivity', 'grit', etc.
    points = Column(Float, default=0.0, nullable=False)
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_user_metric', 'user_id', 'metric_name'),
    )

class ScoreWeights(Base):
    __tablename__ = 'score_weights'
    
    id = Column(Integer, primary_key=True)
    user_id = Column(String, nullable=False, index=True)
    score_name = Column(String, nullable=False)  # 'productivity', 'grit', etc.
    weights = Column(JSON, nullable=False)  # Store all weights as JSON
    last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    __table_args__ = (
        Index('idx_user_score', 'user_id', 'score_name'),
    )
```

## Calibration Workflow Per Score

### Step 1: Analysis (30 min)

1. Review current implementation
2. Document current weights/formulas
3. Identify all parameters
4. Create analysis document

### Step 2: Test Scenarios (30 min)

1. Create 5-10 test scenarios
2. Define expected score ranges
3. Document scenarios

### Step 3: Baseline Measurement (30 min)

1. Run scenarios with current weights
2. Record outputs
3. Compare to expectations

### Step 4: Calibration (60-120 min)

1. Adjust one parameter at a time
2. Test with scenarios
3. Iterate until expectations met
4. Document changes

### Step 5: Points Implementation (60-90 min)

1. Extract raw calculation value
2. Create points calculation method
3. Add database storage
4. Update UI
5. Test accumulation

### Step 6: Documentation (30 min)

1. Document final weights and rationale
2. Document points calculation
3. Update decision matrix
4. Create calibration guide

## Success Criteria

- ✅ All 10 scores calibrated with documented rationale
- ✅ All 10 scores have corresponding points systems
- ✅ Points are cumulative and never reset
- ✅ Scores are normalized to 0-100
- ✅ Unified weight configuration system
- ✅ Calibration dashboard functional
- ✅ UI displays both points and scores
- ✅ All test scenarios pass
- ✅ Documentation complete

## Dependencies

- SQLite/PostgreSQL migration complete
- Database schema can be updated
- Existing score calculations working

## Notes

- Work on one score at a time (don't jump around)
- Complete calibration before implementing points
- Test thoroughly before moving to next score
- Document as you go (don't leave it for later)
- Use calibration dashboard to visualize changes