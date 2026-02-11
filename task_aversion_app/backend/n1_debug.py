# backend/n1_debug.py
"""
Request-scoped logging for get_instance / _load_instances to find N+1 call paths.

Enable with ENABLE_N1_DEBUG=1. Logs to logs/n1_debug.log: request_id, caller site
(file:line function), and call type. After one dashboard load, inspect the log and
aggregate by caller to see which path issues 82 calls.

Usage:
  set ENABLE_N1_DEBUG=1
  start app, load GET / once
  check logs/n1_debug.log or run: python scripts/performance/n1_debug_summary.py
"""
import os
import traceback
from typing import Optional

_LOG_DIR = os.path.join(os.path.dirname(__file__), '..', 'logs')
_LOG_FILE = os.path.join(_LOG_DIR, 'n1_debug.log')
_ENABLED = os.getenv('ENABLE_N1_DEBUG', '').lower() in ('1', 'true', 'yes')

_SKIP_PREFIXES = ('backend/n1_debug.py',)


def _caller_site(
    skip_self_name: Optional[str] = None,
    skip_self_path_contains: Optional[str] = None,
) -> str:
    """Return the frame that called _load_instances/get_instance (the actual call site).
    extract_stack() returns oldest-first, so we iterate in reverse to find the
    callee frame then return the frame above it (the caller).
    """
    stack = traceback.extract_stack()
    # Walk from most recent (end) toward oldest; find callee then its caller
    for i in range(len(stack) - 1, -1, -1):
        frame = stack[i]
        path = frame.filename.replace('\\', '/')
        if any(skip in path for skip in _SKIP_PREFIXES):
            continue
        # This frame is the callee (_load_instances or get_instance); caller is stack[i-1]
        if (
            skip_self_name is not None
            and skip_self_path_contains is not None
            and frame.name == skip_self_name
            and skip_self_path_contains in path
        ):
            if i > 0:
                caller = stack[i - 1]
                p = caller.filename.replace('\\', '/')
                if 'task_aversion_app' in p:
                    idx = p.find('task_aversion_app')
                    p = p[idx:]
                return f"{p}:{caller.lineno} {caller.name}"
            break
        # No callee found; return first non-skip frame (fallback)
        if 'task_aversion_app' in path:
            idx = path.find('task_aversion_app')
            path = path[idx:]
        return f"{path}:{frame.lineno} {frame.name}"
    return "unknown"


def _request_id() -> str:
    try:
        from backend.query_logger import get_request_id
        rid = get_request_id()
        return rid if rid else "no-request"
    except Exception:
        return "no-request"


def _write(line: str) -> None:
    if not _ENABLED:
        return
    try:
        os.makedirs(_LOG_DIR, exist_ok=True)
        with open(_LOG_FILE, 'a', encoding='utf-8') as f:
            f.write(line + "\n")
    except Exception:
        pass


def log_get_instance(instance_id, user_id: Optional[int]) -> None:
    """Call at entry of InstanceManager.get_instance."""
    caller = _caller_site(skip_self_name='get_instance', skip_self_path_contains='instance_manager')
    _write(f"get_instance\trequest={_request_id()}\tcaller={caller}\tinstance_id={instance_id}\tuser_id={user_id}")


def log_load_instances(completed_only: bool, user_id: Optional[int]) -> None:
    """Call at entry of Analytics._load_instances."""
    caller = _caller_site(skip_self_name='_load_instances', skip_self_path_contains='analytics')
    _write(f"_load_instances\trequest={_request_id()}\tcaller={caller}\tcompleted_only={completed_only}\tuser_id={user_id}")
