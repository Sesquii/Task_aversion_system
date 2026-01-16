---
name: Task Management Modes Feature
overview: Implement a configurable "Task Management Modes" system that allows users to choose different tracking approaches (Completionist, Accessibility, Delegator, etc.) based on their workflow needs, starting with Manual Effort Percentage (Option A) as the initial implementation.
todos:
  - id: fix-overcompletion-cap
    content: Remove/increase completion percentage cap in UI (currently suggests 200%, user has done 500%+)
    status: pending
  - id: create-mode-manager
    content: Create task_mode_manager.py for mode configuration and storage
    status: pending
  - id: add-manual-effort-schema
    content: Add manual_effort_percent to actual JSON schema with default 100.0
    status: pending
  - id: implement-manual-effort-ui
    content: Add Manual Effort Mode UI (slider, collapsible section) in complete_task.py
    status: pending
  - id: implement-effective-duration
    content: Add get_effective_duration() helper and integrate into analytics
    status: pending
  - id: create-mode-selection-ui
    content: Create mode selection UI in settings/dashboard
    status: pending
  - id: add-pattern-classification
    content: Add task_pattern field to task templates (Mode 6 foundation)
    status: pending
  - id: implement-pattern-ui
    content: Add pattern selector and pattern-specific fields in create_task.py
    status: pending
  - id: add-simultaneous-tasks
    content: Add simultaneous_tasks array support for Accessibility Mode (Phase 3)
    status: pending
  - id: document-modes
    content: Create user documentation for each mode and when to use them
    status: pending
isProject: false
---

# Task Management Modes Feature

## Overview

Implement a flexible "Task Management Modes" system that allows users to configure how tasks are tracked based on their workflow, procrastination patterns, and emotional tracking needs. This addresses the reality that different users have different pain points and optimization opportunities.

## Core Philosophy Shift

**From**: Single tracking approach for all users

**To**: Configurable modes that adapt to different workflows while maintaining emotional tracking as the foundation

**Implementation Strategy**: Gradual, incremental rollout starting with simplest mode (Manual Effort Percentage) and expanding to more sophisticated modes over time.

## Current State Corrections

### Over-Completion Support

- **Current**: UI suggests 0-200% completion
- **Reality**: System supports up to 500%+ completion (user has done 500% in practice)
- **Action**: Remove or increase completion percentage cap in UI validation
- **Files**: `task_aversion_app/ui/complete_task.py` (line 433-437)

## Task Management Modes

### Mode 1: Standard Mode (Default)

**Current behavior** - No changes needed for existing users

- Standard completion percentage (0-500%+)
- Standard duration tracking
- Over-completion notes (free-form text)
- Focus-based scoring (rewards single-task attention)

### Mode 2: Manual Effort Mode (Option A) - **INITIAL IMPLEMENTATION**

**Target Users**: Users who want to track active vs passive time without complexity

**Features**:

- Manual effort percentage slider (0-100%)
  - Indicates how much of duration was actively spent vs waiting/automated
  - Default: 100% (current behavior)
  - Stored in `actual.manual_effort_percent`
- Effective duration calculation: `effective_duration = duration_minutes * (manual_effort_percent / 100)`
- Analytics integration: Use effective duration for focus-based metrics
- UI: Simple slider in completion form, collapsible section

**Use Cases**:

- Repetitive tasks (sending same prompt every 5 minutes)
- Waiting for AI responses, colleagues, or automated processes
- Tasks with significant loading/waiting time
- Low-effort monitoring tasks

**Implementation Priority**: **HIGH** - Start here as it's simplest and most generally useful

### Mode 3: Accessibility Mode (Option D)

**Target Users**: Users who want structured simultaneous work tracking without complexity

**Features**:

- Manual effort percentage (from Mode 2)
- Simultaneous tasks array (optional)
  - Link to other task instance_ids or note task names
  - Stored in `actual.simultaneous_tasks`
- Enhanced over-completion notes
- Analytics: Adjust focus metrics based on manual effort, but don't penalize simultaneous work

**Use Cases**:

- Edge cases where simultaneous work is valid
- Users who want to document but not deeply analyze simultaneous work

**Implementation Priority**: **MEDIUM** - Build on Mode 2

### Mode 4: Completionist Mode (Option E)

**Target Users**: Users who want granular time breakdown tracking

**Features**:

