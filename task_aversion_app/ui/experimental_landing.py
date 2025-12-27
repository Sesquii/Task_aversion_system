"""Experimental systems landing page.

Lists all experimental features and systems.
"""
from nicegui import ui


@ui.page("/experimental")
def experimental_landing_page():
    """Landing page for experimental systems."""
    
    ui.label("Experimental Systems").classes("text-3xl font-bold mb-4")
    ui.label("These features are experimental and may change or be removed. Use at your own risk.").classes("text-gray-600 mb-6")
    
    # Experimental Systems List
    with ui.card().classes("w-full max-w-4xl p-6"):
        ui.label("Available Experimental Features").classes("text-xl font-semibold mb-4")
        
        # Productivity Hours Goal Tracking System
        with ui.card().classes("p-4 mb-4 border border-gray-300"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("flex-1 gap-2"):
                    ui.label("Productivity Hours Goal Tracking").classes("text-lg font-semibold")
                    ui.label(
                        "Track weekly productivity hours vs goals, set productivity targets, "
                        "and see how goal achievement affects productivity scores. Includes "
                        "hybrid initialization (auto-estimate with manual adjustment)."
                    ).classes("text-sm text-gray-700")
                ui.button(
                    "Open",
                    on_click=lambda: ui.navigate.to("/experimental/productivity-hours-goal-tracking-system")
                ).classes("bg-blue-500 text-white ml-4")
        
        # Formula Baseline Charts
        with ui.card().classes("p-4 mb-4 border border-gray-300"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("flex-1 gap-2"):
                    ui.label("Formula Baseline Charts").classes("text-lg font-semibold")
                    ui.label(
                        "Theoretical charts for all score and points systems to help refine formulas. "
                        "Includes 6 charts per variable plus correlation charts for weight calibration. "
                        "Each chart has a notes section for analysis."
                    ).classes("text-sm text-gray-700")
                ui.button(
                    "Open",
                    on_click=lambda: ui.navigate.to("/experimental/formula-baseline-charts")
                ).classes("bg-blue-500 text-white ml-4")
        
        # Formula Control System
        with ui.card().classes("p-4 mb-4 border border-gray-300"):
            with ui.row().classes("w-full items-center justify-between"):
                with ui.column().classes("flex-1 gap-2"):
                    ui.label("Formula Control System").classes("text-lg font-semibold")
                    ui.label(
                        "Universal formula control system for adjusting formula parameters dynamically. "
                        "Each formula has its own page with adjustable parameters, real-time Plotly visualizations, "
                        "parameter comparison, and CSV persistence. Settings are automatically synced for immediate use in calculations."
                    ).classes("text-sm text-gray-700")
                ui.button(
                    "Open",
                    on_click=lambda: ui.navigate.to("/experimental/formula-control-system")
                ).classes("bg-blue-500 text-white ml-4")
        
        # Placeholder for future experimental systems
        with ui.card().classes("p-4 bg-gray-50 border border-gray-200"):
            ui.label("More experimental features coming soon...").classes("text-sm text-gray-500 italic")
    
    ui.button("Back to Dashboard", on_click=lambda: ui.navigate.to("/")).classes("mt-4")
