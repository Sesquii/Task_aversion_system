---
name: Design Decisions - User-Facing Issues
overview: Focused plan for resolving design decisions that directly impact user experience, including data quality, metric hierarchy, relief score understanding, and aversion tracking requirements.
todos: []
isProject: false
---

# Design Decisions - User-Facing Issues

## Purpose

This plan addresses design decisions that directly impact how users interact with and understand the system. These decisions focus on improving data quality, reducing confusion, and making the interface more actionable.

## Decision Areas

### 1. Expected vs Actual Relief Understanding

**Current State:**

- All 65 completed instances have identical expected and actual relief values
- Users may not understand the difference between prediction (expected) and outcome (actual)
- UI may be pre-filling actual relief with expected relief

**Decision Needed:**

- How to clearly communicate the difference between expected and actual relief
- Whether to add validation warnings when values are identical
- How to improve the completion form to encourage accurate actual relief entry

**Options:**

1. **Educational Approach**: Add tooltips/help text explaining expected vs actual
2. **Validation Warning**: Warn when actual exactly matches expected (unless intentional)
3. **UI Separation**: Clearly separate expected (shown at initialization) from actual (entered at completion)
4. **Default Behavior**: Don't pre-fill actual relief with expected value

**Recommendation**: Combine all four - education + validation + UI separation + no pre-fill**Files to Modify:**

- `ui/complete_task.py` - Add validation and UI improvements
- `ui/initialize_task.py` - Show expected relief clearly
- `ui/analytics_page.py` - Add note when formulas identical due to data uniformity

---

### 2. Metric Hierarchy & Display

**Current State:**

- Dashboard shows many metrics (productivity, grit, efficiency, behavioral, net wellbeing, etc.)
- Recommendation system has 11 metric options
- No clear guidance on which metrics matter most

**Decision Needed:**

- Which metrics should be primary (always visible)?
- Which metrics should be secondary (available but not prominent)?
- How to organize metrics in the dashboard?

**Options:**

1. **Primary Metrics View**: Show 3-5 core metrics prominently
2. **Advanced Metrics Section**: Collapsible section for additional metrics
3. **Metric Categories**: Group by type (performance, wellbeing, efficiency)
4. **User Customizable**: Let users choose their primary metrics

**Recommendation**: Primary metrics view (3-5 core) + advanced section + categories**Primary Metrics Candidates:**

- Weekly Productivity Time
- Weekly Relief Score
- Net Relief Points
- Obstacles Overcome (Robust)
- Completion Rate

**Files to Modify:**

- `ui/dashboard.py` - Reorganize metric display
- `ui/analytics_page.py` - Add metric hierarchy
- `backend/analytics.py` - Ensure primary metrics are easily accessible

---

### 3. Aversion Tracking Requirements

**Current State:**

- Only 8 instances have predicted aversion data
- Aversion is central to the system but underutilized
- Low aversion-stress correlation (r=0.20 vs expected 0.35-0.45) due to missing data

**Decision Needed:**

- Should aversion be required at initialization?
- Should we provide strong defaults based on task history?
- How to encourage users to provide aversion data?

**Options:**

1. **Required Field**: Make aversion mandatory at initialization
2. **Smart Defaults**: Pre-fill with previous average or baseline for task
3. **Optional with Encouragement**: Keep optional but show value of providing it
4. **Progressive Disclosure**: Start optional, require after N tasks

**Recommendation**: Smart defaults + optional with strong encouragement**Implementation:**

- Use `get_previous_aversion_average()` or `get_baseline_aversion_robust()` to pre-fill
- Show tooltip explaining why aversion helps recommendations
- Track aversion completion rate and show impact

**Files to Modify:**

- `ui/initialize_task.py` - Add default aversion with explanation
- `backend/instance_manager.py` - Ensure baseline methods are used
- `ui/dashboard.py` - Show aversion completion rate

---

