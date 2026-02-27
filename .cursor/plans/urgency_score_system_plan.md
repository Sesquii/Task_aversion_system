# Urgency Score System: Plan (Decisions + Implementation Outline)

This plan reflects your decisions on the urgency score system and how it integrates with the recommendation system. It replaces the earlier brainstorm document with concrete choices and implementation notes.

---

## 1. Definition and Scope (Decisions)

- **Urgency = importance over time** (best approximation): combines how “important” or consequential the task is with how time-sensitive it is (e.g. time since initialized, or time to/ past due).
- **Apply to instances** (not templates as the primary unit). Templates can be used to derive defaults (e.g. default due-offset) but the urgency score is computed per instance. Optionally we can surface “template-level” urgency later (e.g. “tasks of this type are often urgent”) without making it the main lever.
- **Urgency is derived**, not a separate user slider: computed from existing sliders/signals (e.g. time since initialized, due date if set, procrastination/behavioral history). No dedicated “urgency” slider in the UI for the user to set.
- **Avoid an all-encompassing “priority score.”** The recommendation system should prioritize using multiple metrics (relief, cognitive load, urgency, etc.) with configurable weights. A single umbrella “priority score” is avoided to prevent confusion and to keep urgency as one factor among others.
- **Key product distinction:** Urgency can reflect **mental/habitual** dimension—e.g. a task that is **habitually procrastinated on** can have higher urgency even without a hard deadline, so “urgency” isn’t only “deadline soon” but also “this keeps getting put off.”

---

## 2. Data and Schema (Decisions)

- **Overdue-based model (not completion window):** Prefer **due date/time on instances**; “overdue” = past that datetime. Completion-window logic is de-emphasized for this pass.
- **Routines:** Acknowledge routines have complex logic; **separate pass** for optimization. For now use best judgment (e.g. routine instances can have optional due derived from routine_time if needed, but full routine redesign is out of scope).
- **Routines vs normal tasks (future):** Routines should eventually live in a **separate system**—own UI and functions, navigable from top bar (with Analytics, etc.). They can optionally be linked to tasks. Goal: separate “task completion” from “routine-ness” to support users who struggle with routines. Current routine system to be isolated and reworked later; not blocking urgency on instances.

**Schema implications:**

- Instance-level **due_at** (or equivalent) datetime, optional. When set, overdue = now > due_at.
- **Task horizon setting:** Global or per-user number of days (e.g. 7 or 14). Used to treat “no due date” tasks that are older than N days as “stale” (yellow, see below).
- No change to “completion window” in this phase beyond what’s needed for overdue; routines left for later pass.

---

## 3. Scoring Formula and Inputs (Decisions)

- **Linear component:** The longer it’s been since a task was **initialized**, the higher urgency goes, up to a **cap/threshold** (bounded).
- **Bounded and monotonic:** Urgency score in a fixed range (e.g. 0–100), monotonic in “more urgent” direction.
- **Overdue flag:** Separate boolean (or equivalent) for “past due_at.” Used for:
  - **Popup** when a task becomes overdue.
  - **UI:** exclamation mark and/or **red stripe / red color** for overdue tasks in the initialized-tasks list.
- **No due date, old tasks:** If a task has **no due date** and has been active (initialized) for **more than task_horizon days**, treat as “stale” and show **yellow** (neutral importance indicator). Task horizon is a **setting** (number of days).
- **Habitual procrastination:** Urgency can incorporate behavioral history (e.g. repeatedly postponed or delayed) so habitually procrastinated tasks get higher derived urgency; exact formula can be rudimentary at first (e.g. count of postpones, or time since first initialized).

**Score inputs (summary):**

- Time since initialized (linear up to threshold).
- Due date/time if present (overdue = max urgency + overdue flag).
- Optional: postponement/cancel-like history for “habitually put off” boost.
- Task horizon used only for “yellow” stale state, not necessarily in the numeric score.

---

## 4. Integration with Recommendation System (Decisions)

- **Urgency as a weighted factor:** Use **urgency score with a weight** in the recommendation ranking (e.g. in `recommendations_by_category()` or equivalent), not only as a filter.
- **Searchable factor:** Urgency is one of the **searchable/filterable** dimensions in recommendations. Project-wide, tooltips for recommendation scores need iteration (what appears depending on search); for now add urgency in a sensible way without over-investing in tooltip copy.
- **“Balance” mode naming:** Do **not** use “balance” (reserved for life-balance subsystem). Prefer something like **“high value tasks”** or **“impetus driven tasks”**—avoid “priority tasks” to avoid conflating with a single priority score.
- **Cognitive profile:** More complex than this task. Desired direction: system that increases load when alignment is high and decreases when alignment is low, with calibration over time. Out of scope for urgency; note for future.

