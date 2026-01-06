---
name: Belief Scores and Load/Misalignment Detection Implementation
overview: Implement belief score system (prediction error-based self-understanding) and probabilistic load/misalignment detection for intervention recommendations. Belief scores derive from existing slider values; state detection uses behavioral signals.
todos:
  - id: belief-score-formulation
    content: Implement calculate_belief_score() method in analytics.py with prediction error-based formula
    status: pending
  - id: belief-score-analytics
    content: "Add belief score analytics methods: calculate_avg_belief_score(), get_belief_score_trend(), identify_low_belief_tasks()"
    status: pending
    dependencies:
      - belief-score-formulation
  - id: state-detection
    content: Implement detect_state_probabilities() method with load/misalignment signals
    status: pending
  - id: helper-methods
    content: "Implement helper methods: _calculate_recent_work_hours(), _calculate_completion_rate(), _calculate_completion_variance(), _calculate_abandonment_rate()"
    status: pending
  - id: intervention-recommendations
    content: Implement get_intervention_recommendations() method with state-based suggestions
    status: pending
    dependencies:
      - state-detection
  - id: belief-score-ui
    content: Add belief score visualization to analytics page (trend chart, low belief tasks)
    status: pending
    dependencies:
      - belief-score-analytics
  - id: state-detection-ui
    content: Add state detection card to dashboard showing load/misalignment probabilities and interventions
    status: pending
    dependencies:
      - intervention-recommendations
  - id: validation-tests
    content: Create validation tests for belief scores and state detection
    status: pending
    dependencies:
      - belief-score-formulation
      - state-detection
---

# Belief Scores and Load/Misalignment Detection Implementation

## Overview

This plan implements two complementary systems:

1. **Belief Scores**: Prediction error-based measurement of self-understanding (how well you predict your own states)
2. **Load/Misalignment Detection**: Probabilistic state detection for intervention recommendations

Both systems derive from existing slider values and behavioral signals - they don't replace explicit input, they enhance it.

---

## Phase 1: Belief Score System Implementation

### 1.1 Belief Score Formulation

**File**: `backend/analytics.py`

Implement prediction error-based belief scores:

```python
def calculate_belief_score(self, instance: pd.Series) -> float:
    """
    Calculate belief score based on prediction accuracy.
    Higher score = better self-understanding.
    
    Formula:
    - Normalize prediction errors for relief, time, load
    - Weighted combination: belief_score = 1 - (w_r * relief_error + w_t * time_error + w_l * load_error)
    - Result ∈ [0, 1], higher = better understanding
    
    Args:
        instance: Task instance row with expected and actual values
        
    Returns:
        Belief score (0.0 to 1.0), where 1.0 = perfect prediction
    """
    # Extract expected vs actual values from instance
    predicted_dict = instance.get('predicted_parsed', {}) if isinstance(instance.get('predicted_parsed'), dict) else {}
    actual_dict = instance.get('actual_parsed', {}) if isinstance(instance.get('actual_parsed'), dict) else {}
    
    # Relief prediction error
    expected_relief = predicted_dict.get('expected_relief') or predicted_dict.get('relief') or instance.get('expected_relief', 50)
    actual_relief = actual_dict.get('actual_relief') or actual_dict.get('relief') or instance.get('relief_score', 50)
    relief_error = min(1.0, abs(expected_relief - actual_relief) / 100.0)
    
    # Time prediction error
    estimated_duration = predicted_dict.get('time_estimate_minutes') or predicted_dict.get('estimate') or instance.get('time_estimate_minutes', 30)
    actual_duration = actual_dict.get('time_actual_minutes') or actual_dict.get('duration') or instance.get('duration_minutes', 30)
    if estimated_duration > 0:
        time_error = min(1.0, abs(estimated_duration - actual_duration) / max(estimated_duration, 1))
    else:
        time_error = 0.5  # Unknown estimate = moderate error
    
    # Load prediction error (cognitive + emotional)
    expected_cognitive = predicted_dict.get('expected_cognitive_load') or predicted_dict.get('cognitive_load') or instance.get('expected_cognitive_load', 50)
    expected_emotional = predicted_dict.get('expected_emotional_load') or predicted_dict.get('emotional_load') or instance.get('expected_emotional_load', 50)
    predicted_load = (expected_cognitive + expected_emotional) / 2.0
    
    actual_cognitive = actual_dict.get('actual_cognitive') or actual_dict.get('cognitive_load') or instance.get('cognitive_load', 50)
    actual_emotional = actual_dict.get('actual_emotional') or actual_dict.get('emotional_load') or instance.get('emotional_load', 50)
    actual_load = (actual_cognitive + actual_emotional) / 2.0
    
    load_error = min(1.0, abs(predicted_load - actual_load) / 100.0)
    
    # Weighted combination (tunable weights)
    weights = {'relief': 0.4, 'time': 0.3, 'load': 0.3}
    belief_score = 1.0 - (
        weights['relief'] * relief_error +
        weights['time'] * time_error +
        weights['load'] * load_error
    )
    
    return max(0.0, min(1.0, belief_score))
```

