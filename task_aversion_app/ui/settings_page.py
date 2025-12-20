from nicegui import ui


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
        ui.label("Data & Troubleshooting").classes("text-lg font-semibold")
        ui.markdown("- **Data Guide**: Currently missing - documentation for local setup, data backup, and troubleshooting is planned but not yet implemented").classes("text-sm text-gray-600 mt-2")
