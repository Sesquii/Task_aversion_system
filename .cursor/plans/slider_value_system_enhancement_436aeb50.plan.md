---
name: ""
overview: ""
todos: []
---

---

name: Slider Value System Enhancement

overview: Enhance the slider value system by renaming "actual" to "final" for clarity, adding deviation detection and notes, implementing a hybrid emotion tracking system with periodic monitoring, comprehensive monitoring settings for slider visibility control, and a primary emotional construct system for focused tracking.

todos:

  - id: rename_actual_to_final

content: ""

status: pending

  - id: deviation_detection

content: Implement deviation detection logic (20+ point difference) and store deviation flags in instance data

status: pending

  - id: slider_notes_component

content: Create reusable slider_with_notes component that shows note icon only when deviation detected

status: pending

dependencies:

      - deviation_detection
  - id: deviation_popup

content: Add popup trigger for significant deviations asking user to explain changes

status: pending

dependencies:

      - deviation_detection
  - id: experience_notes

content: Add optional 'experience notes' field to completion page for emotional context separate from task details

status: pending

  - id: emotional_state_monitor_page

content: Create emotional state monitoring page that displays last input emotions, allows adding/removing emotions, and saves to emotional state log

status: pending

  - id: emotional_state_data_model

content: Extend emotion_manager with emotional state history storage and retrieval methods

status: pending

  - id: settings_monitoring_config

content: "Add emotional monitoring configuration section to settings page: enable/disable toggle and interval (30-60 min) configuration"

status: pending

  - id: dashboard_monitoring_toggle

content: Add toggle button on dashboard (only visible when monitoring enabled in settings) to control active/paused state

status: pending

dependencies:

      - settings_monitoring_config
  - id: monitoring_prompt_logic

content: Implement prompt logic that only triggers when enabled in settings AND active on dashboard AND interval has elapsed, preventing popups when away

status: pending

dependencies:

      - dashboard_monitoring_toggle
      - emotional_state_data_model
  - id: task_emotion_expected_final

content: Update initialize/complete pages to use expected/final emotion terminology and store task-specific emotional changes

status: pending

  - id: fix_emotion_persistence

content: ""

status: pending

dependencies:

      - emotional_state_data_model
      - task_emotion_expected_final
  - id: deviation_visualization

content: Add visual indicators for deviations (colored borders, expected value markers, deviation amounts)

status: pending

dependencies:

      - slider_notes_component
  - id: data_migration

content: Create migration scripts to rename actual_ *fields to final_* in database and CSV backends

status: pending

dependencies:

      - rename_actual_to_final
  - id: monitoring_settings_page

content: Create comprehensive monitoring settings page/section with slider visibility controls (relief/aversion, loads/stress, task emotions)

status: pending

  - id: tracking_preferences_storage

content: Add backend methods to store and retrieve tracking preferences (which sliders are enabled/disabled)

status: pending

  - id: conditional_slider_rendering

content: Update initialize_task.py and complete_task.py to conditionally render sliders based on tracking preferences

status: pending

dependencies:

      - tracking_preferences_storage
  - id: primary_emotional_construct

content: Implement primary emotional construct system: configuration UI, custom construct builder, and integration in monitoring pages

status: pending

  - id: experimental_features_framework

content: Create framework for experimental monitoring features with enable/disable toggles and feedback mechanisms

status: pending

---

# Slider Value System Enhancement

## Overview

Enhance the slider value system to improve clarity, add deviation tracking with notes, implement a robust hybrid emotion tracking system that separates global emotional state monitoring from task-specific emotional changes, provide comprehensive monitoring settings for customizable slider visibility, and introduce a primary emotional construct system for focused emotional dimension tracking.

## Current State Analysis

### Existing Slider System

- **Initialize Task** (`ui/initialize_task.py`): Uses "expected" values (expected_relief, expected_mental_energy, expected_difficulty, expected_emotional_load, expected_physical_load)
- **Complete Task** (`ui/complete_task.py`): Uses "actual" values (actual_relief, actual_mental_energy, actual_difficulty, actual_emotional, actual_physical)
- Emotions stored in `predicted` JSON as `emotion_values` dict and in `actual` JSON
- Persistent emotions stored in `user_state` via `get_persistent_emotions()` / `set_persistent_emotions()`

### Issues Identified

1. "Actual" terminology is ambiguous - "final" is clearer
2. No mechanism to capture why values deviated significantly from expectations
3. Emotions system mixes global state with task-specific predictions
4. When initializing tasks hours in advance, emotion values don't reflect current state at execution time
5. No way to track emotional state over time independently of tasks