**Key Points:**

- Belief scores measure self-understanding (prediction accuracy), not state detection
- Different from ChatGPT's probabilistic state detection
- Can be used to identify when calibration is needed (low belief = high misalignment risk)
- Weights are tunable (can be adjusted based on validation)

### 1.2 Belief Score Analytics Methods

**File**: `backend/analytics.py`

Add methods to calculate and track belief scores:

```python
def calculate_avg_belief_score(self, days: int = 30, task_id: Optional[str] = None) -> float:
    """
    Calculate average belief score over recent period.
    
    Args:
        days: Number of days to look back
        task_id: Optional task ID to filter by
        
    Returns:
        Average belief score (0.0 to 1.0)
    """
    instances = self._load_instances()
    if instances.empty:
        return 0.5  # Default neutral
    
    # Filter to completed instances within time window
    cutoff_date = datetime.now() - timedelta(days=days)
    completed = instances[instances['completed_at'].astype(str).str.len() > 0].copy()
    completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
    completed = completed[completed['completed_at_dt'] >= cutoff_date]
    
    if task_id:
        completed = completed[completed['task_id'] == task_id]
    
    if completed.empty:
        return 0.5
    
    # Calculate belief scores for all instances
    belief_scores = []
    for idx, row in completed.iterrows():
        try:
            score = self.calculate_belief_score(row)
            belief_scores.append(score)
        except Exception as e:
            # Skip instances with calculation errors
            continue
    
    if not belief_scores:
        return 0.5
    
    return sum(belief_scores) / len(belief_scores)

def get_belief_score_trend(self, days: int = 90) -> Dict[str, List]:
    """
    Get belief score trend over time.
    
    Returns:
        Dict with 'dates' (list of date strings) and 'scores' (list of belief scores)
    """
    instances = self._load_instances()
    if instances.empty:
        return {'dates': [], 'scores': []}
    
    cutoff_date = datetime.now() - timedelta(days=days)
    completed = instances[instances['completed_at'].astype(str).str.len() > 0].copy()
    completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
    completed = completed[completed['completed_at_dt'] >= cutoff_date]
    
    if completed.empty:
        return {'dates': [], 'scores': []}
    
    # Group by day and calculate average belief score per day
    completed['date'] = completed['completed_at_dt'].dt.date
    daily_scores = {}
    
    for date, group in completed.groupby('date'):
        scores = []
        for idx, row in group.iterrows():
            try:
                score = self.calculate_belief_score(row)
                scores.append(score)
            except Exception:
                continue
        if scores:
            daily_scores[date] = sum(scores) / len(scores)
    
    # Sort by date
    sorted_dates = sorted(daily_scores.keys())
    return {
        'dates': [str(d) for d in sorted_dates],
        'scores': [daily_scores[d] for d in sorted_dates]
    }

def identify_low_belief_tasks(self, threshold: float = 0.5, min_completions: int = 3) -> List[Dict]:
    """
    Identify tasks with consistently low belief scores (calibration candidates).
    
    Args:
        threshold: Belief score threshold (below this = low belief)
        min_completions: Minimum number of completions to consider
        
    Returns:
        List of dicts with task_id, task_name, avg_belief_score, completion_count
    """
    instances = self._load_instances()
    if instances.empty:
        return []
    
    completed = instances[instances['completed_at'].astype(str).str.len() > 0].copy()
    
    # Group by task_id
    task_beliefs = {}
    for task_id in completed['task_id'].unique():
        task_completed = completed[completed['task_id'] == task_id]
        if len(task_completed) < min_completions:
            continue
        
        scores = []
        for idx, row in task_completed.iterrows():
            try:
                score = self.calculate_belief_score(row)
                scores.append(score)
            except Exception:
                continue
        
        if scores:
            avg_score = sum(scores) / len(scores)
            if avg_score < threshold:
                task_beliefs[task_id] = {
                    'task_id': task_id,
                    'task_name': task_completed.iloc[0].get('task_name', task_id),
                    'avg_belief_score': avg_score,
                    'completion_count': len(task_completed)
                }
    
    return sorted(task_beliefs.values(), key=lambda x: x['avg_belief_score'])
```

