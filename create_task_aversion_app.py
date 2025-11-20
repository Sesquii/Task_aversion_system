import os
import sys

# >>>>>>>>>>>>>>>>>>>>>
# CHANGE THIS TO YOUR TARGET DIRECTORY
TARGET_DIR = r"C:\Users\rudol\OneDrive\Documents\PIF\Task_aversion_system"
# <<<<<<<<<<<<<<<<<<<<<<

PROJECT_NAME = "task_aversion_app"
PROJECT_PATH = os.path.join(TARGET_DIR, PROJECT_NAME)

folders = [
    PROJECT_PATH,
    os.path.join(PROJECT_PATH, "ui"),
    os.path.join(PROJECT_PATH, "backend"),
    os.path.join(PROJECT_PATH, "assets"),
    os.path.join(PROJECT_PATH, "data"),
]

files = {
    os.path.join(PROJECT_PATH, "app.py"): """from nicegui import ui
from ui.main_menu import build_main_menu

with ui.row().classes('w-full justify-center'):
    ui.label('Loading Task Aversion Logger...')

ui.timer(0.1, lambda: build_main_menu(), once=True)

ui.run(title='Task Aversion Logger', port=8080)
""",
    os.path.join(PROJECT_PATH, "requirements.txt"):
        "nicegui\npandas\nmatplotlib\n",

    os.path.join(PROJECT_PATH, "ui", "__init__.py"): "",
    os.path.join(PROJECT_PATH, "ui", "main_menu.py"):
        "# UI will be overwritten by full app code\n",

    os.path.join(PROJECT_PATH, "ui", "add_log.py"): "# placeholder\n",
    os.path.join(PROJECT_PATH, "ui", "view_tasks.py"): "# placeholder\n",
    os.path.join(PROJECT_PATH, "ui", "stats_dashboard.py"): "# placeholder\n",
    os.path.join(PROJECT_PATH, "ui", "settings_page.py"): "# placeholder\n",

    os.path.join(PROJECT_PATH, "backend", "__init__.py"): "",
    os.path.join(PROJECT_PATH, "backend", "csv_manager.py"): "# placeholder\n",
    os.path.join(PROJECT_PATH, "backend", "task_manager.py"): "# placeholder\n",
    os.path.join(PROJECT_PATH, "backend", "stats_engine.py"): "# placeholder\n",
    os.path.join(PROJECT_PATH, "backend", "compute_priority.py"): "# placeholder\n",

    os.path.join(PROJECT_PATH, "assets", "styles.css"): "/* placeholder */\n",

    os.path.join(PROJECT_PATH, "data", "logs.csv"):
        "timestamp,task,aversion_level,relief_prediction,relief_actual,completion_percent,perceived_overextension,time_estimate_minutes,time_actual_minutes,comment,blocker_type\n",

    os.path.join(PROJECT_PATH, "data", "tasks.csv"):
        "task,category,times_logged,avg_aversion,avg_relief,last_logged\n",
}


def main():
    print("\n>>> Creating project folder structure...\n")
    print(f"Target Directory: {TARGET_DIR}")
    print(f"Project Path: {PROJECT_PATH}\n")

    # Create folders
    for folder in folders:
        os.makedirs(folder, exist_ok=True)
        print(f"[OK] Folder: {folder}")

    # Create files
    for file_path, content in files.items():
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"[OK] File: {file_path}")

    print("\n>>> SUCCESS! Project created.")
    print(f"You can now open: {PROJECT_PATH}\\app.py\n")


if __name__ == "__main__":
    main()
