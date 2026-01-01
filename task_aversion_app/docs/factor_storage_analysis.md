# Factor Storage Analysis: Stored vs Derived

## Current State

### Database Schema
- `net_relief` has a database column (`Column(Float)`) but is **NOT actively populated**
- `serendipity_factor` and `disappointment_factor` have **NO database columns**
- Both are currently **derived on-the-fly** in `analytics.py` → `_load_instances()`

### Current Pattern
- **Raw data** (from JSON): `expected_relief`, `actual_relief` → stored in `predicted`/`actual` JSON columns
- **Extracted attributes**: `relief_score`, `cognitive_load`, etc. → stored in dedicated columns
- **Calculated metrics**: `net_relief`, `serendipity_factor`, `disappointment_factor` → **derived on-the-fly**

---

## Option 1: Store Factors in Database (Hardcode)

### Implementation
Add columns to `TaskInstance` model:
```python
serendipity_factor = Column(Float, default=None, nullable=True)
disappointment_factor = Column(Float, default=None, nullable=True)
```

Calculate and store when instance is completed:
```python
# In complete_instance() or _update_attributes_from_payload()
expected_relief = predicted_dict.get('expected_relief')
actual_relief = actual_dict.get('actual_relief')
if expected_relief is not None and actual_relief is not None:
    net_relief = actual_relief - expected_relief
    instance.serendipity_factor = max(0.0, net_relief)
    instance.disappointment_factor = max(0.0, -net_relief)
```

### Pros ✅
1. **Performance**: Faster queries - no calculation needed
   - Can filter/sort directly: `WHERE serendipity_factor > 20`
   - Can index for fast lookups
   - No need to load all data to calculate

2. **Consistency**: Values calculated once, stored forever
   - Historical consistency (if formula changes, old values preserved)
   - Same value every time you query (no recalculation variance)

3. **Query Flexibility**: Can query factors directly
   ```sql
   SELECT * FROM task_instances WHERE serendipity_factor > 15
   SELECT AVG(serendipity_factor) FROM task_instances WHERE completed_at > '2024-01-01'
   ```

4. **Data Integrity**: Single source of truth
   - No risk of different calculations producing different results
   - Easier to audit/debug (value is in database)

5. **Backward Compatibility**: Matches pattern of other stored scores
   - `procrastination_score`, `proactive_score`, `behavioral_score` are stored
   - `net_relief` column exists (just not populated)

### Cons ❌
1. **Storage Space**: Minimal (2 Float columns = ~16 bytes per row)
   - For 10,000 instances: ~160 KB (negligible)

2. **Maintenance Overhead**: Must update when source data changes
   - If `expected_relief` or `actual_relief` is updated, must recalculate factors
   - Need migration script if formula changes

3. **Data Synchronization Risk**: Could become stale
   - If calculation logic changes, old data has old formula
   - Need to decide: recalculate all historical data or keep as-is?

4. **Complexity**: More code to maintain
   - Must calculate on write (completion)
   - Must handle updates if source data changes
   - Need migration scripts for existing data

---

## Option 2: Derive Factors On-The-Fly (Current Approach)

### Implementation
Calculate in `analytics.py` → `_load_instances()`:
```python
df['net_relief'] = df['relief_score_numeric'] - df['expected_relief']
df['serendipity_factor'] = df['net_relief'].apply(lambda x: max(0.0, float(x)) if pd.notna(x) else 0.0)
df['disappointment_factor'] = df['net_relief'].apply(lambda x: max(0.0, -float(x)) if pd.notna(x) else 0.0)
```

### Pros ✅
1. **Always Current**: Uses latest formula automatically
   - Formula changes apply to all data immediately
   - No risk of stale data

2. **Simplicity**: Less code to maintain
   - No write-time calculation
   - No update logic needed
   - No migration scripts

3. **Flexibility**: Easy to experiment with formulas
   - Change formula, all data recalculates
   - No database migrations needed

4. **Single Source of Truth**: Formula is in one place
   - No risk of write-time vs read-time calculation mismatch

### Cons ❌
1. **Performance**: Slower queries
   - Must load all data to calculate
   - Can't filter by factor without loading everything
   - Must calculate for every row every time

2. **No Direct Queries**: Can't query factors directly
   ```sql
   -- NOT POSSIBLE:
   SELECT * FROM task_instances WHERE serendipity_factor > 15
   -- Must load all, calculate, then filter in Python
   ```

3. **Calculation Overhead**: Repeated calculations
   - Same calculation done multiple times if data accessed multiple times
   - No caching (unless implemented separately)

