---
name: Goal Tracking System EXPERIMENTAL
overview: Design and implement an experimental goal tracking system for productivity goals, supporting multiple goal types (hours, counts, streaks, skills) at all levels (global, category, task-specific). This is an exploratory/brainstorming plan to establish the foundation for goal tracking.
todos:
  - id: goal-manager-backend
    content: Create GoalManager class in backend/goal_manager.py with dual backend support (CSV + database), supporting CRUD operations for goals
    status: pending
  - id: goal-tracker-engine
    content: Create GoalTracker class in backend/goal_tracker.py to calculate progress for different goal types (time, count, streak, skill, composite)
    status: pending
    dependencies:
      - goal-manager-backend
  - id: goal-data-model
    content: "Define Goal data model (dataclass/schema) with fields: goal_id, user_id, goal_type, scope, scope_value, target_value, current_value, period, start_date, end_date, status, metadata"
    status: pending
  - id: time-based-goals
    content: Implement time-based goals (daily, weekly, monthly hours) extending existing ProductivityTracker functionality
    status: pending
    dependencies:
      - goal-manager-backend
      - goal-tracker-engine
  - id: count-based-goals
    content: Implement count-based goals (task completion counts by category, task template, period)
    status: pending
    dependencies:
      - goal-manager-backend
      - goal-tracker-engine
  - id: goals-ui-page
    content: Create experimental goals UI page at /experimental/goals with goal list, creation wizard, and progress visualization
    status: pending
    dependencies:
      - goal-manager-backend
  - id: goal-progress-calculation
    content: Implement automatic goal progress calculation and status updates (completed, on_track, at_risk, failed)
    status: pending
    dependencies:
      - goal-tracker-engine
  - id: streak-goals
    content: Implement streak goal tracking (consecutive days/weeks of goal achievement)
    status: pending
    dependencies:
      - goal-manager-backend
      - goal-tracker-engine
  - id: skill-goals
    content: Implement skill improvement goals tracking skills_improved attribute from task instances
    status: pending
    dependencies:
      - goal-manager-backend
      - goal-tracker-engine
  - id: goal-history-tracking
    content: Add goal progress history tracking (daily/weekly snapshots) for trend analysis
    status: pending
    dependencies:
      - goal-manager-backend
  - id: dashboard-goal-widget
    content: Add goal summary widget to main dashboard showing active goals and progress
    status: pending
    dependencies:
      - goals-ui-page
  - id: database-goal-model
    content: Add Goal model to database.py for database backend support (optional, if using database)
    status: pending
    dependencies:
      - goal-data-model
---

# Goal Tracking System EXPERIMENTAL

## Overview

This plan establishes an experimental goal tracking system focused on productivity goals. The system will support multiple goal types (weekly hours, daily hours, task completion counts, streaks, skill improvement) at multiple scopes (global, category-based, task-specific). This is an exploratory implementation to test concepts and gather feedback before full integration.

## Current State Analysis

### Existing Goal Infrastructure

- **ProductivityTracker** (`task_aversion_app/backend/productivity_tracker.py`): Tracks weekly productivity hours and compares to goals
- **UserStateManager** (`task_aversion_app/backend/user_state.py`): Stores productivity goal settings (goal_hours_per_week, starting_hours_per_week)
- **Experimental UI** (`task_aversion_app/ui/productivity_goals_experimental.py`): Basic UI for weekly hours goal tracking
- **Historical Tracking**: Weekly snapshots stored in user preferences JSON

### Gaps Identified

1. Limited to weekly hours goals only
2. No category-specific or task-specific goals
3. No streak tracking or milestone goals
4. No skill improvement goals
5. No goal templates or presets
6. No goal progress visualization beyond basic charts
7. No goal achievement notifications or celebrations
8. No goal adjustment recommendations

## Architecture Design

### Goal Types to Explore

