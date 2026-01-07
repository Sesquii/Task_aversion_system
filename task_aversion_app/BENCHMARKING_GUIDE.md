# Performance Benchmarking Guide

This guide explains how to use the performance benchmarking tools to track improvements in dashboard and analytics page load times.

## Overview

We have **two complementary benchmarking tools**:

1. **Backend Benchmark** (`benchmark_performance.py`) - Measures backend/database performance
2. **E2E Benchmark** - (Removed: `benchmark_performance_playwright.py` - did not accurately reflect actual performance)

## When to Use Each

### Backend Benchmark (Direct Function Calls)

**Use this to:**
- Track database query optimization improvements
- Measure CSV read/write performance
- Isolate backend bottlenecks
- Test individual operations (e.g., `_load_instances()`, `get_relief_summary()`)
- Get fast feedback during development

**What it measures:**
- Individual function execution times
- Database query performance
- CSV file I/O performance
- Backend calculation times

### E2E Benchmark (Removed)

**Note:** The Playwright E2E benchmark script was removed as it did not accurately reflect actual performance. Use the backend benchmark (`benchmark_performance.py`) for accurate performance measurements.

## Setup

### Backend Benchmark

No special setup required - just run:

```bash
cd task_aversion_app
python benchmark_performance.py
```

### E2E Benchmark (Removed)

The Playwright E2E benchmark script has been removed as it did not accurately reflect actual performance.

## Usage Examples

### Basic Backend Benchmark

```bash
# Default: 1 warmup, 3 iterations
python benchmark_performance.py

# Custom iterations
python benchmark_performance.py --warmup 2 --iterations 5

# Save to specific file
python benchmark_performance.py --output baseline_results.json
```

### E2E Benchmark (Removed)

The Playwright E2E benchmark script has been removed. Use `benchmark_performance.py` for accurate performance measurements.

## Interpreting Results

### Backend Benchmark Results

The backend benchmark outputs JSON with:

- `individual_operations`: Timing for each function call
  - `avg_ms`: Average execution time
  - `min_ms`: Fastest execution
  - `max_ms`: Slowest execution
- `dashboard`: Simulated dashboard page load
- `analytics`: Simulated analytics page load
- `data_stats`: Dataset size information
- `summary`: Slowest operations identified

**Key metrics to track:**
- `dashboard.avg_ms`: Should decrease after optimizations
- `analytics.avg_ms`: Should decrease after optimizations
- `individual_operations._load_instances_all.avg_ms`: Database/CSV read performance
- `individual_operations.get_relief_summary.avg_ms`: Analytics calculation performance

### Benchmark Results

The backend benchmark outputs JSON with:

- `dashboard`: Full page load metrics
  - `avg_total`: Total page load time
  - `avg_ttfb`: Time to First Byte (server response time)
  - `avg_domContentLoaded`: DOM ready time
- `analytics`: Analytics page metrics
- `navigation`: Page-to-page navigation time
- `summary`: Overall summary

**Key metrics to track:**
- `dashboard.avg_total`: User-perceived load time
- `dashboard.avg_ttfb`: Backend response time (should correlate with backend benchmark)
- `analytics.avg_total`: Analytics page load time

## Recommended Workflow

### 1. Establish Baseline

**Before optimizations:**

```bash
# Backend baseline
python benchmark_performance.py --output baseline_backend.json

# E2E benchmark removed - use backend benchmark instead
```

### 2. Implement Optimizations

Make your changes (e.g., add database indexes, implement caching, etc.)

### 3. Measure Improvements

**After optimizations:**

```bash
# Backend results
python benchmark_performance.py --output optimized_backend.json

# E2E benchmark removed - use backend benchmark instead
```

### 4. Compare Results

Compare the JSON files to see:
- How much faster backend operations are
- Whether backend improvements translate to faster page loads
- If there are frontend bottlenecks preventing full benefit

## Example Comparison

### Before Optimization

**Backend:**
```json
{
  "dashboard": {"avg_ms": 1250.5},
  "individual_operations": {
    "_load_instances_all": {"avg_ms": 850.2}
  }
}
```

**Note:** E2E benchmark removed - use backend benchmark for accurate measurements.

### After Optimization

**Backend:**
```json
{
  "dashboard": {"avg_ms": 450.8},  // 64% faster!
  "individual_operations": {
    "_load_instances_all": {"avg_ms": 120.5}  // 86% faster!
  }
}
```

**Note:** E2E benchmark removed - use backend benchmark for accurate measurements.
```json
{
  "dashboard": {"avg_total": 950.2, "avg_ttfb": 400.3}  // 55% faster!
}
```

## Tips

1. **Run multiple times**: Performance can vary, so run 3-5 iterations and average
2. **Warm up first**: The first run may be slower due to cold starts
3. **Compare apples to apples**: Use same dataset size, same machine, same conditions
4. **Focus on backend**: Backend benchmark provides accurate performance measurements
5. **Check data stats**: Larger datasets will naturally be slower - track dataset size in results

## Troubleshooting

### Backend Benchmark

- **Import errors**: Make sure you're in the `task_aversion_app` directory
- **Database errors**: Ensure database is initialized and accessible
- **CSV errors**: Check file permissions and that files aren't locked

### E2E Benchmark

- **Connection refused**: Make sure the app is running (`python app.py`)
- **Timeout errors**: Increase timeout or check if app is responding
- **Selector not found**: Update selectors in script to match your UI structure
- **Playwright not installed**: Run `pip install playwright && playwright install chromium`

## Next Steps

After establishing baselines, implement optimizations from the performance plan:
1. Add database indexes
2. Implement caching
3. Optimize queries (batching, column pruning)
4. Reduce CSV usage

Then re-run benchmarks to measure improvements!