## Implementation Plan

### Phase 1: Terminology and Data Model Updates

#### 1.1 Rename "actual" to "final" throughout codebase

- **Files to update:**
- `ui/complete_task.py`: Rename all "actual" labels and variables to "final"
- `backend/instance_manager.py`: Update field names in database/CSV operations
- `backend/task_manager.py`: Update any references to actual values
- Any analytics or computation files that reference actual values
- **Data migration:**
- Create migration script to rename `actual_*` fields to `final_*` in database
- Update CSV column names if using CSV backend
- Maintain backward compatibility during transition

#### 1.2 Update UI Labels

- Change "Actual Relief" → "Final Relief"
- Change "Actual Mental Energy" → "Final Mental Energy"
- Change "Actual Distress" → "Final Distress"
- Change "Actual Physical Demand" → "Final Physical Demand"
- Update all helper text and tooltips accordingly

### Phase 2: Deviation Detection and Notes System

#### 2.1 Deviation Detection Logic

- **File**: `backend/instance_manager.py` or new `backend/deviation_tracker.py`
- Calculate deviation: `abs(final_value - expected_value) >= 20`
- Track deviations for: relief, mental_energy, difficulty, emotional_load, physical_load, emotions
- Store deviation flags in instance data

#### 2.2 Slider Notes UI Component

- **File**: `ui/components/slider_with_notes.py` (new)
- Create reusable component that wraps NiceGUI slider
- Shows note icon/button only when `deviation_detected == True`
- Icon appears next to slider label (e.g., 📝 or note icon)
- Clicking icon opens modal/textarea for deviation explanation
- Notes stored in instance `actual`/`final` JSON as `deviation_notes: {slider_name: "note text"}`

#### 2.3 Popup for Significant Deviations

- **File**: `backend/popup_dispatcher.py` (extend existing)
- Add new trigger type: `deviation_spike`
- Triggered when completing task with 20+ point deviation on any slider
- Popup asks: "You marked [slider] as [X] but expected [Y]. What changed?"
- Response saved to deviation_notes
- Only shows once per completion (not on every edit)

#### 2.4 Integration in Complete Task Page

- **File**: `ui/complete_task.py`
- Replace standard sliders with `slider_with_notes` components
- Pass expected values and final values to detect deviations
- Show deviation indicators (icon) only when deviation >= 20 points
- Store deviation notes in completion data

### Phase 3: Emotional Context/Experience Notes

#### 3.1 Add Experience Notes Field

- **File**: `ui/complete_task.py`
- Add new textarea: "Experience Notes (optional)"
- Label: "Describe how completing this task made you feel, separate from task completion details"
- Store in `actual`/`final` JSON as `experience_notes`
- Distinct from `completion_notes` (task-specific) and `deviation_notes` (slider-specific)

#### 3.2 Display Experience Notes

- Show in task detail views
- Include in analytics/export if relevant
- Optional: Add to initialization page for "expected experience" (future enhancement)

### Phase 4: Hybrid Emotion Tracking System

#### 4.1 Current Emotional State Monitoring Page

- **File**: `ui/emotional_state_monitor.py` (new)
- Standalone page accessible via `/emotional-state`
- Shows all tracked emotions with sliders (0-100 scale)
- "Current Emotional State" title
- Display emotions from last input (most recent emotional_state_log entry)
- Allow adding/removing emotions similar to existing system (comma-separated input + "Update emotions" button)
- Save button updates global emotional state and records timestamp
- Store timestamps and values in time series format

#### 4.2 Emotional State Data Model

- **File**: `backend/emotion_manager.py` (extend)
- Add `get_emotional_state_history(user_id, start_date, end_date)` method
- Store in new table/CSV: `emotional_state_log.csv` or database table
- Fields: timestamp, user_id, emotion_values (JSON dict)
- Separate from task-specific emotion tracking

#### 4.3 Emotional Monitoring Configuration in Settings

- **File**: `ui/settings_page.py` (modify)
- Add new section: "Emotional State Monitoring"
- Enable/disable toggle: "Enable Emotional State Monitoring"
- Interval configuration: Number input for minutes (range 30-60, default 45)
- Label: "Prompt interval (minutes):"
- Help text: "When enabled, you'll be prompted to update your emotional state at regular intervals. Configure the interval and enable/disable monitoring here."
- Store settings: `emotional_monitoring_enabled` (bool), `emotional_monitoring_interval_minutes` (int, default 45)
- **File**: `backend/user_state.py` (extend)
- Add `get_emotional_monitoring_config(user_id)` method - returns enabled status and interval
- Add `set_emotional_monitoring_enabled(user_id, enabled)` method
- Add `set_emotional_monitoring_interval(user_id, interval_minutes)` method
- Add `should_prompt_emotional_state(user_id)` method - checks if enabled AND interval elapsed
- Store: `last_emotional_prompt_at` (datetime) to track when last prompted

