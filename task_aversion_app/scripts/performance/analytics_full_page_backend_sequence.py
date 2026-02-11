#!/usr/bin/env python3
"""
Full analytics page: backend call sequence and data sources.

Targets the Analytics main page (/analytics, ui/analytics_page.py). Documents the
order and identity of backend calls made during a full analytics page load
(build_analytics_page): get_analytics_page_data, composite score load
(get_all_scores_for_composite, calculate_composite_score), get_chart_data,
get_rankings_data, user_state calls. Use to attribute load and plan batching or
caching. Static analysis; no DB or live app required.

Run from task_aversion_app:
  python scripts/performance/analytics_full_page_backend_sequence.py
"""
from __future__ import annotations

import re
import sys
from pathlib import Path


def main() -> int:
    root = Path(__file__).resolve().parent.parent.parent
    analytics_page = root / "ui" / "analytics_page.py"
    if not analytics_page.is_file():
        print(f"[FAIL] Not found: {analytics_page}")
        return 1

    text = analytics_page.read_text(encoding="utf-8", errors="replace")
    # Find build_analytics_page and extract call order (heuristic: analytics_service.* and user_state.*)
    sequence: list[tuple[str, str]] = []  # (call_site, method)
    for m in re.finditer(
        r"(analytics_service\.(\w+)|user_state\.(\w+))",
        text,
    ):
        full = m.group(1)
        an = m.group(2)
        us = m.group(3)
        method = an if an else (us if us else "")
        prefix = "analytics_service" if an else "user_state"
        sequence.append((f"{prefix}.{method}", method))

    # Dedupe while preserving order
    seen: set[str] = set()
    ordered: list[str] = []
    for full, _ in sequence:
        if full not in seen:
            seen.add(full)
            ordered.append(full)

    print("=" * 72)
    print("ANALYTICS FULL PAGE BACKEND SEQUENCE")
    print("=" * 72)
    print("Target: full analytics page (/analytics, build_analytics_page).")
    print("Lists backend calls in source order (approximate load sequence).")
    print()
    print("--- Call order (first occurrence in build_analytics_page) ---")
    for i, call in enumerate(ordered, 1):
        print(f"  {i:2d}. {call}()")
    print()
    print("--- Key data batches (from code) ---")
    print("  1. user_state.get_score_weights (composite weights)")
    print("  2. analytics_service.get_all_scores_for_composite (async timer; composite score load)")
    print("  3. analytics_service.calculate_composite_score (in-memory after get_all_scores_for_composite)")
    print("  4. analytics_service.get_analytics_page_data (dashboard_metrics, relief_summary, time_tracking)")
    print("  5. analytics_service.get_chart_data (trend_series, attribute_distribution, stress_dimension_data)")
    print("  6. analytics_service.get_rankings_data (rankings + leaderboard)")
    print("  7. user_state.get_productivity_goal_settings (for productivity volume section)")
    print()
    print("[INFO] Static scan only. For timings use query log or live app.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
