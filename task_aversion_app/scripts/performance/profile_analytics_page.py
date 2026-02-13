#!/usr/bin/env python3
"""
Profile the analytics page backend load with cProfile.

Runs the same backend calls as build_analytics_page() (cold cache) and outputs
a sorted profile to identify hot functions. Run from task_aversion_app:

  python scripts/performance/profile_analytics_page.py [--warm]
  PROFILE_USER_ID=1 python scripts/performance/profile_analytics_page.py

  --warm   Use warm cache (don't clear before run). Default is cold.
"""
from __future__ import annotations

import cProfile
import os
import pstats
import sys
from datetime import datetime, timezone
from io import StringIO
from pathlib import Path

# Add task_aversion_app to path
ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.chdir(ROOT)


def _mock_auth(user_id: int) -> None:
    """Mock get_current_user to return user_id for profiling without auth."""
    import backend.auth as auth_mod

    auth_mod.get_current_user = lambda: user_id  # type: ignore[method-assign]


def run_analytics_page_backend(user_id: int = 1, warm: bool = False) -> None:
    """Simulate the backend calls made during build_analytics_page()."""
    _mock_auth(user_id)

    from backend.analytics import Analytics

    analytics = Analytics()

    if not warm:
        # Cold load: clear caches
        for attr in (
            "_relief_summary_cache", "_relief_summary_cache_time",
            "_life_balance_cache", "_life_balance_cache_time",
            "_composite_scores_cache", "_composite_scores_cache_time",
            "_instances_cache_all", "_instances_cache_all_time",
            "_instances_cache_completed", "_instances_cache_completed_time",
            "_dashboard_metrics_cache", "_dashboard_metrics_cache_time",
            "_time_tracking_cache", "_time_tracking_cache_time",
            "_time_tracking_cache_params",
            "_trend_series_cache", "_trend_series_cache_time",
            "_attribute_distribution_cache", "_attribute_distribution_cache_time",
            "_stress_dimension_cache", "_stress_dimension_cache_time",
            "_rankings_cache", "_leaderboard_cache", "_leaderboard_cache_time",
            "_leaderboard_cache_top_n",
        ):
            c = getattr(Analytics, attr, None)
            if c is not None and hasattr(c, "clear"):
                c.clear()

    # 1. Warm instances (build_analytics_page does this first)
    analytics._load_instances(user_id=user_id)
    analytics._load_instances(completed_only=True, user_id=user_id)

    # 2. Main batched call
    page_data = analytics.get_analytics_page_data(days=7, user_id=user_id)
    metrics = page_data["dashboard_metrics"]
    relief_summary = page_data["relief_summary"]
    tracking_data = page_data["time_tracking"]

    # 3. Chart data (used later in the page)
    chart_data = analytics.get_chart_data(user_id=user_id)

    # 4. Rankings data
    rankings_data = analytics.get_rankings_data(user_id=user_id)

    # 5. Composite score (async in real page, but we run it for completeness)
    all_scores = analytics.get_all_scores_for_composite(days=7, user_id=user_id)
    from backend.user_state import UserStateManager

    user_state = UserStateManager()
    weights = user_state.get_score_weights(str(user_id)) or {}
    analytics.calculate_composite_score(
        components=all_scores, weights=weights, normalize_components=True
    )

    # 6. Productivity goal settings (used in productivity volume section)
    user_state.get_productivity_goal_settings(str(user_id))

    # Prevent "unused variable" complaints
    _ = metrics, relief_summary, tracking_data, chart_data, rankings_data


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="Profile analytics page backend")
    parser.add_argument(
        "--warm",
        action="store_true",
        help="Use warm cache (don't clear before run)",
    )
    parser.add_argument(
        "--user",
        type=int,
        default=int(os.getenv("PROFILE_USER_ID", "1")),
        help="User ID for profiling (default: 1 or PROFILE_USER_ID)",
    )
    parser.add_argument(
        "-o",
        "--output",
        type=str,
        default="",
        help="Save stats to file (optional)",
    )
    args = parser.parse_args()

    print("=" * 72)
    print("ANALYTICS PAGE PROFILE")
    print("=" * 72)
    print(f"User ID: {args.user}")
    print(f"Cache: {'warm' if args.warm else 'cold'}")
    print()

    # Warmup run (imports, first-time setup) - not profiled
    print("[INFO] Warmup run (loads imports)...")
    run_analytics_page_backend(user_id=args.user, warm=True)
    if not args.warm:
        print("[INFO] Cleared caches for cold profile.")
    print("[INFO] Profiling run...")
    print()

    profiler = cProfile.Profile()
    profiler.enable()
    try:
        run_analytics_page_backend(user_id=args.user, warm=args.warm)
    except Exception as e:
        print(f"[FAIL] {e}")
        import traceback

        traceback.print_exc()
        return 1
    finally:
        profiler.disable()

    s = StringIO()
    ps = pstats.Stats(profiler, stream=s).sort_stats(pstats.SortKey.CUMULATIVE)
    ps.print_stats(80)  # Top 80 by cumulative time

    output = s.getvalue()
    print(output)

    if args.output:
        out_path = Path(args.output)
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        block = f"\n{'=' * 72}\nRUN: {stamp}  (cache: {'warm' if args.warm else 'cold'}, user_id={args.user})\n{'=' * 72}\n{output}"
        if out_path.exists():
            with open(out_path, "a", encoding="utf-8") as f:
                f.write(block)
        else:
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text(block.lstrip(), encoding="utf-8")
        print(f"[INFO] Stats appended to {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
