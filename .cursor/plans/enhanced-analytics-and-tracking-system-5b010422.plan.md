---
name: Enhanced Analytics and Tracking System
overview: ""
todos:

- id: 8ae4e96c-14bf-47f1-9d74-a4b973b9a5a7
content: "Improve input forms in initialize_task.py and complete_task.py: group related inputs, add collapsible sections, tooltips, and prominent previous averages"
status: pending
---

# Enhanced Analytics and Tracking System

## Overview

Improve the analytics and tracking system to better measure task aversion indirectly, enhance emotion tracking with bipolar scales (-100 to +100), add derived/manual modes for factors, track bidirectional capacity changes, measure time-since-completion patterns, and enable template editing with versioning. Balance data collection with user input efficiency.

## Current State Analysis

### Existing Tracking

- **Attributes**: duration_minutes, relief_score, cognitive_load, emotional_load, environmental_effect, skills_improved, behavioral_deviation
- **Emotions**: Currently stored as list of strings in `predicted` JSON and task `categories` field
- **Scales**: Most metrics use 0-100 scale (some legacy 0-10)
- **Analytics**: Relief trends, efficiency scores, task recommendations based on historical data

### Gaps Identified

1. No indirect task aversion measurement (e.g., capacity building from low-load tasks)
2. Emotions are categorical only, no intensity scales
3. No derived vs manual mode for factors
4. Emotions not customizable per task template
5. No template editing/versioning system
6. Missing metrics: time-since-completion, bidirectional capacity, recommendation auto-detection

## Implementation Plan

### Phase 1: Bipolar Emotion Tracking System

#### 1.1 Update Emotion Schema

- **File**: `backend/emotion_manager.py`
- Add support for bipolar emotion pairs (e.g., happy ↔ sad, excited ↔ anxious)
- Store emotion pairs with bipolar scale (-100 to +100)
- Each emotion input tracks 2 emotions on a single bipolar scale
- Maintain backward compatibility with existing emotion strings

#### 1.2 Task Template Emotion Customization

- **File**: `ui/create_task.py`
- Allow each task template to define which emotion pairs to track
- Store selected emotion pairs in task template (extend `categories` or new field)
- Default to global emotion list if none specified
- Emotions are global but customizable per template

#### 1.3 Template Editing and Versioning

- **File**: `ui/create_task.py` (or new `ui/edit_task.py`)
- Add "Edit Template" button to task management UI
- When editing, allow saving as new version or replacing old one
- Track template version history in tasks.csv
- Update task_schema to support versioning

#### 1.4 Bipolar Emotion Input UI

- **File**: `ui/initialize_task.py`
- Replace simple emotion list with bipolar emotion sliders (-100 to +100)
- Each slider represents an emotion pair (e.g., happy ↔ sad)
- Show emotion pairs from task template or global list
- Make it quick to input (sliders with presets at -100, 0, +100)

### Phase 2: Task Aversion Indirect Measurement

#### 2.1 Add Aversion Indicators to Schema

- **File**: `backend/task_schema.py`
- Add new attributes:
- `recommendation_used` (binary): Auto-inferred from init source (recommended vs quick task)
- `excitement_change` (numeric): Change in expected relief after seeing task
- `capacity_before` (numeric): Capacity level before task (0-100)
- `capacity_after` (numeric): Capacity level after task (0-100)
- `capacity_change` (numeric, derived): capacity_after - capacity_before
- `delay_minutes` (already exists, enhance usage)
- `time_since_last_completion` (numeric): Days since this task was last completed
- `completion_frequency_deviation` (numeric): Deviation from social standard frequency
- `recommendation_viewed` (binary): Did user view recommendations before starting?

#### 2.2 Automatic Recommendation Detection

- **File**: `ui/dashboard.py` and recommendation components
- Track init source: if user clicks "init" from recommended task card → auto-set `recommendation_used = True`
- If from quick task or other source → `recommendation_used = False`
- Store recommendation source (category, filters used) in predicted JSON

