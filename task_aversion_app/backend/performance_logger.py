# backend/performance_logger.py
"""
Performance logging utility for tracking initialization and other operations.
Logs timing information to help identify performance bottlenecks.
"""
import os
import time
import json
from datetime import datetime
from typing import Optional, Dict, Any
from contextlib import contextmanager

DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')
PERF_LOG_DIR = os.path.join(DATA_DIR, 'logs')
PERF_LOG_FILE = os.path.join(PERF_LOG_DIR, 'initialization_performance.log')


class PerformanceLogger:
    """Logger for tracking performance metrics."""
    
    def __init__(self, log_file: Optional[str] = None):
        self.log_file = log_file or PERF_LOG_FILE
        self._ensure_log_dir()
        self._operation_stack = []
        self._current_operation = None
    
    def _ensure_log_dir(self):
        """Ensure log directory exists."""
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
    
    def _log(self, level: str, message: str, data: Optional[Dict[str, Any]] = None):
        """Write a log entry."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
        entry = {
            'timestamp': timestamp,
            'level': level,
            'message': message,
            'data': data or {}
        }
        
        # Add operation context if available
        if self._operation_stack:
            entry['operation_stack'] = self._operation_stack.copy()
        
        try:
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + '\n')
        except Exception as e:
            # Fallback to print if file write fails
            print(f"[PerfLogger Error] {e}: {message}")
    
    @contextmanager
    def operation(self, operation_name: str, **kwargs):
        """Context manager for timing an operation."""
        start_time = time.perf_counter()
        self._operation_stack.append(operation_name)
        
        try:
            self._log('START', f"Operation: {operation_name}", kwargs)
            yield
        finally:
            end_time = time.perf_counter()
            duration_ms = (end_time - start_time) * 1000
            self._operation_stack.pop()
            
            self._log('END', f"Operation: {operation_name} completed", {
                **kwargs,
                'duration_ms': round(duration_ms, 2)
            })
    
    def log_event(self, event_name: str, **kwargs):
        """Log a single event without timing."""
        self._log('EVENT', event_name, kwargs)
    
    def log_timing(self, operation_name: str, duration_ms: float, **kwargs):
        """Log a timing measurement."""
        self._log('TIMING', operation_name, {
            **kwargs,
            'duration_ms': round(duration_ms, 2)
        })
    
    def log_error(self, error_message: str, exception: Optional[Exception] = None, **kwargs):
        """Log an error."""
        error_data = {
            **kwargs,
            'error': error_message
        }
        if exception:
            error_data['exception_type'] = type(exception).__name__
            error_data['exception_message'] = str(exception)
        self._log('ERROR', error_message, error_data)


# Global logger instance
_perf_logger = None


def get_perf_logger() -> PerformanceLogger:
    """Get or create the global performance logger instance."""
    global _perf_logger
    if _perf_logger is None:
        _perf_logger = PerformanceLogger()
    return _perf_logger
