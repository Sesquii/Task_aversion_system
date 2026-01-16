"""Goals page - Landing page for goal tracking features."""
from nicegui import ui
from fastapi import Request
from backend.user_state import UserStateManager
from backend.auth import get_current_user

user_state = UserStateManager()
DEFAULT_USER_ID = "default_user"


@ui.page("/goals")
def goals_page(request: Request = None):
    """Goals landing page - Productivity goals only."""
    
    # Get current user for data isolation
    current_user_id = get_current_user()
    if current_user_id is None:
        ui.navigate.to('/login')
        return
    
    user_id_str = str(current_user_id) if current_user_id is not None else DEFAULT_USER_ID
    
    ui.label("Goals").classes("text-3xl font-bold mb-4")
    ui.label("Track and manage your productivity goals.").classes("text-gray-600 mb-6")
    
    # Productivity Hours Goal Tracking
    with ui.card().classes("w-full max-w-4xl p-6"):
        ui.label("Productivity Goals").classes("text-xl font-semibold mb-4")
        
        with ui.card().classes("p-4 mb-4 border border-gray-300"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("flex-1 gap-2"):
                    ui.label("Productivity Hours Goal Tracking").classes("text-lg font-semibold")
                    ui.label(
                        "Track weekly productivity hours vs goals with rolling 7-day or "
                        "Monday-based week calculations. Includes daily trend visualization "
                        "and pace projection."
                    ).classes("text-sm text-gray-700")
                ui.button(
                    "Open",
                    on_click=lambda: ui.navigate.to("/goals/productivity-hours")
                ).classes("bg-blue-500 text-white ml-4")
    
    ui.button("Back to Dashboard", on_click=lambda: ui.navigate.to("/")).classes("mt-4")

