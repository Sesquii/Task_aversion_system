# Composite Score System & Time Tracking Consistency

## Overview

The system now includes two complementary features:

1. **Time Tracking Consistency Score** - Measures how well you track your time (0-100)
2. **Composite Score System** - Combines multiple scores/bonuses/penalties into a single normalized score (0-100)

## Time Tracking Consistency Score

### Purpose

Penalizes untracked time while rewarding proper sleep tracking. Encourages users to log their activities consistently.

### Formula

- **Tracked time** = work + play + self_care + sleep (capped at 8 hours)
- **Untracked time** = 24 hours - tracked time
- **Score** = 100 × (1 - exp(-tracking_coverage × 2.0))

Where `tracking_coverage` = tracked_time / 1440 minutes

### Features

- ✅ Rewards sleep up to 8 hours per day
- ✅ Sleep beyond 8 hours is treated as untracked time
- ✅ Exponential penalty for untracked time (more untracked = steeper penalty)
- ✅ Returns 0-100 score

### Usage

```python
from backend.analytics import Analytics

analytics = Analytics()

# Get full tracking data
tracking_data = analytics.calculate_time_tracking_consistency_score(days=7)
print(f"Score: {tracking_data['tracking_consistency_score']}")
print(f"Tracked: {tracking_data['avg_tracked_time_minutes']} min")
print(f"Untracked: {tracking_data['avg_untracked_time_minutes']} min")

# Get as multiplier (0.0 to 1.0) for adjusting other scores
multiplier = analytics.get_tracking_consistency_multiplier(days=7)
adjusted_score = base_score * multiplier
```

### Integration Example

```python
# Apply tracking consistency as a multiplier to productivity score
tracking_multiplier = analytics.get_tracking_consistency_multiplier(days=7)
productivity_score = calculate_productivity_score(...)
adjusted_productivity = productivity_score * tracking_multiplier
```

## Composite Score System

### Purpose

Combines multiple scores, bonuses, and penalties into a single normalized score (0-100) with customizable weights.

### Available Components

The system automatically gathers these components:

- `tracking_consistency_score` - Time tracking completeness
- `avg_stress_level` - Low stress (inverted: lower stress = higher score)
- `avg_net_wellbeing` - Net wellbeing score
- `avg_stress_efficiency` - Stress efficiency
- `avg_relief` - Average relief score
- `work_volume_score` - Work volume score
- `work_consistency_score` - Work consistency score
- `life_balance_score` - Life balance score
- `weekly_relief_score` - Weekly relief score
- `completion_rate` - Task completion rate
- `self_care_frequency` - Self-care task frequency

### Usage

```python
from backend.analytics import Analytics

analytics = Analytics()

# Get all available scores
all_scores = analytics.get_all_scores_for_composite(days=7)

# Calculate composite with default (equal) weights
composite_result = analytics.calculate_composite_score(
    components=all_scores,
    weights=None,  # Equal weights
    normalize_components=True
)

print(f"Composite Score: {composite_result['composite_score']}")
print(f"Contributions: {composite_result['component_contributions']}")

# Calculate with custom weights
custom_weights = {
    'tracking_consistency_score': 2.0,  # Double weight
    'avg_net_wellbeing': 1.5,
    'work_volume_score': 1.0,
    # ... other components default to 1.0
}

composite_result = analytics.calculate_composite_score(
    components=all_scores,
    weights=custom_weights,
    normalize_components=True
)
```

### Weight Normalization

Weights are automatically normalized to sum to 1.0:

```python
# If you provide weights: {A: 2.0, B: 1.0, C: 1.0}
# They become: {A: 0.5, B: 0.25, C: 0.25}
# Final score = A_score × 0.5 + B_score × 0.25 + C_score × 0.25
```

### Component Normalization

By default, components are clamped to 0-100 range. Set `normalize_components=False` to use raw values:

```python
composite_result = analytics.calculate_composite_score(
    components=all_scores,
    weights=custom_weights,
    normalize_components=False  # Use raw values
)
```

## UI Access

### Composite Score Dashboard

Navigate to `/composite-score` or click "📊 Composite Score Dashboard" in Settings.

Features:
- View composite score (0-100)
- See component contributions
- View time tracking consistency details
- Customize component weights
- Save/reset weight preferences

### Settings Integration

The composite score page is accessible from:
- Settings page → "📊 Composite Score Dashboard"

## User Preferences

Weights are stored per user in `user_preferences.csv`:

```python
from backend.user_state import UserStateManager

user_state = UserStateManager()
user_id = "your_user_id"

# Get weights
weights = user_state.get_score_weights(user_id)

# Set weights
user_state.set_score_weights(user_id, {
    'tracking_consistency_score': 2.0,
    'avg_net_wellbeing': 1.5,
    # ...
})
```

## Integration with Existing Systems

### Using Tracking Consistency as Multiplier

```python
# In any calculation that should be penalized for poor tracking:
tracking_multiplier = analytics.get_tracking_consistency_multiplier(days=7)

# Apply to productivity score
productivity = calculate_productivity_score(...)
adjusted_productivity = productivity * tracking_multiplier

# Apply to relief score
relief = get_relief_score(...)
adjusted_relief = relief * tracking_multiplier
```

### Using Composite Score

```python
# Get overall performance score
all_scores = analytics.get_all_scores_for_composite(days=7)
user_weights = user_state.get_score_weights(user_id) or {}
composite = analytics.calculate_composite_score(
    components=all_scores,
    weights=user_weights
)

overall_score = composite['composite_score']  # 0-100
```

## Default Weights

All components default to weight 1.0 (equal importance). Users can customize via the UI.

## Future Enhancements

1. **Time-decay**: Recent days count more than older days
2. **Streak bonuses**: Reward consistent tracking over time
3. **Category-specific tracking**: Different penalties for different activity types
4. **Adaptive baselines**: Use individual baselines instead of fixed targets
5. **Export/Import**: Share weight configurations between users

---

**Status:** ✅ Implemented
**Location:** 
- `backend/analytics.py`: `calculate_time_tracking_consistency_score()`, `calculate_composite_score()`, `get_all_scores_for_composite()`, `get_tracking_consistency_multiplier()`
- `backend/user_state.py`: `get_score_weights()`, `set_score_weights()`
- `ui/composite_score_page.py`: Composite score dashboard UI

