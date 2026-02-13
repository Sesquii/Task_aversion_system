"""
Instrumentation for debugging page refresh, navigation, cache invalidation, and analytics load.

Enable via environment variables:
- INSTRUMENT_NAVIGATION=1  - Log all ui.navigate.to(), ui.navigate.reload() calls (refresh/navigation debugging)
- INSTRUMENT_CACHE=1       - Log all cache invalidations (Analytics, TaskManager, InstanceManager)
- INSTRUMENT_ANALYTICS=1   - Log analytics page load timing and hot functions

Use separate log files for different debugging sessions:
- INSTRUMENT_LOG_NAV=path  - Override nav log path (default: data/logs/instrumentation_navigation.log)
- INSTRUMENT_LOG_CACHE=path - Override cache log path (default: data/logs/instrumentation_cache.log)
- INSTRUMENT_LOG_ANALYTICS=path - Override analytics log path (default: data/logs/instrumentation_analytics.log)

Example dual-venv usage:
  # Terminal 1: Focus on refresh/navigation bug
  $env:INSTRUMENT_NAVIGATION="1"; $env:INSTRUMENT_CACHE="1"; $env:INSTRUMENT_LOG_NAV="logs/refresh_debug.log"; python app.py

  # Terminal 2: Focus on analytics load speed
  $env:INSTRUMENT_ANALYTICS="1"; $env:INSTRUMENT_LOG_ANALYTICS="logs/analytics_speed.log"; python app.py
"""
import os
import sys
import json
import traceback
import time
from contextvars import ContextVar
from datetime import datetime
from typing import Optional, Any

# Track current page path for navigation events (set by log_page_visit)
_current_path: ContextVar[Optional[str]] = ContextVar('instrumentation_current_path', default=None)

# Base log directory
_BASE_DIR = os.path.join(os.path.dirname(__file__), '..')
_DATA_DIR = os.path.join(_BASE_DIR, 'data')
_LOG_DIR = os.path.join(_DATA_DIR, 'logs')

# Environment-driven enable flags
_NAV_ENABLED = os.getenv('INSTRUMENT_NAVIGATION', '').lower() in ('1', 'true', 'yes')
_CACHE_ENABLED = os.getenv('INSTRUMENT_CACHE', '').lower() in ('1', 'true', 'yes')
_ANALYTICS_ENABLED = os.getenv('INSTRUMENT_ANALYTICS', '').lower() in ('1', 'true', 'yes')

# Log file paths (can be overridden)
_NAV_LOG = os.getenv('INSTRUMENT_LOG_NAV', '').strip() or os.path.join(_LOG_DIR, 'instrumentation_navigation.log')
_CACHE_LOG = os.getenv('INSTRUMENT_LOG_CACHE', '').strip() or os.path.join(_LOG_DIR, 'instrumentation_cache.log')
_ANALYTICS_LOG = os.getenv('INSTRUMENT_LOG_ANALYTICS', '').strip() or os.path.join(_LOG_DIR, 'instrumentation_analytics.log')


def _ensure_log_dir(path: str) -> None:
    d = os.path.dirname(path)
    if d:
        os.makedirs(d, exist_ok=True)


def _get_caller_stack(max_frames: int = 8) -> list:
    """Return abbreviated stack trace, preferring app frames (task_aversion, ui/, backend/)."""
    try:
        tb = traceback.extract_stack()
        lines = []
        for frame in tb:
            f = frame.filename
            if 'instrumentation' in f:
                continue
            is_app = (
                'task_aversion' in f or 'Task_aversion' in f or
                ('ui' + os.sep in f or 'ui/' in f) or
                ('backend' + os.sep in f or 'backend/' in f)
            )
            if is_app:
                if 'task_aversion' in f or 'Task_aversion' in f:
                    idx = f.find('task_aversion') if 'task_aversion' in f else f.find('Task_aversion')
                    if idx >= 0:
                        f = f[idx:]
                lines.append(f"{f}:{frame.lineno} {frame.name}")
                if len(lines) >= max_frames:
                    break
        return lines if lines else [f"{tb[-1].filename}:{tb[-1].lineno} {tb[-1].name}"]
    except Exception:
        return []


def _write_log(path: str, entry: dict) -> None:
    try:
        _ensure_log_dir(path)
        with open(path, 'a', encoding='utf-8') as f:
            f.write(json.dumps(entry) + '\n')
    except OSError as e:
        print(f"[Instrumentation] Failed to write to {path}: {e}", file=sys.stderr)


