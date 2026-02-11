#!/usr/bin/env python3
"""
Cross-cutting: analytics + settings config/read operations.

Spans two pages: lists which backend read operations (user_state.get_*,
analytics_service.get_*) are used on the Analytics page vs the Settings page.
Supports enmeshed optimization by showing shared config reads (e.g. score weights,
productivity goal settings) and page-specific data loads. Static analysis of
ui/analytics_page.py and ui/settings_page.py. Yields meaningful per-page and
shared-call data.

Run from task_aversion_app:
  python scripts/performance/analytics_settings_config_reads.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

# Config-style reads (small/keyed data): score weights, productivity settings, categories
CONFIG_READS = frozenset({
    "get_score_weights",
    "get_productivity_goal_settings",
    "get_cancellation_categories",
    "get_dashboard_metrics",  # monitored metrics config
})


def extract_backend_calls(file_path: Path) -> set[str]:
    """
    Extract backend method calls: user_state.METHOD( or analytics_service.METHOD(.
    Returns set of 'service.method_name'.
    """
    try:
        text = file_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return set()

    found: set[str] = set()
    # user_state.get_*(...) or analytics_service.get_*(...); also set_* for settings writes
    for pattern in (
        r"user_state\.(\w+)\s*\(",
        r"analytics_service\.(\w+)\s*\(",
    ):
        for m in re.finditer(pattern, text):
            method = m.group(1)
            if "user_state" in pattern:
                found.add("user_state." + method)
            else:
                found.add("analytics_service." + method)
    return found


def main() -> int:
    base = Path(__file__).resolve().parent.parent.parent
    analytics_py = base / "ui" / "analytics_page.py"
    settings_py = base / "ui" / "settings_page.py"

    analytics_calls = extract_backend_calls(analytics_py) if analytics_py.is_file() else set()
    settings_calls = extract_backend_calls(settings_py) if settings_py.is_file() else set()

    print("=" * 72)
    print("ANALYTICS + SETTINGS CONFIG READS (cross-cutting: two pages)")
    print("=" * 72)
    print()
    print("--- Analytics page (ui/analytics_page.py) ---")
    config_analytics = sorted(c for c in analytics_calls if c.split(".")[-1] in CONFIG_READS)
    other_analytics = sorted(c for c in analytics_calls if c.split(".")[-1] not in CONFIG_READS)
    if config_analytics:
        print("  Config/weights/settings reads: %s" % ", ".join(config_analytics))
    if other_analytics:
        print("  Other backend calls: %s" % ", ".join(other_analytics))
    print("  Total distinct calls: %d" % len(analytics_calls))
    print()
    print("--- Settings page (ui/settings_page.py) ---")
    config_settings = sorted(c for c in settings_calls if c.split(".")[-1] in CONFIG_READS)
    other_settings = sorted(c for c in settings_calls if c.split(".")[-1] not in CONFIG_READS)
    if config_settings:
        print("  Config/weights/settings reads: %s" % ", ".join(config_settings))
    if other_settings:
        print("  Other backend calls: %s" % ", ".join(other_settings))
    print("  Total distinct calls: %d" % len(settings_calls))
    print()
    shared = analytics_calls & settings_calls
    if shared:
        print("--- Shared (both pages) ---")
        print("  %s" % ", ".join(sorted(shared)))
        print("  These backends are used on both Analytics and Settings; optimize once.")
    print()
    print("[INFO] Config reads (score weights, productivity goals, cancellation categories)")
    print("       are good candidates for caching if hit on both pages.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
