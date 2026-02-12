# Performance Optimization Log

Track performance improvements and remaining bottlenecks for future reference.

---

## 2026-02-12: Vectorization of `get_relief_summary()`

### Problem
Dashboard cold load was 3-5 seconds, with `get_relief_summary()` taking ~2.75 seconds due to row-by-row `.apply()` calls.

### Solution
Implemented vectorized batch versions following two-layer pattern (see `.cursor/rules/vectorization-optimization.mdc`):

1. **`calculate_grit_scores_batch()`** - Replaced row-by-row grit score calculation
2. **`calculate_productivity_scores_batch()`** - Replaced row-by-row productivity score calculation

### Results

| Function | Before | After | Improvement |
|----------|--------|-------|-------------|
| `calculate_grit_score` | 2301.91ms (4.56ms/row) | 1.56ms | **1,476x faster** |
| `calculate_productivity_score` | 109.57ms (0.22ms/row) | 88.61ms | 1.2x faster |
| **Total `get_relief_summary()`** | **2749.77ms** | **193.63ms** | **14.2x faster** |

### Current Breakdown (post-optimization)
```
calculate_productivity_scores_batch: 88.61ms (45.8%)
calculate_efficiency_score:           5.06ms (2.6%)
obstacles_scores_robust:              3.42ms (1.8%)
obstacles_scores_sensitive:           3.50ms (1.8%)
time_for_work_play:                   2.59ms (1.3%)
time_actual_for_avg:                  1.99ms (1.0%)
calculate_grit_scores_batch:          1.56ms (0.8%)
spike_amount_robust/sensitive:        0.69ms (0.3%)
```

### Files Modified
- `backend/analytics.py` - Added batch functions, updated `get_relief_summary()` to use them
- `backend/profiling.py` - New profiling utility for `.apply()` timing
- `.cursor/rules/vectorization-optimization.mdc` - New rule for two-layer pattern

---

## Current Performance Characteristics (2026-02-12)

### Dashboard (Main Page)
| Metric | Time |
|--------|------|
| Cold load (OAuth → basic UI) | ~1.0s |
| UI fully functional (metrics loaded) | +0.2-0.3s |
| Warm refresh | 0.2-0.3s |

### Analytics Page
| Metric | Time |
|--------|------|
| Full page load | ~2.8s |

---

## Remaining Bottlenecks / Future Optimization Opportunities

### 1. Productivity Score Batch (88ms)
Still the largest chunk. The date parsing loop for work/play time lookups could be optimized:
```python
for ca in df['completed_at'].tolist():
    dt = pd.to_datetime(ca)  # Expensive per-row
```
Could vectorize with `pd.to_datetime(df['completed_at'])` and batch lookups.

### 2. Analytics Page (~2.8s)
Not yet profiled. Likely candidates:
- Chart data generation (Plotly)
- Multiple analytics method calls
- Historical data aggregation

**Next step:** Add profiling to analytics page to identify hotspots.

### 3. OAuth → Basic UI (~1s)
Initial load includes:
- Authentication check
- Database connection warmup
- First-time imports
- Initial data fetch

Could investigate with broader page-level timing.

### 4. Other `.apply()` calls
Still using row-by-row for:
- `calculate_efficiency_score` (5ms - low priority)
- `obstacles_scores_robust/sensitive` (7ms combined - low priority)
- `time_for_work_play`, `time_actual_for_avg` (4ms combined - low priority)

These are minor but could be vectorized if needed.

---

## Profiling Commands

### Enable profiling at server boot
```powershell
$env:PROFILE_ANALYTICS="1"; $env:PROFILE_LOG_FILE="logs/profile.log"; python app.py
```

### Check profile output
```powershell
Get-Content logs/profile.log
```

---

## Two-Layer Pattern Reference

When vectorizing formulas:
1. **Keep** original row-by-row function as reference implementation
2. **Add** `_batch` version for production use
3. **Document** cross-references in docstrings
4. **Test** equivalence between versions

See `.cursor/rules/vectorization-optimization.mdc` for details.
