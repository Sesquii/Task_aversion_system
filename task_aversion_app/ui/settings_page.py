from nicegui import ui
from backend.user_state import UserStateManager

user_state = UserStateManager()
DEFAULT_USER_ID = "default_user"


@ui.page("/settings")
def settings_page():
    def go_survey():
        ui.navigate.to("/survey")
    
    # def go_data_guide():
    #     ui.navigate.to("/data-guide")

    def go_composite_score():
        ui.navigate.to("/composite-score")
    
    ui.label("Settings").classes("text-2xl font-bold mb-2")
    with ui.card().classes("w-full max-w-xl p-4 gap-3"):
        ui.label("Surveys").classes("text-lg font-semibold")
        ui.button("Take Mental Health Survey", on_click=go_survey)
        ui.separator()
        ui.label("Scores & Analytics").classes("text-lg font-semibold")
        ui.button("📊 Composite Score Dashboard", on_click=go_composite_score).classes("bg-purple-500 text-white")
        ui.label("View your overall performance score and customize component weights.").classes("text-sm text-gray-600 mt-2")
        
        ui.separator()
        ui.label("Productivity Scoring").classes("text-lg font-semibold")
        ui.label("Adjust productivity weekly curve and burnout thresholds.").classes("text-sm text-gray-600 mb-2")

        # Load existing settings
        existing_settings = user_state.get_productivity_settings(DEFAULT_USER_ID) or {}
        weekly_curve = existing_settings.get("weekly_curve", "flattened_square")
        weekly_burnout_threshold_hours = float(existing_settings.get("weekly_burnout_threshold_hours", 42.0) or 42.0)
        daily_burnout_cap_multiplier = float(existing_settings.get("daily_burnout_cap_multiplier", 2.0) or 2.0)

        weekly_curve_select = ui.select(
            {
                "linear": "Linear (legacy)",
                "flattened_square": "Softened square (default)",
            },
            value=weekly_curve,
            label="Weekly bonus/penalty curve",
        ).props("dense outlined")

        burnout_weekly_input = ui.number(
            label="Weekly burnout threshold (hours/week)",
            value=weekly_burnout_threshold_hours,
            min=10,
            max=100,
            step=1,
        ).props("dense outlined").classes("w-full max-w-sm")

        burnout_daily_cap_input = ui.number(
            label="Daily burnout cap (x daily average)",
            value=daily_burnout_cap_multiplier,
            min=1.0,
            max=4.0,
            step=0.1,
        ).props("dense outlined").classes("w-full max-w-sm")

        def save_productivity_settings():
            settings = {
                "weekly_curve": weekly_curve_select.value or "flattened_square",
                "weekly_burnout_threshold_hours": float(burnout_weekly_input.value or 42.0),
                "daily_burnout_cap_multiplier": float(burnout_daily_cap_input.value or 2.0),
            }
            user_state.set_productivity_settings(DEFAULT_USER_ID, settings)
            ui.notify("Productivity settings saved. Refresh analytics to apply.", color="positive")

        ui.button("Save Productivity Settings", on_click=save_productivity_settings).classes("bg-blue-500 text-white mt-2")
        ui.separator()
        ui.label("Data & Troubleshooting").classes("text-lg font-semibold")
        ui.markdown("- **Data Guide**: Currently missing - documentation for local setup, data backup, and troubleshooting is planned but not yet implemented").classes("text-sm text-gray-600 mt-2")