#### 4.4 Dashboard Toggle Button (Only When Enabled)

- **File**: `ui/dashboard.py` (modify)
- Check if `emotional_monitoring_enabled` is True in settings
- If enabled: Show toggle button/switch on dashboard: "Emotional State Monitoring: ON/OFF"
- Button allows quick toggle of monitoring active state (separate from settings enable/disable)
- When dashboard button is ON: Monitoring active, prompts will appear
- When dashboard button is OFF: Monitoring paused (but still enabled in settings, just not actively prompting)
- Store active state: `emotional_monitoring_active` (bool, separate from `emotional_monitoring_enabled`)
- Show last emotional state check time (from most recent emotional_state_log entry)
- Quick access button: "Update Emotional State" (always visible when monitoring enabled, links to `/emotional-state`)
- **File**: `ui/dashboard.py` or page load handler
- On dashboard load: Check if monitoring enabled in settings AND active on dashboard AND interval elapsed
- If all conditions met: Show popup/modal prompting user to update emotional state
- Popup links to `/emotional-state` page or shows inline form
- Only prompts when both enabled in settings AND active on dashboard (prevents popups when away from device)

#### 4.4 Task-Specific Expected/Final Emotions

- **File**: `ui/initialize_task.py`
- Rename "Current Emotional State" → "Expected Emotional State"
- Label: "How do you expect this task to make you feel?"
- Store as `expected_emotion_values` in `predicted` JSON
- **File**: `ui/complete_task.py`
- Rename "Current Emotional State" → "Final Emotional State"
- Label: "How did completing this task make you feel?"
- Store as `final_emotion_values` in `actual`/`final` JSON
- Show comparison: expected vs final with change indicators

#### 4.5 Fix Emotion State Persistence Issue

- **Problem**: When initializing task hours in advance, emotions are captured at initialization time, not execution time
- **Solution**: 
- At initialization: Store `expected_emotion_values` (predictions)
- At completion: Load most recent `emotional_state_log` entry as baseline, then allow user to adjust for task-specific changes
- Or: Show both "baseline emotional state" (from monitoring) and "task-specific changes" (expected/final deltas)

### Phase 5: UI/UX Improvements

#### 5.1 Deviation Visualization

- Color-code sliders with deviations (e.g., orange border when deviation >= 20)
- Show expected value as marker/line on slider track
- Display deviation amount: "+25" or "-18" next to final value

#### 5.2 Emotional State Monitor Integration

- **File**: `ui/dashboard.py`
- Conditional display: Only show monitoring controls when `emotional_monitoring_enabled` is True (from settings)
- Toggle button: "Emotional State Monitoring: ON/OFF" (controls active state, not enable/disable)
- Show last emotional state check time (from most recent emotional_state_log entry)
- Quick access button: "Update Emotional State" (visible when monitoring enabled, links to `/emotional-state`)
- Display current emotional state summary widget (shows last recorded values)
- When toggle is ON: Show indicator that monitoring is active
- When toggle is OFF: Show that monitoring is paused (but still enabled in settings)

#### 5.3 Navigation and Access

- Emotional state monitor accessible via `/emotional-state` route
- Settings page: Configure enable/disable and interval
- Dashboard: Quick toggle for active/paused state (only visible when enabled in settings)
- Optional: Add to main navigation menu for direct access to emotional state page

### Phase 6: Comprehensive Monitoring Settings

#### 6.1 Unified Monitoring Settings Page

- **File**: `ui/settings_page.py` (extend) or create `ui/settings/monitoring_settings.py`
- Create new section: "Monitoring Settings" or expand existing emotional monitoring section
- Consolidate all monitoring-related settings in one place
- Organized into subsections with clear labels

#### 6.2 Slider Visibility Controls

- **File**: `ui/settings_page.py` or `ui/settings/monitoring_settings.py`
- Add section: "Tracked Metrics"
- Enable/disable toggles for each slider category:
  - **Relief/Aversion** (combined setting - tracks both relief and aversion together)
    - Toggle: "Track Relief & Aversion"
    - When enabled: Shows both relief and aversion sliders in initialize/complete pages
    - When disabled: Hides both sliders
  - **Loads/Stress** (combined setting)
    - Toggle: "Track Cognitive & Physical Loads"
    - Sub-options (checkboxes):
      - Mental Energy Needed
      - Task Difficulty
      - Emotional Load (Distress)
      - Physical Load
    - When enabled: Shows selected load/stress sliders
  - **Task-Based Emotional Monitoring**
    - Toggle: "Track Task-Specific Emotions"
    - When enabled: Shows emotion sliders in initialize/complete pages
    - When disabled: Hides emotion tracking (but global emotional state monitoring can still be active)

