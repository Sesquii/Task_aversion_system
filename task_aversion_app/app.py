from nicegui import ui
from ui.main_menu import build_main_menu

@ui.page('/')
def index_page():
    build_main_menu()

if __name__ == '__main__':
    ui.run(title="Task Aversion Logger", port=8080, reload=False)