### 1.3 Belief Score Visualization

**File**: `ui/analytics_page.py` or `ui/dashboard.py`

Add belief score visualization to analytics:

```python
def add_belief_score_section(analytics: Analytics):
    """Add belief score visualization section."""
    with ui.card().classes("w-full"):
        ui.label("Self-Understanding (Belief Scores)").classes("text-xl font-semibold")
        ui.label("How well you predict your own states (relief, time, load)").classes("text-sm text-gray-600 mb-4")
        
        # Current average belief score
        avg_belief = analytics.calculate_avg_belief_score(days=30)
        with ui.row().classes("gap-4 mb-4"):
            ui.label(f"30-Day Average: {avg_belief:.2f}").classes("text-lg")
            # Visual indicator
            if avg_belief >= 0.7:
                ui.label("✓ Good self-understanding").classes("text-green-600")
            elif avg_belief >= 0.5:
                ui.label("~ Moderate self-understanding").classes("text-yellow-600")
            else:
                ui.label("! Consider calibration").classes("text-red-600")
        
        # Belief score trend
        trend = analytics.get_belief_score_trend(days=90)
        if trend['dates']:
            fig = go.Figure()
            fig.add_trace(go.Scatter(
                x=trend['dates'],
                y=trend['scores'],
                mode='lines+markers',
                name='Belief Score',
                line=dict(color='#3b82f6')
            ))
            fig.update_layout(
                title="Belief Score Trend (90 Days)",
                xaxis_title="Date",
                yaxis_title="Belief Score (0-1)",
                yaxis=dict(range=[0, 1]),
                height=300
            )
            ui.plotly(fig)
        
        # Low belief tasks (calibration candidates)
        low_belief_tasks = analytics.identify_low_belief_tasks(threshold=0.5, min_completions=3)
        if low_belief_tasks:
            with ui.expansion("Tasks Needing Calibration", icon="info").classes("mt-4"):
                ui.label("These tasks have consistently low prediction accuracy:").classes("text-sm mb-2")
                for task in low_belief_tasks[:5]:  # Show top 5
                    ui.label(
                        f"{task['task_name']}: {task['avg_belief_score']:.2f} "
                        f"({task['completion_count']} completions)"
                    ).classes("text-sm")
```

---

## Phase 2: Load vs. Misalignment Detection (Probabilistic)

### 2.1 Probabilistic State Detection

**File**: `backend/analytics.py`

