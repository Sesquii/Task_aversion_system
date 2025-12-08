from nicegui import ui

from backend.user_state import UserStateManager

us = UserStateManager()


@ui.page("/settings")
def settings_page():
    state = {"user_id": None}

    tutorial_toggle = ui.switch("Auto-show tutorial for new sessions", value=True)
    tooltip_toggle = ui.switch("Enable Ctrl+Click tooltips", value=True)

    def apply_preferences():
        uid = state.get("user_id") or "anonymous"
        us.update_preference(uid, "tutorial_auto_show", tutorial_toggle.value)
        us.update_preference(uid, "tooltip_mode_enabled", tooltip_toggle.value)
        ui.run_javascript(f"if (window.TAS_TOOLTIP) {{ TAS_TOOLTIP.setEnabled({str(tooltip_toggle.value).lower()}); }}")
        ui.notify("Settings saved", color="positive")

    def reset_onboarding():
        uid = state.get("user_id") or "anonymous"
        us.update_preference(uid, "tutorial_completed", False)
        us.update_preference(uid, "tutorial_choice", "")
        us.update_preference(uid, "tutorial_auto_show", True)
        ui.notify("Onboarding reset. Tutorial will appear next visit.", color="positive")

    def go_survey():
        ui.navigate.to("/survey")

    async def init_user():
        uid = await ui.run_javascript(UserStateManager.js_get_or_create_user_id())
        state["user_id"] = uid
        prefs = us.ensure_user(uid)
        tutorial_toggle.value = str(prefs.get("tutorial_auto_show", "True")).lower() == "true"
        tooltip_toggle.value = str(prefs.get("tooltip_mode_enabled", "True")).lower() == "true"

    ui.timer(0.1, init_user, once=True, immediate=False)

    ui.label("Settings").classes("text-2xl font-bold mb-2")
    with ui.card().classes("w-full max-w-xl p-4 gap-3"):
        ui.label("Onboarding").classes("text-lg font-semibold")
        tutorial_toggle
        tooltip_toggle
        with ui.row().classes("gap-2"):
            ui.button("Save", on_click=apply_preferences).classes("bg-blue-500 text-white")
            ui.button("Reset Onboarding", on_click=reset_onboarding).props("outline")
        ui.separator()
        ui.label("Surveys").classes("text-lg font-semibold")
        ui.button("Take Mental Health Survey", on_click=go_survey)