4. **Inconsistency Risk**: Different calculations could produce different results
   - If formula changes between calls, results differ
   - Harder to debug (calculation happens at read time)

---

## Comparison Table

| Aspect | Stored (Hardcode) | Derived (On-The-Fly) |
|--------|------------------|---------------------|
| **Query Performance** | ✅ Fast (indexed) | ❌ Slow (must load all) |
| **Filter/Sort by Factor** | ✅ Direct SQL | ❌ Must load all first |
| **Storage Space** | ~16 bytes/row | 0 bytes |
| **Code Complexity** | ❌ Higher (write logic) | ✅ Lower (read logic) |
| **Formula Changes** | ❌ Need migration | ✅ Automatic |
| **Data Consistency** | ✅ Stable (calculated once) | ⚠️ Can vary (recalculated) |
| **Historical Accuracy** | ✅ Preserves old formula | ⚠️ Applies new formula to old data |
| **Maintenance** | ❌ Update on write | ✅ Calculate on read |
| **Debugging** | ✅ Value in DB | ❌ Must trace calculation |

---

## Recommendation: **Hybrid Approach** (Best of Both Worlds)

### Store Factors, But Make Them Optional

1. **Add columns to database** (for performance)
2. **Calculate on write** (when instance completed)
3. **Recalculate on read if missing** (backward compatibility)
4. **Allow formula updates** (recalculate all if needed)

### Implementation Pattern

```python
# In complete_instance() - calculate and store
def _calculate_factors(instance):
    """Calculate factors from expected/actual relief."""
    expected = instance.predicted.get('expected_relief')
    actual = instance.actual.get('actual_relief')
    if expected is not None and actual is not None:
        net = actual - expected
        instance.net_relief = net
        instance.serendipity_factor = max(0.0, net)
        instance.disappointment_factor = max(0.0, -net)
    return instance

# In _load_instances() - use stored if available, else calculate
def _load_instances(self):
    # ... load data ...
    
    # Use stored factors if available, else calculate
    if 'serendipity_factor' in df.columns and df['serendipity_factor'].notna().any():
        # Use stored values
        df['serendipity_factor'] = pd.to_numeric(df['serendipity_factor'], errors='coerce')
    else:
        # Calculate on-the-fly (for backward compatibility)
        df['net_relief'] = df['relief_score_numeric'] - df['expected_relief']
        df['serendipity_factor'] = df['net_relief'].apply(lambda x: max(0.0, float(x)) if pd.notna(x) else 0.0)
        df['disappointment_factor'] = df['net_relief'].apply(lambda x: max(0.0, -float(x)) if pd.notna(x) else 0.0)
```

### Benefits
- ✅ **Performance**: Fast queries when factors are stored
- ✅ **Backward Compatibility**: Works with old data (calculates if missing)
- ✅ **Flexibility**: Can recalculate all if formula changes
- ✅ **Consistency**: Same calculation logic in both places
- ✅ **Migration Path**: Gradual migration (calculate on write, use stored on read)

---

## Decision Factors

### Choose **Stored** if:
- You need to query/filter by factors frequently
- Performance is critical (large datasets)
- You want historical consistency (preserve old formula results)
- You're building analytics dashboards that filter by factors

### Choose **Derived** if:
- You're still experimenting with formulas
- Data volume is small (< 10,000 instances)
- You want maximum flexibility
- You prefer simpler codebase

### Choose **Hybrid** if:
- You want both performance and flexibility
- You have existing data (backward compatibility needed)
- You're migrating from CSV to database
- You want gradual optimization

---

## Current System Context

### Existing Pattern
- **Scores** (`procrastination_score`, `proactive_score`, `behavioral_score`) → **STORED**
- **Net relief** → Column exists but **NOT POPULATED** (currently derived)
- **Factors** → **DERIVED** (no columns exist)

### Recommendation for This System
**Store factors** because:
1. Matches existing pattern (scores are stored)
2. `net_relief` column already exists (just needs population)
3. Analytics modules will query by factors (performance benefit)
4. Formula is stable (simple `max(0, net_relief)` calculation)
5. Small storage cost, large performance benefit

### Migration Strategy
1. Add `serendipity_factor` and `disappointment_factor` columns
2. Calculate on write (in `complete_instance()`)
3. Backfill existing data (one-time migration script)
4. Update `_load_instances()` to use stored values (with fallback to calculate if missing)

---

## Conclusion

**Recommended: Store factors in database** with hybrid approach (calculate on write, use stored on read, fallback to calculate if missing).

This provides:
- Performance benefits for analytics queries
- Consistency with existing score storage pattern
- Backward compatibility for existing data
- Flexibility to recalculate if formula changes
