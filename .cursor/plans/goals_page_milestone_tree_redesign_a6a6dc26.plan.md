---
name: Goals Page Milestone Tree Redesign
overview: Redesign the goals page with a collapsible tree structure for milestones, tasks, and instances. Add milestone-to-instance assignment, instance notes, and a 4-column layout with task editing, initialization, and template management.
todos: []
isProject: false
---

# Goals Page Milestone Tree Redesign

## Overview

Transform the goals page from a simple milestone list into a comprehensive task management interface with:

- Collapsible tree navigation (similar to IDE file explorer)
- 4-column layout for task viewing and editing
- Milestone assignment system (global, template, and job-based)
- Instance-specific notes tracking
- Compact visual design matching dashboard's recently completed tasks

## Architecture

### Data Model Changes

```
milestones (new table)
  ├─ milestone_id (PK)
  ├─ name, description
  ├─ scope ('global', 'template', 'job')
  ├─ scope_id (template_id or job_id, null for global)
  ├─ status ('not_started', 'in_progress', 'completed')
  ├─ notes, created_at, updated_at
  └─ user_id (for future multi-user support)

task_instances (modified)
  ├─ milestone_id (FK, nullable) - single milestone assignment
  └─ instance_notes (JSON) - {"initialization": "...", "pauses": [...], "completion": "..."}
```

### Tree Structure

```
Global Milestones (if any)
  └─ [Global Milestone Nodes]
      └─ [Assigned Instances]

Task Type (Work, Self care, Play)
  └─ Job (if jobs system exists)
      └─ Job Milestones
          └─ [Assigned Instances]
      └─ Task Templates
          └─ Template Milestones
              └─ [Assigned Instances]
  └─ Task Templates (if no jobs)
      └─ Template Milestones
          └─ [Assigned Instances]
```

## Implementation Plan

### Phase 1: Database Schema Updates

**File: `task_aversion_app/backend/database.py`**

1. Add `Milestone` SQLAlchemy model:
   ```python
   class Milestone(Base):
       __tablename__ = 'milestones'
       milestone_id = Column(String, primary_key=True)
       name = Column(String, nullable=False)
       description = Column(Text, default='')
       scope = Column(String, nullable=False)  # 'global', 'template', 'job'
       scope_id = Column(String, nullable=True)  # task_id or job_id
       status = Column(String, default='not_started')
       notes = Column(Text, default='')
       user_id = Column(String, default='default')
       created_at = Column(DateTime, default=datetime.utcnow)
       updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
   ```

2. Modify `TaskInstance` model:

   - Add `milestone_id = Column(String, ForeignKey('milestones.milestone_id'), nullable=True)`
   - Add `instance_notes = Column(JSON, default=dict)` for structured notes

3. Update `init_db()` to create new table

**File: `task_aversion_app/SQLite_migration/XXX_add_milestones.py`** (new migration)

- Create `milestones` table
- Add `milestone_id` and `instance_notes` columns to `task_instances`
- Migrate existing 6 hardcoded milestones from `goals_page.py` to table as template-specific milestones
  - Find or create "Task Aversion System" template
  - Create 6 milestones with `scope='template'`, `scope_id=task_id`
- Update existing milestone status/notes from `user_state` to new table

### Phase 2: Backend Managers

**File: `task_aversion_app/backend/milestone_manager.py`** (new)

Create `MilestoneManager` class with dual backend support (database/CSV):

- `create_milestone(name, description, scope, scope_id=None, user_id='default')`
- `get_milestone(milestone_id)`
- `get_milestones_by_scope(scope, scope_id=None, user_id='default')` - get all global, template, or job milestones
- `update_milestone(milestone_id, **kwargs)`
- `delete_milestone(milestone_id)`
- `assign_instance_to_milestone(instance_id, milestone_id)`
- `get_instances_for_milestone(milestone_id)`
- `get_milestone_progress(milestone_id)` - count assigned/completed instances

**File: `task_aversion_app/backend/instance_manager.py`**

1. Update `create_instance()` to support `milestone_id` parameter
2. Add `update_instance_notes(instance_id, note_type, note_text)` method:

   - `note_type`: 'initialization', 'pause', 'completion'
   - For 'pause': append to `instance_notes['pauses']` array
   - For others: set `instance_notes[note_type]`

3. Add `get_instance_notes(instance_id)` method
4. Update `assign_milestone(instance_id, milestone_id)` method

**File: `task_aversion_app/backend/user_state.py`**

- Keep existing milestone methods for backward compatibility during migration
- Add deprecation warnings
- Eventually remove after migration complete

### Phase 3: UI - Goals Page Redesign

**File: `task_aversion_app/ui/goals_page.py`** (major rewrite)

#### Layout Structure

```
┌─────────────────────────────────────────────────────────────────┐
│ Column 1 (1/4 width)    │ Column 2 (1/4) │ Column 3 (1/4) │ Col 4│
│ Task Tree              │ Task Details   │ All Instances  │ Init │
│ (collapsible)          │ (tabs if multi) │ (toggleable)   │      │
└─────────────────────────────────────────────────────────────────┘
```

**Column 1: Task Tree (leftmost, 1/4 width)**

