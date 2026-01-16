---
name: Repetitive Task and Simultaneous Work Tracking Analysis
overview: Analyze the existing codebase to understand current task tracking mechanisms and explore options for tracking repetitive/low-effort tasks and simultaneous work with manual effort percentage, while maintaining alignment with the emotional tracking/aversion system design intent.
todos:
  - id: analyze-overcompletion
    content: Review existing over-completion note usage patterns in codebase and identify current use cases
    status: pending
  - id: analyze-duration-tracking
    content: Examine duration_minutes calculation logic and identify where waiting/automated time might be embedded
    status: pending
  - id: review-analytics-formulas
    content: Review productivity score, grit score, and focus factor calculations to understand how simultaneous work might conflict
    status: pending
  - id: explore-option-a
    content: Document Option A (Manual Effort Percentage) implementation details and trade-offs
    status: pending
  - id: explore-option-b
    content: Document Option B (Tiered Task System) implementation details and trade-offs
    status: pending
  - id: explore-option-c
    content: Document Option C (Task Pattern Classification) implementation details and trade-offs
    status: pending
  - id: explore-option-d
    content: Document Option D (Enhanced Over-Completion) implementation details - RECOMMENDED
    status: pending
  - id: explore-option-e
    content: Document Option E (Time Breakdown Tracking) implementation details and trade-offs
    status: pending
  - id: create-discussion-doc
    content: Create discussion document with all options, pros/cons, and recommended approach for user review
    status: pending
isProject: false
---

# Repetitive Task and Simultaneous Work Tracking Analysis

## Current State Analysis

### Existing Tracking Mechanisms

1. **Completion Percentage System** (`task_aversion_app/ui/complete_task.py`)

- Supports 0-200% completion (over-completion)
- Over-completion notes field exists for describing extra work
- Currently used for: "If you completed more than 100%, describe what extra work you did..."

2. **Duration Tracking** (`task_aversion_app/backend/instance_manager.py`)

- `duration_minutes` field tracks total time spent
- `time_actual_minutes` stored in `actual` JSON
- `time_spent_before_pause` tracks time across pause/resume cycles
- Calculated from `started_at` to `completed_at` timestamps

3. **Task Schema** (`task_aversion_app/backend/task_schema.py`, `task_aversion_app/backend/database.py`)

- `actual` JSON field stores flexible completion data
- `predicted` JSON field stores initialization estimates
- No existing fields for manual effort percentage or simultaneous task tracking

4. **Analytics Integration** (`task_aversion_app/backend/analytics.py`)

- Productivity score uses `completion_pct` as base score
- Duration used in efficiency calculations
- No current adjustment for manual vs automated effort

### Design Philosophy

- **Primary Focus**: Emotional tracking and task aversion measurement
- **Current Approach**: Most metrics reward focused attention (e.g., focus factor in grit score)
- **Edge Cases**: Over-completion notes allow documenting simultaneous work but don't affect scoring

## Analysis Tasks

### Phase 1: Codebase Analysis

1. **Review Over-Completion Usage Patterns**

- Search for instances where `over_completion_note` is used
- Analyze patterns in existing data (if accessible)
- Document current use cases

2. **Examine Duration vs Active Time Patterns**

- Review how `duration_minutes` is calculated
- Identify where waiting/automated time might be embedded
- Check if pause/resume logic captures active vs passive time

3. **Analyze Task Type Classifications**

- Review `task_type` field usage (Work, Self care, etc.)
- Check if repetitive tasks are identifiable
- Examine task templates for patterns

4. **Review Analytics Formulas**

- Examine productivity score calculations
- Check focus factor and attention-based metrics
- Identify where simultaneous work might conflict with current scoring

### Phase 2: Option Exploration

#### Option A: Manual Effort Percentage (Simple)

**Concept**: Add a single "manual effort percentage" field (0-100%) indicating how much of the duration was actively spent vs waiting/automated.

**Implementation**:

- Add `manual_effort_percent` to `actual` JSON (or as separate field)
- UI: Slider in completion form (defaults to 100%)
- Analytics: Adjust duration-based calculations: `effective_duration = duration_minutes * (manual_effort_percent / 100)`
- Use cases: Repetitive tasks, waiting for AI/colleagues, automated processes

**Pros**:

- Simple, single metric
- Flexible for various scenarios
- Minimal UI changes
- Doesn't require task classification

**Cons**:

- Doesn't capture what was done simultaneously
- May not align with emotional tracking focus
- Could be misused to inflate productivity scores

#### Option B: Tiered Task System (Primary/Secondary/Tertiary)

**Concept**: Allow marking tasks as primary, secondary, or tertiary focus levels during overlapping time periods.

**Implementation**:

