"""
Urgency score computation for task instances.

Urgency = importance over time: combines time since initialized, due date,
and optional habitual procrastination (postpone history). Used for UI (red/yellow)
and as a weighted factor in recommendations.
"""
from datetime import datetime
from typing import Any, Dict, Optional

# Days since initialized at which the "time" component caps (bounded linear)
DEFAULT_DAYS_CAP = 14
# Score contribution per day up to cap
SCORE_PER_DAY_CAP = 5.0
MAX_TIME_SCORE = 70.0
POSTPONE_BOOST_PER_EVENT = 5.0
MAX_POSTPONE_BOOST = 20.0

_DATE_FMTS = (
    "%Y-%m-%d %H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%d",
    "%Y-%m-%dT%H:%M:%S",
)


def _parse_dt(value: Any) -> Optional[datetime]:
    """Parse datetime from string or return None."""
    if value is None or (isinstance(value, str) and not value.strip()):
        return None
    if isinstance(value, datetime):
        return value
    try:
        s = str(value).strip()
        for fmt in _DATE_FMTS:
            try:
                return datetime.strptime(s[: len(fmt) + 2].replace("T", " "), fmt)
            except ValueError:
                continue
        return None
    except (ValueError, TypeError):
        return None


def compute_urgency(
    instance: Dict[str, Any],
    task_horizon_days: int = 14,
    now: Optional[datetime] = None,
) -> Dict[str, Any]:
    """
    Compute urgency score and flags for an instance.

    Args:
        instance: Instance dict with initialized_at, due_at (opt), actual (opt).
        task_horizon_days: Days after which no-due-date tasks are "stale" (yellow).
        now: Reference time (default: now).

    Returns:
        dict with: score (0-100), overdue, stale, due_at_display, explanation.
    """
    if now is None:
        now = datetime.utcnow()

    result = {
        "score": 0.0,
        "overdue": False,
        "stale": False,
        "due_at_display": None,
        "explanation": "",
    }

    initialized_at = _parse_dt(instance.get("initialized_at"))
    due_at = _parse_dt(instance.get("due_at"))

    if due_at is not None:
        result["due_at_display"] = due_at.strftime("%b %d, %I:%M %p").replace(" 0", " ")
        if now > due_at:
            result["overdue"] = True
            result["score"] = 100.0
            result["explanation"] = "Past due"
            return result
        days_left = (due_at - now).total_seconds() / 86400
        if days_left <= 1:
            result["score"] = 70.0 + (1.0 - days_left) * 30.0
        elif days_left <= 3:
            result["score"] = 50.0 + (3.0 - days_left) * 10.0
        else:
            result["score"] = min(50.0, 20.0 + days_left)

    # Only add time-since-init and postpone boost when task has a deadline (urgency = deadline-driven)
    if due_at is not None and initialized_at:
        delta = now - initialized_at
        days_since = max(0.0, delta.total_seconds() / 86400)
        time_component = min(MAX_TIME_SCORE, days_since * SCORE_PER_DAY_CAP)
        result["score"] = min(100.0, result["score"] + time_component)
        if result["explanation"]:
            result["explanation"] += "; "
        result["explanation"] += f"active {int(days_since)} days"
        actual = instance.get("actual") or {}
        if isinstance(actual, str):
            try:
                import json
                actual = json.loads(actual) if actual.strip() else {}
            except (TypeError, ValueError):
                actual = {}
        postpone_history = actual.get("postpone_history") or []
        if isinstance(postpone_history, list):
            n = len(postpone_history)
            boost = min(MAX_POSTPONE_BOOST, n * POSTPONE_BOOST_PER_EVENT)
            result["score"] = min(100.0, result["score"] + boost)
            if boost > 0 and result["explanation"]:
                result["explanation"] += f"; postponed {n} time(s)"
    elif initialized_at:
        # No due date: no urgency score; still set stale and explanation for UI (e.g. yellow)
        delta = now - initialized_at
        days_since = max(0.0, delta.total_seconds() / 86400)
        if result["explanation"]:
            result["explanation"] += "; "
        result["explanation"] += f"active {int(days_since)} days"
        if days_since > task_horizon_days:
            result["stale"] = True
            result["explanation"] += " (stale)"
    else:
        if due_at is None:
            result["explanation"] = "Not initialized"

    result["score"] = round(result["score"], 1)
    return result
