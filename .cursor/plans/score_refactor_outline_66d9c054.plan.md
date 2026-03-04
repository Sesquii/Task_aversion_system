---
name: Score Refactor Outline
overview: An outline and question set for refactoring productivity/execution and introducing new scores (Task Quality, Utility, Challenge), with start-delay tied to due dates and execution sub-score glossary charts. Each section is intended to be drafted as a separate implementation plan in follow-up chats.
todos: []
isProject: false
---

# Score Refactor Clarification Outline

This plan is an **outline with questions** so you can clarify intent and then draft **separate implementation plans** (in new agent chats) for each proposed score and change.

---

## Current state (brief)

- **Productivity score** ([analytics.py](task_aversion_app/backend/analytics.py) ~517–806): Per-task; completion_pct × task-type multiplier × efficiency × goal/burnout. Scale 0–500+ (work). Does **not** use difficulty or start delay.
- **Execution score** ([analytics.py](task_aversion_app/backend/analytics.py) ~8147–8329): Per-task; difficulty × speed × start_speed × completion; base 50, clamped 0–100. **Start speed** uses init→start delay only (no due date).
- **Due dates**: [urgency.py](task_aversion_app/backend/urgency.py) and instance `due_at` ([database.py](task_aversion_app/backend/database.py) ~252). Overdue = `now > due_at`. Used for urgency UI and "Overdue" label.
- **Relief/utility-like data**: `expected_relief` (predicted), `actual_relief` / `relief_score` (actual), `net_relief`; also `serendipity_factor`, `disappointment_factor` in DB.

---

## 1. Productivity refactor and relabeling

**Your direction:** General productivity should factor in "missing factors"; relabel current productivity by what it actually measures; build a more robust productivity score that includes current productivity + execution.

**Proposed structure (to confirm):**

- **Current productivity** measures: completion × task-type × efficiency (time vs estimate) × goal/burnout. That is roughly **"output efficiency"** or **"completion efficiency"** (how much done, how fast, by type).
- **New "robust productivity"** could: (a) keep that as one factor, (b) add a **difficulty-vs-expectation** factor (e.g. task harder or easier than expected, completed in estimated time), (c) optionally absorb or reference execution (e.g. difficulty, start delay) as additional factors.

**Questions for you:**

1. **Relabel:** What name do you want for the **current** formula (the one that is completion × type × efficiency × goal/burnout)? Examples: "Completion efficiency score", "Output score", "Efficiency score", or keep "Productivity score" but document it as "task-type–weighted completion efficiency".
2. **"More or less difficult than expected":** How should we derive "expected difficulty"? Options: (A) use existing predicted fields only (e.g. `initial_aversion`, `cognitive_load`, `task_difficulty`) vs actual (e.g. `stress_level`) to get "expected vs actual difficulty"; (B) add an explicit "expected difficulty" field at init; (C) something else?
3. **Weighting/labeling:** Should the robust productivity score be a single formula with fixed weights, or a **composite** of named sub-scores (e.g. "Completion efficiency" + "Difficulty accuracy" + …) with configurable weights (like composite score weights)?
4. **Execution in productivity:** Should the robust productivity score **include** execution (e.g. difficulty factor, start-delay penalty) inside one formula, or should **Challenge score** (below) be the only place that combines productivity and execution, with productivity staying "output-focused" and just adding the difficulty-vs-expectation factor?

---

## 2. Start delay and due dates

**Your direction:** Start delay should only apply for tasks that are overdue and should only be a penalty; factor in the due-dates system.

**Current:** Start speed = f(init → start delay). No use of `due_at`; same logic for all tasks.

**Proposed:** "Start delay" in scoring: only apply when task has `due_at` and is **overdue** (completed after `due_at`). Penalty only (no bonus for early start). Magnitude could depend on how much of the delay fell after `due_at`, or on total delay when overdue.

**Questions for you:**