- Add `task_tier` field to task instances (primary/secondary/tertiary)
- Add `overlapping_tasks` field linking to other instance_ids
- UI: Task tier selector + "Add overlapping task" button
- Analytics: Weight primary tasks more heavily, secondary/tertiary less
- Validation: Only allow tiered marking if time periods overlap

**Pros**:

- Explicitly captures simultaneous work
- Can track what was done together
- More structured than free-form notes

**Cons**:

- More complex UI and data model
- Requires time overlap validation
- May encourage task splitting (conflicts with focus philosophy)
- Leans toward productivity tooling vs emotional tracking

#### Option C: Task Pattern Classification (Repetitive/Low-Effort)

**Concept**: Classify tasks as "repetitive" or "low-effort" patterns, then apply special tracking rules.

**Implementation**:

- Add `task_pattern` field to task templates: `repetitive`, `low_effort`, `automated`, `standard`
- For repetitive tasks: Track iteration count, average time per iteration
- For low-effort: Track "active minutes" separately from "total minutes"
- Analytics: Different scoring for pattern types

**Pros**:

- Captures the specific use case (repetitive prompts)
- Can track iteration patterns
- Maintains focus on task characteristics

**Cons**:

- Requires task classification upfront
- May not handle ad-hoc simultaneous work
- Adds complexity to task creation

#### Option D: Enhanced Over-Completion Notes (Hybrid)

**Concept**: Keep over-completion notes but add structured fields for simultaneous work tracking.

**Implementation**:

- Add `simultaneous_tasks` JSON array in `actual` field
- Add `manual_effort_percent` field
- Keep `over_completion_note` for free-form description
- Analytics: Use manual_effort_percent for duration adjustments, but don't change base scoring
- UI: Collapsible section "Simultaneous Work" (optional, hidden by default)

**Pros**:

- Minimal disruption to existing system
- Optional (doesn't require all users to use it)
- Maintains emotional tracking focus
- Structured enough for analytics, flexible enough for edge cases

**Cons**:

- Still requires some UI changes
- May not be discoverable if hidden

#### Option E: Time Breakdown Tracking

**Concept**: Track time spent in different activity states: active, waiting, automated, distracted.

**Implementation**:

- Add `time_breakdown` JSON object: `{active: X, waiting: Y, automated: Z, distracted: W}`
- Sum must equal `duration_minutes`
- UI: Time breakdown form with sliders/bars
- Analytics: Use `active` time for focus-based metrics, total time for duration-based

**Pros**:

- Most granular tracking
- Captures all scenarios
- Can derive manual_effort_percent from breakdown

**Cons**:

- Most complex UI
- May be too detailed for most users
- Requires more input effort

## Recommended Approach: Option D (Enhanced Over-Completion)

**Rationale**:

- Aligns with existing over-completion pattern
- Minimal changes to core system
- Optional usage (doesn't force all tasks to use it)
- Maintains emotional tracking focus while allowing edge cases
- Can be implemented incrementally

**Implementation Steps**:

1. **Schema Extension**

- Add `manual_effort_percent` to `actual` JSON (default: 100 if not specified)
- Add `simultaneous_tasks` array to `actual` JSON (optional)
- Keep `over_completion_note` for context

2. **UI Enhancement** (`task_aversion_app/ui/complete_task.py`)

- Add collapsible "Simultaneous Work & Effort Tracking" section
- Manual effort slider (0-100%, default 100%)
- Optional "Add simultaneous task" field (instance_id or task name)
- Show warning if manual_effort_percent < 50%: "Low manual effort may affect focus-based metrics"

3. **Analytics Integration** (`task_aversion_app/backend/analytics.py`)

- Add `get_effective_duration()` helper: `duration * (manual_effort_percent / 100)`
- Use effective duration for focus-based calculations
- Keep total duration for time-based metrics
- Document in analytics that manual_effort_percent is optional

4. **Documentation**

- Update task completion guide
- Explain when to use manual effort tracking
- Clarify that this is for edge cases, not general productivity optimization

## Questions for Discussion

1. **Scope**: Should this apply to all tasks or only specific task types?
2. **Scoring Impact**: Should manual_effort_percent affect productivity/grit scores, or just be informational?
3. **Default Behavior**: Should manual_effort_percent default to 100% (current behavior) or be required input?
4. **Simultaneous Task Linking**: Should we link to other task instances, or just note them in text?
5. **Repetitive Task Detection**: Should we add automatic detection for repetitive patterns (same task completed multiple times in short period)?

## Files to Review

- `task_aversion_app/ui/complete_task.py` - Completion form UI
- `task_aversion_app/backend/instance_manager.py` - Task instance data management
- `task_aversion_app/backend/task_schema.py` - Task attribute definitions
- `task_aversion_app/backend/database.py` - Database schema
- `task_aversion_app/backend/analytics.py` - Scoring formulas
- `task_aversion_app/docs/` - Existing documentation on scoring systems