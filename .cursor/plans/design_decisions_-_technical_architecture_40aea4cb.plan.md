---
name: Design Decisions - Technical Architecture
overview: Focused plan for resolving technical design decisions including scale standardization, formula selection, recommendation system architecture, score system integration, and storage backend strategy.
todos: []
---

# Design Decisions - Technical Architecture

## Purpose

This plan addresses technical design decisions that impact system architecture, code maintainability, and implementation patterns. These decisions focus on standardizing scales, selecting formulas, unifying recommendation logic, integrating scores, and completing storage migration.

## Decision Areas

### 1. Scale Standardization (0-10 vs 0-100)

**Current State:**

- System transitioning from 0-10 to 0-100 scale
- Scaling logic scattered across codebase
- Conditional scaling in tooltips, instance manager, analytics
- Risk of double-scaling values

**Decision Needed:**

- Establish 0-100 as canonical scale throughout system
- Remove all scaling logic or centralize it
- Determine migration strategy for existing 0-10 data

**Options:**

1. **Complete Migration**: Convert all 0-10 data to 0-100, remove scaling logic
2. **Centralized Scaling**: Keep single scaling function, remove scattered logic
3. **Data Layer Scaling**: Scale only at data load time, store as 0-100

**Recommendation**: Complete migration - convert all data to 0-100, remove all scaling logic**Implementation:**

- Run one-time migration script to convert all CSV data
- Update database schema to enforce 0-100 range
- Remove all `scale_values_10_to_100()` and conditional scaling
- Update all formulas to assume 0-100 input
- Add validation to prevent 0-10 values in new data

**Files to Modify:**

- `backend/instance_manager.py` - Remove `scale_values_10_to_100()` method
- `ui/dashboard.py` - Remove conditional scaling in `format_colored_tooltip()`
- `backend/analytics.py` - Remove all scaling logic, assume 0-100
- Create migration script: `scripts/scale_migration_10_to_100.py`

---

### 2. Formula Selection (7 Aversion Formulas)

**Current State:**

- 7 aversion formula variants in analytics system
- All produce identical results when data lacks variation
- Unclear which formula is primary
- No documentation on when to use each

**Formulas Identified:**

1. `expected_only` - Uses only expected relief
2. `actual_only` - Uses only actual relief
3. `minimum` - Uses min(expected, actual)
4. `average` - Uses (expected + actual) / 2
5. `net_penalty` - Bonus for overcoming disappointment
6. `net_bonus` - Different approach to net relief
7. `net_weighted` - Weighted by net_relief

**Decision Needed:**

- Which formula should be primary/default?
- How to document other formulas?
- Should all formulas remain available or deprecate some?

**Options:**

1. **Single Primary**: Choose one formula, mark others experimental
2. **Keep All**: Maintain all formulas but clearly document primary
3. **Deprecate Some**: Remove less useful formulas, keep 2-3

**Recommendation**: Single primary (`net_weighted` or `average`) + document others as experimental**Rationale:**

- `net_weighted` accounts for both expected and actual with variation
- `average` is simple and balanced
- Other formulas are edge cases or alternatives

**Implementation:**

- Set primary formula in `backend/analytics.py`
- Add `AVERSION_FORMULA` constant or config
- Document other formulas in `docs/aversion_formulas.md`
- Update analytics UI to show primary formula prominently
- Make other formulas available via advanced settings

**Files to Modify:**

- `backend/analytics.py` - Define primary formula constant
- `ui/analytics_page.py` - Show primary formula prominently
- `docs/aversion_formulas.md` - Document all formulas
- `task_aversion_app/AVERSION_FORMULAS_SUMMARY.md` - Update with decision

---

### 3. Recommendation System Architecture

**Current State:**

- Multiple recommendation methods: `recommendations()`, `recommendations_by_category()`
- Different strategies (rule-based, metric-based, category-based)
- Unclear priority or when each is used
- Search-based metric filtering adds complexity

**Decision Needed:**

- Unified recommendation engine or separate methods?
- Clear priority rules for recommendation strategies
- How to integrate different recommendation types?

**Options:**

1. **Unified Engine**: Single recommendation method with strategy parameter
2. **Layered Approach**: Primary strategy with fallbacks
3. **Separate Methods**: Keep separate but document when to use each

**Recommendation**: Unified engine with strategy parameter + layered fallbacks**Implementation:**

- Create `get_recommendations(strategy, metrics, filters)` method
- Strategy priority:

