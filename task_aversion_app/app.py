# app.py
from nicegui import ui

# Import managers
from backend.task_manager import TaskManager
from backend.emotion_manager import EmotionManager

# Import UI page builders
from ui.dashboard import build_dashboard
from ui.create_task import create_task_page
from ui.initialize_task import initialize_task_page
from ui.complete_task import complete_task_page

# Instantiate your managers (ONE time)
task_manager = TaskManager()
emotion_manager = EmotionManager()

# Register main page
@ui.page('/')
def index():
    build_dashboard(task_manager, emotion_manager)

# Register subpages
create_task_page()
initialize_task_page(task_manager, emotion_manager)
complete_task_page(task_manager, emotion_manager)

if __name__ == '__main__':
    ui.run(title='Task Aversion System', port=8080)
