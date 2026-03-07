# Grit Score: Glossary Update and Ideal Graphs/Info

## 1. How thorough is the grit formula?

**Conclusion: The formula does not need refinement.** The implementation is already comprehensive.

The production formula in `task_aversion_app/backend/analytics.py` (`calculate_grit_score` and `calculate_grit_scores_batch`) is:

```
grit_score = base_score × persistence_factor_scaled × focus_factor_scaled × passion_factor × time_bonus × disappointment_resilience
```

- **base_score:** `completion_pct` (0–100+).
- **Persistence (0.5–1.5):** obstacle overcoming (40%), aversion resistance (30%), task repetition (20%), consistency (10%).
- **Focus (0.5–1.5):** emotion-based concentration.
- **Passion (0.5–1.5):** relief vs emotional load, dampened if completion < 100%.
- **Time bonus (1.0–3.0):** difficulty-weighted, diminishing returns, fades with repetition.
- **Disappointment resilience (0.67–1.5):** reward completing despite unmet expectations (up to 1.5×); penalize giving up (down to 0.67×).

---

## 2. Glossary text updates (unchanged)

- Bump version to 1.6; add **Disappointment Resilience** as 5th component; update main formula string; add use case line. See original plan for exact copy.

---

## 3. Overview and visualizations (updated per your specs)

### 3.1 Overview: three graphs

**1. Bar chart — 7-day averages of each factor vs total**

- X: factor names (Persistence, Focus, Passion, Time bonus, Disappointment resilience, **Total**).
- Y: 7-day average value for each (factor multipliers or contribution; total = average grit score over last 7 days).
- Purpose: Compare relative contribution of each factor to total over the last week.

**2. Line graph — 30-day trend of each factor’s influence (calibrated to total)**

- X: time (last 30 days, e.g. by day or rolling window).
- Y: each factor’s influence calibrated relative to total score (e.g. contribution share or normalized multiplier over time).
- One line per factor (persistence, focus, passion, time bonus, disappointment resilience) so users see how each component’s influence changes over the month.

**3. Pie chart — components as share of the sum**

- Same conceptual breakdown as the bar chart but as proportions: each of the five factors as a slice of the total (e.g. average contribution or share of sum of components).
- No “total” slice; just the five components summing to 100%.

**Implementation:** Add three Plotly generators (e.g. `generate_grit_overview_bars_7d`, `generate_grit_factors_line_30d`, `generate_grit_components_pie`) and register in `PLOTLY_DATA_CHARTS`. In the grit module in `analytics_glossary.py`, either show all three (e.g. in an overview section) or use one as `overview_chart` and add the other two as additional charts in that section.

---

### 3.2 Per-component theoretical charts — generate all for inspiration

Create and run the five theoretical graphic scripts so you can review the outputs for inspiration:

1. **Persistence:** multiplier vs completion count (with familiarity decay) and/or vs obstacle/aversion level. Script: `grit_score_persistence_factor.py` → `grit_score_persistence_factor.png`.
2. **Focus:** focus factor vs (positive − negative) emotion score. Script: `grit_score_focus_factor.py` → `grit_score_focus_factor.png`.
3. **Passion:** passion factor vs (relief_norm − emotional_norm). Script: `grit_score_passion_factor.py` → `grit_score_passion_factor.png`.
4. **Time bonus:** time_bonus vs time_ratio and vs completion_count (diminishing returns and fade). Script: `grit_score_time_bonus.py` → `grit_score_time_bonus.png`.
5. **Disappointment resilience:** resilience vs disappointment_factor, two curves (completion ≥ 100% vs < 100%). Script: `grit_score_disappointment_resilience.py` → `grit_score_disappointment_resilience.png`.

Place scripts in `task_aversion_app/scripts/graphic_aids/`, wire in `generate_all.py`, output to `assets/graphic_aids/`. Generate the PNGs so you can look at them for inspiration.

---

### 3.3 Data-driven charts — Option A (Plotly)

Use **Option A:** add Plotly data-driven chart generators for each of the five components (and optionally for the three overview charts). Register them in `PLOTLY_DATA_CHARTS` and add mappings in `_get_plotly_chart_key` in `analytics_glossary.py` so the glossary “Your Data” section uses these Plotly charts instead of PNG fallbacks.

---

## 4. Suggested order of work

1. **Glossary text:** Add Disappointment Resilience, update formula and version (no new scripts).
2. **Overview:** Implement the three Plotly charts (bar 7-day, line 30-day, pie components) and add to grit module.
3. **Theoretical scripts:** Implement all five per-component scripts, wire in `generate_all.py`, generate PNGs for review.
4. **Data-driven:** Add five (and optionally three) Plotly generators, register in `PLOTLY_DATA_CHARTS` and `_get_plotly_chart_key`.
