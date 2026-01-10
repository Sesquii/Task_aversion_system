# Recommendation System Logging - Setup Complete

## Overview

Comprehensive logging has been added to the recommendation system to track:
- When recommendations are generated
- What recommendations are shown to users
- Which recommendations users select
- Outcomes of recommended tasks (completion, cancellation, etc.)

## What Was Added

### 1. Recommendation Logger Module (`backend/recommendation_logger.py`)

A new logging module that tracks:
- **Recommendation Generation**: Logs when recommendations are created, including metrics used, filters applied, and all recommendations shown
- **Recommendation Selection**: Logs when users click on recommendations (initialize/start/resume)
- **Recommendation Outcomes**: Logs when recommended tasks are completed, including relief accuracy
- **Task Completion**: Logs all task completions to compare recommended vs non-recommended tasks

### 2. Integration Points

#### Analytics (`backend/analytics.py`)
- `recommendations_by_category()` - Logs when template-based recommendations are generated
- `recommendations_from_instances()` - Logs when instance-based recommendations are generated

#### Dashboard UI (`ui/dashboard.py`)
- Button click handlers for INITIALIZE, START, and RESUME buttons log when recommendations are selected
- Captures context: metrics used, filters applied, recommendation score

#### Instance Manager (`backend/instance_manager.py`)
- `complete_instance()` - Logs outcomes when tasks are completed
- Tracks relief prediction accuracy (predicted vs actual)
- Records completion time

### 3. Analysis Script (`analyze_recommendation_logs.py`)

A script to analyze the logged data:
- Event breakdown by type
- Recommendation generation statistics
- Selection rates and patterns
- Completion rates
- Relief prediction accuracy
- Conversion funnel analysis
- Time-based trends

## Log File Locations

- **Recommendation Events**: `data/logs/recommendations_YYYYMMDD.jsonl` (JSONL format)
- **Debug Logs**: `data/logs/recommendation_debug_YYYYMMDD.log` (standard log format)

## Usage

### Viewing Logs

1. **Run the analysis script**:
   ```bash
   cd task_aversion_app
   python analyze_recommendation_logs.py
   ```

2. **View raw logs**:
   - JSONL files can be read line-by-line (each line is a JSON object)
   - Use any JSON viewer or text editor
   - Logs are organized by date (one file per day)

### What Gets Logged

#### Recommendation Generation Events
```json
{
  "event_type": "recommendation_generated",
  "timestamp": "2026-01-07T12:34:56",
  "mode": "templates",
  "metrics": ["relief_score", "cognitive_load"],
  "filters": {"max_duration": 60},
  "recommendation_count": 10,
  "recommendations": [
    {
      "task_id": "t1234567890",
      "task_name": "Task Name",
      "score": 85.5,
      "rank": 1,
      "metric_values": {...}
    }
  ]
}
```

#### Recommendation Selection Events
```json
{
  "event_type": "recommendation_selected",
  "timestamp": "2026-01-07T12:35:00",
  "task_id": "t1234567890",
  "task_name": "Task Name",
  "recommendation_score": 85.5,
  "action": "initialize",
  "context": {
    "metrics": ["relief_score"],
    "filters": {}
  }
}
```

#### Recommendation Outcome Events
```json
{
  "event_type": "recommendation_outcome",
  "timestamp": "2026-01-07T13:00:00",
  "task_id": "t1234567890",
  "instance_id": "i1234567890",
  "task_name": "Task Name",
  "outcome": "completed",
  "completion_time_minutes": 45.0,
  "actual_relief": 75.0,
  "predicted_relief": 70.0,
  "relief_accuracy": 5.0
}
```

## Next Steps

1. **Use the system normally** - Logging happens automatically
2. **Run analysis periodically** - Use `analyze_recommendation_logs.py` to see patterns
3. **Review insights** - Look for:
   - Which metrics lead to better selections
   - Which recommendations get completed most often
   - Relief prediction accuracy trends
   - Time-of-day patterns
   - Filter effectiveness

## Analysis Insights to Look For

### Selection Rate
- What percentage of recommendations are actually selected?
- Do higher-scored recommendations get selected more often?

### Completion Rate
- What percentage of selected recommendations are completed?
- How does this compare to non-recommended tasks?

### Relief Accuracy
- How accurate are relief predictions?
- Are we overestimating or underestimating relief?

### Metric Effectiveness
- Which metric combinations lead to better outcomes?
- Are certain filters more effective?

### Time Patterns
- Are recommendations more effective at certain times of day?
- Do patterns change over time?

## Notes

- Logging is non-blocking - if logging fails, the app continues normally
- Logs are written to JSONL format for easy parsing
- One log file per day keeps files manageable
- All sensitive data is excluded (only task IDs, names, scores)

## Future Enhancements

Potential improvements:
- Real-time dashboard showing recommendation effectiveness
- Automatic alerts when patterns change
- A/B testing different recommendation algorithms
- Machine learning model training on logged data