#### 2.3 Bidirectional Capacity Analytics

- **File**: `backend/analytics.py`
- Add method to detect bidirectional capacity patterns:
- High load → low load: Does high-load task reduce capacity for low-load tasks?
- Low load → high load: Does low-load task increase capacity for high-load tasks?
- Interspersing patterns: Optimal efficiency from alternating load levels
- Time window analysis: tasks completed within X hours of each other
- Capacity change tracking: measure before/after capacity for each task
- Calculate capacity impact scores (positive and negative)

#### 2.4 Time-Since-Last-Completion Tracking

- **File**: `backend/analytics.py`
- Calculate days since last completion of same task_id
- Track relief scores vs time-since-last-completion
- Identify patterns: relief highest right after completion, aversion builds over time
- Task-specific frequency benchmarks (e.g., laundry ~weekly, shower ~daily)

#### 2.5 Social Standard Frequency Benchmarks

- **File**: `backend/analytics.py`
- Define or learn social standard frequencies for common task types
- Calculate deviation from standard (e.g., laundry should be weekly, if done monthly = high deviation)
- Use deviation as calibration factor for task aversion/expediency
- Store in task template or derive from historical patterns

#### 2.6 Excitement/Relief Change Tracking

- **File**: `ui/initialize_task.py`
- Track initial expected relief when task is created
- Allow user to update expected relief after viewing recommendations
- Calculate excitement_change = updated_relief - initial_relief

### Phase 3: Derived vs Manual Mode for Factors

#### 3.1 Add Mode Support to Schema

- **File**: `backend/task_schema.py`
- Add mode tracking for key factors:
- `relief_mode` (enum: 'derived', 'manual')
- `capacity_mode` (enum: 'derived', 'manual')
- `relief_before` (numeric): For derived mode
- `relief_after` (numeric): For derived mode
- `relief_manual` (binary or numeric): For manual mode - "Did you feel net relief?"
- Store mode preference in task template or user settings

#### 3.2 Derived Mode Implementation

- **File**: `ui/initialize_task.py` and `ui/complete_task.py`
- For derived mode: Measure before/after values
- Relief: measure before task start, after completion
- Capacity: measure before task start, after completion
- Calculate derived values: change = after - before

#### 3.3 Manual Mode Implementation

- **File**: `ui/initialize_task.py` and `ui/complete_task.py`
- For manual mode: Ask simple binary or scale questions
- Relief: "Did you feel net relief from completing the task?" (binary or 0-100)
- Capacity: "Did this task increase your capacity?" (binary or 0-100)
- Formulate clear, simple questions for each factor
- Allow user to choose mode per factor in settings or per task template

#### 3.4 Mode Selection UI

- **File**: `ui/settings_page.py` or task template editor
- Add mode selection for each factor (derived vs manual)
- Store preference globally or per template
- Show appropriate input UI based on selected mode

### Phase 4: Enhanced Analytics

#### 4.1 Aversion Score Calculation

- **File**: `backend/analytics.py`
- Create `calculate_aversion_score()` method:
- High delay → higher aversion
- Low expected relief → higher aversion
- High emotional load + low motivation → higher aversion
- Recommendation usage → lower aversion (user seeking help)
- Excitement increase → lower aversion
- High time_since_last_completion → higher aversion (task piling up)
- High completion_frequency_deviation → higher aversion (deviating from standard)

#### 4.2 Bidirectional Capacity Metrics

- **File**: `backend/analytics.py`
- Add `get_capacity_patterns()`:
- Identify sequences of low-load → high-load tasks (capacity building)
- Identify sequences of high-load → low-load tasks (capacity draining)
- Calculate optimal interspersing patterns
- Measure capacity changes (before/after) for each task
- Track success rate of high-load tasks after low-load tasks
- Track failure rate of low-load tasks after high-load tasks

#### 4.3 Time-Since-Completion Analytics

