---
name: Robust consistency and time alignment scores
overview: Define two primary metrics—time_alignment_score and consistency_score—plus a robust_consistency_score that customizes components per task type. All scores use daily/weekly targets/limits stored on task templates when present, and infer missing targets/limits from task-type averages.
todos: []
isProject: false
---

# Robust Consistency and Time Alignment Scores — Plan

## 1. Metrics and Relationships

- **time_alignment_score (0–100)**
  - Measures *when* tasks are done vs planned (routine_time / completion windows).
  - Aggregated across all tasks, with task-type-dependent weighting.
- **consistency_score (0–100)**
  - Baseline, task-agnostic consistency score: "How well do I hit daily/weekly targets and respect limits across all tasks?"
  - Uses the same formula for all task types (Work, Play, Self care, Sleep, etc.).
- **robust_consistency_score (0–100)**
  - Enhanced consistency score that **customizes components per task type**.
  - Built on top of the same daily/weekly target/limit data and per-template completion stats, but:
    - Uses **task-type-specific sub-components** (e.g. over-limit Play is worse than over-limit Work).
    - Can differ in how daily vs weekly alignment is weighted for each type.
  - Can be exposed as a separate score and/or used as the consistency component in the global composite score.

Relationship:
- `consistency_score` = simple, easy-to-explain global view.
- `robust_consistency_score` = refined view for users who care about nuanced type-specific behavior and for composite/recommendations.

---

## 2. Data Assumptions and Inference Rules

### 2.1 Template-level configuration (provided by other agent)

Each task template may have some or all of:
- **Daily settings**: `daily_target`, `daily_limit` (completions per day).
- **Weekly settings**: `weekly_target`, `weekly_limit` (completions per week).

Not all templates will set these fields.

### 2.2 Inference for templates without explicit settings

For any missing of `{daily_target, daily_limit, weekly_target, weekly_limit}`:
- Compute **task-type-level averages** over templates that *do* have values set.
  - For example, for `task_type = 'Work'`, compute:
    - `avg_daily_target_work`, `avg_daily_limit_work`, `avg_weekly_target_work`, `avg_weekly_limit_work`.
- Use those averages as **derived targets/limits** for templates of that type that lack explicit settings.
- If no templates of that type have explicit values:
  - Fall back to either:
    - A global default per task type (e.g. `default_daily_target_self_care = 1`, `default_weekly_limit_play = 7`), or
    - A neutral behavior (exclude that component or treat as mid-score) — to be decided in implementation.

These derivations should be **cached** (e.g. per user, per period) to avoid recomputing on every call.

### 2.3 Instance/completion data

From existing infrastructure (InstanceManager / DB):
- Per `task_id`, per date/week, we have **completion counts** (and can aggregate by task type).
- We can compute:
  - `daily_count(task_id, date)`
  - `weekly_count(task_id, week)`

These combined with targets/limits (explicit or derived) are the core inputs for consistency metrics.

---

## 3. Baseline Consistency Score (task-agnostic)

### 3.1 Per-period consistency component

For each (task_id, period), where period is a **day** or **week**:
- Let `actual` = actual completions in that period.
- Let `target` = target completions (explicit or derived) for that period.
- Let `limit` = limit completions (explicit or derived) for that period.

Define per-period measures (same for all task types):
- **Target adherence**: how close actual is to target (e.g. capped ratio or smooth curve around 1.0).
- **Limit respect**: penalty as actual moves beyond limit.

Example (conceptual):
- `target_ratio = actual / target` (if target > 0, else neutral=1.0).
- `on_target_score` decays as `target_ratio` moves away from 1.0, symmetric for under/over.
- `limit_penalty` increases as `actual` exceeds `limit` (0 if below limit, rising penalty beyond).
- Period consistency in 
  [0, 100] could be `100 * on_target_score - limit_penalty` (clamped to 0–100).

### 3.2 Aggregate into baseline consistency_score

- **Daily consistency:** aggregate over N recent days (e.g. 14 or 30) across all task_ids, weighted by:
  - Number of days a task had a defined/derived target (`days_in_scope`).
  - Optionally by importance of that task type (simple equal weights here; robust version will customize).
- **Weekly consistency:** similar, but over weeks.
- Combine daily + weekly into **single `consistency_score` (0–100)** with fixed, global weights (e.g. `0.6 * daily + 0.4 * weekly`).

This score uses **identical logic for all task types**—no special treatment of Work vs Play etc.—to stay easy to explain.

---

## 4. Robust Consistency Score (task-type customized)

### 4.1 Task-type-specific semantics

For the same per-period data, **robust_consistency_score** will:
- Use different **weighting and penalties** by task type:
  - **Work:**
    - Under-target may indicate under-commitment; over-target may be mildly positive or neutral, but large over-limit could indicate overwork.
  - **Play:**
    - Under-target might be fine; over-target and over-limit should be penalized more strongly.
  - **Self care:**
    - Under-target is strongly penalized (missing self-care); over-limit likely capped (not negative, but no extra bonus).
  - **Sleep:**
    - Under-target penalized; over-limit (too much sleep) may be gently penalized or neutral depending on your philosophy.
