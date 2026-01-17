from nicegui import ui
from backend.user_state import UserStateManager
from backend.analytics import Analytics
from ui.error_reporting import handle_error_with_ui

user_state = UserStateManager()
analytics = Analytics()
DEFAULT_USER_ID = "default_user"

# Component labels
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

DEFAULT_WEIGHTS = {k: 1.0 for k in COMPONENT_LABELS.keys()}


@ui.page("/settings/composite-score-weights")
def composite_score_weights_page():
    ui.label("Composite Score Weights").classes("text-2xl font-bold mb-2")
    ui.label("Adjust the importance of each component in your composite score. Weights are automatically normalized.").classes("text-gray-600 mb-4")
    
    # Get current user_id
    from backend.auth import get_current_user
    current_user_id = get_current_user()
    user_id_str = str(current_user_id) if current_user_id is not None else DEFAULT_USER_ID
    
    # Get current weights
    current_weights = user_state.get_score_weights(user_id_str) or DEFAULT_WEIGHTS.copy()
    all_scores = analytics.get_all_scores_for_composite(days=7, user_id=current_user_id)
    
    weight_inputs = {}
    
    with ui.card().classes("w-full max-w-4xl p-4 gap-3"):
        with ui.grid(columns=2).classes("gap-3 w-full"):
            for component_name in COMPONENT_LABELS.keys():
                if component_name not in all_scores:
                    continue
                label = COMPONENT_LABELS.get(component_name, component_name)
                current_weight = current_weights.get(component_name, 1.0)
                score_value = all_scores.get(component_name, 0.0)
                
                with ui.card().classes("p-3"):
                    ui.label(label).classes("text-sm font-medium mb-1")
                    ui.label(f"Current Score: {score_value:.1f}").classes("text-xs text-gray-500 mb-2")
                    
                    weight_input = ui.number(
                        label="Weight",
                        value=float(current_weight),
                        min=0.0,
                        max=10.0,
                        step=0.1,
                        precision=1
                    ).classes("w-full").props("dense outlined")
                    weight_inputs[component_name] = weight_input
        
        def save_composite_weights():
            try:
                new_weights = {
                    name: float(input.value) if input.value is not None else 1.0
                    for name, input in weight_inputs.items()
                }
                new_weights = {k: v for k, v in new_weights.items() if v > 0}
                
                if not new_weights:
                    ui.notify("At least one weight must be greater than 0", color='warning')
                    return
                
                user_state.set_score_weights(user_id_str, new_weights)
                ui.notify("Composite score weights saved!", color='positive')
            except Exception as e:
                handle_error_with_ui(
                    operation="save composite score weights",
                    error=e,
                    user_id=current_user_id,
                    context={"page": "composite_score_weights"},
                    user_message="Failed to save composite score weights. Please try again."
                )
        
        def reset_composite_weights():
            for component_name, input_widget in weight_inputs.items():
                input_widget.value = 1.0
            ui.notify("Weights reset to defaults. Click 'Save' to apply.", color='info')
        
        with ui.row().classes("gap-2 mt-3"):
            ui.button("Save Weights", on_click=save_composite_weights, color="positive").classes("bg-green-500 text-white")
            ui.button("Reset to Defaults", on_click=reset_composite_weights).classes("bg-gray-500 text-white")
            ui.button("Back to Settings", on_click=lambda: ui.navigate.to("/settings")).classes("bg-blue-500 text-white")

