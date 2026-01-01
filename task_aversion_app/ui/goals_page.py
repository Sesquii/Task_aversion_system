"""Goals page - Landing page for goal tracking features."""
from nicegui import ui


@ui.page("/goals")
def goals_page():
    """Goals landing page."""
    
    ui.label("Goals").classes("text-3xl font-bold mb-4")
    ui.label("Track and manage your productivity and performance goals.").classes("text-gray-600 mb-6")
    
    # Goals List
    with ui.card().classes("w-full max-w-4xl p-6"):
        ui.label("Available Goals").classes("text-xl font-semibold mb-4")
        
        # Productivity Hours Goal Tracking
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
        
        # Placeholder for future goals
        with ui.card().classes("p-4 bg-gray-50 border border-gray-200"):
            ui.label("More goal tracking features coming soon...").classes("text-sm text-gray-500 italic")
    
    ui.button("Back to Dashboard", on_click=lambda: ui.navigate.to("/")).classes("mt-4")

