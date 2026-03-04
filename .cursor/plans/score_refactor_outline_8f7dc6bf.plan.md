---
name: Score Refactor Outline
overview: An outline and clarification document for refactoring productivity and execution scores, introducing Task Quality, Utility, and Challenge scores, tying start delay to due dates, and adding execution sub-score glossary charts. The plan is structured so you can answer questions and then draft separate implementation plans per score in new agent chats.
todos: []
isProject: false
---

# Score Refactor Outline and Clarification Plan

This plan is an **outline with embedded questions** for you to answer. After you clarify, you can open new agent chats and request separate implementation plans for each score (e.g. "Plan: Productivity score refactor", "Plan: Execution score + start delay + glossary charts", "Plan: Task Quality score", "Plan: Utility score", "Plan: Challenge score").

---

## 1. Current State Summary

- **Productivity score** ([analytics.py](task_aversion_app/backend/analytics.py) `calculate_productivity_score`): completion_pct × task_type_multiplier × efficiency_multiplier × goal/burnout. Measures output and efficiency by type; **does not** include difficulty or start delay. Scale: 0–500+ (work), can be negative (play).
- **Execution score** ([analytics.py](task_aversion_app/backend/analytics.py) `calculate_execution_score`): difficulty + speed + start_speed + completion, multiplicative, 0–100. **Start speed** is currently "delay from init to start" for all tasks; no due-date logic.
- **Due dates**: Instance has `due_at`; [urgency.py](task_aversion_app/backend/urgency.py) sets `overdue = now > due_at`. Used for urgency display and recommendations; not yet used in any score formula.
- **Expected/actual relief**: Stored in predicted_dict (`expected_relief`) and actual_dict (`actual_relief` / `relief_score`). Net relief = actual − expected; used in grit (disappointment resilience) and relief summaries. No standalone "utility" score today.

---

## 2. Productivity Score Refactor

**Goal:** Relabel what the current formula actually measures; add missing factors (e.g. difficulty vs expectation); build a "robust productivity" that can incorporate current productivity + execution-like pieces.

**Proposed direction:**

- **Relabel** the existing score: it is effectively "output efficiency by task type" (completion × type multiplier × time efficiency). Possible names: "Output Score", "Efficiency Score", "Completion Efficiency Score". 
- **New factor:** "Difficulty vs expectation" — task completed in estimated time but harder or easier than expected. This implies a definition of "expected difficulty" (e.g. from prediction) vs "experienced difficulty" (e.g. stress_level, aversion in actual).
- **Robust productivity:** A higher-level score that combines (with configurable or fixed weights): relabeled productivity + difficulty factor + possibly start delay (overdue-only, see below) + volume/consistency as today.

**Questions for you (Productivity):**

1. What should the **relabeled** current productivity score be called in the UI and docs? (e.g. "Output Score", "Efficiency Score", "Completion Efficiency Score", or keep "Productivity Score" and introduce a new "Overall Productivity" that includes more factors?)
2. For "difficulty vs expectation": do you have (or plan to have) an **expected difficulty** field at prediction time (e.g. "how hard do you expect this to be?") so we can compare to post-task stress/aversion? If not, should this factor be "difficulty level" only (no expectation), or derived another way?
3. Should the **robust productivity** score replace the current weekly/dashboard "Productivity Score" everywhere, or appear as a separate metric (e.g. "Overall Productivity") with the relabeled score still available as a component or legacy metric?
4. Should task type (work / self-care / play) and play penalty remain in the robust productivity score with the same logic, or do you want to change how task types are weighted in the combined score?

---

## 3. Start Delay and Due Dates

**Goal:** Start delay should only apply for tasks that are **overdue**, and only as a **penalty** (no bonus for "fast start" on non-overdue tasks in this factor).

**Current:** Start speed factor in execution score = f(init → start delay). Always applied; rewards fast start, penalizes long delay.

**Proposed:** 

