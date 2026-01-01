# ui/summary_page.py
from nicegui import ui
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


@ui.page('/summary')
def summary_page():
    """Summary page showing composite score and component contributions."""
    
    # Get user ID (using a simple approach - in production you'd get this from session)
    user_id = "default_user"  # TODO: Get from session/auth
    
    # Get current weights
    current_weights = user_state.get_score_weights(user_id) or DEFAULT_WEIGHTS.copy()
    
    # Get all scores
    all_scores = analytics.get_all_scores_for_composite(days=7)
    
    # Calculate composite score
    composite_result = analytics.calculate_composite_score(
        components=all_scores,
        weights=current_weights,
        normalize_components=True
    )
    
    ui.label("Summary").classes("text-2xl font-bold mb-2")
    ui.label("View your overall performance score and component contributions.").classes(
        "text-gray-500 mb-4"
    )
    
    # Main composite score display
    with ui.card().classes("w-full max-w-4xl p-6 mb-4"):
        with ui.row().classes("items-center gap-4 w-full"):
            ui.label("Composite Score").classes("text-xl font-semibold")
            with ui.card().classes("p-4 bg-blue-50 border-2 border-blue-300"):
                ui.label(f"{composite_result['composite_score']:.1f}").classes(
                    "text-4xl font-bold text-blue-700"
                )
                ui.label("/ 100").classes("text-lg text-blue-600")
        
        ui.separator().classes("my-4")
        
        # Component contributions
        ui.label("Component Contributions").classes("text-lg font-semibold mb-2")
        contributions = composite_result.get('component_contributions', {})
        normalized_weights = composite_result.get('normalized_weights', {})
        
        with ui.grid(columns=2).classes("gap-2 w-full"):
            for component_name, score_value in all_scores.items():
                contribution = contributions.get(component_name, 0.0)
                weight = normalized_weights.get(component_name, 0.0)
                label = COMPONENT_LABELS.get(component_name, component_name)
                
                with ui.card().classes("p-3"):
                    with ui.row().classes("items-center justify-between w-full"):
                        ui.label(label).classes("text-sm font-medium")
                        ui.label(f"{score_value:.1f}").classes("text-sm text-gray-600")
                    with ui.row().classes("items-center justify-between w-full mt-1"):
                        ui.label(f"Weight: {weight:.1%}").classes("text-xs text-gray-500")
                        ui.label(f"Contribution: {contribution:.1f}").classes("text-xs font-semibold")