---

## 5. UX (Decisions)

- **Where to show urgency:** **All of the above** (recommendation cards, task list, dashboard strip, analytics studio). You’ll use it and trim where it feels overdone.
- **Display:** Show **urgency score** and **deadline datetime** when applicable (e.g. “Urgency: 72 · Due: Feb 28, 2:00 PM”).
- **Explanation:** Support an **explanation flag** (e.g. “why this is urgent” or “why recommended”) for **LLM integration** later; can be a simple text field or structured reason.
- **Postpone urgent tasks:** User can **postpone** an urgent (or any) task. Postpone triggers a **popup to capture reason** (similar to cancel flow). Postpone **feeds into scores** similarly to cancelling (e.g. behavioral/aversion or procrastination signals). Implementation should mirror cancel flow where appropriate.

**Overdue and stale:**

- **Overdue:** Popup when task becomes overdue; exclamation mark; **red stripe or red color** for overdue tasks in initialized tasks list.
- **No due date, old:** Tasks over **task_horizon** days with no due date → **yellow** (stale / neutral importance).

---

## 6. Edge Cases and Behavior (Decisions)

- **Tasks without deadlines:** Shown **yellow** after task_horizon days (neutral importance); no red, no overdue popup.
- **Cancelled and completed in recommendations:** **Exclude** cancelled and completed from recommendations by default. **Middle ground:** a **checkbox in the recommendation UI** to “Include completed and cancelled tasks” (and optionally “Include routines” logic when routines are split out).
- **Excessive urgency:** Implement a **rudimentary** safeguard (e.g. cap weight of urgency in combined score, or simple “max N urgent-only recommendations”). Use it for a while and iterate based on feel; no heavy design up front.

---

## 7. Success and Iteration (Decisions)

- **Success metrics:** Leave open for now; decide after some use.
- **Configurable weights:** Yes—urgency weight (and possibly others) should be **configurable** (e.g. settings or admin) so you can tune without code changes.
- **Logging:** Yes—log when urgency is used in recommendations (e.g. via existing recommendation logger), so you can analyze impact and tune weights.

---

## Implementation Outline (High Level)

1. **Schema**
   - Add optional **due_at** (or equivalent) on **instances**.
   - Add **task_horizon_days** setting (global or per-user).
   - Ensure instance has **initialized_at** (or created_at) for “time since initialized.”

2. **Urgency computation**
   - Implement **urgency score** (0–100, bounded, monotonic):
     - Linear component: time since initialized → score up to threshold.
     - If due_at set: increase toward deadline, then set **overdue** flag when past due_at.
     - Optional: lightweight “habitually procrastinated” boost from postpone/cancel-like history.
   - Expose **overdue** flag and **stale** (no due, age > task_horizon).

3. **UI**
   - **Initialized tasks list:** Red stripe/red for overdue; yellow for stale (no due, > task_horizon).
   - **Overdue popup** when a task crosses into overdue.
   - **Exclamation mark** (or similar) for overdue in list/cards.
   - **Recommendation surfaces:** Show urgency score + deadline when applicable; add urgency as searchable/weighted factor; explanation flag for LLM.
   - **Postpone flow:** Popup with reason (like cancel); persist reason and feed into scoring similarly to cancel.

4. **Recommendations**
   - Add **urgency** as a metric with **configurable weight** in ranking.
   - Default: exclude completed/cancelled; add **checkbox** “Include completed and cancelled” in recommendation UI.
   - Rudimentary cap or limit on urgency dominance (to be tuned).

5. **Routines**
   - No structural change to routine system in this task; use best judgment where routine instances need a due or urgency (e.g. optional derivation from routine_time). Full routine separation and rework is a separate pass.

6. **Config and logging**
   - **Configurable weights** for recommendation (including urgency).
   - **Logging** of recommendation events that include urgency (e.g. via recommendation_logger).

---

## Out of Scope (Noted for Later)

- Full **routine system** redesign and separate navigation/UI.
- **Cognitive profile** (alignment vs load, calibration over time).
- **Life balance** subsystem and naming (“balance” reserved).
- Deep **tooltip** optimization for recommendation scores project-wide (urgency tooltip added minimally).
- Formal **success metrics** and A/B framework (configurable weights + logging only for now).
