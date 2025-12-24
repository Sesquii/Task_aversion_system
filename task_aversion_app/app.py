# app.py
from nicegui import ui
from backend.task_manager import TaskManager
from backend.emotion_manager import EmotionManager
from backend.routine_scheduler import start_scheduler

from ui.dashboard import build_dashboard
from ui.create_task import create_task_page
from ui.initialize_task import initialize_task_page
from ui.complete_task import complete_task_page
from ui.cancel_task import cancel_task_page
from ui.analytics_page import register_analytics_page
from ui.gap_handling import gap_handling_page, check_and_redirect_to_gap_handling
# import submodules without rebinding the nicegui `ui` object
from ui import survey_page  # registers /survey
from ui import settings_page  # registers /settings
# from ui import data_guide_page  # registers /data-guide - TODO: Re-enable when data guide is updated for local setup
from ui import composite_score_page  # registers /composite-score


task_manager = TaskManager()
emotion_manager = EmotionManager()


def register_pages():
    @ui.page('/')
    def index():
        # Check for gap handling needs before showing dashboard
        if check_and_redirect_to_gap_handling():
            return
        try:
            build_dashboard(task_manager)
        except Exception as e:
            # Show user-friendly error page instead of crashing
            import traceback
            error_details = traceback.format_exc()
            print(f"[App] Error building dashboard: {error_details}")
            
            ui.label("⚠️ Dashboard Error").classes("text-2xl font-bold text-red-600 mb-4")
            
            with ui.card().classes("w-full max-w-2xl p-6 bg-red-50 border border-red-200"):
                ui.label("Unable to load the dashboard.").classes("text-lg font-semibold text-red-700 mb-2")
                ui.label(
                    "This may be caused by:\n"
                    "• Data file is open in Excel or another program\n"
                    "• OneDrive sync is in progress\n"
                    "• File permissions issue\n"
                    "• Data corruption"
                ).classes("text-sm text-red-600 mb-4 whitespace-pre-line")
                
                with ui.expansion("Technical Details", icon="info").classes("w-full"):
                    ui.code(error_details).classes("text-xs")
                
                ui.button("Retry", on_click=lambda: ui.navigate.to('/')).classes("mt-4")
                ui.button("Go to Settings", on_click=lambda: ui.navigate.to('/settings')).classes("mt-2")
    
    @ui.page('/gap-handling')
    def gap_handling():
        gap_handling_page()

    create_task_page(task_manager, emotion_manager)
    initialize_task_page(task_manager, emotion_manager)
    complete_task_page(task_manager, emotion_manager)
    cancel_task_page(task_manager, emotion_manager)
    register_analytics_page()


if __name__ in {"__main__", "__mp_main__"}:
    register_pages()
    # Start routine scheduler
    start_scheduler()
    import os
    host = os.getenv('NICEGUI_HOST', '127.0.0.1')  # Default to localhost, use env var in Docker
    ui.run(title='Task Aversion System', port=8080, host=host, reload=False)

