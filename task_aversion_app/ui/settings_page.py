from nicegui import ui


@ui.page("/settings")
def settings_page():
    def go_survey():
        ui.navigate.to("/survey")
    
    def go_data_guide():
        ui.navigate.to("/data-guide")

    ui.label("Settings").classes("text-2xl font-bold mb-2")
    with ui.card().classes("w-full max-w-xl p-4 gap-3"):
        ui.label("Surveys").classes("text-lg font-semibold")
        ui.button("Take Mental Health Survey", on_click=go_survey)
        ui.separator()
        ui.label("Data & Troubleshooting").classes("text-lg font-semibold")
        ui.button("📖 Data Troubleshooting & Info Guide", on_click=go_data_guide).classes("bg-blue-500 text-white")
        ui.label("Learn how your data is stored, how to recover it, and how to transfer it between devices.").classes("text-sm text-gray-600 mt-2")
