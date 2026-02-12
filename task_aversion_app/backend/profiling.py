"""Performance profiling utilities for analytics functions.

Enable profiling by setting environment variables before starting the server:
    PROFILE_ANALYTICS=1          Enable profiling output
    PROFILE_LOG_FILE=path.log    Log to file instead of stdout (optional)
    PROFILE_APPEND=1             Append to file instead of overwrite (optional)

Usage in code:
    from backend.profiling import profile_section, get_profiler

    with profile_section("my_operation"):
        # code to profile
        ...

    # Or for .apply() calls:
    profiler = get_profiler()
    profiler.time_apply(df, func, "calculate_grit_score", axis=1)
"""
import os
import time
from contextlib import contextmanager
from datetime import datetime
from typing import Optional, Callable, Any
import pandas as pd


class AnalyticsProfiler:
    """Profiler for analytics functions with file logging support."""
    
    _instance: Optional['AnalyticsProfiler'] = None
    
    def __init__(self):
        self.enabled = os.getenv("PROFILE_ANALYTICS", "").lower() in ("1", "true", "yes")
        self.log_file_path = os.getenv("PROFILE_LOG_FILE", "").strip()
        self.append_mode = os.getenv("PROFILE_APPEND", "").lower() in ("1", "true", "yes")
        self._log_file = None
        self._session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self._current_function: Optional[str] = None
        self._function_start: Optional[float] = None
        self._section_times: dict = {}
        
        if self.enabled and self.log_file_path:
            self._init_log_file()
    
    def _init_log_file(self):
        """Initialize log file for writing."""
        try:
            log_dir = os.path.dirname(self.log_file_path)
            if log_dir:
                os.makedirs(log_dir, exist_ok=True)
            mode = "a" if self.append_mode else "w"
            self._log_file = open(self.log_file_path, mode, encoding="utf-8")
            self._write_header()
        except OSError as e:
            print(f"[Profiler] Could not open log file {self.log_file_path}: {e}")
            self._log_file = None
    
    def _write_header(self):
        """Write header to log file."""
        if self._log_file:
            self._log_file.write(f"\n{'='*80}\n")
            self._log_file.write(f"Profiling Session: {self._session_id}\n")
            self._log_file.write(f"Started: {datetime.now().isoformat()}\n")
            self._log_file.write(f"{'='*80}\n\n")
            self._log_file.flush()
    
    def _log(self, message: str):
        """Log message to file or stdout."""
        if not self.enabled:
            return
        
        timestamp = datetime.now().strftime("%H:%M:%S.%f")[:-3]
        formatted = f"[Profile {timestamp}] {message}"
        
        if self._log_file:
            self._log_file.write(formatted + "\n")
            self._log_file.flush()
        else:
            print(formatted)
    
    def start_function(self, name: str):
        """Mark the start of a function being profiled."""
        if not self.enabled:
            return
        self._current_function = name
        self._function_start = time.perf_counter()
        self._section_times = {}
        self._log(f">>> START {name}")
    
    def end_function(self):
        """Mark the end of the current function and log summary."""
        if not self.enabled or not self._current_function:
            return
        
        total_ms = (time.perf_counter() - self._function_start) * 1000
        self._log(f"<<< END {self._current_function}: {total_ms:.2f}ms total")
        
        # Log breakdown if we have section times
        if self._section_times:
            self._log(f"    Breakdown:")
            sorted_sections = sorted(
                self._section_times.items(), 
                key=lambda x: x[1], 
                reverse=True
            )
            for section, ms in sorted_sections:
                pct = (ms / total_ms * 100) if total_ms > 0 else 0
                self._log(f"      {section}: {ms:.2f}ms ({pct:.1f}%)")
        
        self._current_function = None
        self._function_start = None
    
    @contextmanager
    def section(self, name: str):
        """Context manager for timing a section of code."""
        if not self.enabled:
            yield
            return
        
        start = time.perf_counter()
        try:
            yield
        finally:
            elapsed_ms = (time.perf_counter() - start) * 1000
            self._section_times[name] = self._section_times.get(name, 0) + elapsed_ms
            self._log(f"    {name}: {elapsed_ms:.2f}ms")
    
    def time_apply(
        self, 
        df: pd.DataFrame, 
        func: Callable, 
        name: str, 
        axis: int = 1,
        **kwargs
    ) -> pd.Series:
        """Time a DataFrame.apply() call and return the result.
        
        Args:
            df: DataFrame to apply function to
            func: Function to apply
            name: Name for logging (e.g., "calculate_grit_score")
            axis: Axis for apply (default 1 for row-wise)
            **kwargs: Additional kwargs to pass to apply
            
        Returns:
            Result of df.apply(func, axis=axis, **kwargs)
        """
        row_count = len(df)
        
        if not self.enabled:
            return df.apply(func, axis=axis, **kwargs)
        
        start = time.perf_counter()
        result = df.apply(func, axis=axis, **kwargs)
        elapsed_ms = (time.perf_counter() - start) * 1000
        per_row_ms = elapsed_ms / row_count if row_count > 0 else 0
        
        self._section_times[name] = self._section_times.get(name, 0) + elapsed_ms
        self._log(f"    .apply({name}): {elapsed_ms:.2f}ms ({row_count} rows, {per_row_ms:.3f}ms/row)")
        
        return result
    
    def close(self):
        """Close the log file if open."""
        if self._log_file:
            self._log_file.write(f"\nSession ended: {datetime.now().isoformat()}\n")
            self._log_file.close()
            self._log_file = None


# Singleton instance
_profiler: Optional[AnalyticsProfiler] = None


def get_profiler() -> AnalyticsProfiler:
    """Get the singleton profiler instance."""
    global _profiler
    if _profiler is None:
        _profiler = AnalyticsProfiler()
    return _profiler


@contextmanager
def profile_section(name: str):
    """Convenience context manager for profiling a section."""
    profiler = get_profiler()
    with profiler.section(name):
        yield


def profile_function(name: str):
    """Decorator to profile an entire function."""
    def decorator(func: Callable) -> Callable:
        def wrapper(*args, **kwargs):
            profiler = get_profiler()
            profiler.start_function(name)
            try:
                return func(*args, **kwargs)
            finally:
                profiler.end_function()
        return wrapper
    return decorator