1. **Time-Based Goals**

   - Weekly productive hours (existing)
   - Daily productive hours
   - Monthly productive hours
   - Time per category (Work, Self Care, etc.)
   - Time per task template

2. **Count-Based Goals**

   - Tasks completed per week/day/month
   - Tasks completed per category
   - Specific task template completion count
   - Cancellation rate goals (stay below threshold)

3. **Streak Goals**

   - Daily completion streaks
   - Weekly goal achievement streaks
   - Category-specific streaks
   - Task-specific streaks

4. **Quality/Performance Goals**

   - Average productivity score target
   - Average relief score target
   - Stress efficiency goals
   - Behavioral score targets

5. **Skill Improvement Goals**

   - Practice specific skills X times per week
   - Improve skill proficiency levels
   - Track skills_improved attribute usage

6. **Composite Goals**

   - Multiple conditions (e.g., "Complete 5 Work tasks AND 3 Self Care tasks per week")
   - Weighted combinations of different goal types

### Goal Scope Levels

1. **Global Goals**: System-wide targets (e.g., "40 hours/week total productivity")
2. **Category Goals**: Per-category targets (e.g., "20 hours/week Work, 10 hours/week Self Care")
3. **Task-Specific Goals**: Per-task-template targets (e.g., "Complete 'Exercise' task 3x/week")

### Data Model Design

#### Goal Schema (Proposed)

```python
@dataclass
class Goal:
    goal_id: str  # Format: g{timestamp}
    user_id: str
    goal_type: str  # 'weekly_hours', 'daily_hours', 'task_count', 'streak', 'skill', 'composite'
    scope: str  # 'global', 'category', 'task_specific'
    scope_value: Optional[str]  # Category name or task_id if scope is category/task_specific
    target_value: float  # Target number (hours, count, etc.)
    current_value: float  # Current progress
    period: str  # 'daily', 'weekly', 'monthly', 'all_time'
    start_date: date
    end_date: Optional[date]  # None for ongoing goals
    status: str  # 'active', 'paused', 'completed', 'failed'
    created_at: datetime
    updated_at: datetime
    metadata: Dict[str, Any]  # Additional goal-specific data
```

#### Database Schema (if using database)

```sql
CREATE TABLE goals (
    goal_id VARCHAR PRIMARY KEY,
    user_id VARCHAR NOT NULL,
    goal_type VARCHAR NOT NULL,
    scope VARCHAR NOT NULL,
    scope_value VARCHAR,
    target_value FLOAT NOT NULL,
    current_value FLOAT DEFAULT 0.0,
    period VARCHAR NOT NULL,
    start_date DATE NOT NULL,
    end_date DATE,
    status VARCHAR DEFAULT 'active',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    metadata JSON
);
```

#### CSV Storage (for CSV backend compatibility)

Store in `data/goals.csv` with columns matching Goal schema fields.

## Implementation Plan

### Phase 1: Core Goal Management Backend

#### 1.1 Create Goal Manager

**File**: `task_aversion_app/backend/goal_manager.py`

- Create `GoalManager` class following dual backend pattern (CSV + database)
- Methods:
  - `create_goal(user_id, goal_type, scope, target_value, ...)` - Create new goal
  - `get_goals(user_id, status='active')` - Get user's goals
  - `get_goal(goal_id)` - Get specific goal
  - `update_goal(goal_id, **updates)` - Update goal properties
  - `delete_goal(goal_id)` - Soft delete (set status='deleted')
  - `calculate_progress(goal_id)` - Calculate current progress for a goal
  - `check_goal_status(goal_id)` - Check if goal is met/failed

#### 1.2 Goal Progress Calculation Engine

**File**: `task_aversion_app/backend/goal_tracker.py`

- Create `GoalTracker` class to calculate progress for different goal types
- Methods:
  - `calculate_time_based_progress(goal, start_date, end_date)` - For hours goals
  - `calculate_count_based_progress(goal, start_date, end_date)` - For task count goals
  - `calculate_streak_progress(goal)` - For streak goals
  - `calculate_skill_progress(goal, start_date, end_date)` - For skill goals
  - `calculate_composite_progress(goal, start_date, end_date)` - For composite goals
