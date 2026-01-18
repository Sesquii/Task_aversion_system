# backend/query_logger.py
"""
Lightweight query logging system to track database queries per request.
Helps identify N+1 query issues by logging query counts for each page load.
Tracks total DB time per request and repeated-query patterns for baseline analysis.

Note: DB time reflects only SQL execute duration (Engine before/after_cursor_execute).
Connection setup, PRAGMA table_info, and ORM/connection overhead are not included;
cold loads with many new connections can show low DB time despite high wall-clock.
"""
import os
import re
import threading
import time
from collections import Counter
from datetime import datetime
from typing import Optional, Dict, List, Tuple
from contextvars import ContextVar

# Thread-local storage for request context (works with both async and sync code)
_thread_local = threading.local()

# Context vars for async request tracking
_request_id: ContextVar[Optional[str]] = ContextVar('request_id', default=None)

# Global state for running totals
_total_queries = 0
_total_requests = 0
_query_log_lock = threading.Lock()

# Log file path
LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'logs')
QUERY_LOG_FILE = os.path.join(LOG_DIR, 'query_log.txt')


def ensure_log_dir():
    """Ensure log directory exists."""
    os.makedirs(LOG_DIR, exist_ok=True)


def get_request_id() -> Optional[str]:
    """Get current request ID from context (thread-local or contextvar)."""
    # Try thread-local first (for SQLAlchemy events)
    if hasattr(_thread_local, 'request_id'):
        return _thread_local.request_id
    # Fall back to contextvar (for async code)
    return _request_id.get()


def set_request_id(request_id: str):
    """Set current request ID in both contextvar and thread-local storage."""
    _request_id.set(request_id)
    _thread_local.request_id = request_id
    _thread_local.query_count = 0
    _thread_local.queries = []
    _thread_local.db_time = 0.0


def increment_query_count(query: Optional[str] = None):
    """Increment query count for current request."""
    # Use thread-local storage (works with SQLAlchemy events)
    if not hasattr(_thread_local, 'query_count'):
        _thread_local.query_count = 0
        _thread_local.queries = []
    
    # Only track queries if we're in a request context
    # (queries outside requests, e.g., during initialization, are still counted globally)
    _thread_local.query_count += 1
    
    if query:
        _thread_local.queries.append(query)
    
    global _total_queries
    with _query_log_lock:
        _total_queries += 1


def get_query_count() -> int:
    """Get query count for current request."""
    if hasattr(_thread_local, 'query_count'):
        return _thread_local.query_count
    return 0


def get_queries() -> List[str]:
    """Get list of queries for current request."""
    if hasattr(_thread_local, 'queries'):
        return _thread_local.queries.copy()
    return []


def add_db_time(seconds: float) -> None:
    """Accumulate DB time for the current request (called from after_cursor_execute)."""
    if not hasattr(_thread_local, 'db_time'):
        _thread_local.db_time = 0.0
    _thread_local.db_time += seconds


def get_db_time() -> float:
    """Get total DB time in seconds for the current request."""
    return getattr(_thread_local, 'db_time', 0.0)


def log_request_summary(path: str, method: str = "GET"):
    """Log summary of queries for a request."""
    request_id = get_request_id()
    query_count = get_query_count()
    queries = get_queries()
    
    global _total_requests
    
    if request_id is None:
        return
    
    ensure_log_dir()
    
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    
    with _query_log_lock:
        _total_requests += 1
        total_queries = _total_queries
        total_requests = _total_requests
    
    db_time_ms = get_db_time() * 1000.0

    # Format log entry
    log_lines = [
        f"\n{'='*80}",
        f"[{timestamp}] {method} {path}",
        f"Request ID: {request_id}",
        f"Queries in this request: {query_count}",
        f"Total DB time: {db_time_ms:.2f} ms",
        f"Running total - Requests: {total_requests}, Queries: {total_queries}",
    ]

    # Top repeated query patterns (normalize: strip Params, collapse whitespace, truncate)
    def _normalize(q: str) -> str:
        s = re.sub(r"\s*\|\s*Params:.*$", "", q, flags=re.IGNORECASE)
        s = re.sub(r"\s+", " ", s).strip()
        return (s[:120] + "...") if len(s) > 120 else s

    if queries:
        patterns = Counter(_normalize(q) for q in queries)
        top = patterns.most_common(5)
        if top and (len(top) > 1 or top[0][1] > 1):
            log_lines.append("\nTop repeated query patterns:")
            for pattern, cnt in top:
                if cnt > 1:
                    log_lines.append(f"  {cnt}x: {pattern[:100]}{'...' if len(pattern) > 100 else ''}")

    # Add query details if there are queries
    if queries:
        log_lines.append(f"\nQuery Details ({len(queries)} queries):")
        for i, query in enumerate(queries, 1):
            # Truncate very long queries
            query_preview = query[:200] + "..." if len(query) > 200 else query
            log_lines.append(f"  {i}. {query_preview}")

    # Add N+1 warning if query count is high
    if query_count > 10:
        log_lines.append(f"\n[WARNING] High query count ({query_count}) - possible N+1 issue!")
    elif query_count > 5:
        log_lines.append(f"\n[INFO] Moderate query count ({query_count}) - review for optimization")
    
    log_lines.append("")
    
    log_entry = "\n".join(log_lines)
    
    # Write to file
    try:
        with open(QUERY_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(log_entry)
    except Exception as e:
        print(f"[QueryLogger] Failed to write log: {e}")


def setup_query_logging(engine):
    """
    Set up SQLAlchemy event listeners to track queries and DB time.

    Args:
        engine: SQLAlchemy engine instance
    """
    from sqlalchemy import event
    from sqlalchemy.engine import Engine

    @event.listens_for(Engine, "before_cursor_execute")
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Intercept SQL queries before execution; record start time for DB timing."""
        query = str(statement)
        if parameters:
            params_str = str(parameters)
            if len(params_str) > 100:
                params_str = params_str[:100] + "..."
            query = f"{query} | Params: {params_str}"
        increment_query_count(query)
        conn.info.setdefault("_query_start", []).append(time.time())
        return None

    @event.listens_for(Engine, "after_cursor_execute")
    def receive_after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Record DB time after each query."""
        try:
            stack = conn.info.get("_query_start")
            if stack:
                start = stack.pop()
                add_db_time(time.time() - start)
        except (IndexError, KeyError, TypeError):
            pass

    print("[QueryLogger] Query logging enabled (count, DB time, repeated-pattern summary)")


def get_query_stats() -> Dict[str, int]:
    """Get current query statistics."""
    with _query_log_lock:
        return {
            'total_queries': _total_queries,
            'total_requests': _total_requests,
            'current_request_queries': get_query_count()
        }


def clear_log():
    """Clear the query log file."""
    ensure_log_dir()
    try:
        if os.path.exists(QUERY_LOG_FILE):
            os.remove(QUERY_LOG_FILE)
        print(f"[QueryLogger] Log file cleared: {QUERY_LOG_FILE}")
    except Exception as e:
        print(f"[QueryLogger] Failed to clear log: {e}")