- **File**: `backend/user_state.py` (extend)
- Add methods:
  - `get_tracking_preferences(user_id)` - Returns dict of enabled/disabled sliders
  - `set_tracking_preferences(user_id, preferences)` - Saves slider visibility settings
- Store in user_preferences:
  - `track_relief_aversion` (bool, default True)
  - `track_mental_energy` (bool, default True)
  - `track_difficulty` (bool, default True)
  - `track_emotional_load` (bool, default True)
  - `track_physical_load` (bool, default True)
  - `track_task_emotions` (bool, default True)

#### 6.3 Integration with Initialize/Complete Pages

- **File**: `ui/initialize_task.py` (modify)
- Check tracking preferences before rendering sliders
- Only show sliders that are enabled in settings
- If all sliders disabled for a category, hide the entire section
- Maintain backward compatibility: If preferences not set, show all sliders (default behavior)

- **File**: `ui/complete_task.py` (modify)
- Same conditional rendering based on tracking preferences
- Only show final value sliders for enabled metrics
- Hide comparison labels if expected value slider was disabled during initialization

#### 6.4 Emotional Monitoring Settings (Consolidated)

- **File**: `ui/settings_page.py` or `ui/settings/monitoring_settings.py`
- Move emotional monitoring configuration to monitoring settings section
- Keep existing functionality:
  - Enable/disable emotional state monitoring
  - Interval configuration (30-60 minutes)
- Add to same section as other monitoring controls for consistency

### Phase 7: Primary Emotional Construct System (Feature Exploration)

#### 7.1 Primary Emotional Construct Concept

- **Purpose**: Allow users to define a primary emotional dimension for focused monitoring
- **Examples**:
  - **Aversion/Relief** (default/main construct)
  - **Paranoia/Anxiety/Fear ↔ Exuberance** (fear-based dimension)
  - **Hyperness/Focus ↔ Distraction** (attention/energy dimension)
  - **Guilt ↔ Pride** (self-evaluation dimension)
  - **Stress ↔ Calm** (activation dimension)
  - Custom user-defined pairs

#### 7.2 Primary Construct Configuration

- **File**: `ui/settings_page.py` or `ui/settings/monitoring_settings.py`
- Add section: "Primary Emotional Construct"
- Radio button or dropdown selection:
  - "Aversion/Relief" (default)
  - "Fear/Anxiety ↔ Exuberance"
  - "Focus ↔ Distraction"
  - "Guilt ↔ Pride"
  - "Stress ↔ Calm"
  - "Custom..." (opens dialog to define custom pair)
- Help text: "Select your primary emotional dimension for focused tracking. This will be emphasized in monitoring and analytics."
- Store: `primary_emotional_construct` (string, default "aversion_relief")

#### 7.3 Custom Construct Builder

- **File**: `ui/settings/monitoring_settings.py` or modal component
- When "Custom..." selected, show dialog:
  - Two text inputs: "Negative pole" (e.g., "Guilt") and "Positive pole" (e.g., "Pride")
  - Optional: Description field
  - Save button creates custom construct
- Store custom constructs in user preferences: `custom_emotional_constructs` (list of dicts)
- Allow multiple custom constructs, select one as primary

#### 7.4 Primary Construct Integration

- **File**: `ui/emotional_state_monitor.py` (modify)
- Highlight primary emotional construct slider(s) visually
- Show primary construct prominently at top of page
- Optional: Show trend graph for primary construct over time

- **File**: `ui/initialize_task.py` and `ui/complete_task.py` (modify)
- Show primary construct emotions more prominently
- Optional: Add quick-select buttons for primary construct values
- Visual emphasis (larger slider, different color, etc.)

- **File**: Analytics/visualization components
- Emphasize primary construct in charts and graphs
- Add dedicated primary construct trend analysis
- Optional: Primary construct dashboard widget

#### 7.5 Feature Testing Framework

- **File**: `ui/settings/monitoring_settings.py` or new experimental section
- Add "Experimental Monitoring Features" section
- Toggle: "Enable experimental features"
- When enabled: Show additional monitoring options
- Allow users to test new constructs/metrics before full release
- Feedback mechanism: "Rate this feature" or "Report issue" buttons

