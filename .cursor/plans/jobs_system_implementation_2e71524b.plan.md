---
name: Jobs System Implementation
overview: Implement a Jobs system that groups tasks into meaningful categories (Development, Upkeep, Fitness, etc.) with job-based navigation, analytics, and search. Jobs act as an intermediate layer between task_type and individual tasks, enabling better organization and emotional pattern analysis.
todos:
  - id: db_models
    content: Add Job and JobTaskMapping SQLAlchemy models to database.py, update init_db()
    status: pending
  - id: job_manager
    content: Create JobManager class with dual backend support (database/CSV), implement CRUD and assignment methods
    status: pending
    dependencies:
      - db_models
  - id: migration_script
    content: Create migration script to add jobs tables and default jobs (Development, Education, Music, Upkeep, Fitness, Videogames, Chat, Bar)
    status: pending
    dependencies:
      - db_models
  - id: top_jobs_analytics
    content: Add get_top_jobs() method to Analytics class - calculate completion count and time spent for jobs with activity in last 30 days
    status: pending
    dependencies:
      - job_manager
  - id: job_analytics_methods
    content: "Add job-specific analytics methods: get_job_analytics(), get_cross_job_recommendations(), get_universal_task_analytics()"
    status: pending
    dependencies:
      - top_jobs_analytics
  - id: dashboard_top_jobs
    content: Replace 'Quick Tasks' with 'Top Jobs' section in dashboard - show job cards with completion count and time spent
    status: pending
    dependencies:
      - top_jobs_analytics
  - id: job_task_selection_page
    content: Create job task selection page (/job-tasks) - display tasks for a job with initialize and add task options
    status: pending
    dependencies:
      - job_manager
  - id: search_enhancement
    content: Add search mode toggle (Job vs Task) to dashboard search, implement unified search showing both job and task results
    status: pending
    dependencies:
      - job_manager
  - id: task_manager_integration
    content: Update TaskManager to support job assignment in create_task() and add assign_to_jobs() method
    status: pending
    dependencies:
      - job_manager
  - id: create_task_ui
    content: Add job selection (multi-select) to create_task.py UI for assigning tasks to jobs
    status: pending
    dependencies:
      - task_manager_integration
---

# Jobs System Implementation Plan

## Overview

Add a Jobs layer between `task_type` (Work/Self care/Play) and individual tasks. Jobs group related tasks (e.g., "Development", "Upkeep", "Fitness") and enable job-based navigation, analytics, and search. Tasks can belong to multiple jobs (many-to-many relationship).

## Architecture

### Data Model

```
task_type (Work, Self care, Play)
  └─ job (Development, Upkeep, Fitness, etc.)
      └─ tasks (many-to-many: task can belong to multiple jobs)
          └─ task_instances
```

### Database Schema

**New Tables:**

1. `jobs` table:

   - `job_id` (String, primary key) - Format: `j{timestamp}`
   - `name` (String, nullable=False)
   - `task_type` (String) - Links to Work/Self care/Play
   - `description` (Text, optional)
   - `created_at`, `updated_at` (DateTime)

2. `job_task_mapping` table (many-to-many):

   - `job_id` (String, foreign key → jobs.job_id)
   - `task_id` (String, foreign key → tasks.task_id)
   - `created_at` (DateTime)
   - Composite primary key: (job_id, task_id)

**Default Jobs:**

- WORK: "Development", "Education", "Music"
- Self care: "Upkeep", "Fitness"
- PLAY: "Videogames", "Chat", "Bar"

## Implementation Phases

### Phase 1: Database & Backend Models

**Files to modify/create:**

1. **[backend/database.py](task_aversion_app/backend/database.py)**

   - Add `Job` SQLAlchemy model
   - Add `JobTaskMapping` SQLAlchemy model
   - Update `init_db()` to create new tables

2. **Create [backend/job_manager.py](task_aversion_app/backend/job_manager.py)**

   - `JobManager` class (similar pattern to `TaskManager`)
   - Methods:
     - `create_job(name, task_type, description='')` → returns job_id
     - `get_job(job_id)` → returns job dict
     - `get_all_jobs(task_type=None)` → returns list of job dicts
     - `update_job(job_id, **kwargs)`
     - `delete_job(job_id)` (with safety checks)
     - `assign_task_to_job(task_id, job_id)`
     - `remove_task_from_job(task_id, job_id)`
     - `get_tasks_for_job(job_id)` → returns list of task dicts
     - `get_jobs_for_task(task_id)` → returns list of job dicts
     - `get_top_jobs(limit=10, days=30)` → returns jobs with completions in last 30 days, sorted by completion count
   - Support both database and CSV backends (dual backend pattern)

### Phase 2: Migration Scripts

**Create [migrate_add_jobs.py](task_aversion_app/migrate_add_jobs.py)**

- Create default jobs (Development, Education, Music, Upkeep, Fitness, Videogames, Chat, Bar)
- Create `jobs` and `job_task_mapping` tables
- No automatic task assignment (manual assignment only per user request)
- Include rollback capability

**Alembic migration (if using Alembic):**

- Create migration file for jobs tables
- Follow existing migration patterns from `.cursor/rules/sql-migration-alembic.mdc`

### Phase 3: UI - Job Selection & Navigation

**Files to modify:**

1. **[ui/dashboard.py](task_aversion_app/ui/dashboard.py)**

   - Replace "Quick Tasks (Last 5)" with "Top Jobs"
   - Display job cards showing:
     - Job name
     - Number of instances completed (last 30 days)
     - Total time spent (last 30 days)
     - Task count for that job
   - Click job card → navigate to job task selection page
   - Filter: Only show jobs with completions in last 30 days