- Time breakdown tracking: `{active: X, waiting: Y, automated: Z, distracted: W}`
- Sum must equal `duration_minutes`
- UI: Time breakdown form with sliders/bars for each category
- Analytics: Use breakdown for detailed analysis
- Manual effort percent derived from: `active / duration_minutes * 100`

**Use Cases**:

- Detailed productivity analysis
- Users who want maximum granularity
- Research/optimization scenarios

**Implementation Priority**: **LOW** - Most complex, implement after other modes prove useful

### Mode 5: Delegator/Management Mode (Option B)

**Target Users**: Users managing multiple tasks or delegating work

**Features**:

- Task tier system (primary/secondary/tertiary)
- Overlapping tasks linking
- Time overlap validation
- Weighted scoring (primary > secondary > tertiary)
- Analytics: Different scoring for tiered tasks

**Use Cases**:

- Project management scenarios
- Delegation tracking
- Multi-tasking validation

**Implementation Priority**: **LOW** - Specialized use case, implement if demand exists

### Mode 6: Template-Specific Mode (Option C)

**Target Users**: Users with repetitive task patterns

**Features**:

- Task pattern classification: `repetitive`, `low_effort`, `automated`, `standard`
- Template-specific sliders/fields based on pattern
- Iteration tracking for repetitive tasks
- Pattern-specific analytics

**Use Cases**:

