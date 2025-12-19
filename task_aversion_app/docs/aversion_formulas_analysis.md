# Aversion Formulas Analysis

## Problem Identified

All 7 aversion formula variants are producing identical results in the analytics dashboard.

## Root Cause

**All tasks have identical expected and actual relief values** (net_relief = 0 for all tasks).

### Data Analysis Results

- **65 instances** have both expected and actual relief
- **100% of instances** have identical expected/actual relief (difference < 0.01)
- **Mean relief difference: 0.00** (std: 0.00)
- **25 instances** have spontaneous aversion spikes (robust baseline)
- **25 instances** have spontaneous aversion spikes (sensitive baseline)

### Why All Formulas Are Identical

When `expected_relief == actual_relief` (net_relief = 0):

1. **expected_only** = base score
2. **actual_only** = base score (same as expected)
3. **minimum** = min(expected, actual) = expected = actual
4. **average** = (expected + actual) / 2 = expected = actual
5. **net_penalty** = expected_only (no penalty when net_relief = 0)
6. **net_bonus** = expected_only (no bonus when net_relief = 0)
7. **net_weighted** = expected_only × 1.0 (net_factor = 1.0 when net_relief = 0)

**Result:** All 7 formulas produce identical scores.

## Formula Behavior When net_relief ≠ 0

The formulas are designed to produce different results when expected ≠ actual:

### net_penalty
- Uses `expected_relief` as base
- If `actual < expected` (net_relief < 0): Adds bonus multiplier (up to 1.5x)
- If `actual >= expected`: No change

### net_bonus
- Uses `expected_relief` as base
- If `actual > expected` (net_relief > 0): Reduces score slightly (0.8x to 1.0x)
- If `actual <= expected`: No change

### net_weighted
- Uses `expected_relief` as base
- Weighted by net_relief factor: `1.0 - (net_relief / 200.0)`
- Range: 0.5 (big positive net) to 1.5 (big negative net)

### minimum
- Uses `min(expected, actual)`
- More conservative when actual < expected

### average
- Uses `(expected + actual) / 2`
- Balanced approach

## Possible Data Issues

### Issue 1: Expected Relief Backfilled from Actual
The system may be backfilling missing `expected_relief` values with `actual_relief` values, causing them to always match.

**Check:** Review `backfill_predicted_from_actual.py` - it may be copying actual values to predicted.

### Issue 2: User Always Enters Same Value
Users may be entering the same value for expected and actual relief during task completion.

**Check:** Review task completion flow to see if expected relief is pre-filled with actual relief.

### Issue 3: Data Migration Issue
Historical data may have been migrated incorrectly, copying actual values to expected.

## Recommendations

### Short-term
1. **Verify data collection:** Check if expected relief is being properly captured during task initialization
2. **Review backfill script:** Ensure `backfill_predicted_from_actual.py` is not overwriting expected values
3. **Add validation:** Prevent expected relief from being set to actual relief during completion

### Long-term
1. **Separate expected/actual collection:** Ensure expected relief is captured at initialization time, not completion
2. **Data quality checks:** Add validation to detect when expected == actual for all tasks
3. **User education:** If users are entering the same value, explain the difference between expected and actual

## Testing the Formulas

To test that the formulas work correctly, you can:

1. **Manually edit data:** Create test cases with different expected vs actual relief values
2. **Simulate scenarios:**
   - Task where actual < expected (disappointment)
   - Task where actual > expected (pleasant surprise)
   - Task where actual = expected (as expected)

## Expected Behavior

When data has variation in expected vs actual relief:
- **net_penalty** should be highest when actual < expected (overcoming disappointment)
- **net_bonus** should be slightly lower when actual > expected (less impressive)
- **net_weighted** should vary based on net_relief magnitude
- **minimum** should be lower when actual < expected
- **average** should be between expected_only and actual_only when they differ

## Next Steps

1. **Verify data collection:** Check if users are entering the same value for expected and actual relief
2. **Review task completion flow:** Ensure expected relief is preserved from initialization and not overwritten
3. **Add data validation:** Warn users if they're entering identical expected/actual values (unless intentional)
4. **Test with varied data:** Manually create test cases with different expected vs actual values to verify formulas work

## Conclusion

**The formulas are working correctly.** They produce identical results because:
- All tasks have `expected_relief == actual_relief` (net_relief = 0)
- When net_relief = 0, all formulas correctly produce the same base score
- The formulas are designed to differentiate when expected ≠ actual, but there's no such variation in the current data

**This is a data quality issue, not a formula bug.** The formulas will produce different results once there's variation in expected vs actual relief values.