- Collapsible tree component (use NiceGUI expansion or custom tree)
- Extra small fonts (`text-xs`)
- Tree structure:

  1. Global Milestones (if any exist)
  2. Task Types (Work, Self care, Play)
  3. Jobs (if jobs system exists, collapsible/optional)
  4. Job Milestones (under each job)
  5. Task Templates (under job or directly under task type)
  6. Template Milestones (under each template)
  7. Task Instances (under milestones, or under template if unassigned)

- Right-click context menu on tree nodes:
  - Templates: Edit, Copy, Initialize New
  - Instances: Edit, Assign to Milestone, View Notes
  - Milestones: Edit, Delete, Create New
- Hover tooltip on instances: show initialization notes from `instance_notes['initialization']`
- Toggle checkbox: "Show Completed Tasks" (shows counts per milestone/template when enabled)
- Bottom totals bar:
  - Initialized tasks count
  - Completed tasks count
  - Unstarted milestones count
  - In progress milestones count
  - Completed milestones count

**Column 2: Task Details (1/4 width)**

- Tab bar at top (if multiple tasks open via double-click)
- Most recently opened task shown by default
- Editable instance fields (predicted/actual JSON data):
  - Form fields for all instance attributes
  - Save button to update instance
- Double-clicking instance in tree opens it here in a new persistent tab

**Column 3: All Initialized Tasks (1/4 width)**

- Toggle: "Show All" / "Show Unassigned Only"
- When "Show All": displays all initialized instances
- When "Show Unassigned Only": only instances with `milestone_id IS NULL`
- List format similar to dashboard's recently completed (compact, minimal whitespace)
- Click to open in Column 2

**Column 4: Template Initialization (1/4 width)**

- Searchable template list (similar to dashboard column 1, but without metrics/completed/recent)
- Search input at top
- Grid/list of existing templates
- "Initialize" button on each template
- "Create New Template" button at top
- Does NOT show initialization page or template creation page directly - uses existing pages via navigation

#### Key Features

1. **Milestone Assignment UI**

   - Right-click instance → "Assign to Milestone" → dropdown of available milestones
   - Milestone creation dialog when creating new milestone
   - Scope selection: Global, Template-specific, Job-specific

2. **Instance Notes Management**

   - Edit initialization notes in Column 2 when viewing instance
   - Pause notes automatically captured during pause (append to array)
   - Completion notes editable in completion flow

3. **Tree State Persistence**

   - Remember expanded/collapsed state (localStorage or user preferences)
   - Remember selected node

4. **Completed Tasks View**

   - When toggle enabled, show counts per milestone/template
   - Format: "Milestone Name: 5 completed"
   - Click count to see list of completed instances

### Phase 4: Integration Points

**File: `task_aversion_app/ui/initialize_task.py`**

- Capture initialization notes in `instance_notes['initialization']` field
- Add optional milestone assignment dropdown during initialization

**File: `task_aversion_app/ui/complete_task.py`**

- Capture completion notes in `instance_notes['completion']` field
- Update milestone progress when instance completed

**File: `task_aversion_app/backend/instance_manager.py`**

- Update pause tracking to append notes to `instance_notes['pauses']` array
- Each pause entry: `{"timestamp": "...", "note": "..."}`

**File: `task_aversion_app/ui/dashboard.py`**

- Update "Recently Completed" to use compact styling (reference for goals page design)
- Ensure consistency in visual style

### Phase 5: Migration & Backward Compatibility

**File: `task_aversion_app/migrate_milestones_to_table.py`** (new)

1. Read existing milestones from `user_state.get_milestones()`
2. Find "Task Aversion System" template (or create if missing)
3. Create 6 milestones in table with `scope='template'`, `scope_id=task_id`
4. Migrate status and notes from user_state
5. For each existing instance, check if it should be assigned to a milestone (manual review or skip)
6. Update user_state to mark migration complete

**Backward Compatibility:**

- Keep `user_state` milestone methods during transition
- Add feature flag to use new milestone system
- Gradual migration path

## Data Flow

### Milestone Progress Calculation

```python
def get_milestone_progress(milestone_id):
    # Count instances assigned to this milestone
    assigned = count_instances(milestone_id=milestone_id)
    completed = count_instances(milestone_id=milestone_id, status='completed')
    return {
        'assigned': assigned,
        'completed': completed,
        'progress_pct': (completed / assigned * 100) if assigned > 0 else 0
    }
```

### Global Milestone Counting

For global milestones like "complete x tasks":

- Count all instances assigned to any template/job milestone
- Or count manually assigned instances to the global milestone
- User chooses counting method when creating global milestone

## Testing Considerations

- Test tree expansion/collapse with large hierarchies
- Test milestone assignment/unassignment
- Test instance notes capture (initialization, pause, completion)
- Test column 2 tab management (multiple open tasks)
- Test column 3 toggle functionality
- Test migration script with existing data
- Test backward compatibility during transition
- Test with and without jobs system (optional job level)

## Files Summary

**New Files:**

- `backend/milestone_manager.py`
- `SQLite_migration/XXX_add_milestones.py`
- `migrate_milestones_to_table.py`

**Modified Files:**

- `backend/database.py` (add Milestone model, modify TaskInstance)
- `backend/instance_manager.py` (add milestone_id, instance_notes support)
- `ui/goals_page.py` (complete redesign)
- `ui/initialize_task.py` (capture initialization notes, optional milestone assignment)
- `ui/complete_task.py` (capture completion notes)
- `backend/user_state.py` (deprecate milestone methods, keep for compatibility)