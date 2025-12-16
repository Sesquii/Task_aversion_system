# app.py
from nicegui import ui
from backend.task_manager import TaskManager
from backend.emotion_manager import EmotionManager

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
from ui import data_guide_page  # registers /data-guide


task_manager = TaskManager()
emotion_manager = EmotionManager()


def register_pages():
    @ui.page('/')
    def index():
        # Check for gap handling needs before showing dashboard
        if check_and_redirect_to_gap_handling():
            return
        build_dashboard(task_manager)
    
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
    ui.run(title='Task Aversion System', port=8080, reload=False)

