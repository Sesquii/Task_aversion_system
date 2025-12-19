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
}


@ui.page('/composite-score')
def composite_score_page():
    """Page for viewing and managing composite score with customizable weights."""
    
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
    
    # Get time tracking details
    tracking_data = analytics.calculate_time_tracking_consistency_score(days=7)
    
    ui.label("Composite Score Dashboard").classes("text-2xl font-bold mb-2")
    ui.label("View your overall performance score and customize component weights.").classes(
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
    
    # Time Tracking Consistency Details
    with ui.card().classes("w-full max-w-4xl p-6 mb-4"):
        ui.label("Time Tracking Consistency").classes("text-xl font-semibold mb-2")
        
        with ui.row().classes("gap-4 flex-wrap"):
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Tracking Score").classes("text-xs text-gray-500")
                ui.label(f"{tracking_data['tracking_consistency_score']:.1f}").classes(
                    "text-2xl font-bold"
                )
                ui.label("/ 100").classes("text-xs text-gray-600")
            
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Avg Tracked Time").classes("text-xs text-gray-500")
                tracked_hours = tracking_data['avg_tracked_time_minutes'] / 60.0
                ui.label(f"{tracked_hours:.1f} hrs").classes("text-lg font-semibold")
                ui.label(f"({tracking_data['avg_tracked_time_minutes']:.0f} min)").classes(
                    "text-xs text-gray-600"
                )
            
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Avg Untracked Time").classes("text-xs text-gray-500")
                untracked_hours = tracking_data['avg_untracked_time_minutes'] / 60.0
                ui.label(f"{untracked_hours:.1f} hrs").classes("text-lg font-semibold text-orange-600")
                ui.label(f"({tracking_data['avg_untracked_time_minutes']:.0f} min)").classes(
                    "text-xs text-gray-600"
                )
            
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Avg Sleep Time").classes("text-xs text-gray-500")
                sleep_hours = tracking_data['avg_sleep_time_minutes'] / 60.0
                ui.label(f"{sleep_hours:.1f} hrs").classes("text-lg font-semibold")
                ui.label(f"({tracking_data['avg_sleep_time_minutes']:.0f} min)").classes(
                    "text-xs text-gray-600"
                )
            
            with ui.card().classes("p-3 min-w-[200px]"):
                ui.label("Tracking Coverage").classes("text-xs text-gray-500")
                coverage_pct = tracking_data['tracking_coverage'] * 100.0
                ui.label(f"{coverage_pct:.1f}%").classes("text-lg font-semibold")
                ui.label("of day tracked").classes("text-xs text-gray-600")
        
        ui.separator().classes("my-3")
        ui.label(
            "Note: Sleep up to 8 hours is rewarded. Untracked time is penalized. "
            "Higher tracking consistency means more of your day is logged."
        ).classes("text-sm text-gray-600")
    
    # Weight customization section
    with ui.card().classes("w-full max-w-4xl p-6 mb-4"):
        ui.label("Customize Component Weights").classes("text-xl font-semibold mb-2")
        ui.label(
            "Adjust the importance of each component in your composite score. "
            "Weights are automatically normalized to sum to 1.0."
        ).classes("text-sm text-gray-600 mb-4")
        
        weight_inputs = {}
        
        with ui.grid(columns=2).classes("gap-4 w-full"):
            for component_name, score_value in all_scores.items():
                label = COMPONENT_LABELS.get(component_name, component_name)
                current_weight = current_weights.get(component_name, 1.0)
                
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
                    ).classes("w-full")
                    weight_inputs[component_name] = weight_input
        
        def save_weights():
            """Save updated weights."""
            new_weights = {
                name: float(input.value) if input.value is not None else 1.0
                for name, input in weight_inputs.items()
            }
            
            # Remove zero weights
            new_weights = {k: v for k, v in new_weights.items() if v > 0}
            
            if not new_weights:
                ui.notify("At least one weight must be greater than 0", color='warning')
                return
            
            user_state.set_score_weights(user_id, new_weights)
            ui.notify("Weights saved! Refresh to see updated composite score.", color='positive')
        
        def reset_weights():
            """Reset weights to defaults."""
            for component_name, input_widget in weight_inputs.items():
                default_weight = DEFAULT_WEIGHTS.get(component_name, 1.0)
                input_widget.value = default_weight
            ui.notify("Weights reset to defaults. Click 'Save Weights' to apply.", color='info')
        
        with ui.row().classes("gap-2 mt-4"):
            ui.button("Save Weights", on_click=save_weights).classes("bg-blue-500 text-white")
            ui.button("Reset to Defaults", on_click=reset_weights).classes("bg-gray-500 text-white")
            ui.button("Refresh Scores", on_click=lambda: ui.navigate.reload()).classes("bg-green-500 text-white")
    
    # Integration info
    with ui.card().classes("w-full max-w-4xl p-6"):
        ui.label("Integration").classes("text-lg font-semibold mb-2")
        ui.label(
            "The tracking consistency score can be used as a multiplier or factor in other calculations. "
            "The composite score provides a holistic view of your performance across all dimensions."
        ).classes("text-sm text-gray-600")
        
        with ui.expansion("How to use tracking consistency as a multiplier", icon="info").classes("w-full mt-2"):
            ui.label(
                "You can multiply other scores by the tracking consistency factor:\n\n"
                "adjusted_score = base_score * (tracking_consistency_score / 100.0)\n\n"
                "This penalizes scores when time tracking is incomplete."
            ).classes("text-sm text-gray-700 whitespace-pre-line p-2")

