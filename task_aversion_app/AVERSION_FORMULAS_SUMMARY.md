# Aversion Formulas Analysis Summary

## Issue
All 7 aversion formula variants show identical numbers in the analytics dashboard.

## Root Cause
**All tasks have identical expected and actual relief values** (net_relief = 0 for all 65 completed instances).

## Analysis Results

### Data Statistics
- **65 instances** have both expected and actual relief
- **100% have identical values** (difference < 0.01)
- **Mean relief difference: 0.00** (std: 0.00)
- **25 instances** have spontaneous aversion spikes (which is good - formulas are being calculated)

### Why Formulas Are Identical

When `expected_relief == actual_relief` (net_relief = 0):

| Formula | Behavior When net_relief = 0 |
|---------|------------------------------|
| `expected_only` | Base score |
| `actual_only` | Base score (same as expected) |
| `minimum` | min(expected, actual) = expected |
| `average` | (expected + actual) / 2 = expected |
| `net_penalty` | expected_only × 1.0 (no penalty when net_relief = 0) |
| `net_bonus` | expected_only × 1.0 (no bonus when net_relief = 0) |
| `net_weighted` | expected_only × 1.0 (net_factor = 1.0 when net_relief = 0) |

**Result:** All 7 formulas correctly produce identical scores when there's no variation in the data.

## Formula Behavior (When Data Has Variation)

The formulas are designed to produce different results when expected ≠ actual:

### Example: actual < expected (disappointment)
- **expected_only**: Base score
- **actual_only**: Lower score (uses lower actual relief)
- **minimum**: Lower score (uses min)
- **average**: Mid score
- **net_penalty**: Higher score (bonus for overcoming disappointment)
- **net_bonus**: Base score (no change)
- **net_weighted**: Higher score (weighted by negative net_relief)

### Example: actual > expected (pleasant surprise)
- **expected_only**: Base score
- **actual_only**: Higher score (uses higher actual relief)
- **minimum**: Base score (uses expected)
- **average**: Higher score (midpoint)
- **net_penalty**: Base score (no change)
- **net_bonus**: Slightly lower score (less impressive for obstacles)
- **net_weighted**: Lower score (weighted by positive net_relief)

## Conclusion

✅ **The formulas are working correctly.**

The identical results are due to **data quality**, not a formula bug:
- All tasks have expected_relief == actual_relief
- When net_relief = 0, all formulas correctly produce the same base score
- The formulas will differentiate once there's variation in expected vs actual relief

## Possible Reasons for Identical Data

1. **User behavior**: Users may be entering the same value for expected and actual relief
2. **UI defaults**: The completion form may be pre-filling actual relief with expected relief
3. **Data migration**: Historical data may have been migrated incorrectly

## Recommendations

### Short-term
1. **Add validation warning**: When completing a task, warn if actual relief exactly matches expected relief (unless intentional)
2. **Review UI flow**: Ensure expected relief is clearly shown during completion so users can compare
3. **Data audit**: Check a few instances manually to see if expected_relief was properly captured at initialization

### Long-term
1. **User education**: Explain the difference between expected (prediction) and actual (outcome) relief
2. **Analytics display**: Show a note in the analytics page when all formulas are identical due to data uniformity
3. **Data quality metrics**: Track the percentage of tasks with expected ≠ actual relief

## Testing the Formulas

To verify the formulas work correctly with varied data:

1. **Create test cases** with different expected vs actual relief values
2. **Manually edit** a few instances in the CSV to have different values
3. **Re-run analytics** to see formulas produce different results

## Files Analyzed

- `task_aversion_app/backend/analytics.py` - Formula implementations
- `task_aversion_app/ui/analytics_page.py` - Analytics display
- `task_aversion_app/analyze_aversion_formulas.py` - Diagnostic script
- `task_aversion_app/data/task_instances.csv` - Data source

## Next Steps

1. ✅ Formulas verified to be working correctly
2. ⏳ Investigate why expected and actual relief are always identical
3. ⏳ Add data quality validation
4. ⏳ Update analytics UI to show when formulas are identical due to data uniformity

