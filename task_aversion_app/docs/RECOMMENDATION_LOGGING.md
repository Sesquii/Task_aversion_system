# Recommendation System Logging

## Overview

The recommendation system now logs all interactions to help you understand what's working and what needs improvement. All logs are written to files in `data/logs/` directory.

## Log Files

### Recommendation Events Log
**File**: `data/logs/recommendations_YYYYMMDD.jsonl`

This is a JSONL (JSON Lines) file where each line is a JSON object representing one event. Three types of events are logged:

1. **`recommendation_generated`** - When recommendations are shown
2. **`recommendation_selected`** - When user clicks on a recommendation
3. **`recommendation_outcome`** - When a recommended task is completed

### Debug Log
**File**: `data/logs/recommendation_debug_YYYYMMDD.log`

Standard Python logging output for debugging issues with the logging system itself.

## Event Types

### 1. recommendation_generated

Logged when recommendations are generated (when dashboard loads or filters change).

**Fields**:
- `event_type`: "recommendation_generated"
- `timestamp`: ISO format timestamp
- `mode`: "templates" or "instances"
- `metrics`: List of metric keys used for ranking
- `filters`: Dictionary of filters applied
- `recommendation_count`: Number of recommendations shown
- `recommendations`: Array of recommendation objects with:
  - `task_id`: Task ID
  - `instance_id`: Instance ID (if instances mode)
  - `task_name`: Task name
  - `score`: Recommendation score (0-100)
  - `rank`: Position in the list (1 = top recommendation)
  - `metric_values`: Dictionary of metric values used

**Example**:
```json
{
  "event_type": "recommendation_generated",
  "timestamp": "2026-01-07T15:30:45.123456",
  "mode": "templates",
  "metrics": ["relief_score", "cognitive_load"],
  "filters": {"max_duration": 60},
  "recommendation_count": 10,
  "recommendations": [
    {
      "task_id": "t1764322772",
      "task_name": "Task Aversion project",
      "score": 85.5,
      "rank": 1,
      "metric_values": {"relief_score": 75.0, "cognitive_load": 60.0}
    }
  ]
}
```

### 2. recommendation_selected

Logged when user clicks INITIALIZE, START, or RESUME on a recommendation.

**Fields**:
- `event_type`: "recommendation_selected"
- `timestamp`: ISO format timestamp
- `task_id`: Task ID
- `instance_id`: Instance ID (if applicable)
- `task_name`: Task name
- `recommendation_score`: Score of the recommendation
- `action`: "initialize", "start", or "resume"
- `context`: Dictionary with:
  - `mode`: "templates" or "instances"
  - `metrics`: Metrics used
  - `filters`: Filters applied

**Example**:
```json
{
  "event_type": "recommendation_selected",
  "timestamp": "2026-01-07T15:31:12.789012",
  "task_id": "t1764322772",
  "instance_id": null,
  "task_name": "Task Aversion project",
  "recommendation_score": 85.5,
  "action": "initialize",
  "context": {
    "mode": "templates",
    "metrics": ["relief_score", "cognitive_load"],
    "filters": {"max_duration": 60}
  }
}
```

### 3. recommendation_outcome

Logged when a recommended task is completed.

**Fields**:
- `event_type`: "recommendation_outcome"
- `timestamp`: ISO format timestamp
- `task_id`: Task ID
- `instance_id`: Instance ID
- `task_name`: Task name
- `outcome`: "completed", "cancelled", or "abandoned"
- `completion_time_minutes`: Time taken to complete
- `actual_relief`: Actual relief score after completion
- `predicted_relief`: Predicted relief score from recommendation
- `relief_accuracy`: Absolute difference between predicted and actual relief

**Example**:
```json
{
  "event_type": "recommendation_outcome",
  "timestamp": "2026-01-07T16:15:30.456789",
  "task_id": "t1764322772",
  "instance_id": "i1764322800",
  "task_name": "Task Aversion project",
  "outcome": "completed",
  "completion_time_minutes": 45.0,
  "actual_relief": 80.0,
  "predicted_relief": 75.0,
  "relief_accuracy": 5.0
}
```

## Analyzing the Logs

### Quick Analysis Script

You can analyze the logs with a simple Python script:

```python
import json
from collections import defaultdict, Counter

# Read all events
events = []
with open('data/logs/recommendations_20260107.jsonl', 'r') as f:
    for line in f:
        events.append(json.loads(line))

# Count events by type
event_counts = Counter(e['event_type'] for e in events)
print("Event counts:", event_counts)

# Find most selected recommendations
selected = [e for e in events if e['event_type'] == 'recommendation_selected']
task_selections = Counter(e['task_name'] for e in selected)
print("\nMost selected tasks:", task_selections.most_common(10))

# Calculate completion rate
generated = len([e for e in events if e['event_type'] == 'recommendation_generated'])
selected_count = len(selected)
completed = len([e for e in events if e['event_type'] == 'recommendation_outcome' and e['outcome'] == 'completed'])

print(f"\nRecommendation stats:")
print(f"  Generated: {generated}")
print(f"  Selected: {selected_count} ({selected_count/generated*100:.1f}% selection rate)")
print(f"  Completed: {completed} ({completed/selected_count*100:.1f}% completion rate)")

# Analyze relief accuracy
outcomes = [e for e in events if e['event_type'] == 'recommendation_outcome' and e.get('relief_accuracy') is not None]
if outcomes:
    avg_accuracy = sum(e['relief_accuracy'] for e in outcomes) / len(outcomes)
    print(f"\nAverage relief prediction accuracy: {avg_accuracy:.1f} points")
```

### Key Metrics to Track

1. **Selection Rate**: % of recommendations that get selected
2. **Completion Rate**: % of selected recommendations that get completed
3. **Relief Accuracy**: How well predicted relief matches actual relief
4. **Top Recommendations**: Which tasks are recommended most often
5. **Metric Effectiveness**: Which metric combinations lead to better selections

## Usage Tips

1. **Let it run for a while**: Collect data over days/weeks to see patterns
2. **Compare metrics**: Try different metric combinations and see which ones lead to better outcomes
3. **Track your patterns**: See which types of recommendations you actually follow through on
4. **Identify improvements**: Look for patterns where predictions are consistently off

## File Location

Logs are stored in:
- `task_aversion_app/data/logs/recommendations_YYYYMMDD.jsonl`
- `task_aversion_app/data/logs/recommendation_debug_YYYYMMDD.log`

The directory is created automatically when the first log entry is written.
