# app.py
from nicegui import ui
from ui.dashboard import build_dashboard
from ui.create_task import create_task_page
from ui.initialize_task import initialize_task_page
from ui.complete_task import complete_task_page

# Register pages
@ui.page('/')
def index():
    build_dashboard()

# Register module pages
# These define their own routes internally
create_task_page()
initialize_task_page()
complete_task_page()

if __name__ == '__main__':
    ui.run(title='Task Aversion System', port=8080, reload=False)