def log_navigation(kind: str, target: str = '', **extra: Any) -> None:
    """Log a navigation event (to, reload, back, forward)."""
    if not _NAV_ENABLED:
        return
    from_path = None
    try:
        from_path = _current_path.get()
    except LookupError:
        pass
    entry = {
        'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
        'event': 'navigation',
        'kind': kind,
        'target': target,
        'from_path': from_path,
        'stack': _get_caller_stack(),
        **extra
    }
    _write_log(_NAV_LOG, entry)


def log_cache_invalidation(manager: str, method: str, user_id: Optional[int] = None, **extra: Any) -> None:
    """Log a cache invalidation event."""
    if not _CACHE_ENABLED:
        return
    entry = {
        'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
        'event': 'cache_invalidation',
        'manager': manager,
        'method': method,
        'user_id': user_id,
        'stack': _get_caller_stack(),
        **extra
    }
    _write_log(_CACHE_LOG, entry)


def log_analytics_event(event: str, duration_ms: Optional[float] = None, **extra: Any) -> None:
    """Log an analytics-related event (e.g. load start, step completion)."""
    if not _ANALYTICS_ENABLED:
        return
    entry = {
        'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
        'event': event,
        **extra
    }
    if duration_ms is not None:
        entry['duration_ms'] = round(duration_ms, 2)
    _write_log(_ANALYTICS_LOG, entry)


def log_page_visit(path: str, query: str = '', **extra: Any) -> None:
    """Log when a page is visited (server-side page function ran).
    Helps distinguish navigation vs refresh: rapid re-visits to same page may indicate reload/reconnect."""
    if not _NAV_ENABLED:
        return
    full_path = path + ('?' + query if query else '')
    try:
        _current_path.set(path)
    except LookupError:
        pass
    entry = {
        'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
        'event': 'page_visit',
        'path': path,
        'query': query,
        **extra
    }
    _write_log(_NAV_LOG, entry)


def instrument_navigate(ui_module: Any) -> None:
    """
    Patch ui.navigate to log all navigation calls.
    Call this early in app startup, before any pages are loaded.
    """
    if not _NAV_ENABLED:
        return
    nav = ui_module.navigate
    if getattr(nav, '_instrumented', False):
        return

    orig_to = nav.to
    orig_reload = nav.reload
    orig_back = nav.back
    orig_forward = nav.forward

    def wrapped_to(path: str) -> None:
        log_navigation('to', target=path)
        orig_to(path)

    def wrapped_reload() -> None:
        log_navigation('reload', target='(current page)')
        orig_reload()

    def wrapped_back() -> None:
        log_navigation('back')
        orig_back()

    def wrapped_forward() -> None:
        log_navigation('forward')
        orig_forward()

    nav.to = wrapped_to
    nav.reload = wrapped_reload
    nav.back = wrapped_back
    nav.forward = wrapped_forward
    nav._instrumented = True

    _write_log(_NAV_LOG, {
        'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
        'event': 'instrumentation_start',
        'message': 'Navigation instrumentation active',
        'log_file': _NAV_LOG
    })
    print(f"[Instrumentation] Navigation logging enabled -> {_NAV_LOG}")


def _log_cache_start() -> None:
    if not _CACHE_ENABLED:
        return
    try:
        _ensure_log_dir(_CACHE_LOG)
        _write_log(_CACHE_LOG, {
            'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
            'event': 'instrumentation_start',
            'message': 'Cache instrumentation active',
            'log_file': _CACHE_LOG
        })
        print(f"[Instrumentation] Cache logging enabled -> {_CACHE_LOG}")
    except Exception:
        pass


def _log_analytics_start() -> None:
    if not _ANALYTICS_ENABLED:
        return
    try:
        _ensure_log_dir(_ANALYTICS_LOG)
        _write_log(_ANALYTICS_LOG, {
            'ts': datetime.now().strftime('%Y-%m-%d %H:%M:%S.%f'),
            'event': 'instrumentation_start',
            'message': 'Analytics instrumentation active',
            'log_file': _ANALYTICS_LOG
        })
        print(f"[Instrumentation] Analytics logging enabled -> {_ANALYTICS_LOG}")
    except Exception:
        pass


def is_nav_enabled() -> bool:
    return _NAV_ENABLED


def is_cache_enabled() -> bool:
    return _CACHE_ENABLED


def is_analytics_enabled() -> bool:
    return _ANALYTICS_ENABLED