- Integrate with:
  - `ProductivityTracker` for hours data
  - `InstanceManager` for task completion data
  - `TaskManager` for task/category data
  - `Analytics` for score-based goals

#### 1.3 Goal Status Evaluation

- Automatic status updates:
  - `completed` - When target_value is reached
  - `on_track` - When progress is >= 85% of target
  - `at_risk` - When progress is < 85% and time remaining is limited
  - `failed` - When period ended and target not met
- Status calculation based on:
  - Current progress vs target
  - Time remaining in period
  - Historical completion rates

### Phase 2: Goal Types Implementation

#### 2.1 Time-Based Goals

- Extend existing weekly hours tracking
- Add daily and monthly hours goals
- Support category-specific hours (e.g., "20 hours/week Work")
- Support task-specific hours (e.g., "5 hours/week on 'Exercise' task")

#### 2.2 Count-Based Goals

- Track task completion counts from `InstanceManager`
- Filter by:
  - Category (Work, Self Care, Play)
  - Task template (specific task_id)
  - Date range (daily, weekly, monthly)
- Examples:
  - "Complete 10 Work tasks per week"
  - "Complete 'Exercise' task 3x per week"

#### 2.3 Streak Goals

- Track consecutive days/weeks of goal achievement
- Store streak data in goal metadata
- Calculate current streak and longest streak
- Examples:
  - "Maintain 7-day completion streak"
  - "Achieve weekly goal 4 weeks in a row"

#### 2.4 Skill Improvement Goals

- Track `skills_improved` attribute from task instances
- Count occurrences of specific skills
- Examples:
  - "Practice 'Python' skill 5 times per week"
  - "Improve 'Communication' skill proficiency"

#### 2.5 Composite Goals

- Support multiple conditions with AND/OR logic
- Weighted scoring for mixed goal types
- Examples:
  - "Complete 5 Work tasks AND 3 Self Care tasks per week"
  - "40 hours/week total AND average productivity score > 50"

### Phase 3: User Interface

#### 3.1 Goal Management Page

**File**: `task_aversion_app/ui/goals_experimental.py`

- Route: `/experimental/goals`
- Features:
  - List all goals (active, completed, paused)
  - Create new goal wizard
  - Edit/delete goals
  - Goal progress visualization
  - Goal status indicators

#### 3.2 Goal Creation Wizard

- Step 1: Select goal type (time, count, streak, skill, composite)
- Step 2: Select scope (global, category, task-specific)
- Step 3: Set target value and period
- Step 4: Set start/end dates (optional)
- Step 5: Review and confirm

#### 3.3 Goal Progress Dashboard

- Progress bars for each goal
- Visual indicators (on track, at risk, completed)
- Historical progress charts (last 4 weeks, last 3 months)
- Comparison to previous periods
- Achievement celebrations (when goals met)

#### 3.4 Goal Integration in Dashboard

- Add goal summary widget to main dashboard
- Show active goals and current progress
- Quick links to goal management page
- Notifications for goal achievements

### Phase 4: Data Storage

#### 4.1 CSV Backend (Default)

- Store goals in `data/goals.csv`
- Columns: goal_id, user_id, goal_type, scope, scope_value, target_value, current_value, period, start_date, end_date, status, created_at, updated_at, metadata
- Use JSON string for metadata column

#### 4.2 Database Backend (Optional)

- Create `Goal` model in `backend/database.py`
- Add migration script for goals table
- Support dual backend pattern (CSV fallback)

#### 4.3 Goal History Tracking

- Store goal progress snapshots (daily/weekly)
- Track goal achievement history
- Store in `data/goal_history.csv` or `goal_history` table
- Enable historical analysis and trends

### Phase 5: Integration Points

#### 5.1 Integration with ProductivityTracker

