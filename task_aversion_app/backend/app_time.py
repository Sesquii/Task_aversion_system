"""
App timezone and datetime helpers.

Central place for "now" and "today" in the app's configured timezone.
Supports per-user timezone (from settings) or app-level TIMEZONE in .env.
When user has "Use my device timezone", the browser sends its timezone and we use that.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, Union

# Lazy-loaded app-level TZ (from env)
_app_tz: Optional[object] = None

# #region agent log
def _tz_debug_log(location: str, message: str, data: dict, hypothesis_id: str = "") -> None:
    """Write one NDJSON line to debug-8cd4d8.log (app dir) for VPS copy."""
    try:
        log_path = Path(__file__).resolve().parent.parent / "debug-8cd4d8.log"
        payload = {
            "sessionId": "8cd4d8",
            "timestamp": int(datetime.now(timezone.utc).timestamp() * 1000),
            "location": location,
            "message": message,
            "data": data,
        }
        if hypothesis_id:
            payload["hypothesisId"] = hypothesis_id
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload) + "\n")
    except Exception:
        pass
# #endregion


def _tz_from_name(tz_name: str):
    """Return ZoneInfo for IANA name, or None if invalid."""
    if not (tz_name and str(tz_name).strip()):
        return None
    try:
        from zoneinfo import ZoneInfo
        return ZoneInfo(str(tz_name).strip())
    except (ImportError, KeyError, OSError):
        return None


def _get_tz():
    """Return the app-level timezone (ZoneInfo) from env. Uses system local if TIMEZONE not set."""
    global _app_tz
    if _app_tz is not None:
        return _app_tz
    tz_name = (os.getenv("TIMEZONE") or "").strip()
    if tz_name:
        tz = _tz_from_name(tz_name)
        if tz is not None:
            _app_tz = tz
            return _app_tz
    _app_tz = False  # Sentinel: use system local
    return _app_tz


def get_app_timezone(user_id: Optional[Union[int, str]] = None) -> Union[object, bool]:
    """
    Return the timezone to use for the given user (ZoneInfo or False for local).
    If user_id is None, tries to get current user from auth; then reads user prefs
    (timezone or detected_tz) or falls back to env TIMEZONE or system local.
    """
    # #region agent log
    _tz_debug_log(
        "app_time.get_app_timezone",
        "get_app_timezone entry",
        {"user_id_in": user_id},
        "H1",
    )
    # #endregion
    tz_name = None
    if user_id is not None:
        try:
            from backend.user_state import UserStateManager
            _user_state = UserStateManager()
            resolved = _user_state.get_resolved_timezone(str(user_id))
            if resolved:
                tz_name = resolved
            # #region agent log
            _tz_debug_log(
                "app_time.get_app_timezone",
                "resolved from user_id path",
                {"user_id": user_id, "resolved_tz_name": tz_name},
                "H1",
            )
            # #endregion
        except Exception as e:
            # #region agent log
            _tz_debug_log("app_time.get_app_timezone", "user_id path exception", {"error": str(e)}, "H1")
            # #endregion
            pass
    if not tz_name:
        try:
            from backend.auth import get_current_user
            uid = get_current_user()
            # #region agent log
            _tz_debug_log(
                "app_time.get_app_timezone",
                "get_current_user when user_id was None or no resolved tz",
                {"auth_uid": uid},
                "H1",
            )
            # #endregion
            if uid is not None:
                from backend.user_state import UserStateManager
                _user_state = UserStateManager()
                resolved = _user_state.get_resolved_timezone(str(uid))
                if resolved:
                    tz_name = resolved
                # #region agent log
                _tz_debug_log(
                    "app_time.get_app_timezone",
                    "resolved from auth uid path",
                    {"uid": uid, "resolved_tz_name": tz_name},
                    "H1",
                )
                # #endregion
        except Exception:
            pass
    fallback = _get_tz()
    # #region agent log
    _tz_debug_log(
        "app_time.get_app_timezone",
        "get_app_timezone result",
        {
            "tz_name_used": tz_name,
            "fallback_is_false": fallback is False,
            "env_TIMEZONE": (os.getenv("TIMEZONE") or "").strip() or None,
        },
        "H1",
    )
    # #endregion
    if tz_name:
        tz = _tz_from_name(tz_name)
        if tz is not None:
            return tz
    return fallback


def now(user_id: Optional[Union[int, str]] = None) -> datetime:
    """
    Current time in the app/user timezone (timezone-aware).
    Pass user_id to use that user's timezone; otherwise uses current user or env.
    """
    tz = get_app_timezone(user_id)
    if tz is False:
        return datetime.now()
    return datetime.now(timezone.utc).astimezone(tz)


def utc_now() -> datetime:
    """Current time in UTC (timezone-aware). Use for storage or auth expiry."""
    return datetime.now(timezone.utc)


def today(user_id: Optional[Union[int, str]] = None):
    """Today's date in the app/user timezone (for "today" logic and date ranges)."""
    return now(user_id).date()