### 4. Stress Measurement Model (User Perspective)

**Current State:**

- System combines cognitive, emotional, physical into single stress metric
- Documentation recommends tracking dimensions separately
- Unclear whether combined or separate is preferred for users

**Decision Needed:**

- Should users see combined stress or separate dimensions?
- How to present both without overwhelming users?

**Options:**

1. **Combined Only**: Show single stress metric (simpler)
2. **Separate Only**: Show three dimensions separately (more detailed)
3. **Both**: Combined for overview, separate in details/analytics
4. **User Choice**: Let users toggle between views

**Recommendation**: Both - combined for dashboard, separate in analytics**Implementation:**

- Dashboard: Show combined stress level
- Analytics: Show separate dimension trends
- Tooltips: Show breakdown when hovering over combined metric

**Files to Modify:**

- `ui/dashboard.py` - Keep combined stress display
- `ui/analytics_page.py` - Add dimension-specific charts
- `backend/analytics.py` - Ensure dimension data is accessible

---

### 5. Data Quality Validation & User Education

**Current State:**

- System detects data quality issues (expected == actual relief) but doesn't enforce correction
- No user education about why data quality matters
- Formulas work correctly but produce identical results

**Decision Needed:**

- How to validate data quality without being intrusive?
- How to educate users about data quality importance?
- When to show warnings vs errors?

**Options:**

1. **Soft Validation**: Show info messages, not errors
2. **Educational Tooltips**: Explain why variation in data helps
3. **Data Quality Dashboard**: Show data quality metrics
4. **Progressive Guidance**: Start with education, add validation over time

**Recommendation**: Educational tooltips + soft validation + data quality metrics**Implementation:**

- Add tooltip to relief fields explaining expected vs actual
- Show info message when actual exactly matches expected (not error)
- Add data quality section to analytics showing variation metrics

**Files to Modify:**

- `ui/complete_task.py` - Add validation messages
- `ui/analytics_page.py` - Add data quality section
- `backend/analytics.py` - Add data quality metrics calculation

---

### 6. Recommendation System Clarity

**Current State:**

- Multiple recommendation strategies (rule-based, metric-based, category-based)
- Users may not understand why certain tasks are recommended
- Search-based metric filtering may be confusing

**Decision Needed:**

- How to explain why tasks are recommended?
- How to simplify metric selection?
- Should recommendations show reasoning?

**Options:**

1. **Show Reasoning**: Display why each task is recommended
2. **Simplify Metrics**: Reduce from 11 to 3-5 most important
3. **Preset Combinations**: Offer "Quick wins", "High relief", "Low stress" presets
4. **Progressive Disclosure**: Start simple, allow advanced filtering

**Recommendation**: Preset combinations + show reasoning + simplified metrics**Implementation:**

- Add preset buttons: "Quick Wins", "High Relief", "Low Stress", "Balanced"
- Show recommendation reason: "Recommended for high relief score"
- Reduce default metrics to 3-5 most impactful

**Files to Modify:**

- `ui/dashboard.py` - Add preset recommendation buttons
- `backend/analytics.py` - Add recommendation reasoning
- `ui/dashboard.py` - Simplify metric selection UI

---

## Implementation Order

1. **Expected vs Actual Relief** - Foundation for data quality
2. **Aversion Tracking** - Core feature improvement
3. **Metric Hierarchy** - Reduces cognitive load
4. **Stress Measurement Model** - Clarifies display strategy
5. **Data Quality Validation** - Builds on relief understanding
6. **Recommendation System Clarity** - Uses improved data

## Success Criteria

- Users understand difference between expected and actual relief
- Aversion data completion rate > 80%
- Primary metrics clearly visible, advanced metrics accessible
- Combined stress shown on dashboard, separate dimensions in analytics
- Data quality warnings shown without being intrusive
- Recommendations include clear reasoning

## Related Plans

- **Design Decisions - Comprehensive Overview**: Overall roadmap