- **Overdue-only start penalty:** Compute "start delay" only when the task has a `due_at` and the instance is **overdue** (completed after due_at). Penalty = some function of delay from due_at to start (or init to start, whichever you prefer). No penalty when task is not overdue.
- **Execution score:** Either (a) remove start_speed from execution and have a separate "overdue start penalty" that feeds into Challenge/robust productivity, or (b) make start_speed in execution conditional: 0 penalty when not overdue; when overdue, penalty based on delay. Same formula, different inputs.

**Questions for you (Start delay / due dates):**

1. For the overdue penalty, what delay do you want to penalize: (A) time from **due_at** to **started_at** (how late you started after the deadline), (B) time from **initialized_at** to **started_at** but only when the task was already overdue at start time, or (C) something else (e.g. time from due_at to completed_at)?
2. Should "start delay" disappear entirely from the **current** execution score (so execution = difficulty + speed + completion only), and the overdue penalty live only in Challenge / robust productivity, or should execution still include a conditional start term (overdue-only penalty)?
3. If a task has **no due date**, should it have zero start-delay impact in all scores (no bonus, no penalty)?

---

## 4. Execution Score Split and Glossary Charts

**Goal:** Split execution into sub-scores (e.g. difficulty execution, speed execution, start execution, completion) and add **data-driven** glossary charts: line (trend), pie (component share), bar (e.g. 7d averages by sub-score).

**Proposed:**

