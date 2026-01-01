# Analytics Module Skill Framework

**Purpose:** Guide for working with the Analytics module, particularly execution score calculations and migration patterns.

**Based on:** Execution Module v1.0 implementation in `backend/analytics.py`

---

## Core Concepts

### 1. Execution Score Architecture

The execution score is a **four-factor multiplicative model** that rewards efficient execution of difficult tasks:

```
execution_score = base_score × (1.0 + difficulty_factor) × 
                  (0.5 + speed_factor × 0.5) × 
                  (0.5 + start_speed_factor × 0.5) × 
                  completion_factor
```

**Key Design Principles:**
- **Multiplicative factors** - All components must be high for high scores
- **Neutral base** - Base score of 50 provides neutral starting point
- **Exponential scaling** - Difficulty uses exponential decay for smooth curves
- **Piecewise functions** - Speed, start speed, and completion use piecewise logic for different regions

### 2. Component Factor Patterns

#### Difficulty Factor Pattern
```python
# Exponential decay formula
difficulty_factor = 1.0 × (1 - exp(-(w_aversion × aversion + w_load × load) / k))
```

**When to use:**
- Rewarding completion of difficult tasks
- Combining multiple difficulty dimensions (aversion + load)
- Smooth, diminishing returns curve

**Key parameters:**
- `w_aversion = 0.7` (higher weight on aversion)
- `w_load = 0.3` (lower weight on cognitive load)
- `k = 50.0` (exponential decay constant)

#### Speed Factor Pattern
```python
# Piecewise function with three regions
if time_ratio <= 0.5:
    factor = 1.0  # Very fast
elif time_ratio <= 1.0:
    factor = 1.0 - (time_ratio - 0.5) × 1.0  # Linear
else:
    factor = 0.5 × (1.0 / time_ratio)  # Exponential decay
```

**When to use:**
- Measuring efficiency relative to estimates
- Rewarding fast completion
- Penalizing slow completion with diminishing returns

**Key thresholds:**
- `0.5` - Very fast threshold (2x speed or faster)
- `1.0` - On-time threshold (completed within estimate)

#### Start Speed Factor Pattern
```python
# Piecewise function with four regions
if delay <= 5:
    factor = 1.0  # Perfect
elif delay <= 30:
    factor = 1.0 - ((delay - 5) / 25.0) × 0.2  # Linear
elif delay <= 120:
    factor = 0.8 - ((delay - 30) / 90.0) × 0.3  # Linear
else:
    factor = 0.5 × exp(-excess / 240.0)  # Exponential decay
```

**When to use:**
- Measuring procrastination resistance
- Rewarding fast starts
- Handling long delays with exponential decay

**Key thresholds:**
- `5 minutes` - Perfect start
- `30 minutes` - Good start
- `120 minutes` - Acceptable start

#### Completion Factor Pattern
```python
# Piecewise function with four regions
if completion >= 100:
    factor = 1.0  # Full
elif completion >= 90:
    factor = 0.9 + (completion - 90) / 10.0 × 0.1  # Near-complete
elif completion >= 50:
    factor = 0.5 + (completion - 50) / 40.0 × 0.4  # Partial
else:
    factor = completion / 50.0 × 0.5  # Low
```

**When to use:**
- Measuring quality of completion
- Rewarding full completion
- Penalizing partial completion proportionally

**Key thresholds:**
- `100%` - Full completion
- `90%` - Near-complete
- `50%` - Partial completion

---

## Data Handling Patterns

### 1. CSV vs Database Format Handling

**Pattern:**
```python
if isinstance(row, pd.Series):
    # CSV format
    predicted_dict = json.loads(row['predicted_dict']) if isinstance(row['predicted_dict'], str) else row['predicted_dict']
    actual_dict = json.loads(row['actual_dict']) if isinstance(row['actual_dict'], str) else row['actual_dict']
else:
    # Database format (dict)
    predicted = row.get('predicted', {})
    actual = row.get('actual', {})
    predicted_dict = predicted if isinstance(predicted, dict) else {}
    actual_dict = actual if isinstance(actual, dict) else {}
```

**When to use:**
- Handling both CSV (pandas Series) and database (dict) formats
- Parsing JSON strings from CSV columns
- Providing fallback defaults

### 2. Missing Data Handling