def format_for_storage(dt: datetime) -> str:
    """
    Format a datetime for storage (e.g. DB/CSV). Caller should pass
    the result of now() or another datetime in the intended zone.
    """
    if not dt:
        return ""
    s = dt.strftime("%Y-%m-%d %H:%M:%S.%f").rstrip("0").rstrip(".")
    return s or dt.strftime("%Y-%m-%d %H:%M:%S")


# Formats we store in DB/CSV (naive, no TZ in string) - try longer first
_STORED_FMTS = (
    ("%Y-%m-%d %H:%M:%S.%f", 26),
    ("%Y-%m-%d %H:%M:%S", 19),
    ("%Y-%m-%d %H:%M", 16),
    ("%Y-%m-%d", 10),
)


def format_for_display(
    stored: Optional[str],
    assume_utc: bool = True,
    fmt: str = "%Y-%m-%d %H:%M",
    user_id: Optional[Union[int, str]] = None,
) -> str:
    """
    Convert a stored timestamp string for display in the user's timezone.

    Use this wherever created_at, completed_at, started_at, etc. are shown
    in the UI. Pass user_id to use that user's timezone (or omit to use current user / env).

    Display format respects the user's 12/24-hour preference (from browser, stored via
    /api/detected-timezone). Pass fmt to override when needed.

    Args:
        stored: Value from DB/CSV (e.g. "2026-02-28 23:23").
        assume_utc: If True, treat stored value as UTC and convert to user TZ.
        fmt: strftime format. Default "%Y-%m-%d %H:%M" (24-hour).
        user_id: User ID for per-user timezone; None = current user or env.

    Returns:
        Formatted string in user timezone, or the original string if unparseable.
    """
    # #region agent log
    _tz_debug_log(
        "app_time.format_for_display",
        "format_for_display entry",
        {"stored": stored, "user_id": user_id, "assume_utc": assume_utc},
        "H3",
    )
    # #endregion
    if not stored or not str(stored).strip():
        return ""
    s = str(stored).strip().replace("T", " ")
    dt = None
    for pattern, max_len in _STORED_FMTS:
        try:
            part = s[:max_len] if len(s) >= max_len else s
            dt = datetime.strptime(part, pattern)
            break
        except ValueError:
            continue
    if dt is None:
        return s
    tz = get_app_timezone(user_id)
    if assume_utc and tz is not False:
        dt = dt.replace(tzinfo=timezone.utc).astimezone(tz)
    elif assume_utc and tz is False:
        dt = dt.replace(tzinfo=timezone.utc).astimezone()
    # Use 12-hour format if user preference is set (from browser), else caller's fmt (default 24h)
    effective_fmt = fmt
    try:
        _uid = user_id
        if _uid is None:
            from backend.auth import get_current_user
            _uid = get_current_user()
        if _uid is not None:
            from backend.user_state import UserStateManager
            if UserStateManager().get_hour12_preference(str(_uid)):
                effective_fmt = "%Y-%m-%d %I:%M %p"
    except Exception:
        pass
    try:
        result = dt.strftime(effective_fmt)
        # #region agent log
        _tz_debug_log(
            "app_time.format_for_display",
            "format_for_display result",
            {
                "stored": stored,
                "user_id": user_id,
                "tz_repr": str(tz) if tz is not False else "system_local",
                "effective_fmt": effective_fmt,
                "result": result,
            },
            "H4",
        )
        # #endregion
        return result
    except (ValueError, TypeError):
        return s