Implement probabilistic belief scores for load/misalignment:

```python
def detect_state_probabilities(self, recent_history: Optional[pd.DataFrame] = None, days: int = 7) -> Dict[str, float]:
    """
    Return probabilistic belief scores for load and misalignment.
    
    Uses behavioral signals derived from slider values and task patterns.
    Probabilistic (0-1), not binary - both can coexist.
    
    Args:
        recent_history: Optional dataframe of recent instances (if None, loads from storage)
        days: Number of days to analyze (default 7)
        
    Returns:
        Dict with 'load_likelihood' and 'misalignment_likelihood' (0.0-1.0)
    """
    if recent_history is None:
        instances = self._load_instances()
        cutoff_date = datetime.now() - timedelta(days=days)
        completed = instances[instances['completed_at'].astype(str).str.len() > 0].copy()
        completed['completed_at_dt'] = pd.to_datetime(completed['completed_at'], errors='coerce')
        recent_history = completed[completed['completed_at_dt'] >= cutoff_date]
    
    if recent_history.empty:
        return {'load_likelihood': 0.0, 'misalignment_likelihood': 0.0}
    
    # Load signals (from slider values and behavioral patterns)
    load_signals = []
    
    # 1. Recent work volume (from task durations)
    recent_work_hours = self._calculate_recent_work_hours(recent_history, days=days)
    # Normalize: >8 hours/day = high load (1.0), <4 hours/day = low load (0.0)
    work_volume_signal = min(1.0, max(0.0, (recent_work_hours / 8.0) / days))
    load_signals.append(('work_volume', work_volume_signal, 0.3))
    
    # 2. Average cognitive/emotional load (from sliders)
    cognitive_loads = pd.to_numeric(recent_history['cognitive_load'], errors='coerce').dropna()
    emotional_loads = pd.to_numeric(recent_history['emotional_load'], errors='coerce').dropna()
    if not cognitive_loads.empty and not emotional_loads.empty:
        avg_load = (cognitive_loads.mean() + emotional_loads.mean()) / 2.0
        # Normalize: >70 = high load (1.0), <30 = low load (0.0)
        load_level_signal = min(1.0, max(0.0, (avg_load - 30) / 40.0))
        load_signals.append(('load_level', load_level_signal, 0.4))
    
    # 3. Completion rate decline (behavioral signal)
    completion_rate = self._calculate_completion_rate(recent_history)
    # Lower completion rate = higher load signal
    completion_signal = 1.0 - completion_rate  # Invert: low completion = high load
    load_signals.append(('completion_rate', completion_signal, 0.3))
    
    # Combine load signals (weighted average)
    if load_signals:
        load_score = sum(weight * signal for _, signal, weight in load_signals) / sum(weight for _, _, weight in load_signals)
    else:
        load_score = 0.0
    
    # Misalignment signals
    misalignment_signals = []
    
    # 1. Completion variance (high variance = uncertainty)
    completion_variance = self._calculate_completion_variance(recent_history)
    # Normalize: variance > 0.3 = high misalignment (1.0), <0.1 = low (0.0)
    variance_signal = min(1.0, max(0.0, (completion_variance - 0.1) / 0.2))
    misalignment_signals.append(('completion_variance', variance_signal, 0.3))
    
    # 2. Low belief scores (poor self-understanding = misalignment)
    belief_scores = []
    for idx, row in recent_history.iterrows():
        try:
            score = self.calculate_belief_score(row)
            belief_scores.append(score)
        except Exception:
            continue
    if belief_scores:
        avg_belief = sum(belief_scores) / len(belief_scores)
        # Low belief = high misalignment signal (invert)
        belief_signal = 1.0 - avg_belief
        misalignment_signals.append(('belief_score', belief_signal, 0.4))
    
    # 3. Task abandonment rate (behavioral signal)
    abandonment_rate = self._calculate_abandonment_rate(recent_history)
    misalignment_signals.append(('abandonment', abandonment_rate, 0.3))
    
    # Combine misalignment signals (weighted average)
    if misalignment_signals:
        misalignment_score = sum(weight * signal for _, signal, weight in misalignment_signals) / sum(weight for _, _, weight in misalignment_signals)
    else:
        misalignment_score = 0.0
    
    return {
        'load_likelihood': min(1.0, max(0.0, load_score)),
        'misalignment_likelihood': min(1.0, max(0.0, misalignment_score))
    }

def _calculate_recent_work_hours(self, instances: pd.DataFrame, days: int = 7) -> float:
    """Calculate total work hours in recent period."""
    durations = pd.to_numeric(instances['duration_minutes'], errors='coerce').dropna()
    if durations.empty:
        return 0.0
    return durations.sum() / 60.0  # Convert minutes to hours

def _calculate_completion_rate(self, instances: pd.DataFrame) -> float:
    """Calculate average completion percentage."""
    completions = pd.to_numeric(instances['completion_percentage'], errors='coerce').dropna()
    if completions.empty:
        return 1.0
    return completions.mean() / 100.0  # Normalize to 0-1

def _calculate_completion_variance(self, instances: pd.DataFrame) -> float:
    """Calculate variance in completion percentages (higher = more uncertainty)."""
    completions = pd.to_numeric(instances['completion_percentage'], errors='coerce').dropna()
    if len(completions) < 2:
        return 0.0
    return completions.std() / 100.0  # Normalize to 0-1 scale

def _calculate_abandonment_rate(self, instances: pd.DataFrame) -> float:
    """Calculate rate of task abandonment (cancelled vs completed)."""
    total = len(instances)
    if total == 0:
        return 0.0
    cancelled = instances[instances.get('cancelled_at', '').astype(str).str.len() > 0]
    return len(cancelled) / total
```