- **File**: `backend/analytics.py`
- Add `get_completion_frequency_patterns()`:
- Calculate average time between completions per task
- Identify task-specific frequency patterns
- Track relief scores vs time-since-last-completion
- Detect when relief drops and aversion builds
- Compare to social standard frequencies

#### 4.4 Recommendation Effectiveness

- **File**: `backend/analytics.py`
- Track recommendation effectiveness:
- Completion rate of recommended vs non-recommended tasks
- Average relief of recommended tasks
- User satisfaction with recommendations (via capacity boost)
- Auto-detected recommendation usage (from init source)

#### 4.5 Analytics Dashboard Updates

- **File**: `ui/analytics_page.py`
- Add aversion score trends
- Show bidirectional capacity patterns
- Display time-since-completion patterns
- Show recommendation effectiveness metrics
- Visualize bipolar emotion intensity over time

### Phase 5: Data Migration and Backward Compatibility

#### 5.1 Schema Migration

- **File**: `backend/task_schema.py`
- Ensure new attributes have sensible defaults
- Handle missing data gracefully in analytics
- Support both derived and manual mode data

#### 5.2 Data Backfill

- **File**: `backend/analytics.py`
- Derive values from existing data where possible:
- `time_since_last_completion` from historical completions
- `completion_frequency_deviation` from historical patterns
- `recommendation_used` from task source (if tracked)
- Mark as "unknown" where not derivable
- Calculate capacity_change from capacity_before/after if available

### Phase 6: UI/UX Improvements

#### 6.1 Streamlined Input Forms

- **Files**: `ui/initialize_task.py`, `ui/complete_task.py`
- Group related inputs (emotions together, capacity together, etc.)
- Use collapsible sections for optional detailed metrics
- Add tooltips explaining each metric and mode (derived vs manual)
- Show previous averages prominently
- Show mode selection clearly (derived vs manual)

#### 6.2 Template Emotion Management

- **File**: `ui/create_task.py` and template editor
- Enhanced emotion pair selection UI (bipolar scales)
- Preview of emotion scales (-100 to +100)
- Quick add/remove emotion pairs per template
- Support editing existing templates

#### 6.3 Template Editing UI

- **File**: `ui/create_task.py` or new `ui/edit_task.py`
- Add "Edit Template" button in task management views
- Load existing template data into form
- Show current version number
- Option to "Save as New Version" or "Replace Current Version"
- Display version history

## Technical Considerations

### Data Storage

- Extend `task_instances.csv` with new columns
- Store bipolar emotion values in `predicted` and `actual` JSON (backward compatible)
- Add new columns for capacity_before/after, time_since_last_completion, etc.
- Store mode preferences (derived/manual) in task template or user settings
- Track template versions in tasks.csv

### Performance

- Analytics calculations should be efficient (pandas operations)
- Cache frequently accessed metrics (time-since-completion, frequency patterns)
- Lazy load detailed analytics
- Efficient sequence pattern detection

### User Experience

- Balance between data richness and input time
- Bipolar emotion sliders are quick (single slider per emotion pair)
- Derived mode: measure before/after (2 inputs)
- Manual mode: simple binary/scale question (1 input)
- Smart defaults based on task template and history
- Clear mode selection UI

## Success Metrics

- User can track emotions with bipolar scales (2 emotions per input)
- Task aversion patterns are visible in analytics
- Bidirectional capacity patterns are detected
- Time-since-completion patterns are tracked
- Recommendation effectiveness is measurable (auto-detected)
- Template editing and versioning works
- Derived vs manual modes available for key factors
- Input time remains reasonable (< 2 minutes for initialization)

## Future Enhancements (Out of Scope)

- ML-based aversion prediction
- Automatic emotion detection
- Advanced sequence pattern recognition
- Multi-user support with personalization
- Learning social standard frequencies from external data
- Automatic mode recommendation (derived vs manual) based on user patterns