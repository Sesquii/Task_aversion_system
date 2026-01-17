# backend/query_logger.py
"""
Lightweight query logging system to track database queries per request.
Helps identify N+1 query issues by logging query counts for each page load.
"""
import os
import threading
from datetime import datetime
from typing import Optional, Dict, List
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
    
    # Format log entry
    log_lines = [
        f"\n{'='*80}",
        f"[{timestamp}] {method} {path}",
        f"Request ID: {request_id}",
        f"Queries in this request: {query_count}",
        f"Running total - Requests: {total_requests}, Queries: {total_queries}",
    ]
    
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
    Set up SQLAlchemy event listeners to track queries.
    
    Args:
        engine: SQLAlchemy engine instance
    """
    from sqlalchemy import event
    from sqlalchemy.engine import Engine
    
    @event.listens_for(Engine, "before_cursor_execute")
    def receive_before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        """Intercept SQL queries before execution."""
        # Format the query for logging
        query = str(statement)
        
        # Add parameters if present (truncated for readability)
        if parameters:
            params_str = str(parameters)
            if len(params_str) > 100:
                params_str = params_str[:100] + "..."
            query = f"{query} | Params: {params_str}"
        
        increment_query_count(query)
        return None  # Don't modify the query
    
    print("[QueryLogger] Query logging enabled")


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
