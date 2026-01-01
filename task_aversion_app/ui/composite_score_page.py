# ui/composite_score_page.py
from nicegui import ui
import json
from backend.analytics import Analytics
from backend.user_state import UserStateManager

analytics = Analytics()
user_state = UserStateManager()

# Default component labels for display
COMPONENT_LABELS = {
    'tracking_consistency_score': 'Time Tracking Consistency',
    'avg_stress_level': 'Low Stress (inverted)',
    'avg_net_wellbeing': 'Net Wellbeing',
    'avg_stress_efficiency': 'Stress Efficiency',
    'avg_relief': 'Average Relief',
    'work_volume_score': 'Work Volume',
    'work_consistency_score': 'Work Consistency',
    'life_balance_score': 'Life Balance',
    'weekly_relief_score': 'Weekly Relief',
    'completion_rate': 'Completion Rate',
    'self_care_frequency': 'Self-Care Frequency',
    'execution_score': 'Execution Score',
}

# Default weights (equal weights)
DEFAULT_WEIGHTS = {
    'tracking_consistency_score': 1.0,
    'avg_stress_level': 1.0,
    'avg_net_wellbeing': 1.0,
    'avg_stress_efficiency': 1.0,
    'avg_relief': 1.0,
    'work_volume_score': 1.0,
    'work_consistency_score': 1.0,
    'life_balance_score': 1.0,
    'weekly_relief_score': 1.0,
    'completion_rate': 1.0,
    'self_care_frequency': 1.0,
    'execution_score': 1.0,
}


@ui.page('/composite-score')
def composite_score_page():
    """Redirect to Summary page for backward compatibility."""
    ui.navigate.to('/summary')

