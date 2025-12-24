---
name: Design Decisions - Comprehensive Overview
overview: High-level overview of all pending design decisions across user experience and technical architecture, showing how they interconnect and providing a roadmap for systematic resolution.
todos: []
---

# Design Decisions -

Comprehensive Overview

## Purpose

This plan provides a high-level roadmap for resolving pending design decisions identified in the system analysis. It connects user-facing and technical issues, showing how decisions in one area affect others.

## Decision Areas

### 1. Data Quality & User Understanding

- **Issue**: Users may not understand expected vs actual relief, leading to identical values
- **Impact**: Formulas work correctly but produce identical results
- **Connection**: Affects formula selection (if data lacks variation, formula choice doesn't matter)

### 2. Scale Standardization

- **Issue**: System transitioning from 0-10 to 0-100 with scattered scaling logic
- **Impact**: Risk of double-scaling, confusion about canonical scale
- **Connection**: Affects all formulas, metrics, and user displays

### 3. Formula Selection

- **Issue**: 7 aversion formula variants with unclear selection criteria
- **Impact**: Maintenance overhead, user confusion
- **Connection**: Depends on data quality (if data uniform, all formulas identical)

### 4. Recommendation System Architecture

- **Issue**: Multiple recommendation strategies without clear priority
- **Impact**: Unpredictable recommendations
- **Connection**: Should integrate with score system decisions

### 5. Score System Integration

- **Issue**: Multiple orthogonal scores without clear combination strategy
- **Impact**: Unclear which scores matter most
- **Connection**: Affects recommendation system and metric hierarchy

### 6. Storage Backend Strategy

- **Issue**: Dual CSV/database support creates complexity, migration incomplete
- **Impact**: Code complexity, potential data inconsistency
- **Connection**: Affects all data access patterns

### 7. Metric Hierarchy & Display

- **Issue**: Too many competing metrics without clear guidance
- **Impact**: Analysis paralysis for users
- **Connection**: Should align with score system integration decisions

### 8. Stress Measurement Model

- **Issue**: Combined vs separate dimension tracking unclear
- **Impact**: Unclear whether combined or separate is preferred
- **Connection**: Affects analytics display and user understanding

### 9. Aversion Tracking Requirements

- **Issue**: Core feature but only 8 instances have predicted aversion data
- **Impact**: Recommendations less effective, core feature underutilized
- **Connection**: Affects data quality and formula effectiveness

### 10. User Education & Validation

- **Issue**: System detects data quality issues but doesn't enforce correction
- **Impact**: Formulas work but produce identical results
- **Connection**: Enables all other improvements

## Decision Dependencies

```javascript
Data Quality & User Understanding
    ↓
Formula Selection (depends on data variation)
    ↓
Score System Integration
    ↓
Recommendation System Architecture
    ↓
Metric Hierarchy & Display
```



```javascript
Scale Standardization
    ↓
All Formulas & Metrics
    ↓
User Displays
```



```javascript
Storage Backend Strategy
    ↓
All Data Access
    ↓
Analytics & Recommendations
```



## Implementation Approach

1. **Foundation First**: Resolve scale standardization and storage backend strategy
2. **Data Quality**: Improve user understanding and validation
3. **Formula & Score Decisions**: Select formulas and define score integration
4. **User Experience**: Implement metric hierarchy and recommendations
5. **Polish**: Stress measurement model and aversion tracking requirements

## Success Criteria

- Single canonical scale (0-100) throughout system
- Clear primary formula with others documented as experimental
- Unified recommendation engine with clear priority rules
- Defined score hierarchy with integration strategy
- User-facing metric hierarchy (primary vs advanced)
- Complete database migration or committed dual support
- Data quality validation with user education
- Clear stress measurement model (combined + separate)
- Aversion tracking with strong defaults or requirements

## Related Plans

- **Design Decisions - User-Facing Issues**: Detailed decisions for user experience improvements
- **Design Decisions - Technical Architecture**: Detailed decisions for system design and implementation
- **Score Calibration System** (`.cursor/plans/score_calibration_system_d8f3a6d0.plan.md`): Existing plan for calibrating score weights
- **Cloud Deployment & Database Migration** (`.cursor/plans/cloud-deployment-database-migration-plan-0b5717d2.plan.md`): Existing plan for storage migration
- **Migration Plans Summary** (`.cursor/plans/MIGRATION_PLANS_SUMMARY.md`): Current migration status and approach

## Decision Priority Framework

### Phase 1: Foundation (Blocks Other Work)

- Scale Standardization
- Storage Backend Strategy

### Phase 2: Data Quality (Enables Formula Work)

- Data Quality & User Understanding
- User Education & Validation
- Aversion Tracking Requirements

### Phase 3: Core Logic (Builds on Data Quality)

- Formula Selection
- Score System Integration

### Phase 4: User Experience (Uses Core Logic)

- Recommendation System Architecture
- Metric Hierarchy & Display
- Stress Measurement Model

## Decision Matrix

| Decision Area | User Impact | Technical Impact | Blocking | Dependencies |

|--------------|-------------|------------------|----------|--------------|

| Scale Standardization | Medium | High | High | None |

| Storage Backend Strategy | Low | High | High | None |

| Data Quality & User Understanding | High | Medium | Medium | None |

| User Education & Validation | High | Low | Medium | Data Quality |

| Aversion Tracking Requirements | High | Low | Medium | None |

| Formula Selection | Medium | Medium | Low | Data Quality |

| Score System Integration | Medium | High | Medium | Formula Selection |

| Recommendation System Architecture | High | Medium | Low | Score Integration |

| Metric Hierarchy & Display | High | Low | Low | Score Integration |

| Stress Measurement Model | Medium | Low | Low | None |

## Implementation Timeline Suggestion

### Week 1-2: Foundation

- Resolve scale standardization (0-100 canonical)
- Complete or commit to storage backend strategy

### Week 3-4: Data Quality

- Implement user education for expected vs actual relief
- Add data quality validation (soft warnings)
- Improve aversion tracking with defaults

### Week 5-6: Core Logic

- Select primary aversion formula
- Define score system integration strategy
- Document experimental formulas

### Week 7-8: User Experience

- Implement unified recommendation engine
- Create metric hierarchy (primary vs advanced)
- Clarify stress measurement model (combined + separate)

## Notes

- All decisions should be documented in decision logs
- No urgency assigned - work at comfortable pace
- Each decision can be made independently within its phase
- Technical decisions should consider user-facing impact