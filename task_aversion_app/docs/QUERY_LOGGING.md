# Query Logging System

## Overview

The query logging system tracks database queries per request to help identify N+1 query issues and performance problems. It logs query counts and details to a file for analysis.

## Features

- **Per-request tracking**: Counts all database queries executed during each page load
- **Running totals**: Tracks cumulative queries and requests across the application
- **Query details**: Logs actual SQL queries (truncated for readability)
- **N+1 detection**: Warns when query count exceeds thresholds (>5 queries = info, >10 queries = warning)
- **Lightweight**: Minimal performance impact, can be disabled via environment variable

## Log File Location

Query logs are written to: `task_aversion_app/logs/query_log.txt`

The log file is created automatically when the first request is logged.

## Log Format

Each request generates a log entry like:

```
================================================================================
[2024-01-15 14:30:45.123] GET /
Request ID: a1b2c3d4
Queries in this request: 8
Total DB time: 12.34 ms
Running total - Requests: 42, Queries: 156

Top repeated query patterns:
  5x: SELECT task_instances.instance_id AS ... WHERE task_instances.instance_id = ?

Query Details (8 queries):
  1. SELECT * FROM tasks WHERE user_id = ? | Params: (1,)
  2. SELECT * FROM task_instances WHERE user_id = ? | Params: (1,)
  ...

[INFO] Moderate query count (8) - review for optimization
```

- **Total DB time**: Sum of all query execution times in the request (ms). Use to compare before/after refactors.
- **Top repeated query patterns**: When the same normalized query runs multiple times, it is listed (e.g. `90x: SELECT ...`). This makes N+1 patterns easy to spot.

## Configuration

### Enable/Disable Query Logging

Set the `ENABLE_QUERY_LOGGING` environment variable:

- `ENABLE_QUERY_LOGGING=1` (default) - Query logging enabled
- `ENABLE_QUERY_LOGGING=0` - Query logging disabled

### Example

```bash
# Disable query logging
export ENABLE_QUERY_LOGGING=0
python app.py

# Enable query logging (default)
export ENABLE_QUERY_LOGGING=1
python app.py
```

## How It Works

1. **Middleware**: `QueryLoggingMiddleware` assigns a unique request ID to each HTTP request
2. **SQLAlchemy Events**: Event listeners intercept all database queries before execution
3. **Thread-local Storage**: Query counts are tracked per request using thread-local storage
4. **Logging**: After each request completes, a summary is written to the log file

## Identifying N+1 Issues

Look for these patterns in the log:

1. **High query counts**: Pages with >10 queries may have N+1 issues
2. **Repeated queries**: Same query pattern repeated many times (e.g., loading tasks in a loop)
3. **Query patterns**: Look for queries like `SELECT * FROM tasks WHERE task_id = ?` repeated many times

### Example N+1 Pattern

```
Queries in this request: 25

Query Details (25 queries):
  1. SELECT * FROM tasks WHERE user_id = ? | Params: (1,)
  2. SELECT * FROM task_instances WHERE task_id = ? | Params: ('t123',)
  3. SELECT * FROM task_instances WHERE task_id = ? | Params: ('t124',)
  4. SELECT * FROM task_instances WHERE task_id = ? | Params: ('t125',)
  ... (22 more similar queries)

[WARNING] High query count (25) - possible N+1 issue!
```

This suggests loading task instances one-by-one instead of using a JOIN or IN clause.

## Baseline Analysis Script

To summarize metrics from the log (per-path query counts, DB time, and most repeated patterns):

```bash
python scripts/analyze_query_baseline.py [path/to/query_log.txt]
```

Default path: `task_aversion_app/logs/query_log.txt`. Use the output to:
- Establish a baseline before refactors (query count and DB time per path).
- Identify N+1 patterns (same SELECT repeated many times).
- Compare after refactors to confirm improvement.

## Clearing the Log

To clear the query log file programmatically:

```python
from backend.query_logger import clear_log
clear_log()
```

Or simply delete `task_aversion_app/logs/query_log.txt`.

## Performance Impact

The query logging system is designed to be lightweight:

- Minimal overhead per query (increment counter, append to list)
- File writes happen asynchronously after request completion
- No blocking operations during query execution
- Can be disabled in production if needed

## Integration

The query logging is automatically enabled when:

1. The database engine is created (in `backend/database.py`)
2. The FastAPI middleware is added (in `app.py`)

Both checks respect the `ENABLE_QUERY_LOGGING` environment variable.