- **Sub-scores:** Same formula as now, but each factor (or groups) exposed as separate series: e.g. `execution_difficulty_score`, `execution_speed_score`, `execution_start_score`, `execution_completion_score` (each 0–100 or normalized). Optionally one combined `execution_score` = current formula.
- **Glossary:** In [analytics_glossary.py](task_aversion_app/ui/analytics_glossary.py), execution module gets an `overview_charts` list (like grit's `overview_charts`). In [plotly_data_charts.py](task_aversion_app/ui/plotly_data_charts.py) (or equivalent), add chart generators that take analytics data and produce: (1) **Line:** sub-scores over time (e.g. last 30 days), (2) **Pie:** component contribution to total execution score, (3) **Bar:** e.g. 7-day averages per sub-score. These need backend methods that return time-series and component breakdown for the selected user/period.

**Questions for you (Execution split + charts):**

1. Confirm sub-score names and granularity: do you want exactly four (difficulty, speed, start, completion), or three (e.g. "difficulty", "speed", "start+completion")? And should the combined execution score remain the same formula (so charts show components that multiply to it)?
2. For the **start** sub-score after due-date changes: when start is overdue-only penalty, should the pie/bar still show "start" as a component (possibly 0 when not overdue), or should the glossary describe execution as three components (difficulty, speed, completion) with "overdue start penalty" documented elsewhere (e.g. Challenge score)?
3. Where should these charts appear: only in the Analytics Glossary execution module tab, or also on the main Analytics page or Dashboard as optional widgets?

---

## 5. Task Quality Score

**Goal:** A single 0–100 **Task Quality** score per task that combines: efficiency (completion/time), difficulty (aversion/load), start speed (or overdue penalty only), and completion quality. Interpretable as "how well this task was done" independent of task type.

**Proposed formula (conceptual):**

- Normalize each input to 0–1: efficiency_term (from completion_time_ratio), difficulty_term (difficulty_bonus), start_term (fast start or overdue penalty only), completion_term (completion_pct).
- Task quality = weighted average of these four, then scale to 0–100. Weights could be equal or configurable (e.g. 0.25 each, or 0.3 efficiency, 0.3 difficulty, 0.2 completion, 0.2 start).
- This score is **per instance**. Aggregates: daily/weekly average, or time-series for charts.

**Questions for you (Task Quality):**

1. Should Task Quality **replace** the current execution score in the composite and dashboard, or coexist (execution stays; Task Quality is an additional metric)?
2. Weights: equal (0.25 each) or do you want different emphasis (e.g. efficiency and completion higher, start lower)?
3. Should Task Quality include **task type** at all (e.g. play tasks capped or downweighted), or strictly "quality of execution" regardless of work/play/self-care?

---

## 6. Utility Score (Prototype)

**Goal:** A "Utility score" with a direct measurement like expected/actual utility, and optionally a derived variant from measured components.

**Data available:** `expected_relief`, `actual_relief` (0–100), `net_relief` = actual − expected. No separate "utility" field; relief is the closest proxy for experienced utility.

**Proposed options:**

- **Direct:** Utility score = f(expected_relief, actual_relief). Examples: (1) ratio actual/expected (capped), (2) actual_relief with bonus/penalty for meeting/exceeding expected, (3) 0–100 scale: 50 + (actual − expected) so "met expectation" ≈ 50.
- **Derived:** Utility = weighted combination of measured components that correlate with "utility" in your model: e.g. actual_relief, completion_pct, net_wellbeing, stress_efficiency, serendipity_factor. Weights and components to be defined.

**Questions for you (Utility):**

1. Should "utility" be explicitly **relief-based** (expected/actual relief as the main inputs), or do you want to introduce a separate "expected utility" / "actual utility" field in the UI and DB later, with the prototype using relief as a stand-in?
2. For the direct variant: do you prefer ratio (actual/expected), difference (actual − expected), or a "met expectation" centered scale (e.g. 50 = met, &gt;50 = exceeded, &lt;50 = below)?
3. For the derived variant: which components should be included (e.g. actual_relief, completion_pct, net_wellbeing, stress_efficiency, disappointment/serendipity) and should they be equally weighted or do you have a priority order?

---

## 7. Challenge Score

**Goal:** A score that combines "productivity" (output/efficiency) and "execution difficulty" — i.e. doing well on hard tasks. Name: "Challenge score".

**Proposed:** Challenge = combination of (1) relabeled productivity or robust productivity, and (2) difficulty-weighted execution (or Task Quality). Options: (A) weighted average of two 0–100 scores (productivity normalized to 0–100 + execution or task_quality), (B) productivity × (1 + difficulty_factor) so harder tasks amplify productivity, (C) separate formula that explicitly multiplies "output" by "difficulty overcome". Scale: 0–100 or 0–150 depending on design.

**Questions for you (Challenge):**

1. Should Challenge use the **relabeled** productivity (efficiency by type) or the **robust productivity** (with difficulty vs expectation and overdue penalty)?
2. Should Challenge use **execution score** (current, possibly with overdue-only start) or **Task Quality** as the "execution/difficulty" side?
3. Preferred combination: (A) average of two normalized scores, (B) productivity × (1 + difficulty_factor), or (C) a new formula you have in mind (describe)?

---

## 8. Implementation Order and Separate Plans

Suggested order for drafting **separate** implementation plans in new chats:

1. **Start delay + due dates** (small, well-scoped): overdue-only penalty definition, where it lives (execution vs Challenge/robust productivity), and integration with [urgency.py](task_aversion_app/backend/urgency.py) / instance `due_at`.
2. **Execution refactor + glossary charts:** Conditional start factor (if kept), sub-scores (difficulty, speed, start, completion), and data-driven line/pie/bar in glossary + backend series methods.
3. **Productivity relabel + robust productivity:** Relabel current score, add "difficulty vs expectation" (and any new fields), define robust productivity formula and where it appears.
4. **Task Quality score:** Formula, weights, per-instance and aggregates, UI/dashboard placement.
5. **Utility score (prototype):** Direct (expected/actual) and optionally derived variant, scale and placement.
6. **Challenge score:** Formula combining productivity side + execution/difficulty side, normalization, and placement in composite/dashboard.

After you answer the questions above, you can paste this outline (and your answers) into new agent chats and ask for a concrete implementation plan for each of the six areas above.