from nicegui import ui
from backend.user_state import UserStateManager

user_state = UserStateManager()
DEFAULT_USER_ID = "default_user"

# Default cancellation categories
DEFAULT_CANCELLATION_CATEGORIES = {
    'did_while_another_active': 'Did task while another task was active',
    'deferred_to_plan': 'Deferred to plan instead of executing',
    'development_test': 'Development/test task',
    'accidental_initialization': 'Accidentally initialized',
    'failed_to_complete': 'Failed to complete task',
    'other': 'Other reason'
}


def get_all_cancellation_categories():
    """Get all cancellation categories (default + custom)."""
    from backend.auth import get_current_user
    current_user_id = get_current_user()
    user_id_str = str(current_user_id) if current_user_id is not None else DEFAULT_USER_ID
    custom_categories = user_state.get_cancellation_categories(user_id_str)
    all_categories = {**DEFAULT_CANCELLATION_CATEGORIES, **custom_categories}
    return all_categories


def get_cancellation_penalties():
    """Get cancellation penalty configuration."""
    penalties = user_state.get_cancellation_penalties(DEFAULT_USER_ID)
    if not penalties:
        return {
            'development_test': 0.0,
            'accidental_initialization': 0.0,
            'deferred_to_plan': 0.1,
            'did_while_another_active': 0.0,
            'failed_to_complete': 1.0,
            'other': 0.5
        }
    return penalties


@ui.page("/settings/cancellation-penalties")
def cancellation_penalties_page():
    ui.label("Cancellation Penalties").classes("text-2xl font-bold mb-2")
    ui.label("Configure productivity penalties for different cancellation reasons. Penalties are multipliers (0.0 = no penalty, 1.0 = full penalty).").classes("text-gray-600 mb-4")
    
    def refresh_penalty_config():
        penalty_container.clear()
        with penalty_container:
            penalties = get_cancellation_penalties()
            all_categories = get_all_cancellation_categories()
            
            with ui.column().classes("w-full gap-3"):
                for cat_key, cat_label in sorted(all_categories.items()):
                    is_default = cat_key in DEFAULT_CANCELLATION_CATEGORIES
                    current_penalty = penalties.get(cat_key, 0.5)
                    
                    with ui.card().classes("w-full p-3 border border-gray-200"):
                        with ui.row().classes("w-full items-center justify-between gap-3"):
                            with ui.column().classes("flex-1 gap-1"):
                                ui.label(cat_label).classes("text-base font-semibold")
                                ui.label(f"Key: {cat_key}").classes("text-xs text-gray-500")
                                if is_default:
                                    ui.label("Default category").classes("text-xs text-blue-600")
                            
                            penalty_input = ui.number(
                                label="Penalty Multiplier",
                                value=current_penalty,
                                min=0.0,
                                max=1.0,
                                step=0.1,
                                precision=1
                            ).classes("w-32").props("dense outlined")
                            
                            def save_penalty(key=cat_key, input_field=penalty_input):
                                new_penalty = float(input_field.value or 0.0)
                                penalties = get_cancellation_penalties()
                                penalties[key] = max(0.0, min(1.0, new_penalty))
                                user_state.set_cancellation_penalties(penalties, DEFAULT_USER_ID)
                                ui.notify("Penalty saved", color="positive")
                            
                            ui.button("Save", on_click=lambda k=cat_key: save_penalty(k, penalty_input), color="positive").classes("bg-green-500 text-white text-xs")
    
    with ui.card().classes("w-full max-w-4xl p-4 gap-3"):
        penalty_container = ui.column().classes("w-full mt-3")
        refresh_penalty_config()
        
        ui.button("Back to Settings", on_click=lambda: ui.navigate.to("/settings")).classes("bg-blue-500 text-white mt-4")