**Key Points:**

- Probabilistic, not binary (both load and misalignment can coexist)
- Derived from existing slider values + behavioral patterns
- Used for intervention recommendations, not diagnosis
- Thresholds are tunable based on validation

### 2.2 Intervention Recommendations

**File**: `backend/analytics.py`

Add intervention-aware recommendations:

```python
def get_intervention_recommendations(self, state_probs: Optional[Dict[str, float]] = None) -> List[Dict]:
    """
    Suggest interventions based on state probabilities.
    Framed as experiments, not prescriptions.
    
    Args:
        state_probs: Optional state probabilities (if None, calculates from recent history)
        
    Returns:
        List of intervention recommendation dicts
    """
    if state_probs is None:
        state_probs = self.detect_state_probabilities()
    
    load = state_probs.get('load_likelihood', 0.0)
    misalignment = state_probs.get('misalignment_likelihood', 0.0)
    
    recommendations = []
    
    # High load + low misalignment = rest candidate
    if load > 0.7 and misalignment < 0.3:
        recommendations.append({
            'type': 'intervention',
            'category': 'rest',
            'message': 'This might be a good moment for a 10-minute break. Want to try?',
            'urgency': 'low',
            'load_likelihood': load,
            'misalignment_likelihood': misalignment
        })
    
    # High misalignment + low load = calibration candidate
    if misalignment > 0.7 and load < 0.3:
        recommendations.append({
            'type': 'intervention',
            'category': 'calibration',
            'message': 'This might be a good moment to do a 10-minute alignment check. Want to try?',
            'urgency': 'low',
            'load_likelihood': load,
            'misalignment_likelihood': misalignment
        })
    
    # High load + high misalignment = danger zone
    if load > 0.7 and misalignment > 0.7:
        recommendations.append({
            'type': 'intervention',
            'category': 'combined',
            'message': 'You might benefit from both rest and clarity. Consider a short break followed by a quick alignment check.',
            'urgency': 'medium',
            'load_likelihood': load,
            'misalignment_likelihood': misalignment
        })
    
    return recommendations
```