1. **Definition of "delay" when overdue:** Should the penalty be based on (A) time from `due_at` to `started_at` (or `completed_at` if no `started_at`), i.e. "how late did you start after the deadline"; (B) time from `initialized_at` to `started_at` but only counted when task is overdue; (C) something else (e.g. time from `due_at` to `completed_at`)?
2. **Tasks without due date:** Should start delay be **ignored** for tasks with no `due_at` (no penalty, no bonus), or do you want a separate rule (e.g. "stale" after N days) that can also trigger a penalty?
3. **Where the penalty lives:** Should this overdue start-delay penalty (a) **replace** the current start_speed_factor in execution score when `due_at` is set and task is overdue; (b) be an **additional** penalty applied on top of execution (or on top of Challenge/Task quality); or (c) only live inside the new **Challenge score** or **Task quality score**, not in the current execution formula?

---

## 3. Execution sub-scores and glossary charts

**Your direction:** Split execution into sub-scores and add data-driven glossary charts: line graph of sub-scores, pie chart of components, bar graph.

**Proposed:** Keep one overall execution score formula but **expose** the four components as named sub-scores: difficulty_factor, speed_factor, start_speed_factor, completion_factor (and optionally an "overdue start penalty" once due-date logic exists). Glossary shows these as components; add three **data-driven** charts (your actual data): (1) line over time (e.g. 7d/30d), (2) pie of component contribution, (3) bar (e.g. 7d averages per component). Wire them like grit's `overview_charts` in [analytics_glossary.py](task_aversion_app/ui/analytics_glossary.py) and add corresponding generators in [plotly_data_charts.py](task_aversion_app/ui/plotly_data_charts.py) (and backend methods to return per-instance or aggregated sub-scores).

**Questions for you:**

1. **Sub-score aggregation:** For the line chart, should the Y-axis be (A) average per day of each sub-score (0–1) across instances, or (B) average of the **overall** execution score per day plus one series per component contribution (e.g. "difficulty contributed X points")?
2. **Pie chart:** Should the pie show (A) contribution to the **current period** average execution score (each component’s multiplicative contribution as a share of the total), or (B) average value of each factor (0–1) normalized to 100%?

---

## 4. Task quality score

**Your direction:** Build out a "task quality" score that combines efficiency, difficulty, start speed, and completion into one 0–100 score.

**Proposed:** One **task quality score** (0–100) per instance: weighted combination of (1) **efficiency** (e.g. completion_time_ratio or same as productivity’s efficiency notion), (2) **difficulty** (e.g. difficulty_bonus 0–1), (3) **start speed** (or overdue start penalty when due dates apply), (4) **completion** (completion_factor 0–1). Each term normalized to 0–100 and combined with configurable weights (e.g. 0.25 each, or user-configurable). This is a single "how well did I do on this task" number; distinct from productivity (which is output/type-focused) and from grit (persistence/passion).

**Questions for you:**

1. **Efficiency term:** Should task quality use the **same** efficiency definition as productivity (completion_time_ratio with same caps), or a simpler one (e.g. raw ratio capped 0–100)?
2. **Relationship to execution:** Should task quality **replace** execution score in the UI/composite, **coexist** (both shown; execution = "efficient execution of difficult tasks", quality = "overall task quality"), or **be the same** formula as execution but renamed and possibly reweighted?
3. **Weights:** Default equal weights (0.25 each) or do you want different defaults (e.g. completion 0.4, efficiency 0.3, difficulty 0.2, start 0.1)?

---

## 5. Utility score (prototype)

**Your direction:** Prototype a "Utility score" with a direct measurement like expected/actual utility, and optionally a derived variant from measured components.

**Proposed:** Two variants:

- **Direct:** **Utility score = f(expected_relief, actual_relief)**. Examples: ratio actual/expected (capped), or normalized difference (e.g. (actual - expected + 100)/2 → 0–100), or "met expectation" = 100 when actual ≥ expected, else proportional. Scale 0–100.
- **Derived:** Combine measured components that correlate with utility: e.g. actual_relief, net_relie