**Pattern:**
```python
# Default to neutral values
difficulty_factor = 0.0  # if aversion is None
speed_factor = 0.5  # if time data missing
start_speed_factor = 0.5  # if timestamp data missing
completion_factor = 1.0  # if completion data missing (assume 100%)
```

**When to use:**
- Handling missing required inputs
- Providing neutral defaults that don't penalize
- Graceful degradation when data is incomplete

### 3. Timestamp Parsing

**Pattern:**
```python
try:
    if isinstance(timestamp, str):
        parsed_time = pd.to_datetime(timestamp)
    else:
        parsed_time = timestamp
    # Calculate time differences
except (ValueError, TypeError, AttributeError) as e:
    # Fallback to neutral value
    factor = 0.5
```

**When to use:**
- Parsing timestamps from various formats
- Handling timezone issues
- Graceful error handling for invalid timestamps

---

## Formula Design Patterns

### 1. Exponential Decay Pattern

**Use for:** Smooth, diminishing returns curves

**Formula:**
```python
value = max_value × (1 - exp(-input / k))
```

**Characteristics:**
- Smooth curve (no abrupt changes)
- Approaches max_value asymptotically
- Early changes have more impact than later changes
- Psychologically accurate (matches human perception)

**Examples:**
- Difficulty bonus: `1.0 × (1 - exp(-combined_difficulty / 50))`
- Improvement multiplier: `1.0 × (1 - exp(-improvement / 30))`

### 2. Piecewise Linear Pattern

**Use for:** Different behavior in different regions

**Formula:**
```python
if input <= threshold1:
    value = max_value
elif input <= threshold2:
    # Linear interpolation
    value = max_value - ((input - threshold1) / (threshold2 - threshold1)) × (max_value - min_value)
else:
    # Different behavior
    value = ...
```

**Characteristics:**
- Clear thresholds for different behaviors
- Smooth transitions between regions
- Easy to understand and modify

**Examples:**
- Speed factor (0.5-1.0 region)
- Start speed factor (5-30 min region)

### 3. Multiplicative Combination Pattern

**Use for:** Requiring all components to be high

**Formula:**
```python
result = base × factor1 × factor2 × factor3 × factor4
```

**Characteristics:**
- All factors must be high for high result
- Low factor significantly reduces result
- Encourages balanced performance

**Examples:**
- Execution score (all four factors)
- Composite score (weighted combination)

### 4. Additive Boost Pattern

**Use for:** Adding bonus without penalty

**Formula:**
```python
result = base × (1.0 + bonus_factor)
```

**Characteristics:**
- Bonus factor adds to result (1.0-2.0 range)
- No penalty if bonus is low (minimum 1.0)
- Encourages improvement without punishing baseline

**Examples:**
- Difficulty factor in execution score: `(1.0 + difficulty_factor)`
- Improvement multiplier in aversion calculations

---

## Migration Patterns

### 1. Adding New Factors to Execution Score

**Steps:**
1. Define the factor calculation function
2. Add factor to `calculate_execution_score()` method
3. Integrate into multiplicative formula
4. Update documentation (execution_module_v1.0.md)
5. Add graphic aid script (if visualizable)
6. Update analytics glossary

**Example:**
```python
# 1. Define factor
def calculate_quality_factor(quality_metrics):
    # ... calculation logic
    return factor  # 0.0-1.0 range

# 2. Add to execution score
quality_factor = calculate_quality_factor(row.get('quality_metrics'))
execution_score = base_score × (
    (1.0 + difficulty_factor) ×
    (0.5 + speed_factor * 0.5) ×
    (0.5 + start_speed_factor * 0.5) ×
    completion_factor ×
    quality_factor  # NEW
)
```

### 2. Modifying Existing Factors

**Steps:**
1. Document current behavior (version current formula)
2. Design new formula (consider backward compatibility)
3. Implement new formula with feature flag (if needed)
4. Test with existing data
5. Update documentation
6. Update graphic aids

**Example:**
```python
# Version 1.0 formula
if USE_NEW_FORMULA:
    # New formula logic
    factor = new_calculation()
else:
    # Old formula logic (backward compatible)
    factor = old_calculation()
```

### 3. Extracting Factors for Reuse

**Pattern:**
```python
# Extract to static method for reuse
@staticmethod
def calculate_speed_factor(time_actual, time_estimate):
    """Calculate speed factor (0.0-1.0)."""
    # ... calculation logic
    return speed_factor

# Use in execution score
speed_factor = Analytics.calculate_speed_factor(time_actual, time_estimate)
```