**Key Points:**

- Framed as experiments, not prescriptions ("This might be a good moment...")
- Non-judgmental, optional
- Time-bounded suggestions (10 minutes)
- Includes state probabilities for transparency

### 2.3 Integration with Recommendation System

**File**: `backend/analytics.py`

Update recommendation system to use state probabilities:

```python
def recommendations(self, filters: Optional[Dict[str, float]] = None, include_interventions: bool = True) -> List[Dict[str, str]]:
    """
    Generate recommendations including interventions if enabled.
    
    Args:
        filters: Optional filters for task recommendations
        include_interventions: Whether to include intervention recommendations
        
    Returns:
        List of recommendation dicts (tasks + interventions)
    """
    # Get standard task recommendations
    task_recommendations = self._get_task_recommendations(filters)
    
    # Add intervention recommendations if enabled
    if include_interventions:
        intervention_recommendations = self.get_intervention_recommendations()
        # Combine and prioritize
        all_recommendations = intervention_recommendations + task_recommendations
    else:
        all_recommendations = task_recommendations
    
    return all_recommendations
```

---

## Phase 3: UI Integration

### 3.1 Dashboard Integration

**File**: `ui/dashboard.py`

Add state probability display to dashboard:

```python
def add_state_detection_card(analytics: Analytics):
    """Add state detection card to dashboard."""
    state_probs = analytics.detect_state_probabilities(days=7)
    
    with ui.card().classes("w-full"):
        ui.label("Current State").classes("text-lg font-semibold")
        
        # Load likelihood
        load = state_probs.get('load_likelihood', 0.0)
        with ui.row().classes("items-center gap-2"):
            ui.label("Load Likelihood:").classes("text-sm")
            ui.linear_progress(value=load).classes("flex-1")
            ui.label(f"{load:.0%}").classes("text-sm")
        
        # Misalignment likelihood
        misalignment = state_probs.get('misalignment_likelihood', 0.0)
        with ui.row().classes("items-center gap-2"):
            ui.label("Misalignment Likelihood:").classes("text-sm")
            ui.linear_progress(value=misalignment).classes("flex-1")
            ui.label(f"{misalignment:.0%}").classes("text-sm")
        
        # Intervention recommendations
        interventions = analytics.get_intervention_recommendations(state_probs)
        if interventions:
            with ui.expansion("Suggestions", icon="lightbulb").classes("mt-2"):
                for intervention in interventions:
                    ui.label(intervention['message']).classes("text-sm mb-2")
```

### 3.2 Analytics Page Integration

**File**: `ui/analytics_page.py`

Add belief score and state detection sections (see Phase 1.3 for belief score visualization).

---

## Phase 4: Validation and Testing

### 4.1 Validation Protocol

**File**: `tests/test_belief_scores.py` (new)

Create validation tests:

```python
def test_belief_score_calculation():
    """Test belief score calculation with known values."""
    # Test perfect prediction (should be 1.0)
    # Test poor prediction (should be < 0.5)
    # Test edge cases (missing values, zero estimates)

def test_state_detection():
    """Test state detection with known patterns."""
    # Test high load scenario
    # Test high misalignment scenario
    # Test combined scenario
```

### 4.2 User Validation

Track agreement between:

- Explicit user self-reports ("I feel exhausted" vs load_likelihood)
- Intervention effectiveness (did suggested intervention help?)
- Belief score trends (are they improving over time?)

---

## Success Metrics

- [ ] Belief score calculation implemented and tested
- [ ] State detection implemented (load/misalignment probabilities)
- [ ] Intervention recommendations working
- [ ] UI integration complete (dashboard + analytics)
- [ ] Validation tests passing
- [ ] Documentation updated

---

## Notes

- Belief scores and state detection are complementary, not replacements
- Both derive from existing slider values (no new input required)
- Probabilistic approach avoids false certainty
- Intervention recommendations are optional and non-judgmental