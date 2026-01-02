# Commit Message - PLANNING DOCUMENT

**[PLANNING COMMIT - NO CODE CHANGES]**

## Planning Intent

This commit adds a comprehensive planning document for enhancing the slider value system and emotion tracking infrastructure. This is a **planning document only** - no code changes have been made. The plan outlines a multi-phase approach to improve clarity, add deviation tracking, implement hybrid emotion monitoring, and provide customizable tracking controls.

## Plan Overview

The plan addresses several key areas:

1. **Terminology Clarity**: Rename "actual" to "final" throughout the system for better semantic clarity
2. **Deviation Tracking**: Detect and capture explanations when values deviate significantly from expectations (20+ points)
3. **Hybrid Emotion System**: Separate global emotional state monitoring from task-specific emotional changes
4. **Comprehensive Monitoring Settings**: Allow users to enable/disable specific sliders and tracking categories
5. **Primary Emotional Construct**: System for focusing on a primary emotional dimension (e.g., Aversion/Relief, Fear/Exuberance, etc.)

## Plan Structure

### Phase 1: Terminology and Data Model Updates
- Rename "actual" → "final" throughout codebase
- Update UI labels and maintain backward compatibility
- Data migration scripts for database and CSV backends

### Phase 2: Deviation Detection and Notes System
- Automatic detection of 20+ point deviations
- Reusable slider component with note icons (only shown on deviations)
- Popup prompts asking for explanations when significant deviations occur
- Deviation notes stored per slider in instance data

### Phase 3: Emotional Context/Experience Notes
- Optional "experience notes" field separate from task completion notes
- Captures how completing a task made the user feel
- Distinct from slider-specific deviation notes

### Phase 4: Hybrid Emotion Tracking System
- **Global Emotional State Monitoring**:
  - Standalone monitoring page (`/emotional-state`)
  - Periodic prompts at configurable intervals (30-60 minutes)
  - Toggleable on dashboard (only when enabled in settings)
  - Stores time-series emotional state data
- **Task-Specific Emotions**:
  - Expected emotions at initialization
  - Final emotions at completion
  - Comparison and change tracking

### Phase 5: UI/UX Improvements
- Visual indicators for deviations (colored borders, expected value markers)
- Dashboard integration for emotional monitoring controls
- Navigation improvements

### Phase 6: Comprehensive Monitoring Settings
- **Unified Settings Page**: All monitoring controls in one place
- **Slider Visibility Controls**:
  - Relief/Aversion (combined toggle)
  - Loads/Stress (combined with sub-options for mental energy, difficulty, emotional load, physical load)
  - Task-based emotional monitoring (separate toggle)
- **Conditional Rendering**: Initialize and complete pages only show enabled sliders
- **Backend Storage**: User preferences for tracking configuration

### Phase 7: Primary Emotional Construct System (Feature Exploration)
- **Primary Construct Selection**:
  - Predefined options: Aversion/Relief (default), Fear/Anxiety ↔ Exuberance, Focus ↔ Distraction, Guilt ↔ Pride, Stress ↔ Calm
  - Custom construct builder for user-defined emotional pairs
- **Integration**: Visual emphasis in monitoring and task pages
- **Analytics Focus**: Primary construct trends in analytics
- **Experimental Features Framework**: Toggle for testing new monitoring features

## Key Features Planned

### Deviation Tracking
- Automatic detection when final values differ from expected by 20+ points
- Note icons appear only on sliders with deviations
- Popup prompts for immediate feedback
- Notes stored per slider for later review

### Emotional Monitoring
- **Settings Configuration**: Enable/disable and interval (30-60 min) in settings page
- **Dashboard Control**: Quick toggle for active/paused state (only visible when enabled)
- **Smart Prompting**: Only prompts when enabled in settings AND active on dashboard AND interval elapsed
- **Time-Series Tracking**: Historical emotional state data separate from task-specific emotions

### Customizable Tracking
- Users can enable/disable entire categories of sliders
- Relief/Aversion, Loads/Stress, and Task Emotions can be toggled independently
- Initialize and complete pages adapt to show only enabled sliders
- Maintains backward compatibility (defaults to all enabled)

### Primary Emotional Construct
- Focus on a single emotional dimension for enhanced tracking
- Predefined constructs or custom user-defined pairs
- Visual emphasis and analytics prioritization
- Framework for future emotional dimension additions

## Data Schema Changes Planned

### Instance Data (predicted JSON)
- `expected_emotion_values` - Task-specific expected emotions
- All existing expected fields maintained

### Instance Data (final JSON - renamed from actual)
- `final_*` fields (renamed from `actual_*`)
- `final_emotion_values` - Task-specific final emotions
- `deviation_notes` - Per-slider deviation explanations
- `experience_notes` - Overall emotional experience description

### New: Emotional State Log
- Time-series table/CSV for global emotional state
- Fields: timestamp, user_id, emotion_values (JSON), notes (optional)

### User Preferences (monitoring settings)
- Emotional monitoring: enabled, interval, active state
- Tracking preferences: per-slider visibility toggles
- Primary emotional construct: selected construct and custom constructs
- Experimental features: enable/disable flags

## Files to Be Modified (When Implemented)

1. `ui/complete_task.py` - Rename actual→final, add deviation detection, notes UI
2. `ui/initialize_task.py` - Update emotion labels, expected emotion tracking, conditional slider rendering
3. `backend/instance_manager.py` - Update field names, add deviation tracking
4. `backend/emotion_manager.py` - Add emotional state history methods
5. `backend/user_state.py` - Add monitoring configuration, tracking preferences, primary construct storage
6. `backend/popup_dispatcher.py` - Add deviation spike trigger
7. `ui/emotional_state_monitor.py` - New file for monitoring page
8. `ui/components/slider_with_notes.py` - New reusable component
9. `ui/settings_page.py` - Add comprehensive monitoring settings section
10. `ui/settings/monitoring_settings.py` - New file (optional) for dedicated settings page
11. `ui/dashboard.py` - Add conditional toggle button, prompt logic, current state display
12. Database migration script - Rename actual_* to final_* columns
13. CSV migration script (if using CSV backend)

## Implementation Approach

- **Phased Implementation**: 7 phases, can be implemented incrementally
- **Backward Compatibility**: All changes maintain compatibility with existing data
- **User Control**: Extensive customization options for tracking preferences
- **Progressive Enhancement**: New features can be enabled/disabled individually

## Testing Considerations (For Implementation)

- Deviation detection with various value combinations
- Popup trigger logic (only on completion, not edit)
- Emotional state monitoring with different intervals
- Data migration (actual→final rename)
- Backward compatibility with existing data
- Note persistence and retrieval
- Emotion state history queries
- Conditional slider rendering based on preferences
- Primary construct selection and custom construct creation

## Future Exploration Areas

- Additional monitoring options: Energy level, Motivation, Confidence, Satisfaction, Time perception, Social context, Environmental factors, Physical state
- Experimental features framework for testing new constructs
- Analytics enhancements for primary construct trends
- Advanced deviation analysis and pattern detection

## Notes

- This is a **planning document only** - no code has been modified
- Implementation can proceed phase by phase
- Each phase can be tested independently
- User preferences will default to showing all sliders (existing behavior) if not configured
- All changes maintain backward compatibility

---

**Status**: Planning Complete - Ready for Implementation Review
