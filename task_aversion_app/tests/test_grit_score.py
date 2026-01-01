import math

import pandas as pd

from backend.analytics import Analytics


def _row(completion_pct=100, time_actual=60, time_estimate=30, relief=60, emotional=40):
    return pd.Series({
        'actual_dict': {
            'completion_percent': completion_pct,
            'time_actual_minutes': time_actual,
            'actual_relief': relief,
            'actual_emotional': emotional,
        },
        'predicted_dict': {
            'time_estimate_minutes': time_estimate,
        },
        'task_id': 't1',
    })


def test_persistence_curve_anchors():
    analytics = Analytics()
    counts = [2, 10, 25, 50, 100]
    expected_ranges = {
        2: (1.0, 1.05),
        10: (1.1, 1.35),
        25: (1.4, 1.8),
        50: (1.9, 2.8),
        100: (3.0, 5.1),
    }
    for c in counts:
        row = _row()
        score = analytics.calculate_grit_score(row, {'t1': c})
        # back out multiplier component: divide by base (100) and time bonus (~1.5 max early)
        multiplier = score / 100.0
        low, high = expected_ranges[c]
        assert low <= multiplier <= high, f"count {c} got {multiplier}"


def test_time_bonus_caps_and_fade():
    analytics = Analytics()
    # 2x overrun, high difficulty -> should get >1.4x time bonus early
    row = _row(time_actual=60, time_estimate=30, relief=60, emotional=40)
    score = analytics.calculate_grit_score(row, {'t1': 1})
    base = 100
    multiplier = score / base
    assert multiplier > 1.4

    # After many repetitions, time bonus should fade
    faded_score = analytics.calculate_grit_score(row, {'t1': 60})
    faded_multiplier = faded_score / base
    assert faded_multiplier < multiplier  # faded down


def test_neutral_when_missing_time():
    analytics = Analytics()
    row = _row(time_actual=0, time_estimate=0)
    score = analytics.calculate_grit_score(row, {'t1': 5})
    # No time data => time_bonus = 1; persistence still >1
    assert score >= 100