1. Metric-based (if metrics provided)
2. Category-based (if category filter)
3. Rule-based (default)

- Preserve existing methods as wrappers for backward compatibility
- Add recommendation reasoning to return values

**Files to Modify:**

- `backend/analytics.py` - Create unified recommendation method
- `ui/dashboard.py` - Use unified method with presets
- `backend/analytics.py` - Add recommendation reasoning

---

### 4. Score System Integration

**Current State:**

- Multiple orthogonal scores: Productivity, Grit, Difficulty Bonus, Execution, Composite
- Composite score exists but execution score is "orthogonal" and optional
- Unclear how scores should be combined
- No clear hierarchy of which scores matter most

**Decision Needed:**

- How should scores be integrated into composite score?
- Should execution score be included?
- What should be the score hierarchy/priority?

**Options:**

1. **All Scores in Composite**: Include all scores with weights
2. **Tiered System**: Primary scores (composite), secondary scores (separate)
3. **Selective Integration**: Some scores in composite, others standalone

**Recommendation**: Tiered system - primary scores in composite, secondary scores available separately**Primary Scores (in Composite):**

- Completion Percentage
- Persistence Multiplier
- Time Tracking Consistency
- Overall Improvement Ratio
- Difficulty Bonus
- Execution Score (optional, default off)

**Secondary Scores (separate):**

- Productivity Score
- Grit Score
- Stress Efficiency
- Net Wellbeing
- Behavioral Score

**Implementation:**

- Update composite score to include execution score (optional)
- Define score categories in analytics
- Update dashboard to show primary scores prominently
- Add secondary scores to advanced analytics section

**Files to Modify:**

- `backend/analytics.py` - Update `calculate_composite_score()` method
- `ui/composite_score_page.py` - Add execution score option
- `ui/dashboard.py` - Show primary vs secondary scores
- `backend/analytics.py` - Add score category constants

---

### 5. Storage Backend Strategy

**Current State:**

- Dual CSV/database support with feature flags
- Extensive fallback logic in managers
- Migration incomplete - CSV still default
- Code complexity from dual-path logic

**Decision Needed:**

- Complete migration to database or commit to dual support?
- Simplify dual-path code or maintain current complexity?
- When to remove CSV support?

**Options:**

1. **Complete Migration**: Remove CSV support, database only
2. **Dual Support**: Keep both, simplify code with better abstraction
3. **Database Default**: Make database default, CSV as fallback only

**Recommendation**: Database default with CSV fallback (simplified)**Implementation:**

- Make database default when `DATABASE_URL` set
- Simplify manager classes with better abstraction layer
- Create `StorageBackend` interface/abstract class
- Reduce code duplication between CSV and database paths
- Keep CSV fallback for development/backup scenarios

**Files to Modify:**

- `backend/task_manager.py` - Simplify dual-path logic
- `backend/instance_manager.py` - Simplify dual-path logic
- `backend/emotion_manager.py` - Simplify dual-path logic
- Create `backend/storage_backend.py` - Abstract storage interface
- Update migration scripts in `SQLite_migration/`

**Related Plans:**

- See `.cursor/plans/cloud-deployment-database-migration-plan-0b5717d2.plan.md`
- See `.cursor/plans/MIGRATION_PLANS_SUMMARY.md`

---

## Implementation Order

1. **Scale Standardization** - Foundation for all formulas and metrics
2. **Storage Backend Strategy** - Simplifies codebase
3. **Formula Selection** - Reduces maintenance overhead
4. **Score System Integration** - Clarifies metric hierarchy
5. **Recommendation System Architecture** - Uses improved scores

## Technical Debt Reduction

### Code Complexity

- Remove scattered scaling logic → Single source of truth
- Simplify dual-path storage → Better abstraction
- Unify recommendation methods → Clearer API

### Maintainability

- Single primary formula → Less code to maintain
- Clear score hierarchy → Easier to understand
- Unified recommendations → Single place to modify

### Data Consistency

- Single scale (0-100) → No scaling bugs
- Database default → Better data integrity
- Clear formula selection → Consistent results

## Success Criteria

- All values stored and processed as 0-100 scale
- Single primary aversion formula with others documented
- Unified recommendation engine with clear strategy priority
- Tiered score system (primary in composite, secondary separate)
- Database as default with simplified CSV fallback
- Reduced code duplication in storage backends
- Clear documentation of all technical decisions

## Related Plans

- **Design Decisions - Comprehensive Overview**: Overall roadmap
- **Design Decisions - User-Facing Issues**: User experience decisions