- Repetitive task templates (like user's prompt-checking example)
- Automated workflow tracking
- Low-effort task optimization

**Implementation Priority**: **MEDIUM** - Useful general feature, can be implemented alongside Mode 2

## Implementation Plan

### Phase 1: Foundation & Mode 2 (Manual Effort Mode)

#### 1.1 Fix Over-Completion Cap

- **File**: `task_aversion_app/ui/complete_task.py`
- Remove or increase `max` validation on completion percentage (currently suggests 200% limit)
- Update UI text to reflect support for 500%+ completion
- Keep `min=0` validation

#### 1.2 Add Mode Configuration System

- **New File**: `task_aversion_app/backend/task_mode_manager.py`
- Store user's selected mode in user preferences or database
- Default mode: "standard" (current behavior)
- Mode options: `standard`, `manual_effort`, `accessibility`, `completionist`, `delegator`, `template_specific`
- Migration: Existing users default to "standard" mode

#### 1.3 Implement Manual Effort Mode

- **Schema**: Add `manual_effort_percent` to `actual` JSON field
  - Type: Float (0.0-100.0)
  - Default: 100.0 if not specified (backward compatible)
- **UI**: `task_aversion_app/ui/complete_task.py`
  - Add collapsible "Effort Tracking" section (only shown in manual_effort mode)
  - Manual effort slider: 0-100%, default 100%
  - Tooltip: "Percentage of time actively working vs waiting/automated"
  - Warning if < 50%: "Low manual effort may affect focus-based metrics"
- **Analytics**: `task_aversion_app/backend/analytics.py`
  - Add `get_effective_duration(instance)` helper method
  - Use effective duration for focus-based calculations
  - Keep total duration for time-based metrics
  - Document in analytics that manual_effort_percent is optional

#### 1.4 Mode Selection UI

- **File**: `task_aversion_app/ui/dashboard.py` or new settings page
- Add "Task Management Mode" selector
- Show description of each mode
- Allow switching modes (with confirmation if data exists)
- Store in user preferences

### Phase 2: Mode 6 (Template-Specific Patterns)

#### 2.1 Task Pattern Classification

- **Schema**: Add `task_pattern` to task templates
  - Options: `standard`, `repetitive`, `low_effort`, `automated`
  - Default: `standard`
- **UI**: `task_aversion_app/ui/create_task.py`
  - Add "Task Pattern" selector when creating/editing templates
  - Show pattern-specific fields based on selection

#### 2.2 Pattern-Specific Fields

- **Repetitive Pattern**:
  - Iteration count field
  - Average time per iteration
  - Pattern-specific analytics
- **Low Effort Pattern**:
  - Active minutes vs total minutes
  - Effort level slider
- **Automated Pattern**:
  - Automation percentage
  - Manual intervention tracking

### Phase 3: Mode 3 (Accessibility Mode)

#### 3.1 Simultaneous Tasks Tracking

- **Schema**: Add `simultaneous_tasks` array to `actual` JSON
  - Array of objects: `{instance_id: str, task_name: str, overlap_minutes: float}`
- **UI**: `task_aversion_app/ui/complete_task.py`
  - "Add Simultaneous Task" button (only in accessibility mode)
  - Link to other task instances or enter task name
  - Optional overlap time tracking
- **Analytics**: Document simultaneous work but don't penalize

### Phase 4: Mode 4 (Completionist Mode) - Future

#### 4.1 Time Breakdown Schema

- **Schema**: Add `time_breakdown` object to `actual` JSON
  - `{active: float, waiting: float, automated: float, distracted: float}`
  - Validation: Sum must equal `duration_minutes`
- **UI**: Time breakdown form with sliders
- **Analytics**: Detailed breakdown analysis

### Phase 5: Mode 5 (Delegator Mode) - Future

#### 5.1 Task Tier System

- **Schema**: Add `task_tier` and `overlapping_tasks` fields
- **UI**: Tier selector and overlap linking
- **Analytics**: Weighted scoring

## Data Schema Changes

### TaskInstance.actual JSON Extensions

```json
{
  // Existing fields...
  "manual_effort_percent": 100.0,  // 0.0-100.0, default 100.0
  "simultaneous_tasks": [           // Optional, Mode 3+
    {
      "instance_id": "i123",
      "task_name": "Music Performance Data",
      "overlap_minutes": 120.0
    }
  ],
  "time_breakdown": {                // Optional, Mode 4
    "active": 60.0,
    "waiting": 30.0,
    "automated": 10.0,
    "distracted": 0.0
  }
}
```

### Task Template Extensions

```json
{
  // Existing fields...
  "task_pattern": "standard",  // standard, repetitive, low_effort, automated
  "pattern_config": {          // Pattern-specific configuration
    // Repetitive: {iteration_tracking: true, avg_iteration_time: 5.0}
    // Low effort: {effort_level_default: 30}
    // Automated: {automation_percent: 80}
  }
}
```

### User Preferences Extensions

```json
{
  // Existing preferences...
  "task_management_mode": "standard",  // Mode selection
  "mode_settings": {                   // Mode-specific settings
    "manual_effort": {
      "default_effort_percent": 100.0,
      "show_warnings": true
    },
    "completionist": {
      "breakdown_categories": ["active", "waiting", "automated", "distracted"]
    }
  }
}
```

## Analytics Integration

### Effective Duration Calculation

```python
def get_effective_duration(instance, mode='standard'):
    """Calculate effective duration based on mode and manual effort."""
    duration = instance.get('duration_minutes', 0)
    
    if mode == 'standard':
        return duration
    
    actual = instance.get('actual', {})
    manual_effort = actual.get('manual_effort_percent', 100.0)
    
    if mode in ['manual_effort', 'accessibility', 'completionist']:
        return duration * (manual_effort / 100.0)
    
    if mode == 'completionist':
        breakdown = actual.get('time_breakdown', {})
        if breakdown:
            return breakdown.get('active', duration)
    
    return duration
```

### Focus Factor Adjustments

- Use effective duration for focus-based metrics
- Keep total duration for time-based metrics
- Document mode-specific adjustments in analytics

## UI/UX Considerations

### Mode Selection

- Settings page or dashboard widget
- Clear descriptions of each mode
- Preview of what changes in completion form
- Warning when switching modes with existing data

### Completion Form Adaptations

- Show/hide fields based on selected mode
- Collapsible sections for advanced tracking
- Tooltips explaining each field
- Validation based on mode requirements

### Backward Compatibility

- All new fields optional with sensible defaults
- Existing tasks work in "standard" mode
- No breaking changes to existing analytics
- Gradual migration path for users

## Migration Strategy

1. **Phase 1**: Implement Mode 2 (Manual Effort) - Most users can benefit
2. **Phase 2**: Add Mode 6 (Template Patterns) - Useful general feature
3. **Phase 3**: Add Mode 3 (Accessibility) - Builds on Mode 2
4. **Phase 4+**: Add Modes 4 & 5 if demand exists

## Testing Considerations

- Test mode switching with existing data
- Verify backward compatibility (standard mode = current behavior)
- Test analytics with different modes
- Validate data integrity across mode transitions
- Test edge cases (500%+ completion, extreme manual effort values)

## Documentation

- User guide for each mode
- When to use each mode
- Migration guide for switching modes
- Analytics impact documentation
- Examples of each mode in practice