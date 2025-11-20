from nicegui import ui
from ui.add_log import build_add_log_page
from backend.task_manager import TaskManager

manager = TaskManager("data/tasks.csv", "data/logs.csv")

def build_main_menu():
    ui.label("Task Aversion Logger").classes("text-3xl font-bold mb-6")

    with ui.column().classes("gap-4"):
        ui.button("➕ Add Log Entry", on_click=lambda: ui.navigate.to('/add'))
        ui.button("📋 View Tasks (Phase 3 soon)")
        ui.button("📊 Statistics Dashboard (Phase 4 soon)")
        ui.button("✨ Most Promising Tasks (Phase 5 soon)")


@ui.page('/add')
def add_page():
    build_add_log_page(manager)