- Optionally weight **daily vs weekly** differently per type:
  - For Sleep or Self care, daily adherence might matter more.
  - For Work, weekly adherence may matter more than exact daily distribution.

### 4.2 Per-task-type components

Define **sub-scores per task type** (all 0–100):
- `consistency_work`
- `consistency_play`
- `consistency_self_care`
- `consistency_sleep`
- `consistency_other` (catch-all)

Each sub-score:
- Uses the same raw inputs (actual vs target/limit per day/week), but:
  - Different curves for target adherence and over-limit penalty.
  - Different mixing of daily vs weekly metrics.
- Example: For Play, we could:
  - Downweight under-target penalties and strongly upweight over-limit penalties.
  - For Work, modest penalties for slightly under-target, small bonuses for modestly over-target, but cap or penalize far beyond limit.

### 4.3 Aggregating into robust_consistency_score

- Use a **weighted average across task-type sub-scores**, with configurable weights per type; e.g.:
  - `robust_consistency_score = Σ(consistency_type * weight_type) / Σ(weight_type)`.
- Defaults could prioritize Work and Self care more than Play.
- Expose both:
  - Overall `robust_consistency_score` (0–100).
  - Breakdown by type for analytics/diagnostics.

---

## 5. Time Alignment Score (unchanged core idea, explicit daily/weekly role)

### 5.1 Inputs

- Template:
  - `routine_time`, `routine_frequency`, `routine_days_of_week`.
  - `completion_window_hours` / `completion_window_days`.
- Instance:
  - `initialized_at`, `completed_at`.
- Targets/limits (daily/weekly) are **not** core to time alignment, but can optionally influence weighting (e.g. more weight on time alignment for high-target Work tasks).

### 5.2 Per-instance alignment

For each completed instance where routine/window exists:
- Measure:
  - **On-time start**: distance in minutes between `initialized_at` (or `started_at`) and the day’s `routine_time`.
  - **Within window**: whether `completed_at` falls within the completion window relative to `initialized_at`.
- Convert each into a 0–100 score with curves that tolerate minor slips but penalize large misalignments.

For instances without routine/window, either:
- Treat as **neutral** (do not affect time_alignment_score), or
- Use task-type defaults later if you add them (not required for first version).

### 5.3 Aggregation and task-type weights

- Aggregate per task and task type over a time window (e.g. 14 days).
- Weight by:
  - Task type (Self care and Sleep may matter more than Play).
  - Number of times the task is scheduled/expected (based on targets, but only as a weight, not part of core formula).
- Produce a single **`time_alignment_score` (0–100)** plus optional breakdown by task type.

---

## 6. Integration Points and Outputs

- **Analytics backend:**
  - Add functions (names illustrative):
    - `calculate_consistency_score(...)`
    - `calculate_robust_consistency_score(...)`
    - `calculate_time_alignment_score(...)`
  - Ensure they can operate on pre-aggregated daily/weekly stats provided by the other agent, or compute from instances as needed.
- **Composite score:**
  - Add `robust_consistency_score` and `time_alignment_score` to the composite components list in `get_all_scores_for_composite`.
  - Update composite weights UI (component labels + default weights) to include:
    - "Consistency (baseline)"
    - "Consistency (robust, type-aware)"
    - "Time alignment".
- **Analytics / dashboard UI:**
  - Display:
    - `consistency_score` as the simple, headline metric.
    - `robust_consistency_score` and `time_alignment_score` in analytics/advanced sections, with per-task-type breakdowns.
- **Future goal tracking:**
  - For goals based on daily/weekly targets/limits, reuse consistency components to report progress and risk (e.g. goals at risk if robust consistency drops below threshold).

---

## 7. Implementation Phases

1. **Data contract & inference utilities**
   - Finalize expected daily/weekly stats format from the other agent (per task_id, per day/week).
   - Implement utilities to compute task-type averages and derive missing targets/limits.
2. **Baseline consistency_score**
   - Implement task-agnostic per-period formula and aggregation over days/weeks.
   - Expose `consistency_score` and verify against simple scenarios.
3. **Robust consistency (task-type customized)**
   - Implement per-task-type sub-scores, curves, and type weights.
   - Expose `robust_consistency_score` and type breakdowns.
4. **Time alignment score**
   - Implement instance-level alignment to routine_time and completion windows.
   - Aggregate into `time_alignment_score` with task-type weights.
5. **Integration into composite and UI**
   - Wire all three scores into analytics, composite score weights, and dashboard/analytics views.
   - Add clear tooltips/glossary entries explaining baseline vs robust consistency.

This plan keeps **two primary exposed metrics** (time_alignment_score and consistency_score) while also introducing a richer **robust_consistency_score** that is explicitly task-type-aware and leverages daily/weekly targets/limits with inference for missing values.