#### 7.6 Additional Monitoring Options (Future Exploration)

- **Potential additions** (to be evaluated):
  - **Energy Level**: Physical energy, mental energy, overall energy
  - **Motivation**: Intrinsic motivation, extrinsic motivation, overall drive
  - **Confidence**: Self-efficacy, task confidence, general confidence
  - **Satisfaction**: Task satisfaction, life satisfaction, progress satisfaction
  - **Time Perception**: Time dilation, time pressure, time awareness
  - **Social Context**: Social pressure, social support, isolation level
  - **Environmental Factors**: Noise level, temperature comfort, lighting
  - **Physical State**: Hunger, fatigue, pain level, comfort

- **Implementation approach**:
  - Start with 2-3 most requested additions
  - Add as experimental features first
  - Gather user feedback
  - Promote to standard features if well-received
  - Allow users to enable/disable each addition individually

## Data Schema Changes

### Instance Data (predicted JSON)

```json
{
  "expected_relief": 50,
  "expected_mental_energy": 60,
  "expected_emotion_values": {"Anxiety": 30, "Excitement": 70},
  ...
}
```

### Instance Data (actual/final JSON)

```json
{
  "final_relief": 65,
  "final_mental_energy": 45,
  "final_emotion_values": {"Anxiety": 20, "Excitement": 80},
  "deviation_notes": {
    "relief": "Task was easier than expected",
    "mental_energy": "Required more focus than anticipated"
  },
  "experience_notes": "Felt accomplished but drained afterward",
  ...
}
```

### New: Emotional State Log

- Table/CSV: `emotional_state_log`
- Columns: timestamp, user_id, emotion_values (JSON), notes (optional)

### User Preferences (monitoring settings)

- Stored in `user_preferences.csv` or database:
- **Emotional Monitoring:**
  - `emotional_monitoring_enabled` (bool, default False) - Set in settings page
  - `emotional_monitoring_interval_minutes` (int, default 45, range 30-60) - Set in settings page
  - `emotional_monitoring_active` (bool, default False) - Toggled on dashboard (only when enabled)
  - `last_emotional_prompt_at` (ISO datetime string, nullable) - Tracked automatically
- **Tracking Preferences (slider visibility):**
  - `track_relief_aversion` (bool, default True)
  - `track_mental_energy` (bool, default True)
  - `track_difficulty` (bool, default True)
  - `track_emotional_load` (bool, default True)
  - `track_physical_load` (bool, default True)
  - `track_task_emotions` (bool, default True)
- **Primary Emotional Construct:**
  - `primary_emotional_construct` (string, default "aversion_relief")
  - `custom_emotional_constructs` (JSON array of dicts: `[{"name": "Guilt/Pride", "negative": "Guilt", "positive": "Pride"}]`)
- **Experimental Features:**
  - `experimental_features_enabled` (bool, default False)
  - `enabled_experimental_features` (JSON array of feature names)

## Files to Modify

1. `ui/complete_task.py` - Rename actual→final, add deviation detection, notes UI
2. `ui/initialize_task.py` - Update emotion labels, expected emotion tracking
3. `backend/instance_manager.py` - Update field names, add deviation tracking
4. `backend/emotion_manager.py` - Add emotional state history methods
5. `backend/user_state.py` - Add monitoring configuration methods (enable/disable, interval, active state)
6. `backend/popup_dispatcher.py` - Add deviation spike trigger
7. `ui/emotional_state_monitor.py` - New file for monitoring page
8. `ui/components/slider_with_notes.py` - New reusable component
9. `ui/settings_page.py` - Add comprehensive monitoring settings section (emotional monitoring, slider visibility, primary construct)
10. `ui/settings/monitoring_settings.py` - New file (optional) for dedicated monitoring settings page
11. `ui/dashboard.py` - Add conditional toggle button (only when enabled in settings), prompt logic, and current state display
12. `backend/user_state.py` - Add tracking preferences and primary construct storage methods
13. Database migration script - Rename actual_ *to final_* columns
14. CSV migration script (if using CSV backend)

## Testing Considerations

- Test deviation detection with various value combinations
- Test popup trigger logic (only on completion, not edit)
- Test emotional state monitoring with different intervals
- Test data migration (actual→final rename)
- Verify backward compatibility with existing data
- Test note persistence and retrieval
- Test emotion state history queries

## Backward Compatibility

- Support reading both "actual_*" and "final_*" field names during transition

- Migrate existing data automatically
- If tracking preferences not set, default to showing all sliders (existing behavior)
- Primary emotional construct defaults to "aversion_relief" if not specified