2. **Create [ui/job_task_selection.py](task_aversion_app/ui/job_task_selection.py)**

   - New page: `/job-tasks?job_id={job_id}`
   - Display all tasks assigned to the job
   - "Initialize Task" button for each task
   - "Add New Task to Job" button (creates task and assigns to job)
   - Search/filter tasks within job
   - Back button to dashboard

3. **[ui/dashboard.py](task_aversion_app/ui/dashboard.py)** - Search Enhancement

   - Add search mode toggle: "Search by Job" or "Search by Task"
   - Job search: Search job names, show matching jobs
   - Task search: Existing behavior (search task names/descriptions)
   - Unified search: Search both jobs and tasks, show results grouped

### Phase 4: Backend Integration

**Files to modify:**

1. **[backend/task_manager.py](task_aversion_app/backend/task_manager.py)**

   - Update `create_task()` to optionally accept `job_ids` parameter
   - Add `assign_to_jobs(task_id, job_ids)` method
   - Update `get_task()` to include `job_ids` in returned dict

2. **[backend/instance_manager.py](task_aversion_app/backend/instance_manager.py)**

   - Update `create_instance()` to preserve job context (optional)
   - Add helper method `get_job_for_instance(instance_id)` → returns job info

3. **[ui/create_task.py](task_aversion_app/ui/create_task.py)**

   - Add job selection (multi-select) when creating task
   - Show job assignment in task edit form

### Phase 5: Analytics Integration

**Files to modify:**

1. **[backend/analytics.py](task_aversion_app/backend/analytics.py)**

   - Add `get_top_jobs(days=30, limit=10)` method:
     - Returns jobs with completions in last N days
     - Includes: job_id, name, completion_count, total_time_minutes, avg_relief, avg_aversion
     - Sorted by completion_count descending

   - Add `get_job_analytics(job_id, days=30)` method:
     - Job-specific metrics: completion rate, avg relief, avg aversion, time distribution
     - Emotional patterns: stress/relief trends for this job
     - Task performance within job

   - Add `get_cross_job_recommendations(job_id, limit=5)` method:
     - Recommends tasks from other jobs based on:
       - Similar emotional profiles (similar relief/stress patterns)
       - Complementary skills
       - Cross-job correlations

   - Add `get_universal_task_analytics()` method:
     - Finds tasks that work well across multiple jobs
     - Identifies tasks with high relief/low stress across all jobs
     - Discovers correlations between tasks and jobs
     - Useful for finding "universal" tasks (like brainstorming)

2. **[ui/analytics_page.py](task_aversion_app/ui/analytics_page.py)** (if exists)

   - Add "Job Analytics" section
   - Display top jobs chart
   - Job-specific analytics views
   - Cross-job recommendations display

### Phase 6: Dashboard Updates

**Files to modify:**

1. **[ui/dashboard.py](task_aversion_app/ui/dashboard.py)**

   - Update `get_top_jobs()` helper function:
     - Query JobManager for top jobs (last 30 days)
     - Format: job name, completion count, time spent
     - Filter out jobs with no recent activity

   - Update template search:
     - Add job search mode
     - Show job results separately from task results
     - Allow filtering by job

2. **Navigation flow:**
   ```
   Dashboard → Click "Top Job" → Job Task Selection Page → Select Task → Initialize Task (existing flow)
   ```


## Data Flow

### Job Frequency Calculation

```python
def get_top_jobs(days=30, limit=10):
    # 1. Get all jobs
    # 2. For each job, get all tasks in that job
    # 3. Get task instances completed in last N days for those tasks
    # 4. Count completions per job
    # 5. Sum time spent per job
    # 6. Filter: only jobs with completions in last 30 days
    # 7. Sort by completion_count descending
    # 8. Return top N
```

### Job-Task Relationship

- Many-to-many: Task can belong to multiple jobs
- When creating task, user selects one or more jobs
- Job assignment can be updated later
- Analytics aggregate by job (sum across all tasks in job)

## Migration Strategy

1. **Create default jobs** (Development, Education, Music, Upkeep, Fitness, Videogames, Chat, Bar)
2. **Create tables** (`jobs`, `job_task_mapping`)
3. **No automatic task assignment** - user manually assigns existing tasks
4. **Backward compatibility**: Tasks without jobs still work (just won't appear in Top Jobs)

## Future Enhancements (Not in Phase 1)

- Job-specific scoring rules (multipliers, weights)
- Job emotional profiles (expected aversion/relief ranges)
- Job milestones/goals
- Job-specific analytics dashboards
- Job templates for quick task creation

## Testing Considerations

- Test job creation/assignment
- Test top jobs calculation (with 30-day filter)
- Test many-to-many relationships (task in multiple jobs)
- Test search by job vs task
- Test analytics aggregation by job
- Test migration script rollback
- Test backward compatibility (tasks without jobs)

## Files Summary

**New files:**

- `backend/job_manager.py`
- `ui/job_task_selection.py`
- `migrate_add_jobs.py`

**Modified files:**

- `backend/database.py` (add Job, JobTaskMapping models)
- `backend/task_manager.py` (job assignment methods)
- `backend/instance_manager.py` (job context helpers)
- `backend/analytics.py` (job analytics methods)
- `ui/dashboard.py` (Top Jobs, search enhancement)
- `ui/create_task.py` (job selection)