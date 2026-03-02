---
name: Sleep score integration plan
overview: Sleep score 0-100 with duration vs target, consistency/fragmentation (tied to relief-per-hour), variation, relief-per-hour; configurable target hours; life balance 7d avg; analytics Sleep card + experimental sleep-tasks emotion card; prototype variants for insomnia (debt/credit) and hypersomnia (stricter over + cap).
todos: []
isProject: false
---

# Sleep Score Integration (Refined Plan)

---

## 1. Locked-in decisions


| Decision                        | Choice                                                                                                                                                                                             |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Scale**                       | 0-100; 100 = target hours consistently most days                                                                                                                                                   |
| **Duration vs target**          | Over target = slight penalty; under = penalty; outlier-robust                                                                                                                                      |
| **Consistency / fragmentation** | Weight by **relief-per-hour first**: fragmentation reduces score more when relief-per-hour is lower (relief-per-hour is higher priority than raw fragmentation)                                    |
| **Time of day**                 | No night vs day bonus                                                                                                                                                                              |
| **Data source**                 | Logged tasks only for now; wearables later                                                                                                                                                         |
| **Variation**                   | Factor: max and average day-to-day difference in total sleep hours over period                                                                                                                     |
| **Relief per hour**             | **(c) Both**: display on Sleep card and influence 0-100 score (e.g. small bonus for high relief-per-hour)                                                                                          |
| **Life balance**                | 7-day average sleep score; use primary formula; avoid double-counting                                                                                                                              |
| **Target hours**                | **Configurable in settings.** Main setting: target hours for **work, sleep, play, self care** (for now). Note: per-template or per-job target hours could be added later depending on granularity. |
| **Sleep vs emotion**            | Track the **10 most common emotions associated with sleep** (not only tired/rested)                                                                                                                |
| **Emotion UI**                  | For now: **experimental secondary card** = "Emotion trends for sleep tasks only." A full **Emotion trends** section in analytics may be planned and built out separately later.                    |
| **Recommendations**             | Defer until formula refined                                                                                                                                                                        |


---

## 2. Score variants (prototype in initial plan)

### 2.1 Default (0-100)

Standard formula: duration vs target, outlier-robust penalties, consistency (fragmentation weighted by relief-per-hour), variation, relief-per-hour bonus.

### 2.2 Insomnia-style variant (debt/credit accumulation)

- **Sleep debt** builds when under target; **sleep credit** when over target; both carry across days.
- Score reflects paying down debt / building credit (similar in spirit to relief score accumulation).
- Prototype this with the initial implementation; postpone only if implementation or tuning becomes too complex without first-hand insomnia experience.

### 2.3 Hypersomnia-style variant (A+B)

- **(A)** Stricter penalty for over target (discourage excess sleep).
- **(B)** Reward for staying at or below a **cap** (e.g. "ideal max" hours); treat **over-cap** as worse than over-target.
- User has hypersomnia; this variant supports that use case. Prototype with initial plan.

---

## 3. Touchpoints and implementation notes

### 3.1 Settings: target hours

- Add main **target hours** setting: **work, sleep, play, self care** (e.g. in user settings or analytics/config).
- Note in code/docs: per-template or per-job target hours could be added later for finer granularity.

### 3.2 Task-type multiplier — `get_task_type_multiplier`

**Location:** [task_aversion_app/backend/analytics.py](task_aversion_app/backend/analytics.py) (lines 491-514)

- Keep placeholder (1.0) until per-day sleep score is available; then optionally tie points to sleep score.

### 3.3 Productivity score — `calculate_productivity_score` and batch

**Locations:** Row ~697-698; vectorized ~956-958 in [task_aversion_app/backend/analytics.py](task_aversion_app/backend/analytics.py)

- Replace `score = completion_pct` for sleep with per-day sleep score from primary formula (and chosen variant if applicable).
- Same logic in row and batch.

### 3.4 Life balance — `get_life_balance_metrics`

**Location:** [task_aversion_app/backend/analytics.py](task_aversion_app/backend/analytics.py) (lines 4462-4491)

- Add **7-day average sleep score** (e.g. `sleep_score_7d_avg`); avoid double-counting with existing life-balance inputs.

### 3.5 Analytics UI

- **Sleep card:** Score, trend, duration vs target, variation, fragmentation, relief-per-hour; **sleep vs emotions** using **10 most common sleep-associated emotions** (not only tired/rested).
- **Experimental secondary card:** "Emotion trends for sleep tasks only" (emotion values over time for tasks with task_type = sleep).
- **Monitored metrics:** Add sleep score to the list in `open_metrics_config_dialog()` ([task_aversion_app/ui/dashboard.py](task_aversion_app/ui/dashboard.py)) and wire value/history like other CALCULATED_METRICS.
- **Later:** Consider a dedicated **Emotion trends** section in analytics (separate from Sleep card); plan and orchestrate when ready.

---

## 4. Component factors (build now)

1. **Daily total sleep (minutes/hours)** — From completed sleep tasks per day (handles naps/fragmentation by design).
2. **Duration vs target (per day)** — Using configurable target hours; deviations for over/under penalties; outlier-robust.
3. **Fragmentation** — Higher priority when **relief-per-hour is low**: fragmentation reduces score more in that case; when relief-per-hour is high, fragmentation matters less.
4. **Sleep variation** — Max and average day-to-day change in total sleep hours over the period.
5. **Relief per hour** — Per task then aggregated; **(c)** both display and input to 0-100 score (e.g. small bonus).
6. **7-day (or N-day) aggregate** — Single 0-100 from per-day components for life balance and dashboard.
7. **Insomnia variant:** Debt/credit accumulation across days; score reflects debt pay-down and credit.
8. **Hypersomnia variant:** Stricter over-target penalty + cap (reward at or below cap; over-cap worse than over-target).

---

## 5. Derived metrics / later work

- Sleep score trend (time series); sleep vs 10 sleep-associated emotions; sleep consistency index; recommendations with sleep context; wearables input; full **Emotion trends** analytics section.

---

## 6. Implementation order

1. **Settings:** Target hours for work, sleep, play, self care (storage + UI).
2. **Backend:** Component factors (daily total, vs target, outlier-robust penalty, fragmentation tied to relief-per-hour, variation, relief-per-hour).
3. **Backend:** Primary 0-100 formula + 7d average; optionally **insomnia** (debt/credit) and **hypersomnia** (stricter over + cap) as selectable variants.
4. **Backend:** Integrate into `get_life_balance_metrics`, `calculate_productivity_score` / batch; avoid double-counting.
5. **Analytics:** Sleep card (score, trend, vs target, variation, fragmentation, relief-per-hour, sleep vs 10 emotions).
6. **Analytics:** Experimental card "Emotion trends for sleep tasks only."
7. **Monitored metrics:** Add sleep score to config list and wire value/history.
8. **Optional:** `get_task_type_multiplier` sleep branch; recommendations when formula is stable.

---

## 7. Features and plans to schedule later

- **Full Emotion trends section** in analytics (dedicated section, not just sleep tasks).
- **Per-template or per-job target hours** (if you want that granularity).
- **Recommendations** with sleep as filter or metric (after formula is refined).
- **Wearables** compatibility for sleep data.
- **get_task_type_multiplier** sleep branch (points depend on sleep score).

If the insomnia or hypersomnia variant proves too complex to tune without more real-world use, document and postpone that variant and keep the default formula in place.