- Extend `ProductivityTracker` to support goal-aware calculations
- Add methods to check goal progress when calculating weekly hours
- Provide goal-based recommendations

#### 5.2 Integration with Analytics

- Add goal achievement metrics to analytics dashboard
- Show goal progress in analytics visualizations
- Track goal completion rates over time

#### 5.3 Integration with Task Recommendations

- Consider active goals when recommending tasks
- Prioritize tasks that contribute to goal progress
- Example: If user has "Complete 5 Work tasks/week" goal, prioritize Work tasks

### Phase 6: Advanced Features (Future Exploration)

#### 6.1 Goal Templates

- Pre-defined goal templates for common scenarios
- Quick goal creation from templates
- Community-shared goal templates (future)

#### 6.2 Goal Recommendations

- Suggest goals based on historical data
- Recommend goal adjustments based on performance
- Smart goal setting (auto-adjust targets based on past performance)

#### 6.3 Goal Notifications

- Notifications when goals are at risk
- Celebrations when goals are achieved
- Weekly goal progress summaries

#### 6.4 Goal Analytics

- Goal completion rate analysis
- Most effective goal types
- Goal difficulty calibration
- Goal abandonment patterns

## File Structure

```
task_aversion_app/
├── backend/
│   ├── goal_manager.py          # NEW: Goal CRUD operations
│   ├── goal_tracker.py          # NEW: Goal progress calculation
│   ├── productivity_tracker.py # EXISTING: Extend for goal integration
│   └── database.py              # EXISTING: Add Goal model if using DB
├── ui/
│   ├── goals_experimental.py    # NEW: Goal management UI
│   └── dashboard.py             # EXISTING: Add goal widget
└── data/
    ├── goals.csv                # NEW: Goals storage (CSV backend)
    └── goal_history.csv         # NEW: Goal progress history
```

## Experimental Considerations

### What Makes This Experimental

1. **Exploratory Design**: Test different goal types and see what works
2. **User Feedback Loop**: Gather feedback before full integration
3. **Flexible Schema**: Metadata field allows testing new goal types without schema changes
4. **Optional Integration**: Goals don't break existing functionality if disabled
5. **Iterative Refinement**: Plan to refine based on usage patterns

### Success Metrics

- Number of goals created by users
- Goal completion rates
- Most popular goal types
- User engagement with goal features
- Integration effectiveness (do goals improve productivity?)

### Risk Mitigation

- Keep goals separate from core task tracking (no breaking changes)
- Use experimental route prefix (`/experimental/goals`)
- Store goals in separate data files (easy to remove if needed)
- Provide clear "experimental" labeling in UI

## Implementation Order

1. **Phase 1**: Core backend (GoalManager, GoalTracker) - Foundation
2. **Phase 2**: Time-based goals first (extends existing system)
3. **Phase 3**: Basic UI for goal management
4. **Phase 4**: Count-based goals (most straightforward after time-based)
5. **Phase 5**: Streak goals (requires history tracking)
6. **Phase 6**: Skill and composite goals (more complex)
7. **Phase 7**: Advanced features (notifications, recommendations)

## Questions for Brainstorming Session

1. Should goals have difficulty levels (easy, medium, hard)?
2. Should goals support "stretch goals" (bonus targets beyond main goal)?
3. Should goals be shareable/template-based?
4. How should failed goals be handled? (Auto-adjust? Reset? Archive?)
5. Should goals support "habits" (daily recurring goals)?
6. Should goals integrate with the composite score system?
7. Should goals have dependencies (e.g., "Complete Goal A before Goal B")?
8. How should goal progress be calculated for partial periods (e.g., mid-week)?

## Next Steps After Plan Approval

1. Start with Phase 1 (GoalManager backend)
2. Create basic goal data model
3. Implement time-based goals (extend existing weekly hours)
4. Build minimal UI for goal creation and viewing
5. Test with real usage data
6. Iterate based on feedback