**Benefits:**
- Reusable across different score calculations
- Easier to test independently
- Consistent behavior across codebase

---

## Testing Patterns

### 1. Factor Calculation Tests

**Pattern:**
```python
def test_difficulty_factor():
    # Test edge cases
    assert calculate_difficulty_bonus(0, 0) == 0.0
    assert calculate_difficulty_bonus(100, 100) > 0.8
    
    # Test typical cases
    factor = calculate_difficulty_bonus(50, 50)
    assert 0.5 < factor < 0.7
    
    # Test missing data
    assert calculate_difficulty_bonus(None, 50) == 0.0
```

### 2. Execution Score Integration Tests

**Pattern:**
```python
def test_execution_score():
    # Create test row
    row = {
        'predicted': {'initial_aversion': 50, 'time_estimate_minutes': 60},
        'actual': {'time_actual_minutes': 30, 'completion_percent': 100},
        'initialized_at': datetime.now(),
        'started_at': datetime.now() + timedelta(minutes=2),
        'completed_at': datetime.now() + timedelta(minutes=32)
    }
    
    # Calculate score
    score = analytics.calculate_execution_score(row)
    
    # Verify range
    assert 0 <= score <= 100
    
    # Verify expected behavior
    assert score > 50  # Should be above neutral for fast, complete execution
```

### 3. Data Format Compatibility Tests

**Pattern:**
```python
def test_csv_format():
    # Test CSV format (pandas Series)
    row = pd.Series({
        'predicted_dict': json.dumps({'initial_aversion': 50}),
        'actual_dict': json.dumps({'time_actual_minutes': 30})
    })
    score = analytics.calculate_execution_score(row)
    assert 0 <= score <= 100

def test_database_format():
    # Test database format (dict)
    row = {
        'predicted': {'initial_aversion': 50},
        'actual': {'time_actual_minutes': 30}
    }
    score = analytics.calculate_execution_score(row)
    assert 0 <= score <= 100
```

---

## Common Pitfalls and Solutions

### 1. Division by Zero

**Problem:**
```python
time_ratio = time_actual / time_estimate  # Fails if time_estimate is 0
```

**Solution:**
```python
if time_estimate > 0 and time_actual > 0:
    time_ratio = time_actual / time_estimate
    # ... calculation
else:
    speed_factor = 0.5  # Neutral default
```

### 2. Missing Timestamp Data

**Problem:**
```python
start_delay = (started_at - initialized_at).total_seconds() / 60.0
# Fails if timestamps are None or invalid
```

**Solution:**
```python
if initialized_at and started_at:
    try:
        # Parse and calculate
        start_delay = calculate_delay(initialized_at, started_at)
    except (ValueError, TypeError, AttributeError):
        start_speed_factor = 0.5  # Neutral default
else:
    start_speed_factor = 0.5  # Neutral default
```

### 3. JSON Parsing Errors

**Problem:**
```python
predicted_dict = json.loads(row['predicted_dict'])  # Fails if invalid JSON
```

**Solution:**
```python
try:
    predicted_dict = json.loads(row['predicted_dict']) if isinstance(row['predicted_dict'], str) else row['predicted_dict']
except (json.JSONDecodeError, TypeError):
    predicted_dict = {}  # Empty dict as fallback
```

### 4. Factor Range Violations

**Problem:**
```python
execution_score = base_score * factor1 * factor2  # May exceed 100
```

**Solution:**
```python
execution_score = base_score * factor1 * factor2
execution_score = max(0.0, min(100.0, execution_score))  # Clamp to range
```

---

## Best Practices

1. **Always provide neutral defaults** for missing data (0.5 for factors, 50 for scores)
2. **Clamp final scores** to expected ranges (0-100)
3. **Handle both CSV and database formats** in calculation methods
4. **Use exponential decay** for smooth, psychologically accurate curves
5. **Document formula versions** when making changes
6. **Test edge cases** (zero values, missing data, extreme values)
7. **Use piecewise functions** for different behavior regions
8. **Make factors reusable** by extracting to static methods
9. **Update documentation** when formulas change
10. **Version formulas** when making significant changes

---

## Related Documentation

- **Execution Module v1.0:** `docs/execution_module_v1.0.md`
- **Analytics Glossary:** `ui/analytics_glossary.py`
- **Formula Review:** `docs/formula_review_analysis.md`
- **Implementation:** `backend/analytics.py`
